"""扮裝套裝性價比 — 用活動代幣兌換的扮裝，每 1 點屬性要花多少台幣.

目前檔期是「龍神的祝福」兌換扮裝 (見 EVENT)。換活動時只要改 EVENT 和
DRESS_SETS 兩個常數，頁面和排序會自動重算。

成本模型有兩段，缺一不可：

    總成本 = 代幣數 × 代幣單價  +  件數 × 每件加持成本

第二段是關鍵 — 加持是按「件」收費，所以件數少的套裝天生佔優勢，光看代幣
價格會得出完全相反的結論 (法老6件套代幣只要 30 顆，卻因為 6 件加持而墊底)。
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


@dataclass(frozen=True)
class DressSet:
    name: str
    pieces: int               # 套裝件數
    coins: int                # 兌換所需代幣 (見 COINS_ARE_PER_PIECE)
    hp: int = 0               # 直接加的 HP
    constitution: int = 0     # 體魄 (需換算率才能比，見 con_to_hp)
    other: str = ""           # 非 HP 加成 (防禦 / 武力 …)


# 回報的代幣數字是「整套總價」還是「每件單價」。
# 站長給的第一筆寫成 `3件 × 10 = 30`，所以其餘單一數字讀作整套總價。
COINS_ARE_PER_PIECE = False

DRESS_SETS: list[DressSet] = [
    DressSet("骷髏在這 2件套",   pieces=2, coins=100, hp=700),
    DressSet("黑魔女三件套",     pieces=3, coins=30,  hp=480),
    DressSet("法老6件套",        pieces=6, coins=30,  hp=320),
    DressSet("白狼2件套",        pieces=2, coins=10,  hp=160),
    DressSet("龍舟三件套",       pieces=3, coins=30,  constitution=16),
    DressSet("小軍師 聖誕3件套", pieces=3, coins=30,  other="防禦 +1000"),
    DressSet("南瓜五件套",       pieces=5, coins=50,  other="武力 +25"),
]


# ---------------------------------------------------------------- 計算
def evaluate(coin_twd: int = EVENT.coin_twd,
             enchant_twd: int = ENCHANT_TWD_PER_PIECE,
             con_to_hp: float = 0.0,
             coins_per_piece: bool = COINS_ARE_PER_PIECE,
             sets: list[DressSet] | None = None) -> list[dict]:
    """算出每套的總成本與 元/HP，依 元/HP 由便宜到貴排序.

    `con_to_hp` 是 1 點體魄換算幾 HP。留 0 表示未知 — 該套會被歸到「無法比較」
    而不是被當成 0 HP 排到最後，避免給出誤導的排名。
    """
    rows: list[dict] = []
    for s in sets if sets is not None else DRESS_SETS:
        coin_total = s.coins * s.pieces if coins_per_piece else s.coins
        coin_cost = coin_total * coin_twd
        enchant_cost = s.pieces * enchant_twd
        total = coin_cost + enchant_cost
        hp = s.hp + (s.constitution * con_to_hp if con_to_hp else 0)
        rows.append({
            "set": s,
            "coin_total": coin_total,
            "coin_cost": coin_cost,
            "enchant_cost": enchant_cost,
            "total_cost": total,
            # 加持佔總成本的比例 — 解釋為什麼件數多的套裝會墊底
            "enchant_share": enchant_cost / total if total else 0.0,
            "hp": hp,
            "twd_per_hp": total / hp if hp else None,
            # 不加持、只算代幣的基準線，用來看加持費改變了多少排名
            "twd_per_hp_raw": coin_cost / hp if hp else None,
        })
    rows.sort(key=lambda r: (r["twd_per_hp"] is None, r["twd_per_hp"] or 0))
    for i, r in enumerate(rows, 1):
        r["rank"] = i if r["twd_per_hp"] is not None else None
    return rows


def break_even_con_to_hp(rows: list[dict]) -> float | None:
    """體魄套裝要達到目前最佳 元/HP，1 點體魄至少得換到幾 HP.

    回答「龍舟三件套值不值得」——不必先知道遊戲的體魄換算率。
    """
    best = next((r["twd_per_hp"] for r in rows if r["twd_per_hp"] is not None), None)
    con_row = next((r for r in rows if r["set"].constitution and not r["set"].hp), None)
    if best is None or con_row is None:
        return None
    # total_cost / (constitution × x) = best  →  x = total_cost / (best × constitution)
    return con_row["total_cost"] / (best * con_row["set"].constitution)
