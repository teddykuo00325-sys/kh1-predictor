"""扮裝套裝性價比 — 用活動代幣兌換的扮裝，每 1 點屬性要花多少台幣.

目前檔期是「龍神的祝福」兌換扮裝 (見 EVENT)。換活動時只要改 EVENT 和
DRESS_SETS 兩個常數，頁面和排序會自動重算。

成本模型有兩段，缺一不可：

    總成本 = 代幣數 × 代幣單價  +  件數 × 每件加持成本

第二段是關鍵 — 加持是按「件」收費，所以件數少的套裝天生佔優勢，光看代幣
價格會得出完全相反的結論 (法老6件套代幣只要 30 顆，卻因為 6 件加持而墊底)。

排名一律**同屬性才比**：HP 跟防禦不能用同一把尺，所以每種屬性各自排一張表。
體魄透過 CONSTITUTION_TO_HP 折算成 HP 後才進 HP 榜。
"""
from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------- 檔期資料
@dataclass(frozen=True)
class Event:
    name: str
    coin_name: str            # 活動代幣名稱
    coin_twd: int             # 1 枚代幣約等於多少台幣
    source: str = ""          # 資料來源 / 回報者
    as_of: str = ""           # YYYY-MM-DD


EVENT = Event(
    name="龍神的祝福 兌換扮裝",
    coin_name="龍神祝福",
    coin_twd=33,
    source="站長實測回報",
    as_of="2026-09-04",
)

# 每件扮裝加持到目標等級的成本 (台幣)。按件計費 — 這是排名的決定因素。
ENCHANT_TWD_PER_PIECE = 600

# 1 點體魄換算幾 HP (站長回報)。體魄套裝靠這個值才能進 HP 榜。
CONSTITUTION_TO_HP = 10.0


@dataclass(frozen=True)
class DressSet:
    name: str
    pieces: int               # 套裝件數
    coins: int                # 兌換所需代幣 (見 COINS_ARE_PER_PIECE)
    hp: int = 0               # 直接加的 HP
    constitution: int = 0     # 體魄 — 折算成 HP 後併入 HP 榜
    defense: int = 0          # 防禦力
    might: int = 0            # 武力


# 排名分組：欄位名 → 顯示名。新增屬性只要在 DressSet 加欄位、這裡加一行。
STAT_LABELS: dict[str, str] = {"hp": "HP", "defense": "防禦力", "might": "武力"}

# 回報的代幣數字是「整套總價」還是「每件單價」。
# 站長給的第一筆寫成 `3件 × 10 = 30`，所以其餘單一數字讀作整套總價。
COINS_ARE_PER_PIECE = False

DRESS_SETS: list[DressSet] = [
    DressSet("骷髏在這 2件套",   pieces=2, coins=100, hp=700),
    DressSet("黑魔女三件套",     pieces=3, coins=30,  hp=480),
    DressSet("德古拉三件套",     pieces=3, coins=30,  hp=480),
    DressSet("法老6件套",        pieces=6, coins=30,  hp=320),
    DressSet("白狼2件套",        pieces=2, coins=10,  hp=160),
    DressSet("龍舟三件套",       pieces=3, coins=30,  constitution=16),
    DressSet("踏雪兩件套",       pieces=2, coins=400, defense=2400),
    DressSet("小軍師 聖誕3件套", pieces=3, coins=30,  defense=1000),
    DressSet("南瓜五件套",       pieces=5, coins=50,  might=25),
]


# ---------------------------------------------------------------- 成本
def cost_of(s: DressSet,
            coin_twd: int = EVENT.coin_twd,
            enchant_twd: int = ENCHANT_TWD_PER_PIECE,
            coins_per_piece: bool = COINS_ARE_PER_PIECE) -> dict:
    """一套的成本拆解 — 代幣、加持、總計，以及加持佔總成本的比例."""
    coin_total = s.coins * s.pieces if coins_per_piece else s.coins
    coin_cost = coin_total * coin_twd
    enchant_cost = s.pieces * enchant_twd
    total = coin_cost + enchant_cost
    return {
        "set": s,
        "coin_total": coin_total,
        "coin_cost": coin_cost,
        "enchant_cost": enchant_cost,
        "total_cost": total,
        # 加持佔總成本的比例 — 解釋為什麼件數多的套裝會墊底
        "enchant_share": enchant_cost / total if total else 0.0,
    }


