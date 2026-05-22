"""Predict next month's activities and recharge gifts.

Algorithm
---------
1. **Festival anchoring** — for the target year/month, list every festival
   whose actual solar date falls in that month (e.g. May → Mother's Day,
   Labour Day, 端午 in lunar years where 5/5 lunar is in May).
   For each festival, look up historical activities whose keywords mention it.
2. **Same-month recurrence** — independently of festivals, collect all
   activities historically published in the same calendar month across years.
   Group by "signature" (first keyword, else first 8 chars of title).
   Compute `confidence = count / observed_years`.
3. **TF-IDF similarity** — for each candidate signature, find the most
   representative example (highest TF-IDF score against the corpus) to
   show its likely description + reward.
4. **Recharge gifts** — group `recharge_gifts` rows by month and by gift_name
   to predict which gift will repeat and at which threshold.
5. **Version cadence** — fit linear cadence on `x.x.x.x 版本` releases to
   guess next version number + date.

Output: dict ready for the Flask template OR pretty-printed CLI table.
"""
from __future__ import annotations

import argparse
import re
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from sklearn.feature_extraction.text import TfidfVectorizer

from . import analyzer, festivals
from .analyzer import tokenize
from .cache import ttl_cache


# How many days before/after the festival's solar date count as "this festival period".
FESTIVAL_WINDOW_DAYS = 14

# An activity that ended within this many days is "recently ended" — likely the
# game shifted the festival activity earlier; treat as "already happened this year".
RECENT_END_DAYS = 60

# Default rolling-window for the "what's coming up?" dashboard view.
DEFAULT_LOOK_BACK_DAYS = 14
DEFAULT_LOOK_FORWARD_DAYS = 45

# Activities we never want to count as "festival activities" — administrative noise.
NOISE_NAME_PREFIXES = ("(前言)", "(無標題)", "★", "活動時間", "活動獎勵", "活動說明",
                       "獎勵說明", "消費金額", "獲獎城池", "備註")
NOISE_NAME_CONTAINS = ("得獎名單", "中獎名單")
NOISE_ARTICLE_KEYWORDS = ("得獎名單", "中獎名單", "反詐騙", "防範盜用", "防騙宣導",
                          "排程", "維護開機", "維護關機")
NOISE_KINDS_FOR_FESTIVAL = {"version"}    # version-update articles aren't festival activities

# Activities whose advertised "period" is longer than this many days are almost
# always extraction errors (e.g. a version note saying "2026/05 ~ 2026/12 適用").
MAX_REASONABLE_PERIOD_DAYS = 90


def _is_noise_activity(a: dict) -> bool:
    name = (a.get("name") or "").strip()
    if any(name.startswith(p) for p in NOISE_NAME_PREFIXES):
        return True
    if any(k in name for k in NOISE_NAME_CONTAINS):
        return True
    title = a.get("article_title") or ""
    if any(k in title for k in NOISE_ARTICLE_KEYWORDS):
        return True
    return False


def _period_too_long(a: dict) -> bool:
    s = _parse_iso_date(a.get("start_dt"))
    e = _parse_iso_date(a.get("end_dt"))
    if not s or not e:
        return False
    return (e - s).days > MAX_REASONABLE_PERIOD_DAYS


_SIG_PUNCT_RE = re.compile(r"[「」『』，,。、！!？\?\s·．:：()（）２３４５６７８９０1234567890]+")


def _normalize_sig(text: str) -> str:
    """Strip punctuation/digits and take the first 6 chars — gives us a stable
    cross-year activity key.  '群英副本通關獎勵２倍！' → '群英副本通關'.
    """
    if not text:
        return ""
    s = _SIG_PUNCT_RE.sub("", text)
    return s[:6]


def _activity_key(a: dict) -> str:
    """Robust signature for cross-year matching."""
    name = a.get("name") or ""
    # If signature() returns a festival/evergreen tag, use it for the high-level
    # bucket; otherwise normalise the name.
    sig = analyzer.signature(a)
    if sig and sig not in {"(前言)", "(無標題)"}:
        # Festival/evergreen tags are short enough to use directly
        return sig
    return _normalize_sig(name)


# ---------------------------------------------------- helpers
def _years_observed(acts: list[dict], month: int) -> int:
    return len({a["year"] for a in acts if a["month"] == month})


def _example_text(act: dict) -> str:
    return f"{act['name']}\n{act['description']}\n{act['reward']}"


