"""Cycle analysis: which activities repeat in which calendar months."""
from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Iterable

import jieba

from . import db, festivals
from .cache import ttl_cache

# silence jieba banner on import
jieba.setLogLevel(60)

STOPWORDS = set("的了在是和有為與及而或為了我們你們各位玩家活動公告期間請於可將每全".split())


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    out = []
    for w in jieba.cut(text):
        w = w.strip()
        if len(w) < 2:
            continue
        if w in STOPWORDS:
            continue
        out.append(w)
    return out


def _month_of(dt: str | None) -> int | None:
    if not dt:
        return None
    try:
        return datetime.fromisoformat(dt).month
    except ValueError:
        try:
            return int(dt[5:7])
        except Exception:
            return None


@ttl_cache(60)        # DB rarely changes between requests; 60s cache plenty
def load_activities() -> list[dict]:
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT a.*, ar.publish_date, ar.category, ar.title AS article_title
               FROM activities a
               JOIN articles ar ON ar.id = a.article_id
               ORDER BY ar.publish_date"""
        ).fetchall()
    out: list[dict] = []
    for r in rows:
        d = r["publish_date"][:10]
        try:
            year = int(d[:4]); month = int(d[5:7])
        except Exception:
            continue
        out.append({
            "id": r["id"], "article_id": r["article_id"], "name": r["name"],
            "article_title": r["article_title"] or "",
            "start_dt": r["start_dt"], "end_dt": r["end_dt"],
            "description": r["description"] or "", "reward": r["reward"] or "",
            "kind": r["kind"], "keywords": (r["keywords"] or "").split(",") if r["keywords"] else [],
            "year": year, "month": month, "publish_date": d,
        })
    return out


def build_month_index(acts: list[dict]) -> dict[int, list[dict]]:
    idx: dict[int, list[dict]] = defaultdict(list)
    for a in acts:
        idx[a["month"]].append(a)
        # also bucket by start month if different
        m_start = _month_of(a["start_dt"])
        if m_start and m_start != a["month"]:
            idx[m_start].append(a)
    return idx


def keyword_frequency(acts: list[dict]) -> Counter:
    c: Counter = Counter()
    for a in acts:
        for kw in a["keywords"]:
            if kw:
                c[kw] += 1
    return c


def signature(a: dict) -> str:
    """A stable signature so we can cluster repeats across years."""
    if a["keywords"]:
        return a["keywords"][0]
    # fall back to first 8 chars of name
    return (a["name"] or "")[:8]


def recharge_history() -> list[dict]:
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT g.*, ar.publish_date
               FROM recharge_gifts g
               JOIN articles ar ON ar.id = g.article_id
               ORDER BY ar.publish_date"""
        ).fetchall()
    return [dict(r) for r in rows]


_SIG_PUNCT_RE = re.compile(r"[「」『』，,。、！!？\?\s·．:：()（）２３４５６７８９０1234567890]+")
_NOISE_KINDS = {"version"}
_NOISE_NAME_PREFIXES = ("(前言)", "(無標題)", "★", "活動時間", "活動獎勵", "活動說明",
                        "獎勵說明", "消費金額", "獲獎城池", "備註")
_NOISE_NAME_CONTAINS = ("得獎名單", "中獎名單")
_NOISE_ARTICLE_KEYWORDS = ("得獎名單", "中獎名單", "反詐騙", "防範盜用", "防騙宣導",
                            "排程", "維護開機", "維護關機")
_MAX_REASONABLE_PERIOD_DAYS = 90


def _normalize_signature(text: str) -> str:
    """Stable cross-year activity key: strip punctuation + digits, take first 6 chars."""
    if not text:
        return ""
    return _SIG_PUNCT_RE.sub("", text)[:6]


def _activity_key(a: dict) -> str:
    """Robust signature for cross-year matching (festival/evergreen tag > first 6 chars)."""
    sig = signature(a)
    if sig and sig not in {"(前言)", "(無標題)"}:
        return sig
    return _normalize_signature(a.get("name") or "")


def _is_noise(a: dict) -> bool:
    name = (a.get("name") or "").strip()
    if any(name.startswith(p) for p in _NOISE_NAME_PREFIXES):
        return True
    if any(k in name for k in _NOISE_NAME_CONTAINS):
        return True
    title = a.get("article_title") or ""
    if any(k in title for k in _NOISE_ARTICLE_KEYWORDS):
        return True
    return a.get("kind") in _NOISE_KINDS


def _parse_dt(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).date()
    except (ValueError, TypeError):
        try:
            return date.fromisoformat(s[:10])
        except (ValueError, TypeError):
            return None


def yearly_recurrence_stats(acts: list[dict] | None = None,
                             min_avg_per_year: float = 2.0,
                             min_years_active: int = 2) -> list[dict]:
    if acts is None:
        return _yearly_recurrence_cached(min_avg_per_year, min_years_active)
    return _yearly_recurrence_stats_impl(acts, min_avg_per_year, min_years_active)


