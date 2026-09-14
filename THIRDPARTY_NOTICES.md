# Сторонние компоненты

GHub сам по себе не содержит чужих бинарников — они скачиваются отдельно
(см. README «Внешние бинарники») и не коммитятся в репозиторий.

| Компонент | Лицензия | Источник |
|---|---|---|
| PresentMon (presentmon.exe) | MIT | https://github.com/GameTechDev/PresentMon |
| LibreHardwareMonitor (LibreHardwareMonitorLib.dll, исходник tools/cputemp.cs) | MPL-2.0 | https://github.com/LibreHardwareMonitor/LibreHardwareMonitor |
| PawnIO (thirdparty/PawnIO_setup.exe, опционально) | проприетарная, см. сайт вендора | https://pawnio.eu |

Перед распространением собранного `dist/` проверь условия лицензий выше
(MIT — сохранить копирайт, MPL-2.0 — открыть изменения самой библиотеки
при модификации, PawnIO — только по условиям вендора).
