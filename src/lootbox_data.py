"""福袋 / 抽獎類道具的期望值資料.

新增福袋只要在 LOOTBOXES append 一筆字典.  helper 會自動算 EV / 淨成本.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


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
class ObservedSample:
    draws: int                 # 實際開了幾包
    total_stars: int           # 實際拿到星數 (不含 main_prize 等值)
    main_prize_count: int = 0  # 同期間中了幾本 main prize
    date: str = ""             # YYYY-MM-DD
    note: str = ""             # 補充

    def effective_stars(self, main_prize_alt_value: int) -> int:
        """加總「等值星數」（含主獎品兌換價值）."""
        return self.total_stars + self.main_prize_count * main_prize_alt_value


@dataclass
class Lootbox:
    id: str
    name: str
    rewards: list[Reward]
    main_prize_name: str
    main_prize_alt_value: int
    main_prize_alt_unit: str
    purchase_channels: list[PurchaseChannel]
    notes: list[str] = None
    observed_samples: list[ObservedSample] = field(default_factory=list)

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
        observed_samples=[
            ObservedSample(draws=20, total_stars=407, main_prize_count=0,
                           date="2026-06-26-A",
                           note="第一輪 — 0 本書，純星 407 = EV 的 29% (z = -0.72σ)"),
            ObservedSample(draws=30, total_stars=600, main_prize_count=1,
                           date="2026-06-26-B",
                           note="第二輪 — 中 1 本，等值 3,600 星 = EV 30抽 (2,097) 的 172%"),
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


# ───────────────────────── 變異 / 實測分析 ─────────────────────────
def variance_per_draw(box: Lootbox) -> float:
    """每抽星數的變異數 (Var[X] = E[X^2] - E[X]^2)."""
    ev = total_ev_per_draw(box)
    e_x2 = sum(r.prob * r.star_value ** 2 for r in box.rewards)
    return e_x2 - ev ** 2


def sigma_per_draw(box: Lootbox) -> float:
    return math.sqrt(variance_per_draw(box))


def analyze_observation(box: Lootbox, draws: int, observed_stars: int,
                         main_prize_count: int = 0,
                         channel_label: str | None = None) -> dict:
    """給定一筆實測 (n 抽得 X 星 + M 本主獎)，分析偏離 EV 與實際成本."""
    if draws <= 0:
        return {}
    ev_per = total_ev_per_draw(box)
    sigma_per = sigma_per_draw(box)
    # 等值星 = 星 + 主獎本數 × 兌換價
    effective_stars = observed_stars + main_prize_count * box.main_prize_alt_value
    expected_total = draws * ev_per
    sigma_total = math.sqrt(draws) * sigma_per
    z = (effective_stars - expected_total) / sigma_total if sigma_total > 0 else 0.0
    p_lower = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    ratio_vs_ev = effective_stars / expected_total if expected_total > 0 else 0
    stars_per_draw_actual = effective_stars / draws

    cost_breakdown = []
    for ch in (box.purchase_channels if channel_label is None else
                [c for c in box.purchase_channels if c.label == channel_label]):
        money_spent = ch.price * draws
        cost_per_star_actual = money_spent / effective_stars if effective_stars > 0 else None
        cost_per_star_ev     = ch.price / ev_per if ev_per > 0 else None
        cost_per_prize_actual = (cost_per_star_actual * box.main_prize_alt_value
                                  if cost_per_star_actual else None)
        cost_per_prize_ev    = (cost_per_star_ev * box.main_prize_alt_value
                                 if cost_per_star_ev else None)
        cost_breakdown.append({
            "channel": ch.label,
            "price_per_draw": ch.price,
            "money_spent": money_spent,
            "cost_per_star_actual": cost_per_star_actual,
            "cost_per_star_ev":     cost_per_star_ev,
            "cost_per_prize_actual": cost_per_prize_actual,
            "cost_per_prize_ev":    cost_per_prize_ev,
            "deviation_factor": (cost_per_star_actual / cost_per_star_ev
                                  if (cost_per_star_actual and cost_per_star_ev) else None),
        })

    return {
        "draws":              draws,
        "observed_stars":     observed_stars,
        "main_prize_count":   main_prize_count,
        "effective_stars":    effective_stars,
        "expected_stars":     expected_total,
        "stars_per_draw_actual": stars_per_draw_actual,
        "ev_per_draw":        ev_per,
        "ratio_vs_ev":        ratio_vs_ev,
        "sigma_total":        sigma_total,
        "z_score":            z,
        "p_lower":            p_lower,
        "p_lower_pct":        p_lower * 100,
        "cost_breakdown":     cost_breakdown,
    }


def cumulative_observation(box: Lootbox) -> dict | None:
    """所有 stored sample 合併的累計分析."""
    if not box.observed_samples:
        return None
    total_draws = sum(s.draws for s in box.observed_samples)
    total_stars = sum(s.total_stars for s in box.observed_samples)
    total_books = sum(s.main_prize_count for s in box.observed_samples)
    if total_draws == 0:
        return None
    return analyze_observation(box, total_draws, total_stars, total_books)