# ---------------------------------------------------- festival window helpers
def _parse_iso_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).date()
    except ValueError:
        try:
            return date.fromisoformat(s[:10])
        except ValueError:
            return None


def _festival_solar_date(fest: festivals.Festival, year: int) -> date | None:
    if fest.name.startswith("母親節"):
        return festivals.mothers_day(year)
    return fest.solar_date(year)


def _activity_in_window(a: dict, w_start: date, w_end: date) -> bool:
    """True if the activity's publish OR active period intersects the window."""
    pub = _parse_iso_date(a["publish_date"])
    if pub and w_start <= pub <= w_end:
        return True
    s = _parse_iso_date(a.get("start_dt"))
    e = _parse_iso_date(a.get("end_dt")) or s
    if s and s <= w_end and (e or s) >= w_start:
        return True
    return False


# ---------------------------------------------------- festival detail (rich view)
ALL_STATUSES = ("進行中", "即將開始", "近期已結束", "已結束", "已公告", "尚未出現")


def _detail_for_festival(fest: festivals.Festival, fest_date: date, target_year: int,
                          clean_acts: list[dict], current_year_acts: list[dict],
                          today: date) -> dict | None:
    """Build the rich detail block for ONE (festival, date, target_year) anchor.

    Status decision uses the entire current year, NOT just the festival window,
    so an activity that was held early (e.g. last month) gets flagged as
    「近期已結束」 instead of being mis-classified as 「尚未出現」.
    """
    if True:    # keep diff small by preserving the indented block below
        years_known = sorted({a["year"] for a in clean_acts} | {target_year})
        anchor: dict[int, tuple[date, date]] = {}
        for y in years_known:
            d = _festival_solar_date(fest, y)
            if d:
                anchor[y] = (d - timedelta(days=FESTIVAL_WINDOW_DAYS),
                             d + timedelta(days=FESTIVAL_WINDOW_DAYS))

        # ---- 1) Historical signatures: PREVIOUS years' window OR festival keyword
        historical: list[dict] = []
        for a in clean_acts:
            if a["year"] == target_year:
                continue
            text = f"{a['name']} {a['description']} {a['reward']}"
            kw_hit = any(kw and kw in text for kw in fest.keywords)
            w = anchor.get(a["year"])
            in_win = bool(w and not _period_too_long(a) and _activity_in_window(a, *w))
            if kw_hit or in_win:
                historical.append(a)

        # ---- 2) Group historical activities by fuzzy signature
        groups: dict[str, list[dict]] = defaultdict(list)
        for a in historical:
            key = _activity_key(a)
            if not key:
                continue
            groups[key].append(a)

        # ---- 3) Include current-year window matches that have no historical key
        for a in current_year_acts:
            text = f"{a['name']} {a['description']} {a['reward']}"
            kw_hit = any(kw and kw in text for kw in fest.keywords)
            w = anchor.get(target_year)
            if w and (kw_hit or (not _period_too_long(a) and _activity_in_window(a, *w))):
                key = _activity_key(a)
                if key and key not in groups:
                    groups[key] = []   # new signature only seen this year

        # ---- 4) For each signature, resolve status against the WHOLE current year
        activities_out: list[dict] = []
        for sig, members in groups.items():
            current_matches = [a for a in current_year_acts if _activity_key(a) == sig]
            years_seen = sorted({m["year"] for m in members}
                                 | {a["year"] for a in current_matches})
            status_info = _resolve_status(current_matches, today)

            latest = (max(members + current_matches, key=lambda m: m["publish_date"])
                       if (members or current_matches) else None)
            if latest is None:
                continue

            examples_by_year: dict[int, dict] = {}
            for m in sorted(members + current_matches, key=lambda m: m["publish_date"]):
                yr = m["year"]
                if yr in examples_by_year:
                    continue
                examples_by_year[yr] = {
                    "name": m["name"],
                    "publish_date": m["publish_date"],
                    "article_id": m["article_id"],
                    "start_dt": m["start_dt"],
                    "end_dt": m["end_dt"],
                }

            activities_out.append({
                "signature": sig,
                "name_example": latest["name"],
                "description_example": latest["description"][:280],
                "reward_example": latest["reward"][:200],
                "kind": latest["kind"],
                "years_seen": years_seen,
                "occurrences": len(members) + sum(1 for c in current_matches
                                                   if c["year"] not in years_seen
                                                   or c not in members),
                "current_status": status_info["status"],
                "current_period": status_info.get("period"),
                "current_article_id": status_info.get("article_id"),
                "days_since_end": status_info.get("days_since_end"),
                "days_until_start": status_info.get("days_until_start"),
                "in_current_year": bool(current_matches),
                "examples_by_year": examples_by_year,
            })

        # Sort: ongoing first, then upcoming, then recently ended, then by frequency
        status_rank = {s: i for i, s in enumerate(ALL_STATUSES)}
        activities_out.sort(key=lambda x: (
            status_rank.get(x["current_status"], 99),
            -len(x["years_seen"]),
            -x["occurrences"],
        ))

        def _count(s):
            return sum(1 for a in activities_out if a["current_status"] == s)

        counts = {
            "in_progress":  _count("進行中"),
            "upcoming":     _count("即將開始"),
            "recent_ended": _count("近期已結束"),
            "ended":        _count("已結束"),
            "announced":    _count("已公告"),
            "missing":      _count("尚未出現"),
        }
        appeared = [a for a in activities_out if a["current_status"] != "尚未出現"]
        missing  = [a for a in activities_out if a["current_status"] == "尚未出現"]

        return {
            "festival": fest.name,
            "festival_date": fest_date.isoformat(),
            "festival_year": target_year,
            "window_start": (fest_date - timedelta(days=FESTIVAL_WINDOW_DAYS)).isoformat(),
            "window_end":   (fest_date + timedelta(days=FESTIVAL_WINDOW_DAYS)).isoformat(),
            "total_signatures": len(activities_out),
            "counts": counts,
            "activities": activities_out,
            "appeared": appeared,
            "missing":  missing,
        }


