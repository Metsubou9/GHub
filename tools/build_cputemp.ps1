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

& dotnet new console -n cputemp_build -o $buildDir --no-restore | Out-Null
if ($LASTEXITCODE -ne 0) { throw "dotnet new failed" }
& dotnet add "$buildDir/cputemp_build.csproj" package LibreHardwareMonitorLib | Out-Null
if ($LASTEXITCODE -ne 0) { throw "dotnet add LibreHardwareMonitorLib failed" }
& dotnet add "$buildDir/cputemp_build.csproj" package System.ServiceProcess.ServiceController | Out-Null
if ($LASTEXITCODE -ne 0) { throw "dotnet add ServiceController failed" }

Copy-Item -LiteralPath (Join-Path $root "tools/cputemp.cs") -Destination (Join-Path $buildDir "Program.cs") -Force

& dotnet publish "$buildDir/cputemp_build.csproj" -c Release -o (Join-Path $root "tools")
if ($LASTEXITCODE -ne 0) { throw "dotnet publish failed" }

Remove-Item -LiteralPath $buildDir -Recurse -Force

Write-Host "Done: tools/cputemp.exe (+ LibreHardwareMonitorLib.dll)"
Write-Host "Проверка: tools/cputemp.exe --diag"
