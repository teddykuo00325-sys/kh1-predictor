"""Taiwan festival mapping — solar (Gregorian) and lunar.

Used by the predictor to seed "what festivals fall in month M" so we can match
historical activities with the same festival anchor.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

try:
    from lunardate import LunarDate
except ImportError:  # lunardate is optional at install time
    LunarDate = None


@dataclass(frozen=True)
class Festival:
    name: str
    keywords: tuple[str, ...]      # match against activity name / description
    month_solar: int | None        # 1..12 if solar-anchored, else None
    day_solar: int | None
    month_lunar: int | None        # if lunar-anchored
    day_lunar: int | None

    def solar_date(self, year: int) -> date | None:
        if self.month_solar and self.day_solar:
            return date(year, self.month_solar, self.day_solar)
        if self.month_lunar and self.day_lunar and LunarDate is not None:
            try:
                return LunarDate(year, self.month_lunar, self.day_lunar).toSolarDate()
            except Exception:
                return None
        return None


# Manually curated — covers everything the news site actually anchors events to.
FESTIVALS: list[Festival] = [
    Festival("元旦 / 新年",      ("元旦", "新年", "迎新", "跨年"),                1, 1, None, None),
    Festival("春節 / 農曆新年",  ("春節", "農曆新年", "過年", "新春", "拜年"), None, None, 1, 1),
    Festival("元宵節",           ("元宵", "燈節", "湯圓"),                       None, None, 1, 15),
    Festival("情人節",           ("情人節", "西洋情人"),                          2, 14, None, None),
    Festival("228 紀念日",        ("228", "和平紀念", "二二八"),                  2, 28, None, None),
    Festival("白色情人節",       ("白色情人",),                                   3, 14, None, None),
    Festival("兒童節",           ("兒童節",),                                     4, 4, None, None),
    Festival("清明節",           ("清明",),                                       4, 5, None, None),     # solar term ~4/4-4/5
    Festival("勞動節",           ("勞動節", "五一", "勞工"),                      5, 1, None, None),
    Festival("母親節 / 慈母節",  ("母親節", "慈母", "感恩母親", "媽媽"),         5, 11, None, None),    # placeholder — overridden below
    Festival("端午節",           ("端午", "粽子", "龍舟"),                        None, None, 5, 5),
    Festival("七夕情人節",       ("七夕", "牛郎", "織女", "中式情人"),           None, None, 7, 7),
    Festival("中元節",           ("中元", "鬼月", "普渡"),                        None, None, 7, 15),
    Festival("父親節",           ("父親節", "爸爸"),                              8, 8, None, None),
    Festival("教師節",           ("教師節",),                                     9, 28, None, None),
    Festival("中秋節",           ("中秋", "月餅", "團圓"),                        None, None, 8, 15),
    Festival("國慶 / 雙十",      ("雙十", "國慶", "10/10"),                       10, 10, None, None),
    Festival("萬聖節",           ("萬聖", "南瓜", "Halloween"),                   10, 31, None, None),
    Festival("光棍節 / 雙11",    ("雙11", "光棍", "11/11"),                       11, 11, None, None),
    Festival("感恩節",           ("感恩節", "Thanksgiving"),                      11, 28, None, None),
    Festival("聖誕節",           ("聖誕", "Xmas", "Christmas"),                   12, 25, None, None),
    Festival("跨年",             ("跨年", "倒數"),                                12, 31, None, None),
]

# Activity-style anchors that are not literal festivals but recur on calendar months
EVERGREEN_TAGS: list[tuple[str, tuple[str, ...]]] = [
    ("月度儲值贈品", ("儲值", "贈晶石", "祝福晶石", "回饋")),
    ("國戰",         ("國戰", "PVP", "梁山", "戰場較勁")),
    ("升級活動",     ("升級成功率", "重鑄", "強化")),
    ("商城促銷",     ("商城", "五折", "買一送一", "限時特賣")),
    ("經驗加倍",     ("經驗", "倍數", "加倍")),
    ("配飾",         ("配飾", "玉珮", "飾品")),
    ("珠寶/修練之珠", ("修練之珠", "戰場之珠", "無畏之珠")),
    ("姻緣守護靈",   ("姻緣守護靈", "守護靈")),
    ("版本更新",     ("版本更新", "改版資訊", "版本公告", "version")),
]


def mothers_day(year: int) -> date:
    """Mother's Day in Taiwan = 2nd Sunday of May."""
    d = date(year, 5, 1)
    # weekday(): Monday=0 .. Sunday=6
    offset = (6 - d.weekday()) % 7
    first_sunday = d.day + offset
    return date(year, 5, first_sunday + 7)


def fathers_day(year: int) -> date:
    """Father's Day in Taiwan = Aug 8 ('八八' homophone for 爸爸)."""
    return date(year, 8, 8)


def festivals_in_month(year: int, month: int) -> list[tuple[Festival, date]]:
    """Return all (festival, actual_date) tuples whose anchor date falls in (year, month)."""
    hits: list[tuple[Festival, date]] = []
    for f in FESTIVALS:
        if f.name.startswith("母親節"):
            d = mothers_day(year)
        else:
            d = f.solar_date(year)
        if d and d.month == month:
            hits.append((f, d))
    return hits


def match_festival(text: str) -> Festival | None:
    """Return the first festival whose keywords appear in the given text."""
    if not text:
        return None
    for f in FESTIVALS:
        for kw in f.keywords:
            if kw and kw in text:
                return f
    return None


def evergreen_tags(text: str) -> list[str]:
    tags: list[str] = []
    if not text:
        return tags
    for tag, kws in EVERGREEN_TAGS:
        if any(k in text for k in kws):
            tags.append(tag)
    return tags
