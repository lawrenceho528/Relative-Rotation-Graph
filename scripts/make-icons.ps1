Add-Type -AssemblyName System.Drawing

$iconDir = Join-Path (Get-Location) "icons"
New-Item -ItemType Directory -Force -Path $iconDir | Out-Null

function New-RggIcon {
  param(
    [int] $Size,
    [string] $Path
  )

  $bitmap = New-Object System.Drawing.Bitmap $Size, $Size
  $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
  $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $scale = $Size / 512.0

  $bg = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml("#182033"))
  $graphics.FillRectangle($bg, 0, 0, $Size, $Size)

  $axisPen = New-Object System.Drawing.Pen ([System.Drawing.ColorTranslator]::FromHtml("#6f7f99"), (18 * $scale))
  $axisPen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
  $axisPen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
  $graphics.DrawLine($axisPen, 104 * $scale, 256 * $scale, 408 * $scale, 256 * $scale)
  $graphics.DrawLine($axisPen, 256 * $scale, 104 * $scale, 256 * $scale, 408 * $scale)

  $greenPen = New-Object System.Drawing.Pen ([System.Drawing.ColorTranslator]::FromHtml("#36c07e"), (28 * $scale))
  $greenPen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
  $greenPen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
  $greenPath = New-Object System.Drawing.Drawing2D.GraphicsPath
  $greenPath.AddBezier(116 * $scale, 146 * $scale, 174 * $scale, 222 * $scale, 238 * $scale, 242 * $scale, 313 * $scale, 220 * $scale)
  $greenPath.AddBezier(313 * $scale, 220 * $scale, 351 * $scale, 209 * $scale, 377 * $scale, 214 * $scale, 395 * $scale, 238 * $scale)
  $graphics.DrawPath($greenPen, $greenPath)

  $bluePen = New-Object System.Drawing.Pen ([System.Drawing.ColorTranslator]::FromHtml("#55a7ff"), (28 * $scale))
  $bluePen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
  $bluePen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
  $bluePath = New-Object System.Drawing.Drawing2D.GraphicsPath
  $bluePath.AddBezier(118 * $scale, 370 * $scale, 181 * $scale, 282 * $scale, 247 * $scale, 259 * $scale, 318 * $scale, 298 * $scale)
  $bluePath.AddBezier(318 * $scale, 298 * $scale, 349 * $scale, 315 * $scale, 376 * $scale, 312 * $scale, 398 * $scale, 289 * $scale)
  $graphics.DrawPath($bluePen, $bluePath)

  $yellow = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml("#d6ae3d"))
  $blue = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml("#55a7ff"))
  $graphics.FillEllipse($blue, 124 * $scale, 338 * $scale, 40 * $scale, 40 * $scale)
  $graphics.FillEllipse($yellow, 302 * $scale, 272 * $scale, 40 * $scale, 40 * $scale)

  $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
  $graphics.Dispose()
  $bitmap.Dispose()
}

New-RggIcon -Size 180 -Path (Join-Path $iconDir "apple-touch-icon.png")
New-RggIcon -Size 192 -Path (Join-Path $iconDir "icon-192.png")
New-RggIcon -Size 512 -Path (Join-Path $iconDir "icon-512.png")
