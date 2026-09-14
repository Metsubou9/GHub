# GHub portable release: собирает dist/GHub-vX.Y-portable.zip,
# в котором уже всё для всех метрик (FPS, темп CPU) - распаковал и запустил.
# Запуск из корня проекта:
#   powershell -ExecutionPolicy Bypass -File build_release.ps1
# Требует: Python 3.10+, .NET SDK (для tools/cputemp.exe), интернет
# (для докачки PresentMon, если его нет рядом).
$ErrorActionPreference = "Stop"

$PRESENTMON_URL = "https://github.com/GameTechDev/PresentMon/releases/download/v2.5.1/PresentMon-2.5.1-x64.exe"
$PRESENTMON_SHA256 = "9bec3083069f58f911e6a512f4806db51a27bd096103087bc1d05ef54c80a191"

$root = $PSScriptRoot
Set-Location -LiteralPath $root

$ver = Select-String -LiteralPath (Join-Path $root "main.py") -Pattern '^VERSION = "(.+)"' |
  Select-Object -First 1 | ForEach-Object { $_.Matches.Groups[1].Value }
if (-not $ver) { throw "Не нашел VERSION в main.py" }

# 1. PresentMon рядом (FPS). Совпадает с пином по sha256 - иначе докачать.
$pm = Join-Path $root "presentmon.exe"
$needDl = $true
if (Test-Path -LiteralPath $pm) {
  $h = (Get-FileHash -LiteralPath $pm -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($h -eq $PRESENTMON_SHA256) { $needDl = $false; Write-Host "presentmon.exe ok (v2.5.1)" }
  else { Write-Warning "presentmon.exe чужой (sha не сошелся) - качаю v2.5.1" }
}
if ($needDl) {
  Write-Host "Качаю PresentMon v2.5.1..."
  Invoke-WebRequest -Uri $PRESENTMON_URL -OutFile $pm
  $h = (Get-FileHash -LiteralPath $pm -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($h -ne $PRESENTMON_SHA256) { throw "sha256 PresentMon не сошелся: $h" }
}

# 2. Хелпер темп CPU. Нет - собрать из исходника (нужен dotnet SDK).
if (-not (Test-Path -LiteralPath (Join-Path $root "tools/cputemp.exe"))) {
  Write-Host "Собираю tools/cputemp.exe..."
  & powershell -ExecutionPolicy Bypass -File (Join-Path $root "tools/build_cputemp.ps1")
  if ($LASTEXITCODE -ne 0) { throw "tools/build_cputemp.ps1 failed" }
}
if (-not (Test-Path -LiteralPath (Join-Path $root "tools/cputemp.exe"))) {
  throw "Нет tools/cputemp.exe после сборки (см. tools/build_cputemp.ps1)"
}

# 3. Сам GHub.exe
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
python -m PyInstaller --noconfirm --onefile --windowed --name GHub `
  --add-data "config;config" --add-data "dashboard;dashboard" `
  --add-data "core/schema.sql;core" --add-data "tools;tools" `
  main.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

# 4. Portable-папка
$port = Join-Path $root "dist/GHub-portable"
if (Test-Path -LiteralPath $port) { Remove-Item -LiteralPath $port -Recurse -Force }
New-Item -ItemType Directory -Path $port, "$port/tools", "$port/config" | Out-Null
Copy-Item -LiteralPath "dist/GHub.exe", "presentmon.exe" -Destination $port -Force
Copy-Item -Path "tools/*.exe", "tools/*.dll" -Destination "$port/tools/" -Force
Copy-Item -LiteralPath "config/games.yaml", "config/optimizer.yaml" -Destination "$port/config/" -Force
Copy-Item -LiteralPath "README.md", "LICENSE", "THIRDPARTY_NOTICES.md" -Destination $port -Force

# 5. Zip
$zip = Join-Path $root "dist/GHub-v$ver-portable.zip"
if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
Compress-Archive -Path (Join-Path $port "*") -DestinationPath $zip
Write-Host "Готово: $zip"
Get-ChildItem -LiteralPath $port -Recurse -File | ForEach-Object {
  Write-Host ("  " + $_.FullName.Substring($port.Length + 1) + "  (" + [math]::Round($_.Length / 1MB, 1) + " MB)")
}
Write-Host "Пользователю: распаковать, запустить GHub.exe от администратора (иначе нет FPS и темп CPU)."