def festival_details(year: int, month: int, acts: list[dict],
                     today: date | None = None) -> list[dict]:
    """Festival breakdowns for every festival anchored to (year, month)."""
    today = today or date.today()
    hits = festivals.festivals_in_month(year, month)
    if not hits:
        return []
    clean_acts = [a for a in acts
                  if not _is_noise_activity(a)
                  and a.get("kind") not in NOISE_KINDS_FOR_FESTIVAL]
    current_year_acts = [a for a in clean_acts if a["year"] == year]
    out: list[dict] = []
    for fest, fest_date in hits:
        d = _detail_for_festival(fest, fest_date, year, clean_acts, current_year_acts, today)
        if d:
            out.append(d)
    return out


def festival_details_in_window(window_start: date, window_end: date,
                                 acts: list[dict], today: date | None = None
                                 ) -> list[dict]:
    """Festival breakdowns for every festival whose solar date falls in the window.

    Checks every year that the window touches (handles the late-December →
    January wrap as well).
    """
    today = today or date.today()
    clean_acts = [a for a in acts
                  if not _is_noise_activity(a)
                  and a.get("kind") not in NOISE_KINDS_FOR_FESTIVAL]

    # Window may straddle a year boundary
    years_to_check = {window_start.year, window_end.year}
    hits: list[tuple[festivals.Festival, date, int]] = []
    for fest in festivals.FESTIVALS:
        for y in years_to_check:
            d = _festival_solar_date(fest, y)
            if d and window_start <= d <= window_end:
                hits.append((fest, d, y))
    hits.sort(key=lambda h: h[1])

    out: list[dict] = []
    for fest, fest_date, target_year in hits:
        current_year_acts = [a for a in clean_acts if a["year"] == target_year]
        d = _detail_for_festival(fest, fest_date, target_year, clean_acts,
                                  current_year_acts, today)
        if d:
            out.append(d)
    return out


