<#
    把多開啟動器打包成可以拷到別台電腦的資料夾 + zip。

    產出：
        dist\神燈多開啟動器\      可直接複製到別台電腦的資料夾
        dist\神燈多開啟動器.zip   壓縮檔

    收件人只要解壓縮 -> 雙擊「啟動神燈多開.cmd」-> 路徑不對就按「瀏覽…」挑
    自己的 SanOLLamp.exe 即可。

    用法： .\build_package.ps1
#>
[CmdletBinding()]
param(
    [string]$OutRoot = (Join-Path (Split-Path $PSScriptRoot -Parent) 'dist')
)

$ErrorActionPreference = 'Stop'

$pkgName = '神燈多開啟動器'
$pkgDir  = Join-Path $OutRoot $pkgName
$zipPath = Join-Path $OutRoot "$pkgName.zip"

Write-Host "打包到 $pkgDir" -ForegroundColor Cyan

# 資料夾本身可能被檔案總管之類的開著而刪不掉；清空內容就夠了，不必強求刪目錄
if (Test-Path $pkgDir) {
    Get-ChildItem $pkgDir -Recurse -Force -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    try { Remove-Item $pkgDir -Recurse -Force -ErrorAction Stop } catch { }
}
New-Item -ItemType Directory -Path $pkgDir -Force | Out-Null

$leftover = @(Get-ChildItem $pkgDir -Force -ErrorAction SilentlyContinue)
if ($leftover.Count -gt 0) {
    Write-Host "  警告：有 $($leftover.Count) 個舊檔清不掉，可能混進打包結果" -ForegroundColor Yellow
    $leftover | ForEach-Object { Write-Host "    $($_.Name)" -ForegroundColor Yellow }
}

# --- 1. 程式本體 ---
foreach ($f in 'launch_gui.ps1', 'lamp_ui.ps1') {
    Copy-Item (Join-Path $PSScriptRoot $f) (Join-Path $pkgDir $f) -Force
    Write-Host "  + $f"
}

# --- 2. 圖示 ---
& (Join-Path $PSScriptRoot 'make_icon.ps1') -OutDir $pkgDir | Out-Null
Write-Host "  + lamp.ico"

# --- 3. 批次檔 ---
# 內容一律純 ASCII：檔名用中文沒問題，但 .cmd 內文有中文容易因為
# 使用者的字碼頁不同而變成亂碼或解析失敗。
function Write-Ascii($path, [string[]]$lines) {
    [IO.File]::WriteAllText($path, (($lines -join "`r`n") + "`r`n"), [Text.Encoding]::ASCII)
}

Write-Ascii (Join-Path $pkgDir '啟動神燈多開.cmd') @(
    '@echo off',
    'start "" powershell -NoProfile -STA -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0launch_gui.ps1"'
)
Write-Host "  + 啟動神燈多開.cmd"

Write-Ascii (Join-Path $pkgDir '建立桌面捷徑.cmd') @(
    '@echo off',
    'powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0make_shortcut.ps1"',
    'pause'
)
Write-Host "  + 建立桌面捷徑.cmd"

# --- 4. 建立捷徑的腳本（中文留在 ps1 裡，UTF-8 BOM 不會亂碼）---
$shortcut = @'
# 在桌面建立一個帶圖示的捷徑，指向同資料夾的啟動批次檔。
# 實作共用 lamp_ui.ps1 的 New-LampShortcut。
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'lamp_ui.ps1')

$lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) '三國神燈 多開啟動器.lnk'
Write-Host ''
if (New-LampShortcut -LinkPath $lnk -PackageDir $PSScriptRoot) {
    Write-Host "  已在桌面建立捷徑：$lnk" -ForegroundColor Green
} else {
    Write-Host "  建立失敗 —— 請確認這個檔案和「啟動神燈多開.cmd」在同一個資料夾。" -ForegroundColor Red
}
Write-Host ''
'@
[IO.File]::WriteAllText((Join-Path $pkgDir 'make_shortcut.ps1'), $shortcut,
                        (New-Object Text.UTF8Encoding($true)))
Write-Host "  + make_shortcut.ps1"

# --- 5. 說明 ---
$readme = @'
三國神燈 多開啟動器
====================================================================

