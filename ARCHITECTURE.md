# 架構契約 — 三層模組拆分

> 本文件是三個並行工作視窗的**唯一協調來源**。
> 動手前先讀「檔案所有權」一節，確認要改的檔案屬於自己的視窗。

## 為什麼要拆

現況 `src/` 是 18 個檔案的平面套件，相依關係其實已經分層且無循環，
但**兩個熱點檔案讓三窗並行必定撞車**：

| 熱點 | 現況 | 問題 |
|---|---|---|
| `src/app.py` | 單檔 15 條路由，只有 feedback 拆了 Blueprint | 網頁窗改路由、架構窗改匯入、腳本窗加指令，全撞同一檔 |
| `src/daily_tasks.py` | 696 行，只有 4 個 def/class → 約 640 行是純資料字面值 | 資料與程式碼混在一起，改一筆任務要 diff 整個模組 |

拆分的目標**不是**追求漂亮的分層，而是讓三個視窗各自擁有互斥的檔案集合。

## 目標結構

保留 `src` 為套件根（`Procfile` / `render.yaml` 改動最小），內部開子套件：

```
三國群英AI腳本計畫/
├── run.py                      # 保留，一鍵入口
├── requirements.txt
├── Procfile / render.yaml      # startCommand 改 src.web:app
├── ARCHITECTURE.md             # 本文件
├── data/
│   ├── news.db                 # 不進 git（build 時重建）
│   ├── raw_html/
│   └── game/                   # ★新增：靜態遊戲資料（進 git）
│       ├── daily_tasks.json
│       ├── dress_stages.json
│       ├── lootboxes.json
│       └── curated_patterns.json
└── src/
    ├── config.py               # ★新增：集中設定（路徑、token、爬蟲參數）
    ├── core/                   # 不依賴 Flask，不依賴 data/game
    │   ├── db.py
    │   ├── cache.py
    │   └── festivals.py
    ├── gamedata/               # 讀 data/game/*.json → dataclass + 計算
    │   ├── loader.py           # JSON 讀取 + 快取
    │   ├── daily.py            # 原 daily_tasks.py 的邏輯部分
    │   ├── dress.py            # 原 dress_strategy.py
    │   ├── lootbox.py          # 原 lootbox_data.py（EV/變異數數學留在 .py）
    │   └── levels.py           # 原 level_data.py（XP 曲線是公式，不外抽）
    ├── analysis/               # 不依賴 Flask
    │   ├── analyzer.py
    │   ├── predictor.py
    │   ├── backtest.py
    │   └── patterns.py         # 原 curated_patterns.py
    ├── ingest/                 # 爬取 / 擷取 / 通知 / 資料維護
    │   ├── scraper.py
    │   ├── extractor.py
    │   ├── notify.py
    │   └── restore_feedback.py
    └── web/                    # Flask 全部集中在此
        ├── __init__.py         # create_app() factory，匯出 app
        ├── views/
        │   ├── dashboard.py    # /  /timeline  /activities  /article/<id>
        │   ├── predict.py      # /accuracy  /recurring  /recharge
        │   ├── game.py         # /lootbox  /levels  /dress-strategy  /daily
        │   ├── feedback.py     # 現有 Blueprint 搬入
        │   └── admin.py        # /healthz  /admin/*
        └── templates/          # 由 templates/ 搬入
```

### 為什麼 `level_data` 不抽 JSON

`level_data.py` 204 行有 12 個 def/class，主體是 XP 曲線與精華成本的**公式**
（`E()`、`xp_to_reach()`、`essence_cost_to_upgrade()`），不是查表資料。抽成 JSON
只會製造一個沒人維護的中間層。`lootbox_data.py` 同理，18 個 def/class 是
EV / 變異數 / 貝氏觀測推論的數學，只有 `Lootbox` 定義本身外抽。

真正值得外抽的是 `daily_tasks.py`（約 640 行字面值）、`dress_strategy.py`
（Stage 清單）、`curated_patterns.py`（樣板字典）。

## 檔案所有權（互斥，不得越界）

