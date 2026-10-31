<#
    三國神燈 UI 自動化模組（被 launch_game.ps1 dot-source 引用）
    ------------------------------------------------------------------
    控制項對照表 (MFC 對話框 class #32770, 三國神燈 V3.0.0.25)
        1000  Button    啟動遊戲
        1001  Edit      帳號欄
        1005  Edit      遊戲路徑      <- 選完帳號會自動帶出
        1012  Static    狀態列
        1019  ComboBox  遊戲帳號      <- 懶載入, 要先 CB_SHOWDROPDOWN
        1021  Edit      登錄密碼
        1024  Edit      保護密碼
        1025  Button    自動登錄,讀取
        1026  ComboBox  伺服器 (5)
        1027  ComboBox  分流   (2)
        1029  ComboBox  角色   (3)
        1030  Button    進遊戲掛機
        1032  Button    自動重啟
        1033  ComboBox  設置   (20)
    地雷：
      * 提權的實例收不到訊息（UIPI），必須用 RunAsInvoker 啟動
      * 讀文字用 SendMessageW + StringBuilder，不要 ReadProcessMemory
#>

if (-not ('LampUI' -as [type])) {
Add-Type -TypeDefinition @"
using System; using System.Text; using System.Runtime.InteropServices; using System.Collections.Generic;
public class LampUI {
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
  [DllImport("user32.dll")] public static extern int  GetWindowThreadProcessId(IntPtr h, out int pid);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassNameW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetDlgItem(IntPtr h, int id);
  [DllImport("user32.dll")] public static extern IntPtr SendMessageW(IntPtr h, uint m, IntPtr w, IntPtr l);
  [DllImport("user32.dll", CharSet=CharSet.Unicode, EntryPoint="SendMessageW")]
  public static extern IntPtr SendSb(IntPtr h, uint m, IntPtr w, StringBuilder l);
  public delegate bool EnumProc(IntPtr h, IntPtr p);
  public static List<IntPtr> Found = new List<IntPtr>();
  public static int TargetPid = 0;

  public static string Title(IntPtr h){ var s=new StringBuilder(512); GetWindowTextW(h,s,512); return s.ToString(); }
  public static string Cls(IntPtr h){ var s=new StringBuilder(256); GetClassNameW(h,s,256); return s.ToString(); }
  public static string GetText(IntPtr h){ var s=new StringBuilder(1024); SendSb(h,0x000D,(IntPtr)1024,s); return s.ToString(); }
  public static string ItemText(IntPtr h,int i){ var s=new StringBuilder(1024); SendSb(h,0x0148,(IntPtr)i,s); return s.ToString(); }

  public static bool Collect(IntPtr h, IntPtr p){
    int q; GetWindowThreadProcessId(h, out q);
    if (q == TargetPid && IsWindowVisible(h) && Cls(h) == "#32770" && Title(h).Length > 0) Found.Add(h);
    return true;
  }
  public static IntPtr MainWindow(int pid){
    TargetPid = pid; Found.Clear();
    EnumWindows(new EnumProc(Collect), IntPtr.Zero);
    return Found.Count > 0 ? Found[0] : IntPtr.Zero;
  }
}
"@
}

$script:CB_GETCOUNT=0x0146; $script:CB_GETCURSEL=0x0147; $script:CB_GETLBTEXT=0x0148
$script:CB_SETCURSEL=0x014E; $script:CB_SHOWDROPDOWN=0x014F; $script:WM_COMMAND=0x0111
$script:CBN_SELCHANGE=1;     $script:BN_CLICKED=0


function Wait-LampWindow {
    param([int]$ProcessId, [int]$TimeoutSec = 25)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $h = [LampUI]::MainWindow($ProcessId)
        if ($h -ne [IntPtr]::Zero) { Start-Sleep -Milliseconds 600; return $h }
        Start-Sleep -Milliseconds 400
    }
    return [IntPtr]::Zero
}