def _resolve_status(current_year_acts: list[dict], today: date) -> dict:
    """Determine status from this-year activities that match a signature.

    Returns a dict with keys:
      status, period, article_id, days_since_end, days_until_start
    """
    if not current_year_acts:
        return {"status": "尚未出現", "period": None, "article_id": None}

    in_progress = None      # (act, s, e)
    upcoming = None         # earliest future start
    most_recent_ended = None  # (act, s, e) - largest end date in the past

    for m in current_year_acts:
        if _period_too_long(m):
            continue
        s = _parse_iso_date(m.get("start_dt"))
        e = _parse_iso_date(m.get("end_dt")) or s
        if not s:
            continue
        if e and s <= today <= e:
            in_progress = (m, s, e)
        elif today < s:
            if not upcoming or s < upcoming[1]:
                upcoming = (m, s, e)
        else:  # today > e
            if not most_recent_ended or (e and e > most_recent_ended[2]):
                most_recent_ended = (m, s, e)

    if in_progress:
        m, s, e = in_progress
        return {"status": "進行中",
                "period": f"{s.isoformat()} ~ {e.isoformat()}",
                "article_id": m["article_id"],
                "days_until_start": 0}
    if upcoming:
        m, s, e = upcoming
        return {"status": "即將開始",
                "period": f"{s.isoformat()} ~ {e.isoformat() if e else '?'}",
                "article_id": m["article_id"],
                "days_until_start": (s - today).days}
    if most_recent_ended:
        m, s, e = most_recent_ended
        days_since = (today - e).days
        status = "近期已結束" if days_since <= RECENT_END_DAYS else "已結束"
        return {"status": status,
                "period": f"{s.isoformat()} ~ {e.isoformat()}",
                "article_id": m["article_id"],
                "days_since_end": days_since}

    # current-year occurrence exists but has no parseable time range
    last = max(current_year_acts, key=lambda a: a["publish_date"])
    return {"status": "已公告", "period": None, "article_id": last["article_id"]}


# ---------------------------------------------------- legacy concise view
def festival_candidates(year: int, month: int, acts: list[dict]) -> list[dict]:
    hits = festivals.festivals_in_month(year, month)
    if not hits:
        return []
    out: list[dict] = []
    for fest, d in hits:
        # find historical activities that mention this festival
        matches = []
        for a in acts:
            text = f"{a['name']} {a['description']} {a['reward']}"
            for kw in fest.keywords:
                if kw and kw in text:
                    matches.append(a)
                    break
        if not matches:
            # festival exists but never been used by the game — still include as low-confidence
            out.append({
                "type": "festival",
                "festival": fest.name,
                "expected_date": d.isoformat(),
                "signature": fest.name,
                "name_example": fest.name + " (歷史無紀錄)",
                "description_example": "",
                "reward_example": "",
                "occurrences": 0,
                "years_seen": [],
                "confidence": 0.05,
            })
            continue
        # use most recent match as the example
        latest = max(matches, key=lambda a: a["publish_date"])
        years_seen = sorted({a["year"] for a in matches})
        observed_years = _years_observed(acts, month) or 1
        conf = min(1.0, len(years_seen) / observed_years + 0.15)  # festival bonus
        out.append({
            "type": "festival",
            "festival": fest.name,
            "expected_date": d.isoformat(),
            "signature": fest.name,
            "name_example": latest["name"],
            "description_example": latest["description"][:280],
            "reward_example": latest["reward"][:200],
            "occurrences": len(matches),
            "years_seen": years_seen,
            "confidence": round(conf, 2),
        })
    return out


# ---------------------------------------------------- recurrence
JUNK_SIGNATURES = {"(前言)", "(無標題)", "活動時間", "活動獎勵", "活動說明", "活動加註",
                   "活動對象", "備註", "獲獎城池"}


def recurrence_candidates(month: int, acts: list[dict], skip_signatures: set[str]) -> list[dict]:
    same_month = [a for a in acts if a["month"] == month]
    if not same_month:
        return []
    observed_years = _years_observed(acts, month) or 1

    groups: dict[str, list[dict]] = defaultdict(list)
    for a in same_month:
        sig = analyzer.signature(a)
        if not sig or sig in skip_signatures or sig in JUNK_SIGNATURES:
            continue
        groups[sig].append(a)

    # TF-IDF for picking exemplars
    corpus_acts = list(same_month)
    corpus_texts = [_example_text(a) for a in corpus_acts]
    tfidf = TfidfVectorizer(tokenizer=tokenize, lowercase=False, max_features=2000)
    try:
        tfidf_matrix = tfidf.fit_transform(corpus_texts)
        scores = tfidf_matrix.sum(axis=1).A1
        score_of = {id(a): float(scores[i]) for i, a in enumerate(corpus_acts)}
    except ValueError:
        score_of = {id(a): 0.0 for a in corpus_acts}

    out: list[dict] = []
    for sig, members in groups.items():
        years_seen = sorted({a["year"] for a in members})
        # confidence: how reliably this signature appears in this month
        conf = min(1.0, len(years_seen) / observed_years)
        # boost slightly if it shows up multiple times within same year (e.g. weekly)
        if len(members) > len(years_seen):
            conf = min(1.0, conf + 0.1)
        exemplar = max(members, key=lambda a: score_of.get(id(a), 0.0))
        out.append({
            "type": "recurring",
            "signature": sig,
            "name_example": exemplar["name"],
            "description_example": exemplar["description"][:280],
            "reward_example": exemplar["reward"][:200],
            "occurrences": len(members),
            "years_seen": years_seen,
            "confidence": round(conf, 2),
            "kind": exemplar["kind"],
            "recurring": len(years_seen) >= 2,
        })
    out.sort(key=lambda x: (-x["recurring"], -x["confidence"], -x["occurrences"]))
    return out