這是什麼
--------
一次開好幾個「三國神燈」視窗，每個自動選好不同的帳號與設置，
省去每開一個就要手動選一次的麻煩。

預設「不會」按下「啟動遊戲」—— 它只把帳號和設置選好就停住，
最後那一下由你自己按。要讓它連啟動也一起按，在介面上把
「選好後按『啟動遊戲』」勾起來。


怎麼用
--------
1. 把整個資料夾複製到電腦任何地方（桌面、D 槽都行）。
2. 雙擊「啟動神燈多開.cmd」。
   ★ 第一次執行後，資料夾裡會自動多出一個帶神燈圖示的捷徑
     「三國神燈 多開啟動器.lnk」，之後改用那個開就有圖示了，
     也可以把它拖到桌面或釘到工作列。
   想直接放一份到桌面，執行「建立桌面捷徑.cmd」，或在程式介面上
   按「建立桌面捷徑」。
3. 第一次開啟時程式會自動找 SanOLLamp.exe。
   找錯或找不到，就按右上角「瀏覽…」挑你自己的 SanOLLamp.exe。
   ★ 要選「神燈」的執行檔，不是遊戲本身的執行檔。
4. 路徑選對後，帳號清單會自動從神燈旁邊的 config 資料夾載入。
5. 打勾要開的帳號，各自挑設置，用「上移 / 下移」排啟動順序。
6. 按「開始啟動」。


注意事項
--------
* 設置下拉只會列出該帳號真的存在的設置檔。沒有設置檔的帳號
  只能選「原本設置」。
* 選了「設置N」會被神燈寫回該帳號的 login.ini，等於永久改掉
  那個帳號記住的設置。不想更動就保持「原本設置」。
* 本工具用一般使用者權限啟動神燈，所以不會跳出「是否允許此App
  變更你的裝置」。這也是自動選帳號能運作的前提 —— 如果你自己
  用「以系統管理員身分執行」另外開了神燈，本工具碰不到那些視窗。
* 你的勾選、順序、設置會記在
  %LOCALAPPDATA%\SanOLLampLauncher\settings.json
  每台電腦各自獨立。
* 「啟動神燈多開.cmd」本身一定是 Windows 的通用批次檔圖示 ——
  .cmd 不能帶自訂圖示，這是 Windows 的限制，不是壞掉。程式視窗
  和捷徑才會顯示神燈圖示。
* 資料夾搬位置後捷徑會失效，但只要再執行一次本體，資料夾裡那個
  捷徑就會自動更新回正確路徑。桌面捷徑則需要重新建立一次。


跑不起來的話
--------
* 「因為這個系統上已停用指令碼執行」：批次檔已經加了繞過參數，
  正常不會遇到。若還是出現，對著 launch_gui.ps1 和 lamp_ui.ps1
  按右鍵 -> 內容 -> 勾選「解除封鎖」-> 確定。
* 視窗一閃就不見：改成在 PowerShell 視窗裡直接執行
  launch_gui.ps1，就看得到錯誤訊息。
* 需要 Windows 內建的 PowerShell 5.1 與 .NET Framework，
  Windows 10 / 11 都有，不用另外安裝。


想知道原理
--------
看「技術解析.md」—— 裡面說明它是怎麼用 Win32 訊息選到帳號的、
為什麼不模擬滑鼠、控制項 ID 對照表，以及開發時踩過的坑。
'@
[IO.File]::WriteAllText((Join-Path $pkgDir '使用說明.txt'), $readme,
                        (New-Object Text.UTF8Encoding($true)))
Write-Host "  + 使用說明.txt"

# --- 5b. 技術解析 ---
Copy-Item (Join-Path $PSScriptRoot '技術解析.md') (Join-Path $pkgDir '技術解析.md') -Force
Write-Host "  + 技術解析.md"

# --- 6. 壓縮 ---
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path $pkgDir -DestinationPath $zipPath -Force

Write-Host ''
Write-Host "完成" -ForegroundColor Green
Get-ChildItem $pkgDir | Select-Object Name, Length | Format-Table -AutoSize
Write-Host "zip: $zipPath ($([Math]::Round((Get-Item $zipPath).Length / 1KB)) KB)"
