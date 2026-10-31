<#
    三國神燈 多開啟動器 — 圖形介面
    ------------------------------------------------------------------
    * 可以選神燈執行檔路徑（預設 C:\Game\SanOLLampTW_Unity\SanOLLamp.exe）
    * 每個帳號一列：打勾要不要啟動、各自挑設置1~20，由上到下依序啟動
    * 設置下拉只列該帳號真的存在的 SettingN.ini
    * 預設只把帳號與設置選好就停住，不按「啟動遊戲」

    注意：神燈會把選擇寫回 config\<帳號>\login.ini，所以在這裡挑設置
          等於改掉該帳號記住的設置。

    設定存在 %LOCALAPPDATA%\SanOLLampLauncher\settings.json。
    用 launch_gui.cmd 雙擊執行。
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'lamp_ui.ps1')

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$DefaultExe   = 'C:\Game\SanOLLampTW_Unity\SanOLLamp.exe'
$SettingsDir  = Join-Path $env:LOCALAPPDATA 'SanOLLampLauncher'
$SettingsFile = Join-Path $SettingsDir 'settings.json'
$KeepOriginal = '原本設置'


function Get-Settings {
    $s = @{ exe=$DefaultExe; accounts=@(); delay=3; autoLogin=$false; start=$false }
    if (Test-Path $SettingsFile) {
        try {
            $j = Get-Content $SettingsFile -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($j.exe)                 { $s.exe       = [string]$j.exe }
            if ($null -ne $j.delay)     { $s.delay     = [double]$j.delay }
            if ($null -ne $j.autoLogin) { $s.autoLogin = [bool]$j.autoLogin }
            if ($null -ne $j.start)     { $s.start     = [bool]$j.start }
            # 舊格式是字串陣列，新格式是 {name, setting}
            if ($j.accounts) {
                $s.accounts = @(foreach ($a in $j.accounts) {
                    if ($a -is [string]) { @{ name = $a; setting = 0 } }
                    else                 { @{ name = [string]$a.name; setting = [int]$a.setting } }
                })
            }
        } catch { }
    }
    return $s
}

function Save-Settings($exe, $accounts, $delay, $autoLogin, $start) {
    try {
        if (-not (Test-Path $SettingsDir)) { New-Item -ItemType Directory -Path $SettingsDir -Force | Out-Null }
        [pscustomobject]@{
            exe       = $exe
            accounts  = @($accounts | ForEach-Object { [pscustomobject]@{ name = $_.name; setting = $_.setting } })
            count     = @($accounts).Count
            delay     = $delay
            autoLogin = $autoLogin
            start     = $start
            savedAt   = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
        } | ConvertTo-Json -Depth 4 | Out-File $SettingsFile -Encoding utf8
    } catch { }
}

$cfg = Get-Settings

# 第一次在這台電腦執行（沒有設定檔）且預設路徑不存在時，自動找一下
if (-not (Test-Path $SettingsFile) -and -not (Test-Path $cfg.exe)) {
    $found = Find-LampExe
    if ($found) { $cfg.exe = $found }
}

# ---------------------------------------------------------------- 介面

$form                 = New-Object Windows.Forms.Form
$form.Text            = '三國神燈 多開啟動器'
$form.Size            = New-Object Drawing.Size(700, 820)
$form.StartPosition   = 'CenterScreen'
$form.FormBorderStyle = 'FixedSingle'
$form.MaximizeBox     = $false
$form.Font            = New-Object Drawing.Font('Microsoft JhengHei UI', 9)

$icoPath = Join-Path $PSScriptRoot 'lamp.ico'
if (Test-Path $icoPath) {
    try { $form.Icon = New-Object Drawing.Icon($icoPath) } catch { }
}

function New-Label($text, $x, $y, $w, $h) {
    $l = New-Object Windows.Forms.Label
    $l.Text = $text; $l.Location = New-Object Drawing.Point($x, $y)
    $l.Size = New-Object Drawing.Size($w, $h)
    return $l
}
function New-Button($text, $x, $y, $w, $h) {
    $b = New-Object Windows.Forms.Button
    $b.Text = $text; $b.Location = New-Object Drawing.Point($x, $y)
    $b.Size = New-Object Drawing.Size($w, $h)
    return $b
}