@ttl_cache(300)
def _yearly_recurrence_cached(min_avg_per_year: float, min_years_active: int) -> list[dict]:
    return _yearly_recurrence_stats_impl(load_activities(),
                                          min_avg_per_year, min_years_active)


def _yearly_recurrence_stats_impl(acts: list[dict],
                                    min_avg_per_year: float,
                                    min_years_active: int) -> list[dict]:
    """For every activity signature, compute yearly cycle stats.

    Only returns signatures that appear at least `min_avg_per_year` times per year
    on average, across at least `min_years_active` distinct years.
    Each row has:
        signature, name_example, kind, total_count, years_active,
        years_seen, per_year_counts {year: count}, avg_per_year,
        month_distribution {1-12: count}, avg_gap_days, median_gap_days,
        last_occurrence, predicted_next_date, sample_examples [{year, name, date}]
    Sorted by avg_per_year descending.
    """
    if acts is None:
        acts = load_activities()
    clean = [a for a in acts if not _is_noise(a)]

    groups: dict[str, list[dict]] = defaultdict(list)
    for a in clean:
        key = _activity_key(a)
        if not key or len(key) < 2:
            continue
        groups[key].append(a)

    out: list[dict] = []
    for sig, members in groups.items():
        per_year: Counter = Counter(m["year"] for m in members)
        years_active = len(per_year)
        total = sum(per_year.values())
        avg = total / years_active

        if years_active < min_years_active:
            continue
        if avg < min_avg_per_year:
            continue

        # month distribution: prefer activity start month, fallback to publish month
        month_dist: Counter = Counter()
        date_list: list[date] = []
        for m in members:
            d = _parse_dt(m.get("start_dt")) or _parse_dt(m.get("publish_date"))
            if d:
                month_dist[d.month] += 1
                date_list.append(d)
            else:
                month_dist[m["month"]] += 1
        date_list.sort()

        # gap analysis — within-year intervals only
        gaps: list[int] = []
        for d1, d2 in zip(date_list, date_list[1:]):
            g = (d2 - d1).days
            if 7 <= g <= 365:           # ignore same-batch (<7d) and year-rollover (>1y)
                gaps.append(g)

        avg_gap = round(statistics.mean(gaps), 1) if gaps else None
        med_gap = round(statistics.median(gaps)) if gaps else None
        last_d  = date_list[-1] if date_list else None
        pred_next = (last_d + timedelta(days=int(med_gap))) if (last_d and med_gap) else None

        # Pick one example per year (most recent)
        by_year_examples: dict[int, dict] = {}
        for m in sorted(members, key=lambda m: m["publish_date"]):
            y = m["year"]
            if y in by_year_examples:
                continue
            by_year_examples[y] = {
                "year": y,
                "name": m["name"],
                "publish_date": m["publish_date"],
                "article_id": m["article_id"],
                "start_dt": m.get("start_dt"),
                "end_dt":   m.get("end_dt"),
            }
        latest = max(members, key=lambda m: m["publish_date"])

        out.append({
            "signature": sig,
            "name_example": latest["name"],
            "kind": latest["kind"],
            "total_count": total,
            "years_active": years_active,
            "years_seen": sorted(per_year.keys()),
            "per_year_counts": dict(per_year),
            "avg_per_year": round(avg, 1),
            "month_distribution": {m: month_dist.get(m, 0) for m in range(1, 13)},
            "avg_gap_days": avg_gap,
            "median_gap_days": med_gap,
            "last_occurrence": last_d.isoformat() if last_d else None,
            "predicted_next_date": pred_next.isoformat() if pred_next else None,
            "examples_by_year": by_year_examples,
        })

    out.sort(key=lambda x: (-x["avg_per_year"], -x["years_active"]))
    return out


def version_history() -> list[dict]:
    """Articles whose title contains a 'x.x.x.x 版本更新' pattern."""
    import re
    pat = re.compile(r"(\d+\.\d+\.\d+\.\d+)\s*版本")
    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM articles ORDER BY publish_date").fetchall()
    out: list[dict] = []
    for r in rows:
        m = pat.search(r["title"])
        if not m:
            continue
        out.append({"id": r["id"], "version": m.group(1), "publish_date": r["publish_date"],
                    "title": r["title"]})
    return out


def summarize() -> dict:
    acts = load_activities()
    by_month = build_month_index(acts)
    return {
        "total_articles": len(set(a["article_id"] for a in acts)),
        "total_activities": len(acts),
        "by_month_count": {m: len(v) for m, v in sorted(by_month.items())},
        "top_keywords": keyword_frequency(acts).most_common(30),
        "kinds": Counter(a["kind"] for a in acts).most_common(),
        "recharge_offers": len(recharge_history()),
        "version_releases": len(version_history()),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(summarize(), ensure_ascii=False, indent=2))
