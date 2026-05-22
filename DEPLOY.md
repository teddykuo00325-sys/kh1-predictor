# 部署到 Render.com (免費雲端)

本系統可部署至 Render.com 的免費 Web Service，讓任何電腦/手機透過公網 URL 存取。

## 前置條件
- 一個 GitHub 帳號 (免費)
- 一個 Render.com 帳號 (用 GitHub 登入即可，免信用卡)

## 部署成本與限制
- **完全免費**：每月 750 小時免費 (一個服務全月開機 = 720 小時)
- **15 分鐘無人使用會休眠**：下次造訪需 ~30 秒冷啟動
- **每次冷啟動會載入 build 階段建好的 `data/news.db`**，不會重新抓
- **想更新資料**：到 Render Dashboard 按「Manual Deploy → Clear build cache & deploy」即可重新抓取

---

## 步驟 1 — 把專案推上 GitHub

在本機 PowerShell 執行（首次使用 git 才需要設身分）：
```powershell
git config --global user.name "你的名字"
git config --global user.email "你的email"
```

然後初始化並推送：
```powershell
cd C:\Users\teddy\三國群英AI腳本計畫
git init
git add .
git commit -m "Initial commit: 三國群英活動預測系統"
git branch -M main
# 先到 https://github.com/new 建立一個 repo (例如 kh1-predictor)，建立後 GitHub 會顯示推送指令
git remote add origin https://github.com/<你的帳號>/kh1-predictor.git
git push -u origin main
```

> 注意：`.gitignore` 已排除 `data/news.db` 和 `data/raw_html/`，所以 repo 不會包含 ~10MB 的爬取資料，這些會在 Render 的 build 階段自動產生。

## 步驟 2 — 連結 Render

1. 開啟 https://dashboard.render.com 用 GitHub 登入
2. 點右上 **New + → Web Service**
3. 選擇剛剛推送的 `kh1-predictor` repo，點 **Connect**
4. 設定畫面 Render 會自動讀取 `render.yaml`，確認以下：
   - **Name**: `kh1-predictor` (或自訂)
   - **Region**: Singapore (距離台灣最近)
   - **Branch**: `main`
   - **Plan**: **Free** ⚠️ 確認選免費方案
5. 點 **Create Web Service**

## 步驟 3 — 等待首次 build

Render 會自動執行 `render.yaml` 裡的 `buildCommand`：
1. `pip install -r requirements.txt`  → ~2 分鐘
2. `python -m src.scraper`            → ~5 分鐘 (抓 294+ 篇公告)
3. `python -m src.extractor`          → ~5 秒 (拆活動)

build 完成後自動啟動 gunicorn，可在 Dashboard 看到狀態變綠。

服務上線 URL 會像這樣：
```
https://kh1-predictor.onrender.com
```

## 步驟 4 — 驗證

開瀏覽器造訪你的 URL：
- `/` → 下月預測 dashboard
- `/healthz` → 健康檢查（回傳 JSON 含文章數量）
- `/timeline`、`/activities`、`/recharge`、`/article/<id>` 也都可用

## 常見問題

### 1. 想更新資料
- Render Dashboard → 你的服務 → 右上 **Manual Deploy** → **Clear build cache & deploy**
- 約 7-10 分鐘後新資料生效

### 2. 第一次造訪很慢
- 免費方案無人使用 15 分鐘會休眠，下次造訪要重新啟動 (~30 秒)
- 若要避免休眠：可用 https://cron-job.org 設定每 14 分鐘 ping 一次 `/healthz`（合法且免費）

### 3. 看到「資料準備中」頁面
- 表示 build 階段的爬蟲還沒跑完或失敗
- 查看 Render Dashboard → **Logs** 看錯誤訊息
- 多半是 build 命令未完成；可手動重新部署

### 4. build 超時 (>15 分鐘)
- 免費方案 build timeout 是 15 分鐘
- 若抓取太慢，可暫時把 `src/scraper.py` 的 `EARLIEST_YEAR` 改為較近期 (例如 2024)
- 或把 `SLEEP_SEC` 降到 0.2

### 5. 完全不用 GitHub 可以嗎？
- 可以，Render 也支援從 Docker Hub 拉 image，但設定較複雜
- 或改用 Hugging Face Spaces (有持久磁碟，可增量更新)

---

## 替代方案：本機跨網（Cloudflare Tunnel）

若不想用雲端，可以保持本機 Flask 開著，用 Cloudflare Tunnel 對外公開：

```powershell
# 1) 下載 cloudflared.exe https://github.com/cloudflare/cloudflared/releases
# 2) 啟動本機 Flask
python -m src.app
# 3) 另開一個視窗
.\cloudflared.exe tunnel --url http://localhost:5000
```

它會印出一個 `https://xxx.trycloudflare.com` URL，免費、不需註冊、不需信用卡，
唯一限制是你關機就沒了。

---

## 替代方案：區域網路 (LAN)

只讓同 WiFi 內的電腦/手機存取，最簡單：

```powershell
$env:HOST="0.0.0.0"; python -m src.app
```

查看自己的內網 IP：
```powershell
ipconfig | findstr IPv4
```

其他裝置開 `http://你的內網IP:5000` 即可。
（Windows 防火牆可能需要允許 Python.exe 對外連線）