# --- 執行檔路徑 ---
$form.Controls.Add((New-Label '神燈執行檔' 12 14 100 20))
$txtExe          = New-Object Windows.Forms.TextBox
$txtExe.Location = New-Object Drawing.Point(12, 36)
$txtExe.Size     = New-Object Drawing.Size(560, 25)
$txtExe.Text     = $cfg.exe
$form.Controls.Add($txtExe)

$btnBrowse = New-Button '瀏覽…' 580 35 95 27
$form.Controls.Add($btnBrowse)

$lblPath = New-Label '' 12 66 663 20
$lblPath.ForeColor = [Drawing.Color]::Gray
$form.Controls.Add($lblPath)

# --- 帳號表格 ---
$form.Controls.Add((New-Label '打勾要啟動的帳號，各自挑設置；由上到下依序啟動' 12 94 450 20))

$grid = New-Object Windows.Forms.DataGridView
$grid.Location              = New-Object Drawing.Point(12, 116)
$grid.Size                  = New-Object Drawing.Size(520, 340)
$grid.AllowUserToAddRows    = $false
$grid.AllowUserToDeleteRows = $false
$grid.AllowUserToResizeRows = $false
$grid.AllowUserToOrderColumns = $false
$grid.RowHeadersVisible     = $false
$grid.SelectionMode         = 'FullRowSelect'
$grid.MultiSelect           = $false
$grid.EditMode              = 'EditOnEnter'
$grid.BackgroundColor       = [Drawing.Color]::White
$grid.BorderStyle           = 'FixedSingle'
$grid.ColumnHeadersHeightSizeMode = 'DisableResizing'

$colChk = New-Object Windows.Forms.DataGridViewCheckBoxColumn
$colChk.HeaderText = '啟動'; $colChk.Name = 'chk'; $colChk.Width = 46
$colChk.SortMode = 'NotSortable'

$colAcc = New-Object Windows.Forms.DataGridViewTextBoxColumn
$colAcc.HeaderText = '帳號'; $colAcc.Name = 'acct'; $colAcc.Width = 170
$colAcc.ReadOnly = $true; $colAcc.SortMode = 'NotSortable'

$colSet = New-Object Windows.Forms.DataGridViewComboBoxColumn
$colSet.HeaderText = '設置'; $colSet.Name = 'setting'; $colSet.Width = 130
$colSet.FlatStyle = 'Flat'; $colSet.SortMode = 'NotSortable'

$colInfo = New-Object Windows.Forms.DataGridViewTextBoxColumn
$colInfo.HeaderText = '可用'; $colInfo.Name = 'info'; $colInfo.Width = 150
$colInfo.ReadOnly = $true; $colInfo.SortMode = 'NotSortable'
$colInfo.DefaultCellStyle.ForeColor = [Drawing.Color]::Gray

# 逐一加入：AddRange 的 params 陣列在 PowerShell 下轉型會失敗
foreach ($c in @($colChk, $colAcc, $colSet, $colInfo)) { [void]$grid.Columns.Add($c) }
$form.Controls.Add($grid)

# 下拉值不在清單中時 WinForms 會丟 DataError，吞掉以免跳例外視窗
$grid.Add_DataError({ param($s, $e) $e.ThrowException = $false })

$btnAll  = New-Button '全選'     542 116 133 28
$btnNone = New-Button '全不選'   542 150 133 28
$btnUp   = New-Button '▲ 上移'  542 192 133 28
$btnDown = New-Button '▼ 下移'  542 226 133 28
$form.Controls.AddRange(@($btnAll, $btnNone, $btnUp, $btnDown))

$lblSel = New-Label '已勾選 0 個' 542 268 133 20
$lblSel.ForeColor = [Drawing.Color]::DimGray
$form.Controls.Add($lblSel)

# --- 選項 ---
$form.Controls.Add((New-Label '間隔秒數' 12 472 60 20))
$numDelay          = New-Object Windows.Forms.NumericUpDown
$numDelay.Location = New-Object Drawing.Point(78, 469)
$numDelay.Size     = New-Object Drawing.Size(55, 25)
$numDelay.Minimum  = 0; $numDelay.Maximum = 60
$numDelay.DecimalPlaces = 1; $numDelay.Increment = 0.5
$numDelay.Value    = [decimal]$cfg.delay
$form.Controls.Add($numDelay)

