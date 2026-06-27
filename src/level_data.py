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
# 站長校正 2026-06: 玩家原始資料寫成「level N 需要 X」(在 N 等需要 X
# 才能升到 N+1)，所以對應 XP_TO_REACH[N+1] = X — 全部往後挪一級。
XP_TO_REACH: dict[int, int] = {
    # ---- 121-151: 等差 +16,900 (起 837,400 對應 L121 = 從 120→121) ----
    **{lvl: 837_400 + 16_900 * (lvl - 121) for lvl in range(121, 152)},
    # ---- 152-166: 等差 +596,900 (起 1,941,300) ----
    **{lvl: 1_941_300 + 596_900 * (lvl - 152) for lvl in range(152, 167)},
    # ---- 167-181: 等差 +5,816,900 (起 16,114,800) ----
    **{lvl: 16_114_800 + 5_816_900 * (lvl - 167) for lvl in range(167, 182)},
    # ---- 182-191: 2 億 each ----
    **{lvl: E(2)    for lvl in range(182, 192)},
    # ---- 192-211: 12 億 each ----
    **{lvl: E(12)   for lvl in range(192, 212)},
    # ---- 212-221: 24 億 each ----
    **{lvl: E(24)   for lvl in range(212, 222)},
    # ---- 222-231: UNKNOWN ----
    # ---- 232-237: 等差 +2 億 (起 26 億, 237→238 = 36 億) ----
    **{lvl: E(26 + 2 * (lvl - 232)) for lvl in range(232, 238)},
    # ---- 238-245: 等差 +3 億 (起 39 億, 站長校驗 238→239 = 42億 ✓) ----
    **{lvl: E(39 + 3 * (lvl - 238)) for lvl in range(238, 246)},
    # ---- 246-250: 等差 +4 億 (起 64 億, 站長校驗 245→246 = 64億) ----
    **{lvl: E(64 + 4 * (lvl - 246)) for lvl in range(246, 251)},
    # ---- 251: UNKNOWN (約 85 億 估計) ----
    # ---- 252-260: explicit (用 -> 箭頭標示故不需移位) ----
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
# 公式 (十位數分界制)
# ───────────────────
#   升級成本 = floor(current_level / 10) × 5 + 5     (對 level >= 2)
#   特例：level 1 → 2 免費  (cost 0)
#   特例：level 100 為封頂   (cost 0)
#
# 已知校驗點：
#   30 級 → 31: floor(30/10)*5+5 = 20 ✓
#   35 級 → 36: floor(35/10)*5+5 = 20 ✓
#   46 級 → 47: floor(46/10)*5+5 = 25 ✓
#   85 級 → 86: floor(85/10)*5+5 = 45 ✓
# 全部 1→100 總成本 = 2,740 顆 ✓ (與站長實測一致)


def essence_cost_to_upgrade(current_level: int) -> int:
    """Cost in essence to upgrade FROM `current_level` to `current_level + 1`."""
    if current_level < 1 or current_level >= 100:
        return 0
    if current_level == 1:
        return 0                       # 1 → 2 免費
    return (current_level // 10) * 5 + 5


@dataclass(frozen=True)
class EssenceRange:
    level_from:   int        # 當前等級下限 (含)
    level_to:     int        # 當前等級上限 (含)
    per_level:    int        # 升一級所需精隨
    upgrade_count: int       # 此區段中實際發生的升級次數

    @property
    def subtotal(self) -> int:
        return self.per_level * self.upgrade_count


# Tens-digit-based ranges (level 1-9 has 8 paid upgrades because 1→2 is free).
MARTIAL_ESSENCE_RANGES: list[EssenceRange] = [
    EssenceRange(level_from=1,  level_to=9,  per_level=5,  upgrade_count=8),   # 1→2 免費
    EssenceRange(level_from=10, level_to=19, per_level=10, upgrade_count=10),
    EssenceRange(level_from=20, level_to=29, per_level=15, upgrade_count=10),
    EssenceRange(level_from=30, level_to=39, per_level=20, upgrade_count=10),
    EssenceRange(level_from=40, level_to=49, per_level=25, upgrade_count=10),
    EssenceRange(level_from=50, level_to=59, per_level=30, upgrade_count=10),
    EssenceRange(level_from=60, level_to=69, per_level=35, upgrade_count=10),
    EssenceRange(level_from=70, level_to=79, per_level=40, upgrade_count=10),
    EssenceRange(level_from=80, level_to=89, per_level=45, upgrade_count=10),
    EssenceRange(level_from=90, level_to=99, per_level=50, upgrade_count=10),
]

MARTIAL_ESSENCE_CAP = 100               # 戰技封頂等級 (不消耗精隨)
# 不再需要 override — 範圍表的算術總和本身就是 2740。
TOTAL_ESSENCE_TO_CAP_OVERRIDE: int | None = None


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
    """Total essence to reach the given martial-skill level (from level 1)."""
    return sum(essence_cost_to_upgrade(L) for L in range(1, level))


def essence_between(from_level: int, to_level: int) -> int:
    return essence_for_level(to_level) - essence_for_level(from_level)


def total_essence_to_cap() -> int:
    return essence_for_level(MARTIAL_ESSENCE_CAP)
