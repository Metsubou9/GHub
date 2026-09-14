# Сборка tools/cputemp.exe (температура CPU через LibreHardwareMonitor).
# Запуск из корня проекта:
#   powershell -ExecutionPolicy Bypass -File tools/build_cputemp.ps1
# Требует установленный .NET SDK (dotnet --version).
# Скачивает LibreHardwareMonitorLib с NuGet, бинарники кладутся в tools/
# (они в .gitignore и в репо не коммитятся).

$ErrorActionPreference = "Stop"

if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
  throw "Не найден 'dotnet'. Установи .NET SDK: https://dotnet.microsoft.com/download"
}
$sdks = & dotnet --list-sdks 2>$null
if (-not $sdks) {
  throw "Найден только .NET runtime, а нужен .NET SDK. Установи SDK: https://dotnet.microsoft.com/download"
}

$root = Split-Path -Parent $PSScriptRoot
$buildDir = Join-Path $root ".cputemp_build"

if (Test-Path -LiteralPath $buildDir) {
  Remove-Item -LiteralPath $buildDir -Recurse -Force
}
New-Item -ItemType Directory -Path $buildDir | Out-Null

& dotnet new console -n cputemp_build -o $buildDir -f net8.0 --no-restore | Out-Null
if ($LASTEXITCODE -ne 0) { throw "dotnet new failed" }
& dotnet add "$buildDir/cputemp_build.csproj" package LibreHardwareMonitorLib --version 0.9.5 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "dotnet add LibreHardwareMonitorLib failed" }
& dotnet add "$buildDir/cputemp_build.csproj" package System.ServiceProcess.ServiceController --version 8.0.0 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "dotnet add ServiceController failed" }

Copy-Item -LiteralPath (Join-Path $root "tools/cputemp.cs") -Destination (Join-Path $buildDir "Program.cs") -Force

# Self-contained single-file: на машине пользователя .NET ставить не нужно.
# (LHM 0.9.5 кладет реализацию только в runtimes/, поэтому обычный
# framework-dependent publish молча выпускает exe без LibreHardwareMonitorLib.dll.)
& dotnet publish "$buildDir/cputemp_build.csproj" -c Release -r win-x64 --self-contained `
  -p:AssemblyName=cputemp -p:PublishSingleFile=true -o (Join-Path $root "tools")
if ($LASTEXITCODE -ne 0) { throw "dotnet publish failed" }

foreach ($need in @("cputemp.exe")) {
  if (-not (Test-Path -LiteralPath (Join-Path $root "tools/$need"))) {
    Write-Host "Содержимое tools/ после publish:"
    Get-ChildItem -LiteralPath (Join-Path $root "tools") -File | ForEach-Object { Write-Host ("  " + $_.Name) }
    throw "Нет tools/$need после сборки cputemp"
  }
}

Remove-Item -LiteralPath $buildDir -Recurse -Force

Write-Host "Done: tools/cputemp.exe (+ LibreHardwareMonitorLib.dll)"
Write-Host "Проверка: tools/cputemp.exe --diag"