$lblNote = New-Label '設置選「原本設置」就完全不動那個帳號的設定' 155 472 400 20
$lblNote.ForeColor = [Drawing.Color]::Gray
$form.Controls.Add($lblNote)

$chkAutoLogin          = New-Object Windows.Forms.CheckBox
$chkAutoLogin.Text     = '選好後按「自動登錄,讀取」'
$chkAutoLogin.Location = New-Object Drawing.Point(12, 502)
$chkAutoLogin.Size     = New-Object Drawing.Size(300, 24)
$chkAutoLogin.Checked  = $cfg.autoLogin
$form.Controls.Add($chkAutoLogin)

$chkStart           = New-Object Windows.Forms.CheckBox
$chkStart.Text      = '選好後按「啟動遊戲」'
$chkStart.Location  = New-Object Drawing.Point(12, 528)
$chkStart.Size      = New-Object Drawing.Size(300, 24)
$chkStart.Checked   = $cfg.start
$chkStart.ForeColor = [Drawing.Color]::Firebrick
$form.Controls.Add($chkStart)

$lblStartHint = New-Label '不勾的話只把帳號與設置選好，啟動遊戲由你自己按' 32 552 450 20
$lblStartHint.ForeColor = [Drawing.Color]::Gray
$form.Controls.Add($lblStartHint)

# --- 動作 ---
$btnGo = New-Button '開始啟動' 12 582 200 38
$btnGo.Font = New-Object Drawing.Font('Microsoft JhengHei UI', 10, [Drawing.FontStyle]::Bold)
$form.Controls.Add($btnGo)

$btnShortcut = New-Button '建立桌面捷徑' 240 582 160 38
$form.Controls.Add($btnShortcut)

$btnClose = New-Button '關閉' 510 582 165 38
$form.Controls.Add($btnClose)

$txtLog            = New-Object Windows.Forms.TextBox
$txtLog.Location   = New-Object Drawing.Point(12, 630)
$txtLog.Size       = New-Object Drawing.Size(663, 142)
$txtLog.Multiline  = $true
$txtLog.ReadOnly   = $true
$txtLog.ScrollBars = 'Vertical'
$txtLog.BackColor  = [Drawing.Color]::White
$txtLog.Font       = New-Object Drawing.Font('Consolas', 9)
$form.Controls.Add($txtLog)


# ---------------------------------------------------------------- 行為

function Write-Log($msg) {
    $txtLog.AppendText(('[{0}] {1}{2}' -f (Get-Date -Format 'HH:mm:ss'), $msg, [Environment]::NewLine))
    $txtLog.SelectionStart = $txtLog.TextLength
    $txtLog.ScrollToCaret()
    [Windows.Forms.Application]::DoEvents()
}

function Update-SelCount {
    $grid.EndEdit() | Out-Null
    $n = 0
    foreach ($r in $grid.Rows) { if ($r.Cells['chk'].Value -eq $true) { $n++ } }
    $lblSel.Text = "已勾選 $n 個"
}

function Add-AccountRow($exe, $name, $checked, $setting) {
    $avail = @(Get-LampAccountSettings -ExePath $exe -Account $name)
    $i = $grid.Rows.Add()
    $row = $grid.Rows[$i]
    $row.Cells['chk'].Value  = [bool]$checked
    $row.Cells['acct'].Value = $name

    $cell = $row.Cells['setting']
    [void]$cell.Items.Add($KeepOriginal)
    foreach ($n in $avail) { [void]$cell.Items.Add("設置$n") }

    $want = if ($setting -ge 1) { "設置$setting" } else { $KeepOriginal }
    $cell.Value = if ($cell.Items.Contains($want)) { $want } else { $KeepOriginal }

    $row.Cells['info'].Value = if ($avail.Count -gt 0) { "設置 $($avail -join ',')" } else { '此帳號沒有設置檔' }
    if ($avail.Count -eq 0) { $cell.ReadOnly = $true }
}