def stat_amount(s: DressSet, stat: str, con_to_hp: float = CONSTITUTION_TO_HP) -> float:
    """一套在某屬性上的實得點數；HP 會把體魄折算進來."""
    amount = float(getattr(s, stat, 0) or 0)
    if stat == "hp" and con_to_hp:
        amount += s.constitution * con_to_hp
    return amount


# ---------------------------------------------------------------- 排名
def rank_by(stat: str,
            coin_twd: int = EVENT.coin_twd,
            enchant_twd: int = ENCHANT_TWD_PER_PIECE,
            con_to_hp: float = CONSTITUTION_TO_HP,
            coins_per_piece: bool = COINS_ARE_PER_PIECE,
            sets: list[DressSet] | None = None) -> list[dict]:
    """某一屬性的性價比排名，由便宜到貴.

    只收該屬性 > 0 的套裝 — 把沒有這個屬性的套裝當成 0 點排到最後，會給出
    誤導的排名，不如不列。
    """
    rows: list[dict] = []
    for s in sets if sets is not None else DRESS_SETS:
        amount = stat_amount(s, stat, con_to_hp)
        if amount <= 0:
            continue
        r = cost_of(s, coin_twd, enchant_twd, coins_per_piece)
        r["amount"] = amount
        r["cost_per"] = r["total_cost"] / amount
        # 不加持、只算代幣的基準線 — 用來看加持費改變了多少排名
        r["cost_per_raw"] = r["coin_cost"] / amount
        # 折算來的點數要標示出來，數字才不會看起來像官方寫的
        r["derived"] = stat == "hp" and not s.hp and bool(s.constitution)
        rows.append(r)

    # 嚴格劣勢：另一套「點數不低於它、總成本更便宜」——這種套裝沒有理由買，
    # 連「我要衝單套上限」都不算藉口。
    for r in rows:
        r["dominated_by"] = next(
            (o["set"].name for o in rows
             if o is not r and o["amount"] >= r["amount"]
             and o["total_cost"] < r["total_cost"]),
            None)

    rows.sort(key=lambda r: r["cost_per"])
    # 同款換皮 (黑魔女 / 德古拉) 完全同價，共用名次而不是硬排 1、2 名
    rank = 0
    prev: float | None = None
    for i, r in enumerate(rows, 1):
        if prev is None or abs(r["cost_per"] - prev) > 1e-9:
            rank, prev = i, r["cost_per"]
        r["rank"] = rank
    return rows


def rankings(**kw) -> list[dict]:
    """每個有資料的屬性一組排名，HP 排在最前面 (STAT_LABELS 的順序)."""
    out: list[dict] = []
    for stat, label in STAT_LABELS.items():
        rows = rank_by(stat, **kw)
        if not rows:
            continue
        out.append({
            "stat": stat,
            "label": label,
            "rows": rows,
            "best": rows[0],
            "worst": rows[-1],
            # 換皮同價時並列第一，KPI 要把並列的都念出來
            "best_names": " / ".join(r["set"].name for r in rows
                                      if r["rank"] == rows[0]["rank"]),
            "max_amount_row": max(rows, key=lambda r: r["amount"]),
        })
    return out


def break_even_con_to_hp(coin_twd: int = EVENT.coin_twd,
                          enchant_twd: int = ENCHANT_TWD_PER_PIECE,
                          coins_per_piece: bool = COINS_ARE_PER_PIECE) -> dict | None:
    """體魄套裝要擠上 HP 榜首，1 點體魄至少得換到幾 HP.

    跟目前的 CONSTITUTION_TO_HP 無關 — 拿「不含體魄的 HP 榜首」當標準，
    所以換算率改了這個門檻也不會跟著跑。
    """
    pure = rank_by("hp", coin_twd, enchant_twd, con_to_hp=0,
                    coins_per_piece=coins_per_piece)
    con_set = next((s for s in DRESS_SETS if s.constitution and not s.hp), None)
    if not pure or con_set is None:
        return None
    target = pure[0]["cost_per"]
    cost = cost_of(con_set, coin_twd, enchant_twd, coins_per_piece)["total_cost"]
    # cost / (constitution × x) = target  →  x = cost / (target × constitution)
    rate = cost / (target * con_set.constitution)
    return {
        "set": con_set,
        "rate": rate,                          # 需要的 1 點體魄 = ? HP
        "total_hp": rate * con_set.constitution,
        "beats": pure[0]["set"].name,
        "target_cost_per": target,
    }
