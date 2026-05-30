"""扮裝加持策略 — 各等級道具使用對照與階段建議.

資料以「等級」為 key（+1 ~ +20），UI 把連續同策略的等級合併為階段。
玩家輸入目前各件扮裝的等級可即時得到下一步該用什麼道具。
"""
from __future__ import annotations

from dataclasses import dataclass, field


# True  → 嘗試前 *必用*
# False → 不用
# "on_fail" → 失敗破壞時才用 (修復類)
@dataclass(frozen=True)
class LevelPolicy:
    target_level: int
    add: bool = True             # 加持（強化）
    bless: bool = False          # 祝福
    protect: bool = False        # 普通保護
    special_protect: bool = False  # 特殊保護（失敗不掉等）
    repair: str = ""             # 普通修復
    special_repair: str = ""     # 特殊修復


POLICIES: list[LevelPolicy] = (
    [LevelPolicy(lvl, add=True) for lvl in range(1, 4)] +                            # +1~+3
    [LevelPolicy(lvl, add=True, special_repair="on_fail") for lvl in range(4, 11)] + # +4~+10
    [LevelPolicy(lvl, add=True, bless=True) for lvl in range(11, 13)] +              # +11~+12
    [LevelPolicy(lvl, add=True, bless=True, special_repair="on_fail")
        for lvl in range(13, 20)] +                                                  # +13~+19
    [LevelPolicy(20, add=True, bless=True, special_protect=True)]                    # +20
)


@dataclass
class Stage:
    name: str                    # 階段名 (e.g. '+1 ~ +3')
    level_from: int
    level_to: int
    use_before: list[str]        # 嘗試前要先用的
    use_on_fail: list[str]       # 失敗時才用的
    rationale: str               # 為什麼這樣選
    sop_text: str = ""           # 實戰 SOP 描述


STAGES: list[Stage] = [
    Stage("+1 ~ +3",   1,  3,  ["加持"], [],
          "100% 必中，浪費道具沒意義",
          "純加持，三連衝完直奔 +3"),
    Stage("+4 ~ +10",  4, 10,  ["加持"], ["特殊修復"],
          "失敗率 1-7%，祝福不划算；偶爾失敗用特殊修復救回，免破壞重來",
          "繼續純加持，破壞時才用特殊修復"),
    Stage("+11 ~ +12", 11, 12, ["加持", "祝福"], [],
          "祝福把 80-83% 拉到 100%，必中保送",
          "加持 + 祝福必中"),
    Stage("+13 ~ +19", 13, 19, ["加持", "祝福"], ["特殊修復"],
          "祝福壓低失敗率到 3-22%，失敗才用特殊修復救（反應型）",
          "加持 + 祝福，破壞時才特殊修復"),
    Stage("+20",       20, 20, ["加持", "祝福", "特殊保護"], [],
          "失敗率 25% 最高，預防型特殊保護避免反覆失敗，比反應型省",
          "三件道具堆滿，失敗不掉等再衝"),
]


# 永遠不用的道具
NEVER_USE = [
    {
        "name": "普通保護",
        "cost": "16 元",
        "reason": "特殊組合包效率更高 (同等防護成本攤平後 25/次 vs 16/次, 但特殊不掉等)",
    },
    {
        "name": "普通修復",
        "cost": "80 元",
        "reason": "永遠用不到 — 開特殊保護就不會失敗，沒開就用特殊修復救回，裝備永遠不會回到 0",
    },
]


# 採購時機 (一次買 1 組規則下的累計需求)
PURCHASE_PLAN = [
    {"phase": "階段 1 結束 (+12 完成)", "cum_special_protect": 0,
     "cum_special_repair": 2, "buy_now": 2,
     "note": "邊衝邊買，剛好夠用"},
    {"phase": "階段 2 結束 (+19 完成)", "cum_special_protect": 0,
     "cum_special_repair": 7, "buy_now": 5,
     "note": "+13~+19 預估失敗 6-7 次"},
    {"phase": "階段 3 結束 (+20 完成)", "cum_special_protect": 8,
     "cum_special_repair": 8, "buy_now": 1,
     "note": "最後關 +20 每件 1-2 次過"},
]


# SOP (3 個階段)
SOP = [
    {
        "phase": "階段 1：6 件並行衝到 +12 (簡單階段)",
        "flow": "+1 加持 → +2 加持 → +3 加持 → +4~+10 加持 (失敗就特殊修復) → +11 加持+祝福 → +12 加持+祝福",
        "estimate": "加持 ×60、祝福 ×12、特殊修復 0~2 個",
        "strategy": "6 件全部做完同階段，再進階",
    },
    {
        "phase": "階段 2：6 件交替衝 +13~+19 (危險階段)",
        "flow": "+13 加持+祝福 → 失敗就特殊修復 → +14~+19 同上",
        "estimate": "加持 ×56、祝福 ×56、特殊修復 6-7 個",
        "strategy": "不衝完一件就換下一件，降低連敗的心理壓力",
    },
    {
        "phase": "階段 3：最後關 +20 (最終 BOSS)",
        "flow": "+20 加持+祝福+特殊保護 → 失敗等級不變不破壞 → 再來一次",
        "estimate": "加持 ×8、祝福 ×8、特殊保護 ×8 (每件 1-2 次)",
        "strategy": "三道具堆滿打到過為止",
    },
]


def get_policy(level: int) -> LevelPolicy | None:
    for p in POLICIES:
        if p.target_level == level:
            return p
    return None


def get_stage(level: int) -> Stage | None:
    for s in STAGES:
        if s.level_from <= level <= s.level_to:
            return s
    return None


def next_step_for(current_level: int) -> dict:
    """玩家輸入「目前 +X」，回傳下一步該怎麼做."""
    if current_level >= 20:
        return {"target": None, "status": "done", "message": "已到 +20 滿級，無需強化"}
    target = current_level + 1
    p = get_policy(target)
    s = get_stage(target)
    if not p or not s:
        return {"target": target, "status": "unknown"}
    return {
        "target": target,
        "current": current_level,
        "policy": p,
        "stage": s,
        "use_before": s.use_before,
        "use_on_fail": s.use_on_fail,
        "rationale": s.rationale,
    }
