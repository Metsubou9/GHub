# Сборка отдельной приложухи. Запуск из корня проекта:
#   powershell -ExecutionPolicy Bypass -File build_exe.ps1
# Внешние бинарники (presentmon.exe, tools/cputemp.exe) в репо НЕ хранятся,
# см. README "Внешние бинарники". Без них сборка пройдет, но FPS/темп CPU
# будут недоступны (degraded mode). Положи их рядом перед сборкой, чтобы
# они попали в dist/.
pip install -r requirements.txt
python -m PyInstaller --noconfirm --onefile --windowed --name GHub `
  --add-data "config;config" --add-data "dashboard;dashboard" `
  --add-data "core/schema.sql;core" --add-data "tools;tools" `
  main.py
New-Item -ItemType Directory -Path "dist/tools", "dist/thirdparty" -Force | Out-Null
if (Test-Path -LiteralPath "presentmon.exe") {
  Copy-Item -LiteralPath "presentmon.exe" -Destination "dist/presentmon.exe" -Force
} else {
  Write-Warning "presentmon.exe не найден в корне - FPS будет недоступен (см. README)"
}
if (Test-Path -LiteralPath "tools/cputemp.exe") {
  Copy-Item -Path "tools/*.exe", "tools/*.dll" -Destination "dist/tools/" -Force
} else {
  Write-Warning "tools/cputemp.exe не найден - темп CPU будет недоступна (см. tools/build_cputemp.ps1)"
}
if (Test-Path -LiteralPath "thirdparty/PawnIO_setup.exe") {
  Copy-Item -LiteralPath "thirdparty/PawnIO_setup.exe" -Destination "dist/thirdparty/PawnIO_setup.exe" -Force
}
if (-not (Test-Path -LiteralPath "dist/config/games.yaml")) {
  New-Item -ItemType Directory -Path "dist/config" -Force | Out-Null
  Copy-Item -LiteralPath "config/games.yaml" -Destination "dist/config/games.yaml"
}
Write-Host "Done: dist/GHub.exe (+ presentmon.exe and config/games.yaml nearby)"