| 視窗 | 擁有 | 不得碰 |
|---|---|---|
| **架構** | `src/config.py`、`src/core/`、`src/gamedata/`、`src/analysis/`、`data/game/*.json`、本文件 | `src/web/`、`src/ingest/`、`templates/` |
| **網頁** | `src/web/`、`src/web/templates/`（含全部 15 個模板） | `src/core/`、`src/analysis/`、`src/gamedata/` |
| **腳本** | `src/ingest/`、`scripts/`、`.github/workflows/`、`Procfile`、`render.yaml` | `src/web/`、`src/core/` |

跨界需求走「請求 → 架構窗實作」，不要自己伸手改別層。

## 遷移順序（重要）

三窗同時在跑，**順序錯了會互相蓋掉**。用 shim 讓每一步都不破壞現有匯入：

### Phase 1 — 架構窗（先做，其他兩窗此時照舊工作）

1. 新增 `src/config.py`，把 `db.py` 寫死的 `DB_PATH` 改成可用 `KH1_DB_PATH`
   環境變數覆寫（見下節「持久化」）。
2. `git mv` 建立 `src/core/`、`src/analysis/`、`src/gamedata/`。
3. 在舊路徑留 shim，例如 `src/db.py` 內容變成 `from src.core.db import *  # noqa`。
   → 此時 `src/app.py`、`src/scraper.py` 完全不用改，兩窗不受影響。
4. 抽 `data/game/*.json` + 改寫對應 loader。

### Phase 2 — 網頁窗

5. 建 `src/web/`，`create_app()` factory，路由按上表拆 5 個 blueprint。
6. `templates/` → `src/web/templates/`。
7. 保留 `src/app.py` 只做 `from src.web import app`，讓 `Procfile` 暫時不用改。

### Phase 3 — 腳本窗

8. 建 `src/ingest/`，搬 scraper / extractor / notify / restore_feedback。
9. 更新 `render.yaml` 的 buildCommand（`python -m src.ingest.scraper` 等）與
   `Procfile` 的 `src.web:app`。
10. 更新 `.github/workflows/weekly-update.yml` 的模組路徑。

### Phase 4 — 架構窗收尾

11. 刪掉全部 shim，`grep -rn "from src import\|from \. import"` 確認無殘留。
12. 一次 deploy 驗證 `/healthz` 與全部 15 條路由。

**Phase 之間要等前一階段 commit 完成再開始**，不要跳。

## 未解決的架構債：資料持久化

這是移植前最該先定案的一塊，目前的機制很脆弱：

- `data/news.db` 不進 git，每次 Render deploy 於 buildCommand 階段整個重爬重建。
- 使用者回饋（`feedback` 表）因此每次 deploy 都會消失，靠
  `src/ingest/restore_feedback.py` 從 git 裡的備份 JSON 撈回來。
- 也就是說**回饋資料的真實來源是 git commit**，不是資料庫。

三種可行方向，尚未決定：

| 方案 | 代價 | 換到的 |
|---|---|---|
| 維持現狀 + `config.py` 抽出路徑 | 最低 | 只是讓路徑可注入，債還在 |
| 換有持久磁碟的平台（Fly.io + volume / HF Spaces） | 中，要改部署 | DB 真正持久，`restore_feedback` 可刪 |
| feedback 外移到託管 Postgres（Neon / Supabase 免費層） | 中高，要加 driver 與 migration | 回饋與爬取資料解耦，各自獨立生命週期 |

`config.py` 的設計要能容納以上任一種，不要把 SQLite 假設寫進介面。

## 相依規則（拆完後必須維持）

```
config  ←  core  ←  gamedata
                 ←  analysis
                 ←  ingest
                 ←  web  ←（可依賴以上全部）
```

- `core/`、`analysis/`、`gamedata/`、`ingest/` 一律**不得 import flask**。
- `web/` 是唯一知道 HTTP 存在的層。
- 反向匯入（core 匯入 web、analysis 匯入 ingest）視為架構違規。

驗證指令：

```bash
grep -rn "flask" src/core src/analysis src/gamedata src/ingest && echo "架構違規" || echo "OK"
```

## 安全備註

`scripts/test_prod_feedback.py`（已於 2026-09-03 刪除）曾把線上 `ADMIN_TOKEN`
以明碼寫在原始碼裡。`.gitignore` 未排除 `scripts/`，一次 `git add .` 就會外洩。

規則：**任何 token 只從環境變數讀，不得出現在原始碼**。煙霧測試腳本統一用
`BASE`／`ADMIN_TOKEN` 兩個環境變數參數化，本機與生產共用同一支。
