<#
    三國群英 單一視窗卡頓 — 監控與調校
    ------------------------------------------------------------------
    用途：打 BOSS 卡的當下，量出到底是什麼在卡；並直接做「鎖大核 + 提高
          優先權」的 A/B 比較。

    為什麼要提權：遊戲是以系統管理員身分啟動的，一般權限讀不到它的執行緒
    資訊，也不能設定親和性／優先權。本腳本會自動要求提權。

    用法：
        # 列出所有遊戲視窗
        .\lamp_perf.ps1 -List

        # 監控 60 秒（打 BOSS 的時候跑）
        .\lamp_perf.ps1 -Title 反˙冰沁 -Seconds 60

        # A/B：先量 30 秒 → 套用調校 → 再量 30 秒 → 印比較
        .\lamp_perf.ps1 -Title 反˙冰沁 -AB -Seconds 30

        # 只套用調校（不監控）
        .\lamp_perf.ps1 -Title 反˙冰沁 -Tune

        # 還原
        .\lamp_perf.ps1 -Title 反˙冰沁 -Revert

    關鍵指標：
        主執行緒%  — Unity 主執行緒佔「單顆核心」的百分比。
                     接近 100 就是瓶頸（主執行緒是單執行緒，再多核也沒用）。
        GPU3D%     — 若很低而主執行緒很高，就確定是 CPU 側的問題。
