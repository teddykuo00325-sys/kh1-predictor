"""Character XP and martial-essence (戰技精隨) lookup data.

Convention
----------
`XP_TO_REACH[N]` = experience required to LEVEL UP TO level N (i.e. from N-1 → N).
                  Counts as "the cost of reaching N".

If a level is missing from the dict, its cost is unknown — the UI will mark it
as 「待補」.  You can fill it in by editing this file directly and committing.

Units
-----
- All XP values are in raw experience points (整數).
- 億 (yì) = 10^8 = 100_000_000.  Helper `E()` converts 億 → raw points.

Source notes
------------
- 181-220 from operator's in-game log (2026-05).
- 251-260 from operator's in-game log (2026-05).
- 1-180 and 221-250: TODO — fill in when data available.  Likely sources:
  https://wiki2.gamer.com.tw/wiki.php?n=7107:等級、練等
  (wiki currently 403s automated fetches; manual copy needed).
"""
from __future__ import annotations

from dataclasses import dataclass


def E(n: float) -> int:
    """Convert 億 to raw experience integer."""
    return int(n * 100_000_000)


# Levels 181-260 (and a few notes beyond).  Stored as flat dict for explicit
# coverage; ranges are expanded inline so missing values are obvious.
XP_TO_REACH: dict[int, int] = {
    # ---- 120-150: 等差數列，起 837,400，每級 +16,900 ----
    **{lvl: 837_400 + 16_900 * (lvl - 120) for lvl in range(120, 151)},
    # ---- 151-165: 等差數列，起 1,941,300，每級 +596,900 ----
    **{lvl: 1_941_300 + 596_900 * (lvl - 151) for lvl in range(151, 166)},
    # ---- 166-180: 等差數列，起 16,114,800，每級 +5,816,900 ----
    **{lvl: 16_114_800 + 5_816_900 * (lvl - 166) for lvl in range(166, 181)},
    # ---- 181-190: 2 億 each ----
    **{lvl: E(2)    for lvl in range(181, 191)},
    # ---- 191-210: 12 億 each ----
    **{lvl: E(12)   for lvl in range(191, 211)},
    # ---- 211-220: 24 億 each ----
    **{lvl: E(24)   for lvl in range(211, 221)},
    # ---- 221-250: UNKNOWN (TODO fill in) ----
    # ---- 252-260: explicit values ----
    252: E(90),
    253: E(95),
    254: E(100),
    255: E(105),
    256: E(110),
    257: E(116),
    258: E(122),
    259: E(128),
    260: E(134),
}

LEVEL_CAP        = 260          # 目前已知封頂等級
LEVEL_CAP_FILL_XP = E(141)      # 滿等後填到 99.9% 顯示所需的內部 XP (260 -> 99.9% = 141億)


# ------------------------------------------------------------------ 戰技精隨
@dataclass(frozen=True)
class EssenceRange:
    level_from:   int      # 升至這個等級開始
    level_to:     int      # 升至這個等級結束 (含)
    per_level:    int      # 每升一級需幾顆戰技精隨
    upgrade_count: int     # 此區間共幾次升級

    @property
    def subtotal(self) -> int:
        return self.per_level * self.upgrade_count


MARTIAL_ESSENCE_RANGES: list[EssenceRange] = [
    EssenceRange(level_from=2,   level_to=5,   per_level=5,  upgrade_count=4),   # 1->5
    EssenceRange(level_from=6,   level_to=15,  per_level=10, upgrade_count=10),
    EssenceRange(level_from=16,  level_to=25,  per_level=15, upgrade_count=10),
    EssenceRange(level_from=26,  level_to=35,  per_level=20, upgrade_count=10),
    EssenceRange(level_from=36,  level_to=46,  per_level=25, upgrade_count=11),  # 注意：11 次
    EssenceRange(level_from=47,  level_to=56,  per_level=30, upgrade_count=10),
    EssenceRange(level_from=57,  level_to=66,  per_level=35, upgrade_count=10),
    EssenceRange(level_from=67,  level_to=76,  per_level=40, upgrade_count=10),
    EssenceRange(level_from=77,  level_to=86,  per_level=45, upgrade_count=10),
    EssenceRange(level_from=87,  level_to=96,  per_level=50, upgrade_count=10),
    EssenceRange(level_from=97,  level_to=99,  per_level=55, upgrade_count=3),
    EssenceRange(level_from=100, level_to=100, per_level=60, upgrade_count=1),
]

MARTIAL_ESSENCE_CAP = 100         # 戰技封頂等級
# 站長實測：升到 100 級封頂總共耗用 2740 顆，與下表各段相加（2970）有 230
# 顆差。差異原因尚待釐清，先以站長提供值為準顯示。
TOTAL_ESSENCE_TO_CAP_OVERRIDE = 2740


# ------------------------------------------------------------------ helpers
def xp_to_reach(level: int) -> int | None:
    """Required XP to go from level-1 to level.  None if unknown."""
    return XP_TO_REACH.get(level)


def xp_between(from_level: int, to_level: int) -> tuple[int, list[int]]:
    """Sum of XP_TO_REACH for levels (from_level + 1, ..., to_level).
    Returns (total_known_xp, list_of_unknown_levels)."""
    if to_level <= from_level:
        return 0, []
    total = 0
    unknown: list[int] = []
    for lvl in range(from_level + 1, to_level + 1):
        xp = XP_TO_REACH.get(lvl)
        if xp is None:
            unknown.append(lvl)
        else:
            total += xp
    return total, unknown


def cumulative_xp_to(level: int) -> tuple[int, list[int]]:
    """Total known XP from level 1 to the given level."""
    return xp_between(1, level)


def known_level_ranges() -> list[tuple[int, int]]:
    """Contiguous ranges of levels that have data."""
    if not XP_TO_REACH:
        return []
    sorted_levels = sorted(XP_TO_REACH.keys())
    ranges: list[tuple[int, int]] = []
    start = prev = sorted_levels[0]
    for lvl in sorted_levels[1:]:
        if lvl == prev + 1:
            prev = lvl
        else:
            ranges.append((start, prev))
            start = prev = lvl
    ranges.append((start, prev))
    return ranges


def missing_level_ranges(max_level: int = 260) -> list[tuple[int, int]]:
    """Inverse of known_level_ranges — what's still TODO."""
    known = set(XP_TO_REACH)
    missing: list[tuple[int, int]] = []
    in_run = False
    start = 0
    for lvl in range(1, max_level + 1):
        if lvl not in known:
            if not in_run:
                start = lvl
                in_run = True
        else:
            if in_run:
                missing.append((start, lvl - 1))
                in_run = False
    if in_run:
        missing.append((start, max_level))
    return missing


def essence_for_level(level: int) -> int:
    """How many martial-essence stones to reach the given martial-skill level."""
    cost = 0
    for r in MARTIAL_ESSENCE_RANGES:
        if level >= r.level_to:
            cost += r.subtotal
        elif level >= r.level_from:
            n = level - r.level_from + 1
            cost += n * r.per_level
            break
    return cost


def essence_between(from_level: int, to_level: int) -> int:
    return essence_for_level(to_level) - essence_for_level(from_level)


def total_essence_to_cap() -> int:
    return essence_for_level(MARTIAL_ESSENCE_CAP)
