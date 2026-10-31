<#
    三國群英 多開 — 常駐自動調校

    解決的問題：親和性與優先權只綁在「當前行程」上，視窗一重開就全部消失，
    而且不會有任何提示。本程式常駐偵測，發現新的 SangoOL.exe 或設定被重置
    就自動補上，所以不管你怎麼重開視窗，調校永遠在。

    做的事（每隔幾秒檢查一次，已經正確的就跳過）：
      * 主力視窗   -> 鎖大核 + 提高優先權
      * 其他實例   -> 趕到小核（可用 -NoIsolate 關閉）
      * 讀 Player.log 的已載入物件數，超過門檻就提醒該重開客戶端

    用法：
        .\lamp_autotune.ps1 -MainTitle 反˙冰沁
        .\lamp_autotune.ps1 -FollowForeground          # 自動跟著你正在玩的視窗
        .\lamp_autotune.ps1 -MainTitle 反˙冰沁 -NoIsolate -Priority AboveNormal

    停止：直接關掉這個視窗，或按 Ctrl+C。
    停止後設定會留著（不會自動還原），要還原用 lamp_perf.ps1 -Revert。
#>
[CmdletBinding()]
param(
    [string] $MainTitle,
    [switch] $FollowForeground,
    [string] $PCores   = '0-5',
    [string] $ECores   = '6-13',
    [ValidateSet('Normal','AboveNormal','High')]
    [string] $Priority = 'High',
    [switch] $NoIsolate,
    [int]    $IntervalSec = 5,
    [int]    $ObjWarn  = 140000,
    [string] $LogPath
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

# ---------------------------------------------------------------- 提權

$isAdmin = ([Security.Principal.WindowsPrincipal] `
            [Security.Principal.WindowsIdentity]::GetCurrent()
           ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

# 只有在「真的碰不到遊戲行程」時才提權。
# 用 launch_gui.ps1（RunAsInvoker）開的實例是非提權的，一般權限就讀寫得到，
# 不必為了它跳 UAC；手動雙擊開的實例才是提權的，那時才需要。
function Test-CanTune {
    $g = @(Get-Process SangoOL -ErrorAction SilentlyContinue)
    if ($g.Count -eq 0) { return $null }          # 還沒開遊戲，無法判斷
    foreach ($p in $g) {
        try {
            $null = $p.ProcessorAffinity          # 讀得到就表示有權限
            $null = $p.Threads[0].TotalProcessorTime
            return $true
        } catch { }
    }
    return $false
}

if (-not $isAdmin) {
    $can = Test-CanTune
    if ($can -eq $false) {
        Write-Host ''
        Write-Host '  偵測到遊戲是以系統管理員身分啟動的，一般權限碰不到它。' -ForegroundColor Yellow
        Write-Host '  正在要求提權…' -ForegroundColor Yellow
        $argLine = @('-NoProfile','-ExecutionPolicy','Bypass','-File', "`"$PSCommandPath`"")
        foreach ($kv in $PSBoundParameters.GetEnumerator()) {
            if ($kv.Value -is [switch]) { if ($kv.Value) { $argLine += "-$($kv.Key)" } }
            else { $argLine += "-$($kv.Key)"; $argLine += "`"$($kv.Value)`"" }
        }
        Start-Process powershell -Verb RunAs -ArgumentList $argLine
        return
    }
    elseif ($can -eq $true) {
        Write-Host ''
        Write-Host '  遊戲是非提權啟動的，一般權限即可操作 — 不需要 UAC。' -ForegroundColor Green
    }
    else {
        Write-Host ''
        Write-Host '  目前沒有遊戲在跑，先以一般權限啟動；' -ForegroundColor DarkYellow
        Write-Host '  之後若發現碰不到遊戲行程，會提示你改用系統管理員身分重跑。' -ForegroundColor DarkYellow
    }
}

if (-not $MainTitle -and -not $FollowForeground) {
    Write-Host ''
    Write-Host '  請用 -MainTitle <角色名關鍵字> 指定主力視窗，' -ForegroundColor Red
    Write-Host '  或用 -FollowForeground 讓它自動跟著你正在操作的視窗。' -ForegroundColor Red
    Write-Host ''
    Read-Host '  按 Enter 結束'
    return
}

# ---------------------------------------------------------------- 工具

if (-not ('AtWin' -as [type])) {
Add-Type -TypeDefinition @"
using System; using System.Text; using System.Runtime.InteropServices; using System.Collections.Generic;
public class AtWin {
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
  [DllImport("user32.dll")] public static extern int  GetWindowThreadProcessId(IntPtr h, out int pid);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  public delegate bool EnumProc(IntPtr h, IntPtr p);
  public static List<string> Rows = new List<string>();
  static bool Cb(IntPtr h, IntPtr p){
    if(!IsWindowVisible(h)) return true;
    var s = new StringBuilder(512); GetWindowTextW(h, s, 512);
    if (s.Length == 0) return true;
    int q; GetWindowThreadProcessId(h, out q);
    Rows.Add(q + "\t" + s.ToString() + "\t" + (h == GetForegroundWindow() ? "1" : "0"));
    return true; }
  public static void Scan(){ Rows.Clear(); EnumWindows(new EnumProc(Cb), IntPtr.Zero); }
}
"@
}

function ConvertTo-Mask([string]$spec) {
    $mask = [int64]0
    foreach ($part in $spec -split ',') {
        $part = $part.Trim()
        if ($part -match '^(\d+)-(\d+)$') {
            foreach ($i in [int]$matches[1]..[int]$matches[2]) { $mask = $mask -bor ([int64]1 -shl $i) }
        } elseif ($part -match '^\d+$') {
            $mask = $mask -bor ([int64]1 -shl [int]$part)
        }
    }
    return $mask
}

# 回傳 @{ pid = @{ Title=...; Fore=$true/$false } }
function Get-GameWindowMap {
    [AtWin]::Scan()
    $pids = @(Get-Process SangoOL -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
    $map = @{}
    foreach ($r in [AtWin]::Rows) {
        $f = $r -split "`t"
        $q = [int]$f[0]
        if ($pids -contains $q) { $map[$q] = @{ Title = $f[1]; Fore = ($f[2] -eq '1') } }
    }
    return $map
}

$script:logFile = if ($LogPath) { $LogPath } else {
    Join-Path ([Environment]::GetFolderPath('Desktop')) ('自動調校紀錄_{0}.log' -f (Get-Date -Format 'MMdd'))
}

function Write-Act($msg, $color = 'Gray') {
    $line = '[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $msg
    Write-Host "  $line" -ForegroundColor $color
    try { Add-Content -Path $script:logFile -Value $line -Encoding UTF8 } catch { }
}

# 已載入物件數只來自「持有 Player.log 的那一個實例」，不一定是主力視窗
function Get-LoadedObjects {
    $p = "$env:USERPROFILE\AppData\LocalLow\Userjoy\三國群英傳PC\Player.log"
    if (-not (Test-Path $p)) { return $null }
    try {
        $tail = Get-Content $p -Tail 400 -Encoding UTF8 -ErrorAction Stop
        for ($i = $tail.Count - 1; $i -ge 0; $i--) {
            if ($tail[$i] -match 'Loaded Objects now:\s*(\d+)') { return [int]$matches[1] }
        }
    } catch { }
    return $null
}

# ---------------------------------------------------------------- 主迴圈

$maskP = ConvertTo-Mask $PCores
$maskE = ConvertTo-Mask $ECores

Write-Host ''
Write-Host '  === 三國群英 常駐自動調校 ===' -ForegroundColor Cyan
Write-Host "  CPU        ：$((Get-CimInstance Win32_Processor).Name)" -ForegroundColor DarkGray
Write-Host "  主力視窗   ：$(if($FollowForeground){'自動跟隨前景視窗'}else{$MainTitle})" -ForegroundColor DarkGray
Write-Host "  主力設定   ：核心 $PCores (遮罩 $maskP) + $Priority" -ForegroundColor DarkGray
Write-Host "  其他實例   ：$(if($NoIsolate){'不變動'}else{"核心 $ECores (遮罩 $maskE)"})" -ForegroundColor DarkGray
Write-Host "  檢查間隔   ：$IntervalSec 秒" -ForegroundColor DarkGray
Write-Host "  紀錄檔     ：$script:logFile" -ForegroundColor DarkGray
Write-Host ''
Write-Host '  關掉這個視窗即停止。設定不會自動還原。' -ForegroundColor DarkYellow
Write-Host ''

Write-Act '開始監看' 'Cyan'

$known      = @{}     # pid -> 已套用的設定描述
$mainPid    = 0
$foreStreak = @{}     # pid -> 連續在前景的次數
$lastWarn   = [datetime]::MinValue
$tick       = 0

while ($true) {
    try {
        $tick++
        $map = Get-GameWindowMap
        if ($map.Count -eq 0) {
            if ($tick % 12 -eq 1) { Write-Act '目前沒有遊戲視窗，等待中…' 'DarkGray' }
            Start-Sleep -Seconds $IntervalSec
            continue
        }

        # --- 決定主力視窗 ---
        $newMain = 0
        if ($FollowForeground) {
            $fore = @($map.GetEnumerator() | Where-Object { $_.Value.Fore })
            if ($fore.Count -eq 1) {
                $fp = [int]$fore[0].Key
                $foreStreak[$fp] = [int]$foreStreak[$fp] + 1
                # 連續 3 次都在前景才切換，避免滑過去就改設定
                if ($foreStreak[$fp] -ge 3) { $newMain = $fp }
                foreach ($k in @($foreStreak.Keys)) { if ($k -ne $fp) { $foreStreak[$k] = 0 } }
            }
            if ($newMain -eq 0) { $newMain = $mainPid }
        } else {
            $hit = @($map.GetEnumerator() | Where-Object { $_.Value.Title -like "*$MainTitle*" })
            if ($hit.Count -ge 1) { $newMain = [int]$hit[0].Key }
        }

        if ($newMain -ne 0 -and $newMain -ne $mainPid) {
            $t = $map[$newMain].Title
            if ($mainPid -eq 0) { Write-Act "主力視窗 = pid=$newMain $t" 'Cyan' }
            else { Write-Act "主力視窗換成 pid=$newMain $t（原本 pid=$mainPid 已不在或已切換）" 'Yellow' }
            $mainPid = $newMain
            $known.Remove($mainPid) | Out-Null
        }
        if ($mainPid -ne 0 -and -not $map.ContainsKey($mainPid)) {
            Write-Act "主力視窗 pid=$mainPid 已關閉" 'Yellow'
            $mainPid = 0
        }

        # --- 套用設定（冪等：已經對的就跳過）---
        foreach ($entry in $map.GetEnumerator()) {
            $procId = [int]$entry.Key
            $title  = $entry.Value.Title
            $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
            if (-not $p) { continue }

            $isMain   = ($procId -eq $mainPid)
            $wantMask = if ($isMain) { $maskP } elseif ($NoIsolate) { $null } else { $maskE }
            $wantPri  = if ($isMain) { $Priority } else { 'Normal' }

            $curMask = try { [int64]$p.ProcessorAffinity } catch { -1 }
            $curPri  = try { [string]$p.PriorityClass }    catch { '?' }

            # 讀不到（curMask = -1）代表權限不足，這是提權遊戲 + 非提權腳本的典型情況
            if ($curMask -eq -1 -and -not $isAdmin -and -not $script:warnedPerm) {
                Write-Act "碰不到 pid=$procId（權限不足）— 這個遊戲是提權啟動的" 'Red'
                Write-Act '請關掉本程式，改用「以系統管理員身分執行」重跑，否則調校不會生效' 'Red'
                $script:warnedPerm = $true
            }

            $changed = @()
            if ($null -ne $wantMask -and $curMask -ne $wantMask -and $curMask -ne -1) {
                try { $p.ProcessorAffinity = [IntPtr]$wantMask; $changed += "親和性->$(if($isMain){$PCores}else{$ECores})" }
                catch { Write-Act "pid=$procId 親和性設定失敗：$($_.Exception.Message)" 'Red' }
            }
            if ($curPri -ne $wantPri -and $curPri -ne '?') {
                try { $p.PriorityClass = $wantPri; $changed += "優先權->$wantPri" }
                catch { Write-Act "pid=$procId 優先權設定失敗：$($_.Exception.Message)" 'Red' }
            }
            if ($changed.Count -gt 0) {
                $tag = if ($isMain) { '[主力]' } else { '[背景]' }
                Write-Act "$tag pid=$procId $title  $($changed -join '，')" 'Green'
            }
            $known[$procId] = "$curMask/$curPri"
        }

        # --- 物件數提醒 ---
        if ($tick % 12 -eq 0) {
            $obj = Get-LoadedObjects
            if ($null -ne $obj -and $obj -ge $ObjWarn -and ((Get-Date) - $lastWarn).TotalMinutes -ge 15) {
                Write-Act "已載入物件 $obj 超過門檻 $ObjWarn — 卸載停頓會明顯變長，建議重開客戶端" 'Red'
                Write-Act '（這個數字只來自持有 Player.log 的那一個實例，不一定是主力視窗）' 'DarkGray'
                $lastWarn = Get-Date
            }
        }

        # --- 定期狀態回報 ---
        if ($tick % 60 -eq 0) {
            $obj = Get-LoadedObjects
            $objTxt = if ($null -ne $obj) { "，物件 $obj" } else { '' }
            Write-Act "監看中：$($map.Count) 個實例，主力 pid=$mainPid$objTxt" 'DarkGray'
        }
    }
    catch {
        Write-Act "迴圈發生例外（已忽略，繼續執行）：$($_.Exception.Message)" 'Red'
    }
    Start-Sleep -Seconds $IntervalSec
}