#>
[CmdletBinding()]
param(
    [string] $Title,
    [int]    $ProcId,
    [int]    $Seconds = 60,
    [switch] $List,
    [switch] $Tune,
    [switch] $Revert,
    [switch] $AB,
    [switch] $IsolateOthers,
    [string] $PCores   = '0-5',
    [string] $ECores   = '6-13',
    [ValidateSet('Normal','AboveNormal','High')]
    [string] $Priority = 'AboveNormal',
    [string] $Csv
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

# ---------------------------------------------------------------- 提權

$isAdmin = ([Security.Principal.WindowsPrincipal] `
            [Security.Principal.WindowsIdentity]::GetCurrent()
           ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host ''
    Write-Host '  需要系統管理員權限（遊戲是提權啟動的，否則讀不到執行緒）' -ForegroundColor Yellow
    Write-Host '  正在要求提權…' -ForegroundColor Yellow
    $argLine = @('-NoProfile','-ExecutionPolicy','Bypass','-NoExit','-File', "`"$PSCommandPath`"")
    foreach ($kv in $PSBoundParameters.GetEnumerator()) {
        if ($kv.Value -is [switch]) { if ($kv.Value) { $argLine += "-$($kv.Key)" } }
        else { $argLine += "-$($kv.Key)"; $argLine += "`"$($kv.Value)`"" }
    }
    Start-Process powershell -Verb RunAs -ArgumentList $argLine
    return
}

# ---------------------------------------------------------------- 工具

if (-not ('WinEnum' -as [type])) {
Add-Type -TypeDefinition @"
using System; using System.Text; using System.Runtime.InteropServices; using System.Collections.Generic;
public class WinEnum {
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
  [DllImport("user32.dll")] public static extern int  GetWindowThreadProcessId(IntPtr h, out int pid);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  public delegate bool EnumProc(IntPtr h, IntPtr p);
  public static List<string> Rows = new List<string>();
  static bool Cb(IntPtr h, IntPtr p){
    if(!IsWindowVisible(h)) return true;
    var s = new StringBuilder(512); GetWindowTextW(h, s, 512);
    if (s.Length == 0) return true;
    int q; GetWindowThreadProcessId(h, out q);
    Rows.Add(q + "\t" + s.ToString());
    return true; }
  public static void Scan(){ Rows.Clear(); EnumWindows(new EnumProc(Cb), IntPtr.Zero); }
}
"@
}

function Get-GameWindows {
    [WinEnum]::Scan()
    $pids = @(Get-Process SangoOL -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
    $map = @{}
    foreach ($r in [WinEnum]::Rows) {
        $f = $r -split "`t"
        if ($pids -contains [int]$f[0]) { $map[[int]$f[0]] = $f[1] }
    }
    return $map
}

# 把 "0-5" 或 "0,1,2" 轉成親和性遮罩
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

function Resolve-Target {
    $map = Get-GameWindows
    if ($ProcId -gt 0) {
        if (-not (Get-Process -Id $ProcId -ErrorAction SilentlyContinue)) { throw "找不到 pid=$ProcId" }
        return $ProcId
    }
    if (-not $Title) { throw '請用 -Title <視窗標題關鍵字> 或 -ProcId <pid> 指定目標，或用 -List 查看' }
    $hit = @($map.GetEnumerator() | Where-Object { $_.Value -like "*$Title*" })
    if ($hit.Count -eq 0) { throw "沒有視窗標題包含「$Title」。用 -List 看有哪些。" }
    if ($hit.Count -gt 1) {
        Write-Host '  符合的視窗不只一個：' -ForegroundColor Yellow
        $hit | ForEach-Object { Write-Host "    pid=$($_.Key)  $($_.Value)" }
        throw '請給更精確的關鍵字'
    }
    Write-Host "  目標：pid=$($hit[0].Key)  $($hit[0].Value)" -ForegroundColor Cyan
    return [int]$hit[0].Key
}

# ---------------------------------------------------------------- 量測

# 回傳：行程核心用量、最忙執行緒佔單核%、前三忙執行緒
function Measure-Threads([int]$procId, [double]$interval) {
    $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if (-not $p) { return $null }
    $before = @{}
    foreach ($t in $p.Threads) {
        try { $before[$t.Id] = $t.TotalProcessorTime.TotalSeconds } catch { }
    }
    $procBefore = $p.TotalProcessorTime.TotalSeconds
    Start-Sleep -Milliseconds ([int]($interval * 1000))
    $p.Refresh()
    $deltas = @()
    foreach ($t in $p.Threads) {
        try {
            if ($before.ContainsKey($t.Id)) {
                $d = $t.TotalProcessorTime.TotalSeconds - $before[$t.Id]
                if ($d -gt 0) { $deltas += [pscustomobject]@{ Id = $t.Id; Pct = 100 * $d / $interval } }
            }
        } catch { }
    }
    $deltas = @($deltas | Sort-Object Pct -Descending)
    return [pscustomobject]@{
        ProcCores = [Math]::Round(($p.TotalProcessorTime.TotalSeconds - $procBefore) / $interval, 2)
        MainPct   = if ($deltas.Count -gt 0) { [Math]::Round($deltas[0].Pct, 1) } else { 0 }
        Top3      = ($deltas | Select-Object -First 3 | ForEach-Object { "$($_.Id):$([Math]::Round($_.Pct))%" }) -join ' '
        Private   = [Math]::Round($p.PrivateMemorySize64 / 1MB)
        Threads   = $p.Threads.Count
        Responding= $p.Responding
    }
}

function Measure-Gpu([int]$procId) {
    $d = 0.0; $u = 0.0
    try {
        foreach ($c in (Get-Counter "\GPU Process Memory(pid_${procId}*)\Dedicated Usage" -ErrorAction Stop).CounterSamples) { $d += $c.CookedValue }
    } catch { }
    try {
        foreach ($c in (Get-Counter "\GPU Engine(pid_${procId}*engtype_3D)\Utilization Percentage" -ErrorAction Stop).CounterSamples) { $u += $c.CookedValue }
    } catch { }
    return [pscustomobject]@{ VramMB = [Math]::Round($d / 1MB); Gpu3D = [Math]::Round($u, 1) }
}

function Get-CoreSnapshot {
    $out = @()
    try {
        $s = (Get-Counter '\Processor(*)\% Processor Time' -ErrorAction Stop).CounterSamples |
             Where-Object { $_.InstanceName -ne '_total' }
        foreach ($x in ($s | Sort-Object { [int]$_.InstanceName })) {
            $out += [Math]::Round($x.CookedValue)
        }
    } catch { }
    return $out
}

function Invoke-Monitor([int]$procId, [int]$secs, [string]$label) {
    Write-Host ''
    Write-Host "  === $label（$secs 秒）===" -ForegroundColor Cyan
    Write-Host '  時間      主執行緒%  行程核心  GPU3D%  VRAM  私有MB  回應   前三忙執行緒'
    $rows = @()
    $t0 = Get-Date
    $tick = 0
    while (((Get-Date) - $t0).TotalSeconds -lt $secs) {
        $m = Measure-Threads $procId 1.0
        if (-not $m) { Write-Host '  行程已結束'; break }
        $tick++
        if ($tick % 4 -eq 1) { $script:lastGpu = Measure-Gpu $procId }
        $g = $script:lastGpu
        $row = [pscustomobject]@{
            時間       = (Get-Date -Format 'HH:mm:ss')
            階段       = $label
            主執行緒Pct = $m.MainPct
            行程核心    = $m.ProcCores
            GPU3D      = $g.Gpu3D
            VRAM_MB    = $g.VramMB
            私有MB     = $m.Private
            回應       = $m.Responding
            前三執行緒  = $m.Top3
        }
        $rows += $row
        $color = if ($m.MainPct -ge 90) { 'Red' } elseif ($m.MainPct -ge 70) { 'Yellow' } else { 'Gray' }
        Write-Host ("  {0}  {1,8}  {2,8}  {3,6}  {4,5}  {5,6}  {6,-6} {7}" -f `
            $row.時間, $row.主執行緒Pct, $row.行程核心, $row.GPU3D, $row.VRAM_MB, $row.私有MB, $row.回應, $row.前三執行緒) -ForegroundColor $color
    }
    return $rows
}

function Show-Summary($rows, $label) {
    if (-not $rows -or $rows.Count -eq 0) { return }
    $m = $rows | Measure-Object 主執行緒Pct -Average -Maximum
    $c = $rows | Measure-Object 行程核心 -Average -Maximum
    $g = $rows | Measure-Object GPU3D -Average -Maximum
    $bad = @($rows | Where-Object { $_.主執行緒Pct -ge 90 }).Count
    $nr  = @($rows | Where-Object { -not $_.回應 }).Count
    [pscustomobject]@{
        階段           = $label
        樣本數         = $rows.Count
        '主執行緒平均%' = [Math]::Round($m.Average,1)
        '主執行緒尖峰%' = [Math]::Round($m.Maximum,1)
        '主執行緒爆滿次數' = $bad
        '行程平均核心'  = [Math]::Round($c.Average,2)
        'GPU3D平均%'   = [Math]::Round($g.Average,1)
        '無回應次數'    = $nr
    }
}

# ---------------------------------------------------------------- 調校

function Invoke-Tune([int]$procId) {
    $p = Get-Process -Id $procId
    $maskP = ConvertTo-Mask $PCores
    Write-Host ''
    Write-Host '  === 套用調校 ===' -ForegroundColor Green
    try {
        $p.ProcessorAffinity = [IntPtr]$maskP
        Write-Host "    親和性 -> 核心 $PCores (遮罩 $maskP)" -ForegroundColor Green
    } catch { Write-Host "    親和性設定失敗：$($_.Exception.Message)" -ForegroundColor Red }
    try {
        $p.PriorityClass = $Priority
        Write-Host "    優先權 -> $Priority" -ForegroundColor Green
    } catch { Write-Host "    優先權設定失敗：$($_.Exception.Message)" -ForegroundColor Red }

    if ($IsolateOthers) {
        $maskE = ConvertTo-Mask $ECores
        $n = 0
        foreach ($o in Get-Process SangoOL) {
            if ($o.Id -eq $procId) { continue }
            try { $o.ProcessorAffinity = [IntPtr]$maskE; $n++ } catch { }
        }
        Write-Host "    其他 $n 個實例 -> 核心 $ECores" -ForegroundColor Green
    }
}

function Invoke-Revert([int]$procId) {
    $all = ConvertTo-Mask "0-$([int]$env:NUMBER_OF_PROCESSORS - 1)"
    Write-Host ''
    Write-Host '  === 還原 ===' -ForegroundColor Yellow
    foreach ($o in Get-Process SangoOL) {
        try {
            $o.ProcessorAffinity = [IntPtr]$all
            $o.PriorityClass = 'Normal'
        } catch { }
    }
    Write-Host "    全部 $(@(Get-Process SangoOL).Count) 個實例已還原為：全核心 + Normal 優先權" -ForegroundColor Yellow
}

# ---------------------------------------------------------------- 主流程

Write-Host ''
Write-Host '  三國群英 卡頓監控／調校' -ForegroundColor Cyan
Write-Host "  CPU：$((Get-CimInstance Win32_Processor).Name)" -ForegroundColor DarkGray
Write-Host "  邏輯核心 $env:NUMBER_OF_PROCESSORS    大核設定 $PCores    小核設定 $ECores" -ForegroundColor DarkGray

if ($List) {
    $map = Get-GameWindows
    Write-Host ''
    Write-Host "  找到 $($map.Count) 個遊戲視窗：" -ForegroundColor Cyan
    foreach ($k in ($map.Keys | Sort-Object)) {
        $p = Get-Process -Id $k -ErrorAction SilentlyContinue
        $aff = try { [int64]$p.ProcessorAffinity } catch { '讀不到' }
        $pri = try { $p.PriorityClass } catch { '讀不到' }
        Write-Host ("    pid={0,-6} {1,-28} 優先權={2,-12} 親和性={3}" -f $k, $map[$k], $pri, $aff)
    }
    Write-Host ''
    return
}

$target = Resolve-Target
$script:lastGpu = Measure-Gpu $target

if ($Revert) { Invoke-Revert $target; Write-Host ''; return }

if ($AB) {
    $before = Invoke-Monitor $target $Seconds '調校前'
    Invoke-Tune $target
    Start-Sleep -Seconds 3
    $after  = Invoke-Monitor $target $Seconds '調校後'

    Write-Host ''
    Write-Host '  ================= A/B 比較 =================' -ForegroundColor Cyan
    @( (Show-Summary $before '調校前'), (Show-Summary $after '調校後') ) |
        Format-Table -AutoSize | Out-String | Write-Host

    $b = Show-Summary $before '前'; $a = Show-Summary $after '後'
    if ($b -and $a) {
        $d = $b.'主執行緒平均%' - $a.'主執行緒平均%'
        if ($d -gt 5)      { Write-Host "  主執行緒負載下降 $([Math]::Round($d,1)) 個百分點 —— 調校有效" -ForegroundColor Green }
        elseif ($d -lt -5) { Write-Host "  主執行緒負載反而上升 $([Math]::Round(-$d,1)) 個百分點 —— 建議 -Revert" -ForegroundColor Red }
        else               { Write-Host '  主執行緒負載沒有明顯變化 —— 瓶頸不在核心排程' -ForegroundColor Yellow }
        Write-Host '  （最終還是以你自己看畫面順不順為準，數字只是佐證）' -ForegroundColor DarkGray
    }
    $rows = @($before) + @($after)
} elseif ($Tune) {
    Invoke-Tune $target
    Write-Host ''
    return
} else {
    $rows = Invoke-Monitor $target $Seconds '監控'
    Write-Host ''
    Show-Summary $rows '監控' | Format-Table -AutoSize | Out-String | Write-Host
}

if (-not $Csv) {
    $Csv = Join-Path ([Environment]::GetFolderPath('Desktop')) ("卡頓紀錄_{0}.csv" -f (Get-Date -Format 'MMdd_HHmm'))
}
if ($rows -and $rows.Count -gt 0) {
    $rows | Export-Csv -Path $Csv -NoTypeInformation -Encoding UTF8
    Write-Host "  紀錄已存檔：$Csv" -ForegroundColor Cyan
}

Write-Host ''
Write-Host '  怎麼看：' -ForegroundColor DarkGray
Write-Host '    主執行緒% 接近 100 且 GPU3D% 很低  -> CPU 單執行緒瓶頸（符合目前的推論）' -ForegroundColor DarkGray
Write-Host '    主執行緒% 不高但畫面還是卡          -> 瓶頸在別處（網路、磁碟、或 GPU 驅動）' -ForegroundColor DarkGray
Write-Host '    GPU3D% 很高                        -> 這次真的是 GPU 瓶頸，降解析度才有用' -ForegroundColor DarkGray
Write-Host ''
