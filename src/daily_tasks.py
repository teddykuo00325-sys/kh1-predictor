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

    # ─── 6/25 年中盛事一波 (#1585, 2026-06-25 ~ 2026-07-23) ───
    DailyTask(
        id="2026-0625-bamen",
        title="🔥 八門全開，一二三層成功率 +10%",
        category="event",
        where="八門升級介面",
        time_rule="活動期間內每次升級",
        reward="第 1、2、3 層每次升級成功率再提升 10%",
        note="這波是集中衝八門的檔期，材料 + 成功率同時 up",
        keywords=["八門", "升級", "成功率", "全開"],
        active_from=date(2026, 6, 25),
        active_until=date(2026, 7, 23),
    ),
    DailyTask(
        id="2026-0625-shangu-hundun",
        title="上古‧混沌 討伐 (年中大王)",
        category="event",
        where="玉山地圖",
        time_rule="每日 23:00 出現",
        reward="始源混沌召喚術訣、始源混沌殘章、軒轅晉升福袋、四轉技能書頁、修練石/覺醒石等",
        note="殘章 ×50 於煉造房 = 1 個術訣",
        keywords=["上古", "混沌", "王", "23:00", "玉山"],
        active_from=date(2026, 6, 25),
        active_until=date(2026, 7, 23),
    ),
    DailyTask(
        id="2026-0625-support-outdoor",
        title="支援露天 領月行商令牌",
        category="event",
        where="露天市場 — 擺攤達人",
        time_rule="活動期間每日領取",
        reward="行商月令牌 ×1",
        keywords=["支援露天", "行商", "月行商"],
        active_from=date(2026, 6, 25),
        active_until=date(2026, 7, 23),
    ),
    DailyTask(
        id="2026-0625-buff-station",
        title="購買強勢 Buff（異象之地）",
        category="event",
        where="異象之地 — 群英增益官",
        time_rule="活動期間可買",
        reward="鐵腕/剛體/結界/兵強化/行軍強化 各 lv20 (效果不疊加)",
        note="打王前先貼上",
        keywords=["Buff", "增益官", "異象之地"],
        active_from=date(2026, 6, 25),
        active_until=date(2026, 7, 23),
    ),
    DailyTask(
        id="2026-0625-skill-refund",
        title="戰技返還 % 提升 (50% → 80%)",
        category="event",
        where="戰技返還系統",
        time_rule="活動期間內使用",
        reward="返還戰技書材料 80% (原 50%)",
        note="想重點戰技組合的最佳時機",
        keywords=["戰技", "返還", "改天賦"],
        active_from=date(2026, 6, 25),
        active_until=date(2026, 7, 23),
    ),
    DailyTask(
        id="2026-0625-cross-ssg",
        title="跨服國戰 一錠參戰",
        category="event",
        where="跨服國戰",
        time_rule="跨服國戰時段",
        reward="降低參戰門檻，一錠即可參與",
        keywords=["跨服", "國戰", "一錠"],
        active_from=date(2026, 6, 25),
        active_until=date(2026, 7, 23),
    ),
    DailyTask(
        id="2026-0625-ssg-cities",
        title="國戰指定城池額外獎勵 (北平/上庸/壽春)",
        category="event",
        where="北平、上庸、壽春",
        time_rule="符合參戰時間與積分條件",
        reward="國戰名駒禮盒 I、高級群英之星箱",
        keywords=["國戰", "城池", "北平", "上庸", "壽春"],
        active_from=date(2026, 6, 25),
        active_until=date(2026, 7, 23),
    ),
    DailyTask(
        id="2026-0625-recharge-pinjie",
        title="💰 儲值滿 5000 送品階石箱(彩)",
        category="event",
        where="儲值介面",
        time_rule="每筆單筆 5000 元 (含) 以上",
        reward="品階石箱(彩) ×1",
        note="彩色品階石箱是這波獨家獎品",
        keywords=["儲值", "品階石", "品階石箱"],
        active_from=date(2026, 6, 25),
        active_until=date(2026, 7, 23),
    ),
    DailyTask(
        id="2026-0625-pvp",
        title="廣寒宮 / 骷墳古社 PVP 開放",
        category="event",
        where="廣寒宮、骷墳古社",
        time_rule="活動期間為 PVP 地圖",
        reward="PVP 戰鬥",
        keywords=["PVP", "廣寒宮", "骷墳古社"],
        active_from=date(2026, 6, 25),
        active_until=date(2026, 7, 23),
    ),
    DailyTask(
        id="2026-0625-soul-swap",
        title="化身換魂 全面 8 折",
        category="event",
        where="化身系統",
        time_rule="活動期間所有換魂 -20%",
        reward="換魂費用 8 折",
        keywords=["化身", "換魂", "8折"],
        active_from=date(2026, 6, 25),
        active_until=date(2026, 7, 23),
    ),
    DailyTask(
        id="2026-0625-troop-soul",
        title="全系列兵魂 升級至 9 級 / 10 級",
        category="event",
        where="煉造房",
        time_rule="活動期間可升級",
        reward="9 級兵魂、10 級兵魂",
        keywords=["兵魂", "煉造房", "升級"],
        active_from=date(2026, 6, 25),
        active_until=date(2026, 7, 23),
    ),
    DailyTask(
        id="2026-0625-practice-map",
        title="修練地圖 戰技材料掉落",
        category="event",
        where="晉升/躍升/飛升/駿升 修練地圖",
        time_rule="活動期間打怪額外掉落",
        reward="技能精髓、戰技碎片、技能玉髓",
        note="打怪順手集戰技材料",
        keywords=["修練地圖", "戰技碎片", "技能精髓", "技能玉髓"],
        active_from=date(2026, 6, 25),
        active_until=date(2026, 7, 23),
    ),

    # ─── 7/23 新一波活動 (#1607, 2026-07-23 ~ 2026-08-13) ───
    DailyTask(
        id="2026-0723-lubu",
        title="🔥 天下無雙「魔神呂布」降臨",
        category="event",
        where="待官方公告地圖",
        time_rule="每日 23:00 出現",
        reward="待補（延續魔神系列，通常有召喚術訣、四轉技能書頁等）",
        keywords=["呂布", "魔神", "王", "23:00"],
        active_from=date(2026, 7, 23),
        active_until=date(2026, 8, 12),
    ),
    DailyTask(
        id="2026-0723-support-front",
        title="支援前線 領獎勵",
        category="event",
        where="待補",
        time_rule="每日領取",
        reward="支援前線補給品",
        note="需 150 等 + 五品官以上",
        keywords=["支援前線", "150等", "五品官"],
        active_from=date(2026, 7, 23),
        active_until=date(2026, 8, 12),
    ),
    DailyTask(
        id="2026-0723-map-coin",
        title="💰 修練地圖遊戲幣 2-3 倍掉落",
        category="event",
        where="晉升/躍升/飛升/駿升 修練地圖",
        time_rule="活動期間打怪",
        reward="遊戲幣 2-3 倍",
        note="錢包空的黃金檔期",
        keywords=["遊戲幣", "掉落", "修練地圖"],
        active_from=date(2026, 7, 23),
        active_until=date(2026, 8, 12),
    ),
    DailyTask(
        id="2026-0723-material-exchange",
        title="材料道具兌換官",
        category="event",
        where="露天市場",
        time_rule="活動期間",
        reward="新兌換選項（詳見官方公告）",
        keywords=["兌換", "材料", "露天市場"],
        active_from=date(2026, 7, 23),
        active_until=date(2026, 8, 12),
    ),
    DailyTask(
        id="2026-0723-mingjiang-challenge",
        title="名將珠的挑戰",
        category="event",
        where="加持系統",
        time_rule="活動期間",
        reward="名將珠特殊挑戰獎勵",
        note="需將道具加持至 +20 才能挑戰",
        keywords=["名將珠", "加持", "挑戰"],
        active_from=date(2026, 7, 23),
        active_until=date(2026, 8, 12),
    ),
    DailyTask(
        id="2026-0723-qunying-buff",
        title="群英老祖的祝福 (免費 buff)",
        category="event",
        where="待官方公告 NPC",
        time_rule="每日領取",
        reward="免費 buff 狀態加成",
        keywords=["群英老祖", "祝福", "buff", "免費"],
        active_from=date(2026, 7, 23),
        active_until=date(2026, 8, 12),
    ),
    DailyTask(
        id="2026-0723-market-fee",
        title="群英交易站上架費 1 折",
        category="event",
        where="群英交易站",
        time_rule="活動期間所有規格",
        reward="上架費用 -90%",
        note="想清倉舊物或交易的最佳時機",
        keywords=["交易站", "上架", "1折"],
        active_from=date(2026, 7, 23),
        active_until=date(2026, 8, 12),
    ),
    DailyTask(
        id="2026-0723-pvp-maps",
        title="樓蘭奇境 / 日耳曼尼亞 PVP",
        category="event",
        where="樓蘭奇境、日耳曼尼亞",
        time_rule="活動期間為 PVP 地圖",
        reward="PVP 戰鬥",
        keywords=["PVP", "樓蘭奇境", "日耳曼尼亞"],
        active_from=date(2026, 7, 23),
        active_until=date(2026, 8, 12),
    ),
    DailyTask(
        id="2026-0723-ssg-silver",
        title="國戰龍銀獲得 2 倍",
        category="event",
        where="國戰",
        time_rule="國戰結算時",
        reward="龍銀 ×2",
        keywords=["國戰", "龍銀"],
        active_from=date(2026, 7, 23),
        active_until=date(2026, 8, 12),
    ),
    DailyTask(
        id="2026-0723-ssg-cities",
        title="國戰指定城池獎勵 (鄴/宛/武陵)",
        category="event",
        where="鄴、宛、武陵",
        time_rule="佔領指定城池",
        reward="國戰額外獎勵箱",
        keywords=["國戰", "城池", "鄴", "宛", "武陵"],
        active_from=date(2026, 7, 23),
        active_until=date(2026, 8, 12),
    ),
    DailyTask(
        id="2026-0723-recharge-wuxia",
        title="💰 儲值滿 5000 送無瑕女媧玉+伏羲石",
        category="event",
        where="儲值介面",
        time_rule="每單筆",
        reward="滿 5,000 → 無瑕女媧玉×1、無瑕伏羲石×1；滿 10,000 → 各 ×2",
        note="不限次數",
        keywords=["儲值", "無瑕", "女媧玉", "伏羲石"],
        active_from=date(2026, 7, 23),
        active_until=date(2026, 8, 12),
    ),

    # ═══════════════════════════════════════════════════════════════
    # 🎉 08/13 大改版「軍破五丈原」(41.0.0.1) — 2026-08-13 ~ 2026-09-10
    #    新地圖：五丈原古道、渭水
    #    新 BOSS：夏侯霸、姜維、諸葛恪、諸葛誕、丁奉、鄧艾
    #    新副本：長阪坡救主（220 級）
    #    新系統：武魂通用、四轉技能、八門第四層、機關陸式、
    #           戰印系統、懸賞榜、大赦符
    # ═══════════════════════════════════════════════════════════════
    DailyTask(
        id="2026-0813-wuzhangyuan-pack",
        title="🎁 免費領「五丈原整備包/物資包」(一次性)",
        category="event",
        where="霸王大殿 — 群英歸來獎勵官",
        time_rule="活動期間內領取一次",
        reward="整備包=武器+防具+腰帶+褶褲+護飾+配件+座騎自選；物資包=搜魂仙符×30、四倍符、化身券、萬象包等",
        note="⚠️ 一經選取無法更換 / 裝備類 60 日時效 / 10/15 更新後未使用完全移除 / 需 100 lv",
        keywords=["五丈原", "整備包", "物資包", "群英歸來"],
        active_from=date(2026, 8, 13),
        active_until=date(2026, 9, 10),
    ),
    DailyTask(
        id="2026-0813-wuzhangyuan-boss",
        title="🐉 五丈原新王討伐（夏侯霸/姜維/諸葛恪/諸葛誕/丁奉/鄧艾）",
        category="event",
        where="五丈原古道、渭水",
        time_rule="每日常駐",
        reward="王怪掉落 + 懸賞獎勵",
        note="新地圖打王同時完成每週懸賞",
        keywords=["五丈原", "王", "夏侯霸", "姜維", "諸葛恪", "諸葛誕", "丁奉", "鄧艾"],
        active_from=date(2026, 8, 13),
        active_until=None,
    ),
    DailyTask(
        id="2026-0813-changbanpo",
        title="⚔️ 群英副本「長阪坡救主」(220 級 / 3 日重置)",
        category="event",
        where="副本宮殿 — 長阪坡救主屏風",
        time_rule="3 日重置 / 隊長消耗群英副本通行證 ×3",
        reward="金/銀/鐵寶箱、群英精銳之星、群英之星、群英副本通行證",
        note="限制 3 人以上組隊 / 2 分流限制",
        keywords=["長阪坡", "副本", "群英副本", "群英版"],
        active_from=date(2026, 8, 13),
        active_until=None,
    ),
    DailyTask(
        id="2026-0813-huashen-drop",
        title="修練地圖打怪掉落化身抽卡券",
        category="event",
        where="晉升/躍升/飛升/駿升 修練地圖",
        time_rule="活動期間打怪額外掉落",
        reward="化身抽卡券、化身抽卡券I/II/III",
        note="配合打怪掉寶率加倍（~08/27）雙重加成",
        keywords=["化身", "抽卡券", "修練地圖"],
        active_from=date(2026, 8, 13),
        active_until=date(2026, 9, 10),
    ),
    DailyTask(
        id="2026-0813-level-warseal",
        title="🏆 等級成就戰印（200~260 級每 10 級一個「永久」戰印）",
        category="event",
        where="霸王大殿 — 等級成就官",
        time_rule="達等級即可領取，可升級",
        reward="200~260 級各對應成就戰印（打怪經驗 +1%~+10%、體力 +100~+1000、持續 2 小時、冷卻 6 小時）",
        note="戰印永久有效 / 不可交易、存倉 / 260 級 +10% 經驗最強",
        keywords=["戰印", "等級成就", "永久", "200", "210", "220", "230", "240", "250", "260"],
        active_from=date(2026, 8, 13),
        active_until=None,
    ),
    DailyTask(
        id="2026-0813-daily-hunt",
        title="📋 每日懸賞任務（3 條）",
        category="event",
        where="懸賞榜系統",
        time_rule="每日重置",
        reward="龍銀寶箱 x3+x2+x1",
        note="1. 五丈原古道/渭水 擊殺 1000 隻 → 龍銀寶箱×3\n2. 梁山水寨 擊殺 1000 隻 → 龍銀寶箱×2\n3. 骷墳古社系列 擊殺 1000 隻 → 龍銀寶箱×1",
        keywords=["懸賞", "每日", "龍銀寶箱", "1000隻"],
        active_from=date(2026, 8, 13),
        active_until=date(2026, 9, 10),
    ),
    DailyTask(
        id="2026-0813-weekly-hunt",
        title="📋 每週懸賞任務（3 條，王怪貢獻）",
        category="event",
        where="懸賞榜系統",
        time_rule="每週重置",
        reward="積分寶箱 x10+x6+x4",
        note="1. 五丈原王怪×5 → 積分寶箱×10\n2. 梁山水寨王怪×5 → 積分寶箱×6\n3. 骷墳古社王怪×5 → 積分寶箱×4",
        keywords=["懸賞", "每週", "積分寶箱", "王怪"],
        active_from=date(2026, 8, 13),
        active_until=date(2026, 9, 10),
    ),
    DailyTask(
        id="2026-0813-unity-reward",
        title="🎁 Unity 獎勵一次性領取",
        category="event",
        where="露天市場 — Unity 福利官",
        time_rule="一次性領取",
        reward="知雨披風、高級化身券×10、Unity支援箱(30日經驗8倍符+30日轉運符+雲母石×30+藍晶石+穩定石+熔煉玉)",
        note="需 150 lv + 五品官以上 + Unity 版本上線滿 3 小時",
        keywords=["Unity", "獎勵", "一次性", "知雨披風", "8倍符"],
        active_from=date(2026, 8, 13),
        active_until=date(2026, 9, 10),
    ),
    DailyTask(
        id="2026-0813-weiyan-task",
        title="🗡️ 魏延每日任務 → 換天怒披風",
        category="event",
        where="霸王大殿 — 魏延",
        time_rule="每日 1 次接取",
        reward="魏延的信物 → 12 個換天怒披風 / 10 個換專精鎖 / 5 個換專精調整水",
        note="需 150 lv + 五品官 / 完整換齊需連續 12 天不斷任務",
        keywords=["魏延", "信物", "天怒披風", "專精鎖", "專精調整水"],
        active_from=date(2026, 8, 13),
        active_until=date(2026, 9, 10),
    ),
    DailyTask(
        id="2026-0813-fashion-shop",
        title="👘 時尚旅人扮裝販售",
        category="event",
        where="霸王大殿 — 時尚旅人",
        time_rule="限時販售期間",
        reward="龍神祝福 ×5/10/50/200/500 換各類扮裝、坐騎、飾品",
        note="龍寶(限定) = 500 龍神祝福 / 端陽靈羽等永久坐騎 = 50",
        keywords=["時尚旅人", "扮裝", "龍神祝福", "龍寶"],
        active_from=date(2026, 8, 13),
        active_until=date(2026, 9, 10),
    ),
    DailyTask(
        id="2026-0813-new-huashen",
        title="🔮 新化身開放（搜魂令/搜魂仙符）",
        category="event",
        where="化身系統",
        time_rule="活動期間可搜魂/煉化/換魂",
        reward="劉琮、蔡和、蔡中、范方、耿武、劉岱、蔡勳、楊弘 (搜魂令) / 夏侯惇、郝昭、夏侯尚+以上 (搜魂仙符) / 夏侯惇 (煉化+換魂)",
        note="夏侯惇為外觀強制化身，無法被裝備/扮裝覆蓋",
        keywords=["化身", "搜魂", "夏侯惇", "郝昭", "劉琮"],
        active_from=date(2026, 8, 13),
        active_until=None,
    ),
    DailyTask(
        id="2026-0813-config-upgrade",
        title="⭐ 能力配件 +10 升級為 ★ 系列（永久）",
        category="event",
        where="煉造房 — 配件類製作",
        time_rule="永久開放",
        reward="+10 百龍之智/養精蓄銳/強身健體/天下布武/後發先至/統兵遣將 → ★ 系列（體力+2000、防禦+200、技力+1000、對應屬性+300、四屬防+10%、防封+10%、減傷+7）",
        keywords=["配件", "升級", "★", "百龍之智", "天下布武"],
        active_from=date(2026, 8, 13),
        active_until=None,
    ),
    DailyTask(
        id="2026-0813-forge-up",
        title="🔨 全加持機率 UP",
        category="event",
        where="煉造房",
        time_rule="活動期間內加持",
        reward="全加持機率提升",
        note="搭配這波衝武器加持 / 扮裝加持最省道具",
        keywords=["加持", "機率", "UP", "煉造房"],
        active_from=date(2026, 8, 13),
        active_until=date(2026, 9, 10),
    ),
    DailyTask(
        id="2026-0813-drop-double",
        title="💰 全地圖打怪掉寶率加倍",
        category="event",
        where="全地圖",
        time_rule="活動期間打怪",
        reward="掉寶率 ×2",
        note="✨ 這條只到 08/27 (兩週)，不是整個活動期間，把握前半",
        keywords=["掉寶", "加倍", "打怪"],
        active_from=date(2026, 8, 13),
        active_until=date(2026, 8, 27),
    ),
    DailyTask(
        id="2026-0813-bamen-4th",
        title="🌀 八門系統第四層開放",
        category="event",
        where="八門升級介面",
        time_rule="永久開放",
        reward="乾/兌/離/震/巽/坎/艮/坤 各門滿級能力（體力/技力+1000、攻擊+10、武將技+1~2%、PVP傷害/減免+300 或 +2%）",
        note="開穴需經脈丹 ×10 / 需第三層滿 20 才能開第四層 / 全滿 20 級：普攻&全技能 0.6% 轉化為技力+體力",
        keywords=["八門", "第四層", "經脈丹", "乾", "兌", "離", "震"],
        active_from=date(2026, 8, 13),
        active_until=None,
    ),
    DailyTask(
        id="2026-0813-jiguan-6",
        title="🤖 機關人陸式升級開放",
        category="event",
        where="三主城工坊門口/露天市場 — 機關道長",
        time_rule="每日任務 / 22 小時重複接取",
        reward="陸式強化合金 ×2~4 / 完成三次額外獎勵",
        note="需群英之星 ×20 換合金 / 軒轅、神鳶、兩儀 分別升級 / 通用材料乾坤機關箱陸",
        keywords=["機關人", "陸式", "軒轅", "神鳶", "兩儀", "強化合金", "機關道長"],
        active_from=date(2026, 8, 13),
        active_until=None,
    ),
    DailyTask(
        id="2026-0813-amnesty",
        title="📜 大赦符 (30日) 新增",
        category="event",
        where="遊戲內道具",
        time_rule="30 日效果",
        reward="大赦符（惡名/通緝相關）",
        note="細節詳見遊戲內說明",
        keywords=["大赦符", "30日", "惡名"],
        active_from=date(2026, 8, 13),
        active_until=None,
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
