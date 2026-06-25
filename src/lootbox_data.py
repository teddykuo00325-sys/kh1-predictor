"""福袋 / 抽獎類道具的期望值資料.

新增福袋只要在 LOOTBOXES append 一筆字典.  helper 會自動算 EV / 淨成本.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Reward:
    name: str               # 顯示名稱
    prob: float             # 機率 (0.0 - 1.0)
    star_value: int         # 換算成「主流通用幣」的單位數 (此處用群英之星)


@dataclass
class PurchaseChannel:
    label: str              # 顯示名稱 (商城 / 商人)
    price: int              # 單抽單價 (台幣 / 元)
    discount_note: str = ""  # 折扣說明


@dataclass
class Lootbox:
    id: str
    name: str
    rewards: list[Reward]
    main_prize_name: str    # 大獎名稱 (對應 reward 之一)
    main_prize_alt_value: int  # 大獎在另一系統的等值（讓玩家比較成本）
    main_prize_alt_unit: str   # 等值單位名 (e.g. "群英之星")
    purchase_channels: list[PurchaseChannel]
    notes: list[str] = None

    def __post_init__(self):
        if self.notes is None:
            self.notes = []


LOOTBOXES: list[Lootbox] = [
    Lootbox(
        id="soldier-stamina-bag",
        name="士兵體力進階福袋",
        rewards=[
            Reward("士兵體力進階之書", 0.01, 3000),
            Reward("群英之星(500)",  0.02, 500),
            Reward("群英之星(300)",  0.03, 300),
            Reward("群英之星(100)",  0.04, 100),
            Reward("群英之星(50)",   0.15, 50),
            Reward("群英之星(30)",   0.20, 30),
            Reward("群英之星(10)",   0.25, 10),
            Reward("群英之星(3)",    0.30, 3),
        ],
        main_prize_name="士兵體力進階之書",
        main_prize_alt_value=3000,
        main_prize_alt_unit="群英之星",
        purchase_channels=[
            PurchaseChannel("商城",  50, ""),
            PurchaseChannel("商人",  40, "8 折"),
        ],
        notes=[
            "進階之書可用 3,000 群英之星兌換，故視為等值",
            "非中獎袋累積的星星也算「換來的書」，所以實際淨成本遠低於 100 抽 × 單價",
        ],
    ),
    # 之後新增福袋直接在這裡 append
]


# ───────────────────────── helpers ─────────────────────────
def reward_breakdown(box: Lootbox) -> list[dict]:
    """每個獎品的 prob × value 期望貢獻."""
    return [{
        "name": r.name,
        "prob": r.prob,
        "prob_pct": r.prob * 100,
        "star_value": r.star_value,
        "ev_contribution": r.prob * r.star_value,
    } for r in box.rewards]


def total_ev_per_draw(box: Lootbox) -> float:
    """每抽期望值 (in star units)."""
    return sum(r.prob * r.star_value for r in box.rewards)


def prob_sum(box: Lootbox) -> float:
    """所有機率加總（健康度檢查，應為 1.0）."""
    return sum(r.prob for r in box.rewards)


def channel_analysis(box: Lootbox) -> list[dict]:
    """每個購買通路的 cost-per-main-prize 計算."""
    ev = total_ev_per_draw(box)
    out = []
    for ch in box.purchase_channels:
        # 每元換得多少星
        stars_per_money = ev / ch.price
        # 取得 main prize 需要的抽數 (期望)
        # 用 prob 1/p 來看是「直接中」需要的抽數
        main_prize_prob = next((r.prob for r in box.rewards if r.name == box.main_prize_name), 0)
        draws_for_one_direct_hit = 1 / main_prize_prob if main_prize_prob > 0 else None
        # 實際淨成本：累積 main_prize_alt_value 個星所需金額
        net_cost_per_prize = (ch.price * box.main_prize_alt_value) / ev if ev > 0 else None
        out.append({
            "channel": ch.label,
            "price":   ch.price,
            "discount_note": ch.discount_note,
            "stars_per_money": stars_per_money,
            "draws_for_one_direct_hit": draws_for_one_direct_hit,
            "net_cost_per_prize": net_cost_per_prize,
        })
    return out


def calc_for_target(box: Lootbox, channel_label: str, target_count: int) -> dict | None:
    """計算「想取得 N 本大獎」需要的成本與抽數."""
    if target_count < 1:
        return None
    ch = next((c for c in box.purchase_channels if c.label == channel_label), None)
    if not ch:
        return None
    ev = total_ev_per_draw(box)
    net_cost_per_prize = (ch.price * box.main_prize_alt_value) / ev if ev > 0 else None
    main_prize_prob = next((r.prob for r in box.rewards if r.name == box.main_prize_name), 0)
    total_cost = net_cost_per_prize * target_count if net_cost_per_prize else None
    total_draws = total_cost / ch.price if total_cost else None
    direct_draws_needed = (1 / main_prize_prob) * target_count if main_prize_prob > 0 else None
    return {
        "target_count": target_count,
        "channel": ch.label,
        "price_per_draw": ch.price,
        "ev_per_draw": ev,
        "total_cost_money": total_cost,
        "total_draws": total_draws,
        "direct_hit_draws": direct_draws_needed,
        "savings_vs_direct_hit_money": (direct_draws_needed - total_draws) * ch.price
            if direct_draws_needed and total_draws else None,
    }


def get_box(box_id: str) -> Lootbox | None:
    return next((b for b in LOOTBOXES if b.id == box_id), None)
