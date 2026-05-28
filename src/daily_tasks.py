"""每日任務清單 — 玩家每天該執行的固定任務 + 活動期間限定任務.

編輯規則
--------
要新增任務：在 CORE_TASKS 或 EVENT_TASKS append 一筆 DailyTask(...)
要結束任務：把 active_until 設成截止日，過後自動不顯示
要快速找關鍵字：每個任務有 keywords，UI 可搜尋

`active_from` / `active_until` 都是 date object，None = 永久有效
任務 id 必須穩定（用於 localStorage 記憶勾選狀態）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class DailyTask:
    id: str                                # 穩定識別符 (kebab-case)
    title: str                             # 顯示名稱
    category: str = "core"                 # core / event / weekly
    where: Optional[str] = None            # 位置 / NPC
    time_rule: Optional[str] = None        # 何時/頻率
    reward: Optional[str] = None           # 主要獎勵
    note: Optional[str] = None             # 注意事項
    keywords: list[str] = field(default_factory=list)
    active_from: Optional[date] = None     # 開始日期 (None = 永久)
    active_until: Optional[date] = None    # 結束日期 (None = 永久)


# ════════════════════════════════════════════════════════════════════
#  CORE — 永遠該做的每日例行
# ════════════════════════════════════════════════════════════════════
CORE_TASKS: list[DailyTask] = [
    DailyTask(
        id="daily-signin",
        title="每日簽到",
        where="宣明殿 / 霸王大殿",
        time_rule="每日 00:00 重置",
        reward="每日簽到禮包",
        keywords=["簽到"],
    ),
    DailyTask(
        id="group-raid",
        title="群英副本通關 (每日 5 次)",
        where="霸王大殿 副本入口",
        time_rule="每日重置",
        reward="副本寶箱",
        note="活動期間配合「群英副本獎勵 2 倍」效益最高",
        keywords=["副本", "群英副本"],
    ),
    DailyTask(
        id="recharge-rank",
        title="本週儲值排行 (前 5 名搶獎)",
        where="儲值頁面",
        time_rule="每週四結算（次週公告得獎名單）",
        reward="當期排行獎品（如：頂級飾品箱、化身自選包、錦囊類）",
        note="獎品內容會隨季節 / 改版調整",
        category="weekly",
        keywords=["儲值", "排行", "前5名"],
    ),
    DailyTask(
        id="ssg-daily",
        title="國戰參戰",
        where="跨服 / 本服國戰",
        time_rule="每日國戰時段（依排程）",
        reward="積分、獎勵箱、城池佔領禮",
        keywords=["國戰", "PVP"],
    ),
    DailyTask(
        id="practice-map",
        title="修練地圖打怪",
        where="修練地圖",
        time_rule="無重置（但配合活動才划算）",
        reward="經驗、修練之珠、活動材料",
        keywords=["修練"],
    ),
]


# ════════════════════════════════════════════════════════════════════
#  EVENT — 活動期間限定的每日任務
#  (過期會自動隱藏；只需新增不需刪除)
# ════════════════════════════════════════════════════════════════════
EVENT_TASKS: list[DailyTask] = [

    # ─── 端午 / 5月底 活動 (#1565, 2026-05-28 ~ 2026-06-25) ───
    DailyTask(
        id="2026-duanwu-quyuan",
        title="領屈原的祝福 buff",
        category="event",
        where="露天市場 — 屈原",
        time_rule="每日領取",
        reward="全屬防 +20%、防禦力 +20%、移動速度 +20%",
        keywords=["屈原", "端午", "buff"],
        active_from=date(2026, 5, 28),
        active_until=date(2026, 6, 25),
    ),
    DailyTask(
        id="2026-duanwu-qiongqi",
        title="上古窮奇討伐",
        category="event",
        where="駱谷地圖",
        time_rule="每日 23:00 出現",
        reward="始源窮奇召喚術訣、修練石、覺醒石、技能物品",
        note="可與屈原 buff 搭配增加生存性",
        keywords=["窮奇", "上古窮奇", "駱谷"],
        active_from=date(2026, 5, 28),
        active_until=date(2026, 6, 25),
    ),
    DailyTask(
        id="2026-duanwu-dungeon",
        title="端午禮物副本",
        category="event",
        where="與龍王交談進入",
        time_rule="每日 1 次",
        reward="重午寶箱（金龍之珠、防禦玉、搜魂令、修練石 隨機）",
        keywords=["端午", "副本", "重午寶箱", "龍王"],
        active_from=date(2026, 5, 28),
        active_until=date(2026, 6, 25),
    ),
    DailyTask(
        id="2026-duanwu-cross-ssg",
        title="跨服國戰殺敵（積分 ×3）",
        category="event",
        where="跨服國戰",
        time_rule="跨服國戰時段",
        reward="最高每場 3,000 積分",
        keywords=["國戰", "跨服", "積分"],
        active_from=date(2026, 5, 28),
        active_until=date(2026, 6, 25),
    ),
    DailyTask(
        id="2026-duanwu-merit",
        title="打王領功勳 ×2",
        category="event",
        where="各地圖王怪",
        time_rule="活動期間每日皆可",
        reward="功勳 ×2",
        keywords=["功勳", "打王"],
        active_from=date(2026, 5, 28),
        active_until=date(2026, 6, 25),
    ),
    DailyTask(
        id="2026-duanwu-ssg-prize",
        title="國戰指定城池額外獎勵",
        category="event",
        where="徐州、天水、桂陽",
        time_rule="符合參戰時間與積分條件",
        reward="國戰名駒禮盒 I、高級群英之星箱、群英之星箱",
        keywords=["國戰", "城池", "額外獎勵"],
        active_from=date(2026, 5, 28),
        active_until=date(2026, 6, 25),
    ),
    DailyTask(
        id="2026-duanwu-search-soul",
        title="領搜魂令（用於換新化身）",
        category="event",
        where="露天市場 — 搜魂獎勵員",
        time_rule="活動期間每日領取",
        reward="搜魂令（取陳泰、郭嘉等新化身用）",
        keywords=["搜魂令", "化身"],
        active_from=date(2026, 5, 28),
        active_until=date(2026, 6, 25),
    ),
    DailyTask(
        id="2026-duanwu-soldier",
        title="武將/名將士兵升級（成功率 70%）",
        category="event",
        where="士兵升級介面",
        time_rule="活動期間升 +1~+9 級成功率由 50% → 70%",
        reward="升級成功率提高 20%",
        note="平常衝不上去的 +N 級可趁這檔嘗試",
        keywords=["士兵", "升級", "成功率"],
        active_from=date(2026, 5, 28),
        active_until=date(2026, 6, 25),
    ),
]


# ════════════════════════════════════════════════════════════════════
#  Helpers
# ════════════════════════════════════════════════════════════════════
def tasks_for(today: date) -> dict:
    """Return tasks bucketed by what's relevant today.

    Returns:
      core: list of CORE_TASKS (always shown)
      active: EVENT_TASKS currently within their active range
      upcoming: EVENT_TASKS starting within the next 14 days
      recently_ended: EVENT_TASKS that ended within the past 7 days
    """
    active, upcoming, recently_ended = [], [], []
    for t in EVENT_TASKS:
        s = t.active_from
        e = t.active_until
        if s and today < s:
            if (s - today).days <= 14:
                upcoming.append(t)
        elif e and today > e:
            if (today - e).days <= 7:
                recently_ended.append(t)
        else:
            active.append(t)
    return {
        "core": list(CORE_TASKS),
        "active": active,
        "upcoming": upcoming,
        "recently_ended": recently_ended,
    }


def all_task_ids() -> set[str]:
    return {t.id for t in CORE_TASKS} | {t.id for t in EVENT_TASKS}
