# Сторонние компоненты

GHub сам по себе не содержит чужих бинарников — они скачиваются отдельно
(см. README «Внешние бинарники») и не коммитятся в репозиторий.

| Компонент | Лицензия | Источник |
|---|---|---|
| PresentMon (presentmon.exe) | MIT | https://github.com/GameTechDev/PresentMon (релизный zip включает v2.5.1, пин и sha256 — в `build_release.ps1`) |
| LibreHardwareMonitor (исходник tools/cputemp.cs, LHM 0.9.5) | MPL-2.0 | https://github.com/LibreHardwareMonitor/LibreHardwareMonitor (релизный zip включает self-contained `tools/cputemp.exe`, .NET на машине пользователя не нужен) |
| PawnIO (thirdparty/PawnIO_setup.exe, опционально) | проприетарная, см. сайт вендора | https://pawnio.eu |

Перед распространением собранного `dist/` проверь условия лицензий выше
(MIT — сохранить копирайт, MPL-2.0 — открыть изменения самой библиотеки
при модификации, PawnIO — только по условиям вендора).
