"""Parse stored article HTML into structured activity records.

Each article in `articles` is split into N activity blocks.  A typical structure:

    <strong>勞動節狂歡，商城全館五折or買一送一喔！</strong>
    [活動對象] 所有玩家
    [活動時間] 04/30(四) 12:00 ~ 05/07(四) 09:00
    [活動說明] ...
    [活動獎勵] ...

Each block becomes a row in `activities`.  Recharge-gift lines like
"每單筆儲值達5,000元(含)以上，即贈送1個祝福晶石箱" become rows in `recharge_gifts`.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from . import db, festivals

# brackets used by the news editor — both half/full-width
BRACKET_PAIRS = [("[", "]"), ("【", "】"), ("〔", "〕")]
TAG_TIME    = ("活動時間", "活動期間")
TAG_DESC    = ("活動說明", "活動內容")
TAG_REWARD  = ("活動獎勵",)
TAG_NOTE    = ("活動加註", "備註", "注意事項")
TAG_TARGET  = ("活動對象",)

DATE_RANGE_RE = re.compile(
    r"(\d{1,4})[/.\-年]\s*(\d{1,2})[/.\-月]?\s*(\d{1,2})?[^0-9~～\-]*?"
    r"(?:\((?:[一二三四五六日週周天]|Mon|Tue|Wed|Thu|Fri|Sat|Sun|MON|TUE|WED|THU|FRI|SAT|SUN)\))?"
    r"\s*(\d{1,2}):(\d{2})"
    r"\s*[~～\-到至]\s*"
    r"(?:(\d{1,4})[/.\-年]\s*)?"
    r"(?:(\d{1,2})[/.\-月]?)?\s*(\d{1,2})?[^0-9]*?"
    r"(\d{1,2}):(\d{2})"
)

# Primary pattern: gift name wrapped in Chinese quotation marks 「...」
RECHARGE_QUOTED_RE = re.compile(
    r"每?單?筆?儲值[達到]?\s*([0-9,]+)\s*元(?:\(含\))?[^「]*?贈[送给]?\s*(\d+)?\s*(?:個|份|組|顆|張|盒|箱|本|套)?\s*[「『]([^」』]{1,40})[」』]"
)
# Fallback: terminate at common clause breakers (，每 / ，依此類推 / 。 / 喔)
RECHARGE_PLAIN_RE = re.compile(
    r"每?單?筆?儲值[達到]?\s*([0-9,]+)\s*元(?:\(含\))?[^贈]*?贈[送给]?\s*(\d+)\s*(?:個|份|組|顆|張|盒|箱|本|套)\s*([^\n，。]{2,30}?)(?=，|。|\n|依此類推|喔|$)"
)
# Sentinels we must NOT capture as a gift name
BAD_GIFT_PREFIXES = ("依此", "每單", "每筆", "不限")

VERSION_RE = re.compile(r"(\d+\.\d+\.\d+\.\d+)\s*版本")


def _bracket_split(text: str) -> dict[str, str]:
    """Given the body of one activity block, find [活動時間] etc and return dict."""
    fields: dict[str, str] = {}
    # normalise full-width to half
    norm = text.replace("【", "[").replace("】", "]").replace("〔", "[").replace("〕", "]")
    # find every [tag] and slice up
    positions = [(m.start(), m.end(), m.group(1)) for m in re.finditer(r"\[([^\[\]\n]{2,8})\]", norm)]
    for i, (s, e, tag) in enumerate(positions):
        nxt = positions[i + 1][0] if i + 1 < len(positions) else len(norm)
        value = norm[e:nxt].strip().strip("：:").strip()
        fields.setdefault(tag, value)
    return fields


def _resolve_date_parts(a: str | None, b: str | None, c: str | None,
                         fallback_year: int) -> tuple[int, int, int]:
    """Map captured groups to (year, month, day).

    Accepts either YYYY/MM/DD (a=4-digit year) or MM/DD (a is month, c is None).
    """
    if c is not None and a and len(a) == 4:
        return int(a), int(b), int(c)
    if c is not None:                # rare YY/MM/DD — promote to 20YY
        return 2000 + int(a), int(b), int(c)
    # MM/DD form: a=month, b=day
    return fallback_year, int(a), int(b)


def parse_date_range(s: str, fallback_year: int) -> tuple[str | None, str | None]:
    """Parse '04/30(四) 12:00 ~ 05/07(四) 09:00' into ISO-ish datetimes."""
    if not s:
        return None, None
    m = DATE_RANGE_RE.search(s)
    if not m:
        return None, None
    g = m.groups()
    try:
        y1, mo1, d1 = _resolve_date_parts(g[0], g[1], g[2], fallback_year)
        h1, mi1 = int(g[3]), int(g[4])
        # second date: if g[6] present we have month+day, else inherit
        if g[5] and g[6] and (g[7] or g[5] and len(g[5]) == 4):
            y2, mo2, d2 = _resolve_date_parts(g[5], g[6], g[7], y1)
        elif g[5] and g[6]:
            # MM/DD form for the right side
            y2, mo2, d2 = y1, int(g[5]), int(g[6])
        elif g[5]:                  # only one number — treat as day
            y2, mo2, d2 = y1, mo1, int(g[5])
        else:
            y2, mo2, d2 = y1, mo1, d1
        h2, mi2 = int(g[8]), int(g[9])
        start = datetime(y1, mo1, d1, h1, mi1)
        end = datetime(y2, mo2, d2, h2, mi2)
        # if end < start, assume the right side rolled into the next month
        if end < start:
            if mo2 < 12:
                end = end.replace(month=mo2 + 1)
            else:
                end = end.replace(year=y2 + 1, month=1)
        return start.isoformat(), end.isoformat()
    except (ValueError, TypeError):
        return None, None


def classify_activity(name: str, desc: str, reward: str) -> str:
    blob = " ".join((name, desc, reward))
    if VERSION_RE.search(name) or "版本更新" in name or "改版" in name:
        return "version"
    if "儲值" in blob and ("贈" in blob or "回饋" in blob):
        return "recharge"
    if any(k in blob for k in ("國戰", "梁山", "PVP", "戰場較勁")):
        return "pvp"
    if any(k in blob for k in ("商城", "五折", "買一送一", "限時特賣", "特賣")):
        return "mall"
    f = festivals.match_festival(name) or festivals.match_festival(desc)
    if f:
        return "festival"
    if any(k in blob for k in ("成功率", "升級", "重鑄", "強化")):
        return "upgrade"
    if any(k in blob for k in ("經驗", "加倍", "倍數")):
        return "boost"
    return "other"


def extract_keywords(name: str, desc: str) -> list[str]:
    """Lightweight keyword set: festival hits + evergreen tags + version + nouns."""
    kws: list[str] = []
    f = festivals.match_festival(name) or festivals.match_festival(desc)
    if f:
        kws.append(f.name)
    kws.extend(festivals.evergreen_tags(f"{name} {desc}"))
    v = VERSION_RE.search(name) or VERSION_RE.search(desc)
    if v:
        kws.append("版本-" + v.group(1))
    return list(dict.fromkeys(kws))   # dedup keep order


# ---------------------------------------------------- main per-article logic
_BRACKET_HEADER_RE = re.compile(r"^[\[【〔](活動時間|活動期間|活動對象|活動說明|活動內容|"
                                  r"活動獎勵|活動加註|備註|注意事項|獲獎城池)[\]】〕]?\s*$")


def _is_header_text(text: str) -> bool:
    """Decide whether a paragraph's text looks like an activity header.

    Real headers are short Chinese phrases (4-40 chars) NOT a bracket tag and
    not a generic table-cell label.
    """
    if not text or len(text) < 4 or len(text) > 60:
        return False
    if _BRACKET_HEADER_RE.match(text):
        return False
    if text in {"活動時間", "活動期間", "活動對象", "活動說明", "活動獎勵", "活動加註",
                "備註", "注意事項", "消費金額", "獎勵說明", "獲獎城池", "獎勵"}:
        return False
    # purely digits / commas (table cell content)
    if re.fullmatch(r"[\d,，.\s]+", text):
        return False
    return True


def _segment_blocks(content_html: str) -> list[tuple[str, str]]:
    """Walk the article body and yield (title, body_text) blocks.

    A new block starts when we see a paragraph whose entire text sits inside a
    <strong> AND the text looks like a real activity title (see _is_header_text).
    """
    soup = BeautifulSoup(content_html, "lxml")
    if soup.find("body"):
        soup = soup.body
    blocks: list[tuple[str, list[str]]] = []
    current_title: str | None = None
    current_body: list[str] = []

    def flush():
        text = "\n".join(t for t in current_body if t.strip())
        if not text and current_title is None:
            return
        blocks.append((current_title or "(前言)", text))

    # Paragraph-like leaf elements only: a <p> or <div> with no further p/div
    # descendants.  This skips the wrapping <div class="newstxt"> AND handles
    # version-update articles that use <div> instead of <p> for their paragraphs.
    paragraphs = [el for el in soup.find_all(["p", "div"])
                   if not el.find(["p", "div"], recursive=True)]

    for p in paragraphs:
        text = p.get_text("\n", strip=True)
        if not text:
            continue
        strong = p.find("strong")
        if strong and strong.get_text(strip=True) == text and _is_header_text(text):
            flush()
            current_title = text
            current_body = []
        else:
            current_body.append(text)
    flush()

    # Drop empty blocks and prelude-only-no-body
    cleaned: list[tuple[str, str]] = []
    for title, body in blocks:
        if not body:
            continue
        cleaned.append((title, body))
    return cleaned


def extract_recharge_gifts(article_id: int, body: str, period_start: str | None,
                            period_end: str | None) -> list[dict]:
    out: list[dict] = []
    seen: set[tuple[int, str]] = set()  # dedup within article

    def _add(threshold: int, qty: int | None, gift: str, raw: str):
        gift = gift.strip().strip("，。 ")
        if not gift or any(gift.startswith(p) for p in BAD_GIFT_PREFIXES):
            return
        key = (threshold, gift[:24])
        if key in seen:
            return
        seen.add(key)
        out.append({
            "article_id": article_id,
            "threshold": threshold,
            "gift_name": gift,
            "gift_qty": qty,
            "period_start": period_start,
            "period_end": period_end,
            "raw_text": raw.strip(),
        })

    for m in RECHARGE_QUOTED_RE.finditer(body):
        threshold = int(m.group(1).replace(",", ""))
        qty = int(m.group(2)) if m.group(2) else 1
        gift = m.group(3)
        _add(threshold, qty, gift, m.group(0))
    for m in RECHARGE_PLAIN_RE.finditer(body):
        threshold = int(m.group(1).replace(",", ""))
        qty = int(m.group(2))
        gift = m.group(3)
        _add(threshold, qty, gift, m.group(0))
    return out


def process_article(row, conn) -> tuple[int, int]:
    """Returns (activities_inserted, recharge_inserted)."""
    html_path = db.ROOT / row["html_path"] if row["html_path"] else None
    if not html_path or not html_path.exists():
        return 0, 0
    raw = html_path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(raw, "lxml")
    content = soup.select_one("div.newstxt")
    if not content:
        return 0, 0

    blocks = _segment_blocks(str(content))
    pub_year = int(row["publish_date"][:4])

    # wipe previous extractions for this article so we can re-run
    conn.execute("DELETE FROM activities WHERE article_id=?", (row["id"],))
    conn.execute("DELETE FROM recharge_gifts WHERE article_id=?", (row["id"],))

    n_act = 0
    # remember which activity covers which date range, so we can attach gifts
    activity_id_by_seq: dict[int, int] = {}
    activity_range_by_seq: dict[int, tuple[str | None, str | None]] = {}

    for seq, (title, body) in enumerate(blocks):
        fields = _bracket_split(body)
        time_str = fields.get("活動時間") or fields.get("活動期間") or ""
        start_dt, end_dt = parse_date_range(time_str, pub_year)
        desc   = fields.get("活動說明") or fields.get("活動內容") or ""
        reward = fields.get("活動獎勵") or ""
        note   = fields.get("活動加註") or fields.get("備註") or ""
        kind   = classify_activity(title, desc, reward)
        keywords = ",".join(extract_keywords(title, f"{desc} {reward}"))

        cur = conn.execute(
            """INSERT INTO activities
               (article_id, seq, name, start_dt, end_dt, description, reward, note, kind, keywords)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (row["id"], seq, title[:200], start_dt, end_dt, desc, reward, note, kind, keywords),
        )
        activity_id_by_seq[seq] = cur.lastrowid
        activity_range_by_seq[seq] = (start_dt, end_dt)
        n_act += 1

    # Recharge gifts: scan the ENTIRE article body once (not per block) to avoid dupes.
    # Attach each gift to the closest recharge-kind activity if any, else None.
    full_text = content.get_text("\n", strip=True)
    recharge_seq = next((s for s, (t, _) in enumerate(blocks)
                         if "儲值" in t or "回饋" in t), None)
    if recharge_seq is None and blocks:
        recharge_seq = 0    # fallback to first block
    if recharge_seq is not None:
        period = activity_range_by_seq.get(recharge_seq, (None, None))
        attach_id = activity_id_by_seq.get(recharge_seq)
    else:
        period = (None, None); attach_id = None

    n_gift = 0
    for g in extract_recharge_gifts(row["id"], full_text, period[0], period[1]):
        conn.execute(
            """INSERT INTO recharge_gifts
               (article_id, activity_id, threshold, gift_name, gift_qty, period_start, period_end, raw_text)
               VALUES (?,?,?,?,?,?,?,?)""",
            (g["article_id"], attach_id, g["threshold"], g["gift_name"],
             g["gift_qty"], g["period_start"], g["period_end"], g["raw_text"]),
        )
        n_gift += 1

    return n_act, n_gift


def run() -> None:
    db.init_schema()
    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM articles ORDER BY publish_date").fetchall()
    print(f"[extract] articles: {len(rows)}")
    total_a = total_g = 0
    with db.cursor() as conn:
        for r in rows:
            a, g = process_article(r, conn)
            total_a += a
            total_g += g
    print(f"[extract] activities={total_a}  recharge_gifts={total_g}")


if __name__ == "__main__":
    run()
