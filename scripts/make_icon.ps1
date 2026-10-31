<#
    產生「三國神燈 多開啟動器」的圖示。
    畫一張 256x256，再縮成各尺寸，手動組出多尺寸 .ico（內嵌 PNG，Vista 以後支援）。

    用法：
        .\make_icon.ps1                      # 輸出到本資料夾
        .\make_icon.ps1 -OutDir ..\dist\...  # 輸出到指定資料夾
        .\make_icon.ps1 -Preview             # 另外輸出 lamp_preview.png 方便看
#>
[CmdletBinding()]
param(
    [string]$OutDir = $PSScriptRoot,
    [switch]$Preview
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

function New-RoundedPath([single]$x, [single]$y, [single]$w, [single]$h, [single]$r) {
    $p = New-Object Drawing.Drawing2D.GraphicsPath
    $d = $r * 2
    $p.AddArc($x,           $y,          $d, $d, 180, 90)
    $p.AddArc($x + $w - $d, $y,          $d, $d, 270, 90)
    $p.AddArc($x + $w - $d, $y + $h - $d,$d, $d,   0, 90)
    $p.AddArc($x,           $y + $h - $d,$d, $d,  90, 90)
    $p.CloseFigure()
    return $p
}

function New-Master {
    $bmp = New-Object Drawing.Bitmap(256, 256, [Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g   = [Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = 'AntiAlias'
    $g.Clear([Drawing.Color]::Transparent)

    $gold     = [Drawing.Color]::FromArgb(255, 242, 196,  83)
    $goldDark = [Drawing.Color]::FromArgb(255, 176, 118,  28)

    # --- 底：深藍圓角方塊 ---
    $bg = New-RoundedPath 6 6 244 244 54
    $bgBrush = New-Object Drawing.Drawing2D.LinearGradientBrush(
        (New-Object Drawing.Point(0, 0)), (New-Object Drawing.Point(0, 256)),
        [Drawing.Color]::FromArgb(255, 38, 56, 94),
        [Drawing.Color]::FromArgb(255, 11, 17, 33))
    $g.FillPath($bgBrush, $bg)
    $edge = New-Object Drawing.Pen([Drawing.Color]::FromArgb(70, 255, 255, 255), 3)
    $g.DrawPath($edge, $bg)

    # --- 火焰：燈嘴正上方 ---
    $flame = New-Object Drawing.Drawing2D.GraphicsPath
    $flame.AddBezier(52, 120,  34, 100,  48, 86,  54, 62)
    $flame.AddBezier(54,  62,  66,  88,  76, 102, 62, 120)
    $flame.CloseFigure()
    $flameBrush = New-Object Drawing.Drawing2D.LinearGradientBrush(
        (New-Object Drawing.Point(30, 58)), (New-Object Drawing.Point(30, 124)),
        [Drawing.Color]::FromArgb(255, 255, 240, 170),
        [Drawing.Color]::FromArgb(255, 240, 130,  40))
    $g.FillPath($flameBrush, $flame)

    # 火焰暈光
    $halo = New-Object Drawing.Drawing2D.GraphicsPath
    $halo.AddEllipse(26, 56, 62, 76)
    $haloBrush = New-Object Drawing.Drawing2D.PathGradientBrush($halo)
    $haloBrush.CenterColor    = [Drawing.Color]::FromArgb(90, 255, 200, 90)
    $haloBrush.SurroundColors = @([Drawing.Color]::FromArgb(0, 255, 200, 90))
    $g.FillPath($haloBrush, $halo)

    # --- 提把：右側粗弧 ---
    $handlePen = New-Object Drawing.Pen($goldDark, 15)
    $handlePen.StartCap = 'Round'; $handlePen.EndCap = 'Round'
    $g.DrawArc($handlePen, 168, 126, 64, 66, -80, 250)

    # --- 燈嘴：左側尖嘴 ---
    $spout = New-Object Drawing.Drawing2D.GraphicsPath
    $spout.AddPolygon(@(
        (New-Object Drawing.PointF(92, 158)),
        (New-Object Drawing.PointF(30, 126)),
        (New-Object Drawing.PointF(22, 142)),
        (New-Object Drawing.PointF(86, 186))
    ))
    $spoutBrush = New-Object Drawing.SolidBrush($goldDark)
    $g.FillPath($spoutBrush, $spout)

    # --- 燈身 ---
    $body = New-Object Drawing.Drawing2D.GraphicsPath
    $body.AddEllipse(64, 138, 130, 76)
    $bodyBrush = New-Object Drawing.Drawing2D.LinearGradientBrush(
        (New-Object Drawing.Point(64, 138)), (New-Object Drawing.Point(64, 214)),
        $gold, $goldDark)
    $g.FillPath($bodyBrush, $body)

    # 燈身高光
    $shineBrush = New-Object Drawing.SolidBrush([Drawing.Color]::FromArgb(110, 255, 255, 255))
    $g.FillEllipse($shineBrush, 86, 150, 52, 20)

    # --- 燈蓋與頂珠 ---
    $g.FillEllipse($bodyBrush, 108, 120, 48, 26)
    $knobBrush = New-Object Drawing.SolidBrush($gold)
    $g.FillEllipse($knobBrush, 122, 104, 20, 20)

    # --- 底座 ---
    $baseBrush = New-Object Drawing.SolidBrush($goldDark)
    $basePath  = New-RoundedPath 92 206 76 16 8
    $g.FillPath($baseBrush, $basePath)

    $g.Dispose()
    return $bmp
}

function Resize-Bitmap($src, [int]$size) {
    $dst = New-Object Drawing.Bitmap($size, $size, [Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g   = [Drawing.Graphics]::FromImage($dst)
    $g.InterpolationMode = 'HighQualityBicubic'
    $g.PixelOffsetMode   = 'HighQuality'
    $g.SmoothingMode     = 'AntiAlias'
    $g.Clear([Drawing.Color]::Transparent)
    $g.DrawImage($src, (New-Object Drawing.Rectangle(0, 0, $size, $size)))
    $g.Dispose()
    return $dst
}

# 把點陣圖轉成 ICO 內嵌用的 32bpp DIB
# （BITMAPINFOHEADER + BGRA 由下而上 + 全 0 的 AND 遮罩）
#
# 為什麼不走別條路：
#   * PNG-in-ICO：Explorer 讀得懂，但 System.Drawing.Icon 解不開，
#     WinForms 的 $form.Icon 會拿不到圖。
#   * Bitmap.GetHicon() + Icon.Save()：資料合法，但色彩會被量化成 4bpp，
#     金色燈身會變成色塊。
function ConvertTo-IcoDib($bm) {
    $w = $bm.Width; $h = $bm.Height
    $rect = New-Object Drawing.Rectangle(0, 0, $w, $h)
    $data = $bm.LockBits($rect, [Drawing.Imaging.ImageLockMode]::ReadOnly,
                         [Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $stride = $data.Stride
    $buf = New-Object byte[] ($stride * $h)
    [Runtime.InteropServices.Marshal]::Copy($data.Scan0, $buf, 0, $buf.Length)
    $bm.UnlockBits($data)

    $ms = New-Object IO.MemoryStream
    $bw = New-Object IO.BinaryWriter($ms)
    $bw.Write([uint32]40)        # biSize
    $bw.Write([int32]$w)         # biWidth
    $bw.Write([int32]($h * 2))   # biHeight = 影像 + 遮罩
    $bw.Write([uint16]1)         # biPlanes
    $bw.Write([uint16]32)        # biBitCount
    $bw.Write([uint32]0)         # biCompression = BI_RGB
    $bw.Write([uint32]($w * $h * 4))
    $bw.Write([int32]0); $bw.Write([int32]0)
    $bw.Write([uint32]0); $bw.Write([uint32]0)

    # 影像由下而上；記憶體內已是 BGRA，與 DIB 所需順序一致
    for ($y = $h - 1; $y -ge 0; $y--) { $bw.Write($buf, $y * $stride, $w * 4) }

    # AND 遮罩：32bpp 有 alpha 所以全 0，但每列仍要補齊到 4 位元組
    $maskRow = [int]([Math]::Floor(($w + 31) / 32) * 4)
    $zero = New-Object byte[] $maskRow
    for ($y = 0; $y -lt $h; $y++) { $bw.Write($zero, 0, $maskRow) }

    $bw.Flush()
    $bytes = $ms.ToArray()
    $bw.Close(); $ms.Dispose()
    # 前置逗號：避免 PowerShell 把 byte[] 展開成 Object[]，
    # 那會讓 BinaryWriter.Write() 挑到錯誤的多載，每張只寫 1 個 byte
    return ,$bytes
}

# ICONDIR(6) + ICONDIRENTRY(16 x N) + 各張影像資料
function Save-Ico($master, [int[]]$sizes, [string]$path) {
    $imgs = @()
    foreach ($s in $sizes) {
        $bm = Resize-Bitmap $master $s
        $imgs += ,@{ size = $s; data = [byte[]](ConvertTo-IcoDib $bm) }
        $bm.Dispose()
    }

    $fs = [IO.File]::Open($path, [IO.FileMode]::Create)
    $bw = New-Object IO.BinaryWriter($fs)
    $bw.Write([uint16]0)                 # reserved
    $bw.Write([uint16]1)                 # type = icon
    $bw.Write([uint16]$imgs.Count)

    $offset = 6 + 16 * $imgs.Count
    foreach ($p in $imgs) {
        $len = ([byte[]]$p.data).Length
        $dim = if ($p.size -ge 256) { 0 } else { $p.size }
        $bw.Write([byte]$dim)            # width（256 要寫 0）
        $bw.Write([byte]$dim)            # height
        $bw.Write([byte]0)               # palette
        $bw.Write([byte]0)               # reserved
        $bw.Write([uint16]1)             # planes
        $bw.Write([uint16]32)            # bpp，與 DIB 內容一致
        $bw.Write([uint32]$len)
        $bw.Write([uint32]$offset)
        $offset += $len
    }
    foreach ($p in $imgs) { $bw.Write([byte[]]$p.data) }
    $bw.Flush(); $bw.Close(); $fs.Close()
}

if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }
$master  = New-Master
$icoPath = Join-Path $OutDir 'lamp.ico'
Save-Ico $master @(256, 64, 48, 32, 16) $icoPath
Write-Host "已產生 $icoPath ($((Get-Item $icoPath).Length) bytes)"

if ($Preview) {
    $pv = Join-Path $OutDir 'lamp_preview.png'
    $master.Save($pv, [Drawing.Imaging.ImageFormat]::Png)
    Write-Host "預覽圖 $pv"
}
$master.Dispose()