# 帳號下拉是懶載入：先展開才有項目
function Get-LampAccounts {
    param([IntPtr]$Main)
    $cbo = [LampUI]::GetDlgItem($Main, 1019)
    if ($cbo -eq [IntPtr]::Zero) { return @() }
    [void][LampUI]::SendMessageW($cbo, $CB_SHOWDROPDOWN, [IntPtr]1, [IntPtr]::Zero)
    Start-Sleep -Milliseconds 500
    $n = [int][LampUI]::SendMessageW($cbo, $CB_GETCOUNT, [IntPtr]::Zero, [IntPtr]::Zero)
    $list = @()
    for ($i = 0; $i -lt $n; $i++) { $list += [LampUI]::ItemText($cbo, $i) }
    [void][LampUI]::SendMessageW($cbo, $CB_SHOWDROPDOWN, [IntPtr]0, [IntPtr]::Zero)
    return $list
}


# CB_SETCURSEL 不會觸發程式的處理常式，要自己補 CBN_SELCHANGE 通知
function Set-LampCombo {
    param([IntPtr]$Main, [int]$CtrlId, [int]$Index)
    $cbo = [LampUI]::GetDlgItem($Main, $CtrlId)
    if ($cbo -eq [IntPtr]::Zero) { return $false }
    [void][LampUI]::SendMessageW($cbo, $CB_SETCURSEL, [IntPtr]$Index, [IntPtr]::Zero)
    $wp = [IntPtr](($CBN_SELCHANGE -shl 16) -bor $CtrlId)
    [void][LampUI]::SendMessageW($Main, $WM_COMMAND, $wp, $cbo)
    Start-Sleep -Milliseconds 400
    return ([int][LampUI]::SendMessageW($cbo, $CB_GETCURSEL, [IntPtr]::Zero, [IntPtr]::Zero)) -eq $Index
}


function Invoke-LampButton {
    param([IntPtr]$Main, [int]$CtrlId)
    $btn = [LampUI]::GetDlgItem($Main, $CtrlId)
    if ($btn -eq [IntPtr]::Zero) { return $false }
    $wp = [IntPtr](($BN_CLICKED -shl 16) -bor $CtrlId)
    [void][LampUI]::SendMessageW($Main, $WM_COMMAND, $wp, $btn)
    return $true
}


function Get-LampField {
    param([IntPtr]$Main, [int]$CtrlId)
    $h = [LampUI]::GetDlgItem($Main, $CtrlId)
    if ($h -eq [IntPtr]::Zero) { return '' }
    return [LampUI]::GetText($h)
}


