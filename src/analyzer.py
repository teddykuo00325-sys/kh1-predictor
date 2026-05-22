"""Cycle analysis: which activities repeat in which calendar months."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from typing import Iterable

import jieba

from . import db, festivals

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