function Reload-Accounts {
    $grid.Rows.Clear()
    $exe = $txtExe.Text.Trim()
    if (-not (Test-Path $exe)) {
        $lblPath.Text = '找不到執行檔'
        $lblPath.ForeColor = [Drawing.Color]::Firebrick
        $btnGo.Enabled = $false; Update-SelCount; return
    }
    $all = @(Get-LampAccountsFromDisk -ExePath $exe)
    if ($all.Count -eq 0) {
        $lblPath.Text = '執行檔有效，但旁邊的 config\ 讀不到任何帳號資料夾'
        $lblPath.ForeColor = [Drawing.Color]::Firebrick
        $btnGo.Enabled = $false; Update-SelCount; return
    }

    # 上次勾選的排前面並維持順序，其餘照原順序接在後面
    $savedNames = @($cfg.accounts | ForEach-Object { $_.name } | Where-Object { $all -contains $_ })
    foreach ($n in $savedNames) {
        $s = ($cfg.accounts | Where-Object { $_.name -eq $n } | Select-Object -First 1).setting
        Add-AccountRow $exe $n $true $s
    }
    foreach ($n in $all) {
        if ($savedNames -notcontains $n) { Add-AccountRow $exe $n $false 0 }
    }

    $lblPath.Text = "config\ 找到 $($all.Count) 個帳號"
    $lblPath.ForeColor = [Drawing.Color]::Gray
    $btnGo.Enabled = $true
    Update-SelCount
}

function Move-GridRow($delta) {
    $grid.EndEdit() | Out-Null
    if (-not $grid.CurrentRow) { return }
    $i = $grid.CurrentRow.Index
    $j = $i + $delta
    if ($j -lt 0 -or $j -ge $grid.Rows.Count) { return }
    $row = $grid.Rows[$i]
    $grid.Rows.RemoveAt($i)
    $grid.Rows.Insert($j, $row)
    $grid.ClearSelection()
    $grid.Rows[$j].Selected = $true
    $grid.CurrentCell = $grid.Rows[$j].Cells['acct']
}

function Set-AllChecks($value) {
    $grid.EndEdit() | Out-Null
    foreach ($r in $grid.Rows) { $r.Cells['chk'].Value = $value }
    $grid.Refresh()
    Update-SelCount
}

$btnBrowse.Add_Click({
    $dlg = New-Object Windows.Forms.OpenFileDialog
    $dlg.Filter = '神燈執行檔 (SanOLLamp.exe)|SanOLLamp.exe|所有執行檔 (*.exe)|*.exe'
    $dlg.Title  = '選擇神燈執行檔'
    if (Test-Path $txtExe.Text) { $dlg.InitialDirectory = Split-Path $txtExe.Text -Parent }
    if ($dlg.ShowDialog() -eq 'OK') { $txtExe.Text = $dlg.FileName; Reload-Accounts }
})

$txtExe.Add_Leave({ Reload-Accounts })
$btnAll.Add_Click({  Set-AllChecks $true })
$btnNone.Add_Click({ Set-AllChecks $false })
$btnUp.Add_Click({   Move-GridRow -1 })
$btnDown.Add_Click({ Move-GridRow  1 })
$grid.Add_CurrentCellDirtyStateChanged({
    if ($grid.IsCurrentCellDirty) { $grid.CommitEdit([Windows.Forms.DataGridViewDataErrorContexts]::Commit) }
})
$grid.Add_CellValueChanged({ param($s, $e) if ($e.ColumnIndex -eq 0) { Update-SelCount } })
$btnShortcut.Add_Click({
    $lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) '三國神燈 多開啟動器.lnk'
    if (New-LampShortcut -LinkPath $lnk -PackageDir $PSScriptRoot) {
        Write-Log "已在桌面建立捷徑：$lnk"
        [void][Windows.Forms.MessageBox]::Show("已在桌面建立捷徑。", '完成')
    } else {
        [void][Windows.Forms.MessageBox]::Show(
            "建立失敗。`n`n這個功能只在發佈包裡有效（要和「啟動神燈多開.cmd」放在同一個資料夾）。",
            '無法建立')
    }
})

$btnClose.Add_Click({ $form.Close() })

