# 三國群英 Online 活動 / 儲值贈品預測系統

依據 `kh1.uj.com.tw` 官方歷史公告 (2023-至今)，分析活動週期，並預測下個月可能出現的活動與儲值贈品。

## 架構

```
三國群英AI腳本計畫/
├── requirements.txt
├── run.py                      # 一鍵入口 (scrape → analyze → serve)
├── data/
│   ├── news.db                 # SQLite 歷史資料
│   └── raw_html/               # 原始 HTML 快取
├── src/
│   ├── scraper.py              # 從 ajax_news_list.php 抓列表 + 個別文章
│   ├── extractor.py            # 將文章拆成多個活動條目
│   ├── festivals.py            # 國曆/農曆節日對應表
│   ├── analyzer.py             # TF-IDF + 同月頻率分析
│   ├── predictor.py            # 下月預測 (規則式 + 相似度)
│   └── app.py                  # Flask 儀表板
└── templates/                  # Jinja2 HTML
    ├── base.html
    ├── dashboard.html
    ├── timeline.html
    ├── activities.html
    └── article.html
```

## 使用方式

```powershell
# 1) 安裝套件
pip install -r requirements.txt

# 2) 一鍵抓資料 → 分析 → 開啟 Dashboard (預設 http://127.0.0.1:5000)
python run.py

# 或分階段
python -m src.scraper            # 只抓資料 (增量, 已存在的跳過)
python -m src.scraper --full     # 強制重抓
python -m src.extractor          # 重新萃取活動條目
python -m src.predictor          # 在終端列印下月預測
python -m src.app                # 只啟動 Dashboard
```

## 預測邏輯

1. **節日對應** - `festivals.py` 內建台灣國曆+農曆節日字典 (春節、清明、母親節、端午、七夕、中秋、雙十、聖誕…)。
2. **同月歷史** - 把每筆活動依「公告月份」分組，計算每個活動關鍵字在該月過去 N 年的出現次數。
3. **版本節奏** - 偵測「40.0.1.x 版本更新公告」的發布週期 (約 7-14 天)，預測下次版本號與日期。
4. **儲值贈品** - 解析「每單筆儲值達 X 元」「贈送 Y」字串，建立贈品-金額樣板，按月份重複出現程度排序。
5. **信心分數** - 出現次數 / 觀察月數，0-100% 區間。

詳細演算法見 `src/predictor.py`。
