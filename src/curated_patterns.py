"""Operator-curated long-term patterns.

These are domain-knowledge predictions that the auto-detector can't easily
infer from raw text, but that the site operator has spotted over multiple
years.  They surface on the dashboard alongside auto-detected predictions
and persist regardless of which time-window the user is browsing.

Add a new pattern by appending a dict to PATTERNS below.  Format:

    {
      "id":              short stable identifier (kebab-case)
      "title":           human-readable name shown on the dashboard
      "anchor": {
        "month":         1-12, the calendar month the pattern centres on
        "day":           1-31, the typical day in that month (defaults 15)
        "flex_days":     ± N days the window can shift in practice
      }
      "kind":            "recharge" / "festival" / "version" / "other"
      "confidence":      0.0 - 1.0  (operator's subjective belief)
      "source":          who/when added this entry
      "description":     paragraph explaining the pattern
      "expected_signals": [keywords ...]   used to highlight related auto-detections
      "historical_evidence": [
        {"year": Y, "article_id": id, "note": "what happened"},
        ...
      ]
    }
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable


PATTERNS: list[dict] = [
    {
        "id": "feb-weekly-topspender-prize",
        "title": "2 月「當週儲值前 5 名」高價值獎品檔期",
        "anchor": {"month": 2, "day": 15, "flex_days": 28},   # Feb ± 4 weeks (覆蓋整個 1月底~3月初)
        "kind": "recharge",
        "confidence": 0.95,
        "source": "站長觀察 (2026-05 加入)",
        "description": (
            "每年 2 月附近都會推出「每週儲值總額前 N 名抽稀有獎品」活動 — "
            "機制每週 1 次得獎、每年都有，但**獎品內容每年換**：\n"
            "  • 2023 年 2 月 → 大喬錦囊 / 小喬錦囊 / 戰技之心\n"
            "  • 2024 年 2 月 → 大喬錦囊 / 小喬錦囊（重複 2023）\n"
            "  • 2025 年 2 月 → 化身自選包(盛唐)\n"
            "  • 2026 年 2 月 → 頂級飾品箱(自選)\n"
            "獎品共同特徵：高價值、自選型（讓玩家挑想要的）、與該年改版內容契合。"
            "下一次 (2027/02) 大機率仍有此活動，獎品預計再換新。"
        ),
        "expected_signals": [
            "當週儲值總額前", "當週消費總額前",
            "頂級飾品", "錦囊", "化身自選", "戰技之心", "套裝禮盒",
        ],
        "historical_evidence": [
            {"year": 2023, "article_id": 580,  "note": "2023-01-26 起：小喬錦囊得獎名單；2 月延續大喬/小喬，3 月轉戰技之心"},
            {"year": 2024, "article_id": 887,  "note": "2024-02-01 起 4 週：大喬/小喬錦囊"},
            {"year": 2025, "article_id": 1463, "note": "2025-01-23 起 4 週：化身自選包(盛唐)"},
            {"year": 2026, "article_id": 1483, "note": "2026-02-05 起 4 週：頂級飾品箱(自選)"},
        ],
    },
    # —— 之後新增的 pattern 寫在這裡 ——
]


def _next_anchor_date(pattern: dict, after: date) -> date:
    """Return the next occurrence of this pattern's anchor on or after `after`."""
    m = pattern["anchor"]["month"]
    d = pattern["anchor"].get("day", 15)
    flex = pattern["anchor"].get("flex_days", 14)
    year = after.year
    while True:
        try:
            candidate = date(year, m, d)
        except ValueError:
            # 2/29 in non-leap year — clamp to 28th
            candidate = date(year, m, min(d, 28))
        # Pattern is "next" if its window has not entirely passed.
        if candidate + timedelta(days=flex) >= after:
            return candidate
        year += 1


def relevant_patterns(today: date | None = None) -> list[dict]:
    """All curated patterns with their next-occurrence metadata for the UI."""
    today = today or date.today()
    out: list[dict] = []
    for p in PATTERNS:
        anchor = _next_anchor_date(p, today)
        flex = p["anchor"].get("flex_days", 14)
        window_start = anchor - timedelta(days=flex)
        window_end   = anchor + timedelta(days=flex)
        days_until = (anchor - today).days
        if today < window_start:
            status = "尚未到期"
        elif window_start <= today <= window_end:
            status = "處於預期視窗"
        else:                       # past the anchor — _next_anchor_date should prevent this
            status = "已過期"
        out.append({
            **p,
            "next_anchor_date":  anchor.isoformat(),
            "next_window_start": window_start.isoformat(),
            "next_window_end":   window_end.isoformat(),
            "days_until_anchor": days_until,
            "status":            status,
        })
    out.sort(key=lambda x: x["days_until_anchor"])
    return out