$btnGo.Add_Click({
    $grid.EndEdit() | Out-Null
    $exe = $txtExe.Text.Trim()
    if (-not (Test-Path $exe)) { [void][Windows.Forms.MessageBox]::Show('找不到執行檔。', '錯誤'); return }

    $picked = @()
    foreach ($r in $grid.Rows) {
        if ($r.Cells['chk'].Value -ne $true) { continue }
        $sv = [string]$r.Cells['setting'].Value
        $num = 0
        if ($sv -match '^設置(\d+)$') { $num = [int]$matches[1] }
        $picked += @{ name = [string]$r.Cells['acct'].Value; setting = $num }
    }
    if ($picked.Count -eq 0) { [void][Windows.Forms.MessageBox]::Show('請至少勾選一個帳號。', '沒有選擇'); return }

    $delay   = [double]$numDelay.Value
    $doLogin = $chkAutoLogin.Checked
    $doStart = $chkStart.Checked

    if ($doStart) {
        $lines = ($picked | ForEach-Object { "  $($_.name)  $(if($_.setting -ge 1){"設置$($_.setting)"}else{'原本設置'})" }) -join "`n"
        $msg = "將依序啟動 $($picked.Count) 個，並且會按下「啟動遊戲」。`n`n$lines`n`n確定要繼續嗎？"
        if ([Windows.Forms.MessageBox]::Show($msg, '確認', 'YesNo', 'Warning') -ne 'Yes') { return }
    }

    Save-Settings $exe $picked $delay $doLogin $doStart

    $btnGo.Enabled = $false; $btnClose.Enabled = $false
    $txtLog.Clear()
    Write-Log "開始：$($picked.Count) 個帳號，間隔 $delay 秒"

    $ok = 0; $bad = @()
    for ($i = 0; $i -lt $picked.Count; $i++) {
        $acct = $picked[$i].name
        $want = [int]$picked[$i].setting
        $desc = if ($want -ge 1) { "設置$want" } else { '原本設置' }
        Write-Log ("[{0}/{1}] {2} ({3}) — 啟動中…" -f ($i+1), $picked.Count, $acct, $desc)

        $procId = Start-LampProcess -ExePath $exe
        if ($procId -eq 0) { Write-Log '        啟動失敗'; $bad += $acct; continue }

        $h = Wait-LampWindow -ProcessId $procId
        if ($h -eq [IntPtr]::Zero) { Write-Log "        pid=$procId 找不到視窗"; $bad += $acct; continue }

        $list = Get-LampAccounts -Main $h
        $idx  = [Array]::IndexOf($list, $acct)
        if ($idx -lt 0) { Write-Log "        '$acct' 不在神燈清單中"; $bad += $acct; continue }
        if (-not (Set-LampCombo -Main $h -CtrlId 1019 -Index $idx)) {
            Write-Log '        選帳號失敗'; $bad += $acct; continue
        }
        Start-Sleep -Milliseconds 800

        $path = Get-LampField -Main $h -CtrlId 1005
        if ([string]::IsNullOrWhiteSpace($path)) {
            Write-Log '        帳號選了但路徑沒帶出來，中止這個視窗'; $bad += $acct; continue
        }
        Write-Log "        pid=$procId 帳號已選，路徑=$path"

        if ($want -ge 1 -and $want -le 20) {
            if (Set-LampCombo -Main $h -CtrlId 1033 -Index ($want - 1)) { Write-Log "        設置 -> 設置$want" }
            else { Write-Log "        設置$want 設定失敗（繼續）" }
        }
        if ($doLogin) {
            [void](Invoke-LampButton -Main $h -CtrlId 1025)
            Write-Log '        已按「自動登錄,讀取」'
            Start-Sleep -Milliseconds 1200
        }
        if ($doStart) {
            [void](Invoke-LampButton -Main $h -CtrlId 1000)
            Write-Log '        已按「啟動遊戲」'
        }
        $ok++

        if ($i -lt $picked.Count - 1 -and $delay -gt 0) {
            Start-Sleep -Seconds $delay
            [Windows.Forms.Application]::DoEvents()
        }
    }

    Write-Log "完成：$ok / $($picked.Count) 個"
    if ($bad.Count -gt 0) { Write-Log "有問題的：$($bad -join ', ')" }
    $btnGo.Enabled = $true; $btnClose.Enabled = $true
})

# 在發佈包資料夾裡留一個帶圖示的捷徑，讓使用者有漂亮的東西可以雙擊／釘選。
# 每次啟動都重寫，資料夾搬家後會自動修正。從原始碼資料夾執行時會自動略過。
[void](New-LampShortcut -LinkPath (Join-Path $PSScriptRoot '三國神燈 多開啟動器.lnk') `
                        -PackageDir $PSScriptRoot)

Reload-Accounts
Write-Log '就緒。勾選帳號、挑設置後按「開始啟動」。'
[void]$form.ShowDialog()