# 用 RunAsInvoker 啟動一個實例，回傳新行程的 pid（失敗回 0）。
# 不提權是 UI 自動化的前提：提權的實例會被 UIPI 擋掉。
function Start-LampProcess {
    param([string]$ExePath, [switch]$AsAdmin)
    $prev = $env:__COMPAT_LAYER
    if (-not $AsAdmin) { $env:__COMPAT_LAYER = 'RunAsInvoker' }
    try {
        $before = @(Get-Process SanOLLamp -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
        Start-Process -FilePath $ExePath -WorkingDirectory (Split-Path $ExePath -Parent) | Out-Null
        $deadline = (Get-Date).AddSeconds(20)
        while ((Get-Date) -lt $deadline) {
            $new = @(Get-Process SanOLLamp -ErrorAction SilentlyContinue | Where-Object { $before -notcontains $_.Id })
            if ($new.Count -gt 0) { return $new[0].Id }
            Start-Sleep -Milliseconds 300
        }
        return 0
    } finally {
        if ($null -eq $prev) { Remove-Item Env:\__COMPAT_LAYER -ErrorAction SilentlyContinue }
        else { $env:__COMPAT_LAYER = $prev }
    }
}


# 帳號清單等同 <exe 目錄>\config\ 底下的子資料夾（已驗證與神燈下拉選單完全一致）。
# 讀資料夾不用開暫時實例，所以 UI 載入是瞬間的。
function Get-LampAccountsFromDisk {
    param([string]$ExePath)
    $dir = Join-Path (Split-Path $ExePath -Parent) 'config'
    if (-not (Test-Path $dir)) { return @() }
    return @(Get-ChildItem $dir -Directory -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name)
}


# 回傳某帳號實際存在的設置編號，例如 @(1,2,4,6)。
# 神燈的「設置」下拉永遠是 20 項，但沒有對應 SettingN.ini 的那些是空的，
# 選下去等於套用一份空設定 —— 所以 UI 只列真的存在的。
# 換一台電腦時幫使用者先猜路徑。只掃固定磁碟的幾個常見位置，
# 不做全碟搜尋（會慢到不能用）。猜不到就回空字串，讓使用者自己瀏覽。
function Find-LampExe {
    $patterns = @()
    foreach ($d in [IO.DriveInfo]::GetDrives()) {
        if ($d.DriveType -ne 'Fixed' -or -not $d.IsReady) { continue }
        $r = $d.RootDirectory.FullName.TrimEnd('\')
        $patterns += "$r\Game\*\SanOLLamp.exe"
        $patterns += "$r\*\SanOLLamp.exe"
        $patterns += "$r\*\*\SanOLLamp.exe"
    }
    $desktop = [Environment]::GetFolderPath('Desktop')
    $patterns += "$desktop\*\SanOLLamp.exe"
    $patterns += "$desktop\*\*\SanOLLamp.exe"

    foreach ($p in $patterns) {
        $hit = @(Get-ChildItem $p -File -ErrorAction SilentlyContinue) | Select-Object -First 1
        # config\ 存在才算數，否則只是個沒設定過的空安裝
        if ($hit -and (Test-Path (Join-Path $hit.DirectoryName 'config'))) { return $hit.FullName }
    }
    foreach ($p in $patterns) {
        $hit = @(Get-ChildItem $p -File -ErrorAction SilentlyContinue) | Select-Object -First 1
        if ($hit) { return $hit.FullName }
    }
    return ''
}


# 建立／更新一個指向啟動批次檔、帶自訂圖示的捷徑。
# 為什麼需要：.cmd 檔在檔案總管一律是通用批次檔圖示，Windows 不給換。
# 捷徑(.lnk)才能帶圖示，而且 .lnk 存的是絕對路徑，所以資料夾一搬就失效 ——
# 因此每次啟動都重寫一次，等於自動修正。
function New-LampShortcut {
    param(
        [Parameter(Mandatory)][string]$LinkPath,
        [Parameter(Mandatory)][string]$PackageDir
    )
    $target = Join-Path $PackageDir '啟動神燈多開.cmd'
    if (-not (Test-Path $target)) { return $false }   # 不是從發佈包執行，跳過
    try {
        $sh = New-Object -ComObject WScript.Shell
        $s  = $sh.CreateShortcut($LinkPath)
        $s.TargetPath       = $target
        $s.WorkingDirectory = $PackageDir
        $s.Description      = '三國神燈 多開啟動器'
        $s.WindowStyle      = 7          # 最小化，避免閃一個黑色主控台視窗
        $ico = Join-Path $PackageDir 'lamp.ico'
        if (Test-Path $ico) { $s.IconLocation = "$ico,0" }
        $s.Save()
        return $true
    } catch {
        return $false
    }
}


function Get-LampAccountSettings {
    param([string]$ExePath, [string]$Account)
    $dir = Join-Path (Join-Path (Split-Path $ExePath -Parent) 'config') $Account
    if (-not (Test-Path $dir)) { return @() }
    return @(Get-ChildItem $dir -Filter 'Setting*.ini' -ErrorAction SilentlyContinue |
             ForEach-Object { if ($_.Name -match '^Setting(\d+)\.ini$') { [int]$matches[1] } } |
             Sort-Object)
}