# ---------------------------------------------------- recharge gifts
def recharge_candidates(month: int) -> list[dict]:
    rows = analyzer.recharge_history()
    if not rows:
        return []
    same_month = [r for r in rows if r["publish_date"][5:7] == f"{month:02d}"]
    # also include rows whose period_start month equals target
    for r in rows:
        ps = r.get("period_start")
        if ps and ps[5:7] == f"{month:02d}" and r not in same_month:
            same_month.append(r)
    if not same_month:
        return []
    groups: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for r in same_month:
        gift = (r["gift_name"] or "").strip()
        thr  = r["threshold"] or 0
        # collapse minor wording variants
        gift_key = re.sub(r"[\s,，。、!！]+", "", gift)[:24]
        groups[(gift_key, thr)].append(r)
    observed_years = len({r["publish_date"][:4] for r in same_month}) or 1
    out: list[dict] = []
    for (gift_key, thr), members in groups.items():
        years_seen = sorted({r["publish_date"][:4] for r in members})
        conf = min(1.0, len(years_seen) / observed_years)
        latest = max(members, key=lambda r: r["publish_date"])
        out.append({
            "gift_name": latest["gift_name"],
            "threshold": thr,
            "qty_example": latest["gift_qty"],
            "raw_text_example": latest["raw_text"],
            "occurrences": len(members),
            "years_seen": years_seen,
            "confidence": round(conf, 2),
        })
    out.sort(key=lambda x: (-x["confidence"], -x["threshold"]))
    return out


# ---------------------------------------------------- version cadence
def predict_next_version() -> dict | None:
    versions = analyzer.version_history()
    if len(versions) < 3:
        return None
    # use most recent N=10 releases for cadence
    recent = versions[-10:]
    dates = [datetime.fromisoformat(v["publish_date"]).date() for v in recent]
    deltas = [(b - a).days for a, b in zip(dates, dates[1:]) if (b - a).days > 0]
    if not deltas:
        return None
    avg = statistics.mean(deltas)
    med = statistics.median(deltas)
    last_version = recent[-1]["version"]
    last_date = dates[-1]
    next_date = last_date + timedelta(days=int(round(med)))
    # increment last segment of version (best-effort, since we don't know major bumps)
    parts = [int(x) for x in last_version.split(".")]
    parts[-1] += 1
    return {
        "last_version": last_version,
        "last_publish_date": last_date.isoformat(),
        "predicted_version": ".".join(str(p) for p in parts),
        "predicted_date": next_date.isoformat(),
        "avg_days_between": round(avg, 1),
        "median_days_between": med,
        "releases_observed": len(versions),
    }


# ---------------------------------------------------- main entry (legacy month mode)
def predict(target: date | None = None) -> dict:
    target = target or _default_target()
    return _predict_month_cached(target.year, target.month)


