<#
    三國神燈 多開啟動器
    ------------------------------------------------------------------
    問你要開幾個視窗 -> 依序啟動 -> 每個視窗自動選好帳號與設置，然後停住。
    預設「不會」按啟動遊戲，要按才加 -Start。
    輸入值與帳號清單記在 %LOCALAPPDATA%\SanOLLampLauncher\settings.json，
    下次直接按 Enter 沿用。

    帳號清單：settings.json 的 accounts 陣列，第 N 個視窗用第 N 個帳號。
    用 -ListAccounts 可以印出神燈目前認得的所有帳號。

    UAC：預設帶 __COMPAT_LAYER=RunAsInvoker，不跳提示。這同時是 UI 自動化
         能運作的前提 —— 提權的實例會被 UIPI 擋掉，腳本碰不到。

    範例：
        .\launch_game.ps1                  # 互動式
        .\launch_game.ps1 -Count 3         # 開 3 個，用清單前 3 個帳號
        .\launch_game.ps1 -Accounts teddy810,teddy710
        .\launch_game.ps1 -ListAccounts        # 列出所有帳號後結束
        .\launch_game.ps1 -Count 2 -Start      # 連「啟動遊戲」也一起按（預設不按）
#>
[CmdletBinding()]
param(
    [int]      $Count,
    [double]   $Delay,
    [string]   $ExePath,
    [string[]] $Accounts,
    [int]      $Setting,
    [switch]   $Start,
    [switch]   $AutoLogin,
    [switch]   $ListAccounts,
    [switch]   $AsAdmin,
    [switch]   $NoPrompt
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
. (Join-Path $PSScriptRoot 'lamp_ui.ps1')

$DefaultExe   = 'C:\Game\SanOLLampTW_Unity\SanOLLamp.exe'
$DefaultDelay = 3
$MaxCount     = 20
$SettingsDir  = Join-Path $env:LOCALAPPDATA 'SanOLLampLauncher'
$SettingsFile = Join-Path $SettingsDir 'settings.json'


function Get-Settings {
    $s = @{ count=1; delay=$DefaultDelay; exe=$DefaultExe; accounts=@(); setting=0 }
    if (Test-Path $SettingsFile) {
        try {
            $j = Get-Content $SettingsFile -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($j.count -gt 0)        { $s.count    = [int]$j.count }
            if ($null -ne $j.delay)    { $s.delay    = [double]$j.delay }
            if ($j.exe)                { $s.exe      = [string]$j.exe }
            if ($j.accounts)           { $s.accounts = @($j.accounts) }
            if ($null -ne $j.setting)  { $s.setting  = [int]$j.setting }
        } catch {
            Write-Host "  (設定檔讀取失敗，用預設值：$($_.Exception.Message))" -ForegroundColor DarkYellow
        }
    }
    return $s
}

function Save-Settings($s) {
    try {
        if (-not (Test-Path $SettingsDir)) { New-Item -ItemType Directory -Path $SettingsDir -Force | Out-Null }
        [pscustomobject]@{
            count    = $s.count
            delay    = $s.delay
            exe      = $s.exe
            accounts = @($s.accounts)
            setting  = $s.setting
            savedAt  = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
        } | ConvertTo-Json | Out-File $SettingsFile -Encoding utf8
    } catch {
        Write-Host "  (設定檔寫入失敗：$($_.Exception.Message))" -ForegroundColor DarkYellow
    }
}

function Get-RunningCount($exe) {
    try { @(Get-Process -Name ([IO.Path]::GetFileNameWithoutExtension($exe)) -ErrorAction Stop).Count } catch { 0 }
}

# Start-LampProcess / Get-LampAccounts 等來自 lamp_ui.ps1


# ---------------------------------------------------------------- 主流程

$saved = Get-Settings
if (-not $ExePath) { $ExePath = $saved.exe }
if (-not $PSBoundParameters.ContainsKey('Delay'))   { $Delay   = $saved.delay }
if (-not $PSBoundParameters.ContainsKey('Setting')) { $Setting = $saved.setting }

Write-Host ''
Write-Host '  === 三國神燈 多開啟動器 ===' -ForegroundColor Cyan
Write-Host "  執行檔：$ExePath" -ForegroundColor DarkGray

if (-not (Test-Path $ExePath)) {
    Write-Host "`n  [錯誤] 找不到執行檔：$ExePath" -ForegroundColor Red
    if (-not $NoPrompt) { Read-Host '  按 Enter 結束' }
    exit 1
}
if ($AsAdmin) {
    Write-Host '  權限：維持提權（會跳 UAC，且自動化無法運作）' -ForegroundColor DarkYellow
} else {
    Write-Host '  權限：一般使用者，不跳 UAC' -ForegroundColor DarkGray
}

# --- 列出帳號 ---
if ($ListAccounts) {
    Write-Host "`n  開一個暫時實例來讀帳號清單…" -ForegroundColor DarkGray
    $tmpPid = Start-LampProcess -ExePath $ExePath -AsAdmin:$AsAdmin
    if ($tmpPid -eq 0) { Write-Host '  啟動失敗' -ForegroundColor Red; exit 1 }
    $h = Wait-LampWindow -ProcessId $tmpPid
    $list = Get-LampAccounts -Main $h
    Write-Host "`n  神燈認得的帳號：" -ForegroundColor Cyan
    for ($i = 0; $i -lt $list.Count; $i++) { Write-Host ("      [{0,2}] {1}" -f $i, $list[$i]) }
    Stop-Process -Id $tmpPid -Force
    Write-Host "`n  暫時實例已關閉。" -ForegroundColor DarkGray
    if (-not $NoPrompt) { Read-Host '  按 Enter 結束' }
    exit 0
}

$already = Get-RunningCount $ExePath
Write-Host "  目前已開啟：$already 個" -ForegroundColor DarkGray

# --- 帳號清單 ---
if (-not $Accounts -or $Accounts.Count -eq 0) { $Accounts = @($saved.accounts) }
if ($Accounts.Count -gt 0) {
    Write-Host "  帳號清單：$($Accounts -join ', ')" -ForegroundColor DarkGray
} else {
    Write-Host '  帳號清單：(未設定 — 只會開視窗，不選帳號)' -ForegroundColor DarkYellow
    Write-Host '             先跑 -ListAccounts 看有哪些，再用 -Accounts 指定。' -ForegroundColor DarkYellow
}
Write-Host ''

# --- 決定要開幾個 ---
$maxAllowed = if ($Accounts.Count -gt 0) { [Math]::Min($MaxCount, $Accounts.Count) } else { $MaxCount }
if ($PSBoundParameters.ContainsKey('Count') -and $Count -gt 0) {
    $target = $Count
} elseif ($NoPrompt) {
    $target = $saved.count
} else {
    $target = 0
    while ($target -lt 1) {
        $answer = Read-Host "  要開幾個視窗? (1-$maxAllowed，Enter = 上次的 $($saved.count))"
        if ([string]::IsNullOrWhiteSpace($answer)) { $target = $saved.count }
        elseif ($answer -match '^\s*\d+\s*$')      { $target = [int]$answer.Trim() }
        else { Write-Host '  請輸入數字。' -ForegroundColor Yellow; continue }
        if ($target -lt 1 -or $target -gt $maxAllowed) {
            Write-Host "  請輸入 1 到 $maxAllowed 之間的數字。" -ForegroundColor Yellow
            $target = 0
        }
    }
}
if ($target -gt $maxAllowed) {
    Write-Host "  上限 $maxAllowed（受帳號清單長度限制），已調整。" -ForegroundColor Yellow
    $target = $maxAllowed
}

$saved.count = $target; $saved.delay = $Delay; $saved.exe = $ExePath
$saved.accounts = @($Accounts); $saved.setting = $Setting
Save-Settings $saved

# --- 逐一啟動並設定 ---
Write-Host "`n  啟動 $target 個（間隔 $Delay 秒）…`n" -ForegroundColor Green
$ok = 0
$failed = @()

for ($i = 0; $i -lt $target; $i++) {
    $acct = if ($i -lt $Accounts.Count) { $Accounts[$i] } else { $null }
    $tag  = "[{0}/{1}]" -f ($i + 1), $target
    $name = if ($acct) { $acct } else { '(不選帳號)' }
    Write-Host "    $tag $name" -ForegroundColor White

    $procId = Start-LampProcess -ExePath $ExePath -AsAdmin:$AsAdmin
    if ($procId -eq 0) {
        Write-Host '          啟動失敗' -ForegroundColor Red
        $failed += $name
        continue
    }
    Write-Host "          pid=$procId" -ForegroundColor DarkGray

    if ($AsAdmin -or -not $acct) {
        $ok++
        if ($i -lt $target - 1 -and $Delay -gt 0) { Start-Sleep -Seconds $Delay }
        continue
    }

    $h = Wait-LampWindow -ProcessId $procId
    if ($h -eq [IntPtr]::Zero) {
        Write-Host '          找不到視窗，跳過設定' -ForegroundColor Red
        $failed += $name
        continue
    }

    $list = Get-LampAccounts -Main $h
    $idx  = [Array]::IndexOf($list, $acct)
    if ($idx -lt 0) {
        Write-Host "          帳號 '$acct' 不在神燈清單中，跳過" -ForegroundColor Red
        $failed += $name
        continue
    }
    if (-not (Set-LampCombo -Main $h -CtrlId 1019 -Index $idx)) {
        Write-Host '          選帳號失敗' -ForegroundColor Red
        $failed += $name
        continue
    }

    Start-Sleep -Milliseconds 800
    $path = Get-LampField -Main $h -CtrlId 1005
    if ([string]::IsNullOrWhiteSpace($path)) {
        Write-Host '          選了帳號但遊戲路徑沒帶出來 — 中止這個視窗的後續動作' -ForegroundColor Red
        $failed += $name
        continue
    }
    Write-Host "          帳號已選，路徑=$path" -ForegroundColor DarkGray

    if ($Setting -ge 1 -and $Setting -le 20) {
        if (Set-LampCombo -Main $h -CtrlId 1033 -Index ($Setting - 1)) {
            Write-Host "          設置 -> 設置$Setting" -ForegroundColor DarkGray
        } else {
            Write-Host "          設置$Setting 設定失敗（繼續）" -ForegroundColor DarkYellow
        }
    }

    if ($AutoLogin) {
        [void](Invoke-LampButton -Main $h -CtrlId 1025)
        Write-Host '          已按「自動登錄,讀取」' -ForegroundColor DarkGray
        Start-Sleep -Milliseconds 1200
    }

    if ($Start) {
        [void](Invoke-LampButton -Main $h -CtrlId 1000)
        Write-Host '          已按「啟動遊戲」' -ForegroundColor Green
    } else {
        Write-Host '          已就緒，啟動遊戲由你自己按' -ForegroundColor DarkGray
    }
    $ok++

    if ($i -lt $target - 1 -and $Delay -gt 0) { Start-Sleep -Seconds $Delay }
}

Start-Sleep -Seconds 1
Write-Host "`n  完成：$ok / $target 個。目前執行中 $(Get-RunningCount $ExePath) 個。" -ForegroundColor Cyan
if ($failed.Count -gt 0) { Write-Host "  有問題的：$($failed -join ', ')" -ForegroundColor Yellow }
Write-Host ''
if (-not $NoPrompt) { Read-Host '  按 Enter 關閉視窗' }