@ttl_cache(300)
def _predict_month_cached(year: int, month: int) -> dict:
    acts = analyzer.load_activities()

    fest = festival_candidates(year, month, acts)
    fest_details = festival_details(year, month, acts)
    # Skip recurring-list signatures that we are already covering in the festival panel.
    skip = {f["signature"] for f in fest}
    for fd in fest_details:
        for a in fd["activities"]:
            skip.add(a["signature"])
    recur = recurrence_candidates(month, acts, skip)
    recurring_strong = [r for r in recur if r["recurring"]]
    recurring_weak   = [r for r in recur if not r["recurring"]]
    recharge = recharge_candidates(month)
    version = predict_next_version()

    summary = analyzer.summarize()

    return {
        "mode": "month",
        "target_year": year,
        "target_month": month,
        "today": date.today().isoformat(),
        "festival_candidates": fest,
        "festival_details": fest_details,
        "recurring_candidates": recurring_strong,
        "weak_candidates": recurring_weak,
        "recharge_candidates": recharge,
        "next_version": version,
        "summary": summary,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


# ---------------------------------------------------- rolling window mode (new default)
def predict_rolling(today: date | None = None,
                    look_back: int = DEFAULT_LOOK_BACK_DAYS,
                    look_forward: int = DEFAULT_LOOK_FORWARD_DAYS) -> dict:
    """Predict activities in the window [today - look_back, today + look_forward].

    This is the practical "what's coming up?" view — it crosses month boundaries
    so end-of-May activities and start-of-June festivals appear together.
    """
    return _predict_rolling_cached(today or date.today(), look_back, look_forward)


@ttl_cache(300)        # 5 min — heavy work, results stable until DB changes (next deploy)
def _predict_rolling_cached(today: date, look_back: int, look_forward: int) -> dict:
    window_start = today - timedelta(days=look_back)
    window_end   = today + timedelta(days=look_forward)

    acts = analyzer.load_activities()
    fest_details = festival_details_in_window(window_start, window_end, acts, today)

    # Recharge gifts: union of months touched by the window
    recharge_months = set()
    cur = window_start.replace(day=1)
    while cur <= window_end:
        recharge_months.add(cur.month)
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)
    recharge: list[dict] = []
    seen_keys: set[tuple[str, int]] = set()
    for m in recharge_months:
        for g in recharge_candidates(m):
            k = (g["gift_name"][:20], g["threshold"])
            if k in seen_keys:
                continue
            seen_keys.add(k)
            recharge.append(g)
    recharge.sort(key=lambda x: (-x["confidence"], -x["threshold"]))

    # Currently-active or upcoming activities that aren't tied to any festival.
    # Useful for periods with no festival in the window.
    clean_acts = [a for a in acts
                  if not _is_noise_activity(a)
                  and a.get("kind") not in NOISE_KINDS_FOR_FESTIVAL]
    covered_keys = {a["signature"] for fd in fest_details for a in fd["activities"]}
    other_current: list[dict] = []
    other_keys_seen: set[str] = set()
    for a in clean_acts:
        if a["year"] != today.year:
            continue
        s = _parse_iso_date(a.get("start_dt"))
        e = _parse_iso_date(a.get("end_dt")) or s
        if not s or _period_too_long(a):
            continue
        # in or near our window?
        if e < window_start or s > window_end:
            continue
        key = _activity_key(a)
        if key in covered_keys or key in other_keys_seen:
            continue
        other_keys_seen.add(key)
        if s <= today <= (e or s):
            status = "進行中"
        elif today < s:
            status = "即將開始"
        elif (today - (e or s)).days <= RECENT_END_DAYS:
            status = "近期已結束"
        else:
            status = "已結束"
        other_current.append({
            "signature": key,
            "name": a["name"],
            "kind": a["kind"],
            "start_dt": a["start_dt"],
            "end_dt": a["end_dt"],
            "article_id": a["article_id"],
            "status": status,
        })
    other_current.sort(key=lambda x: (
        {"進行中": 0, "即將開始": 1, "近期已結束": 2, "已結束": 3}.get(x["status"], 9),
        x.get("start_dt") or "",
    ))

    version = predict_next_version()
    summary = analyzer.summarize()

    return {
        "mode": "rolling",
        "today": today.isoformat(),
        "window_start": window_start.isoformat(),
        "window_end":   window_end.isoformat(),
        "look_back": look_back,
        "look_forward": look_forward,
        "festival_details": fest_details,
        "other_current": other_current,
        "recharge_candidates": recharge,
        "next_version": version,
        "summary": summary,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def _default_target() -> date:
    today = date.today()
    if today.month == 12:
        return date(today.year + 1, 1, 1)
    return date(today.year, today.month + 1, 1)


# ---------------------------------------------------- CLI
def _print_report(p: dict):
    if p.get("mode") == "rolling":
        print(f"\n=== 預測：滾動視窗 {p['window_start']} ~ {p['window_end']} "
              f"(今天 {p['today']}, 回看 {p['look_back']} 天 + 向前 {p['look_forward']} 天) ===")
    else:
        print(f"\n=== 預測：{p['target_year']}-{p['target_month']:02d} 月份模式 ===")
    print(f"資料量：{p['summary']['total_articles']} 篇 / "
          f"{p['summary']['total_activities']} 活動條目 / "
          f"{p['summary']['recharge_offers']} 儲值贈品紀錄")

    if p["next_version"]:
        v = p["next_version"]
        print(f"\n[版本更新預測]  下個版本 ~ {v['predicted_version']} @ {v['predicted_date']}  "
              f"(平均週期 {v['avg_days_between']} 天 / 中位數 {v['median_days_between']} 天)")

    if p.get("mode") == "rolling" and p.get("other_current"):
        print(f"\n[本年其他進行中 / 近期活動 (不屬於任何節日的)]")
        for o in p["other_current"][:15]:
            print(f"   {o['status']:<8}  [{o['kind']:<8}]  {o['name'][:30]:<30}  "
                  f"{o.get('start_dt') or '?'} ~ {o.get('end_dt') or '?'}")

    print(f"\n[節日活動詳情]  (今天 = {p['today']})")
    BADGES = {
        "進行中":     "🟢 進行中",
        "即將開始":   "🟡 即將開始",
        "近期已結束": "🟠 近期已結束",
        "已結束":     "⚪ 已結束",
        "已公告":     "🔵 已公告",
        "尚未出現":   "🔴 尚未出現",
    }
    for fd in p["festival_details"]:
        c = fd["counts"]
        print(f"\n  ◆ {fd['festival']}  @ {fd['festival_date']}  "
              f"(視窗 {fd['window_start']} ~ {fd['window_end']})")
        print(f"    歷年共 {fd['total_signatures']} 種活動  |  "
              f"進行中 {c['in_progress']}  即將 {c['upcoming']}  近期已結束 {c['recent_ended']}  "
              f"已結束 {c['ended']}  已公告 {c['announced']}  尚未出現 {c['missing']}")
        for a in fd["activities"]:
            badge = BADGES.get(a["current_status"], a["current_status"])
            extra = ""
            if a.get("days_since_end") is not None and a["current_status"].endswith("已結束"):
                extra = f"  (結束 {a['days_since_end']} 天前)"
            elif a.get("days_until_start"):
                extra = f"  (還有 {a['days_until_start']} 天)"
            period = f"  {a['current_period']}" if a["current_period"] else ""
            print(f"      {badge:<16} [{a['kind']:<8}] {a['name_example'][:30]:<30}  "
                  f"歷年 {a['years_seen']}{period}{extra}")

    if "recurring_candidates" in p:        # only in month mode
        print("\n[同月重複活動候選 (≥2年重複)]")
        if not p["recurring_candidates"]:
            print("  (此月份歷年無多年重複的活動)")
        for r in p["recurring_candidates"]:
            print(f"  • [{r['kind']:<8}] {r['signature']:<14}  信心 {int(r['confidence']*100):>3}%  "
                  f"次數 {r['occurrences']:>2}  歷年 {r['years_seen']}"
                  f"\n      範例: {r['name_example']}")
        if p.get("weak_candidates"):
            print(f"\n[單年參考活動 (僅 1 年出現, 共 {len(p['weak_candidates'])} 條, 顯示前 5)]")
            for r in p["weak_candidates"][:5]:
                print(f"  • [{r['kind']:<8}] {r['signature']:<14}  歷年 {r['years_seen']}  範例: {r['name_example']}")

    print("\n[儲值贈品候選]")
    if not p["recharge_candidates"]:
        print("  (此月份歷年無儲值贈品紀錄)")
    for g in p["recharge_candidates"]:
        print(f"  • 滿 {g['threshold']:>6} 元 → 贈 {g['gift_name']}  "
              f"(信心 {int(g['confidence']*100):>3}%, 歷年 {g['years_seen']})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", help="legacy month mode: YYYY-MM. Default is rolling window from today.")
    ap.add_argument("--back",  type=int, default=DEFAULT_LOOK_BACK_DAYS,
                    help=f"rolling mode: look-back days (default {DEFAULT_LOOK_BACK_DAYS})")
    ap.add_argument("--ahead", type=int, default=DEFAULT_LOOK_FORWARD_DAYS,
                    help=f"rolling mode: look-forward days (default {DEFAULT_LOOK_FORWARD_DAYS})")
    args = ap.parse_args()
    if args.month:
        y, m = args.month.split("-")
        _print_report(predict(date(int(y), int(m), 1)))
    else:
        _print_report(predict_rolling(look_back=args.back, look_forward=args.ahead))


if __name__ == "__main__":
    main()
