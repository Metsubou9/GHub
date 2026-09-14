# GHub

Игровой хаб для Windows: оверлей, мониторинг (CPU/GPU/RAM/FPS/пинг), дашборд,
профили оптимизации и запись сессий в SQLite. Запуск — `python main.py`, позже `GHub.exe`.

![Windows](https://img.shields.io/badge/OS-Windows-blue) ![Python](https://img.shields.io/badge/python-3.10%2B-green) ![License](https://img.shields.io/badge/license-MIT-lightgrey)

## Возможности

- Оверлей поверх игр (FPS, задержка кадра, пинг, CPU/GPU) + трей с управлением
- FPS через PresentMon v2 (без инжекта, безопасно для античита)
- Пинг до сервера текущей катки (автопоиск IP) с fallback-хостами
- Профили `singleplayer` / `multiplayer` в `config/games.yaml` — новая игра = 3 строки
- Оптимизатор процесса (приоритет, affinity) — `config/optimizer.yaml`
- Дашборд в браузере (`http://127.0.0.1:8765`), история сессий в SQLite
- Работает в degraded mode: без админа/бинарников показывает `--` вместо метрик

## Быстрый старт

```powershell
# 1. Python 3.10+, затем:
pip install -r requirements.txt
python main.py
# Дашборд: http://127.0.0.1:8765
# Выход: трей -> Выход / Ctrl+C
```

Для FPS и температуры CPU нужны внешние бинарники (ниже). Без них всё
запускается, но FPS/темп покажут `--`.

## Внешние бинарники (не хранятся в репо)

| Что | Куда положить | Где взять |
|---|---|---|
| `presentmon.exe` (FPS) | корень проекта | [PresentMon Releases](https://github.com/GameTechDev/PresentMon) |
| `tools/cputemp.exe` + `LibreHardwareMonitorLib.dll` (темп CPU) | `tools/` | `powershell -ExecutionPolicy Bypass -File tools/build_cputemp.ps1` |
| `thirdparty/PawnIO_setup.exe` (опционально) | `thirdparty/` | сайт вендора |

Требуют запуск от администратора (ETW для FPS, драйвер для сенсоров CPU).
Логи при проблемах: `%TEMP%\ghub_presentmon_err.log`, `%TEMP%\ghub_cpu.log`.

## Сборка GHub.exe

```powershell
powershell -ExecutionPolicy Bypass -File build_exe.ps1
# Результат: dist/GHub.exe (+ presentmon.exe и config рядом, если они были)
```

## Конфигурация

- `config/games.yaml` — игры, профили `singleplayer`/`multiplayer`, пинг-хосты, порт дашборда
- `config/optimizer.yaml` — профили оптимизации процесса
- `config/*.local.yaml` — локальные переопределения (в git не коммитятся)

## Структура

```
main.py               точка входа (оверлей, трей, дашборд, цикл сессий)
core/                 детектор игр, конфиг, SQLite-хранилище
modules/monitoring/   коллектор Windows, FPS (PresentMon), пинг, поиск IP катки
modules/optimizer/    профили и применение приоритета/affinity
modules/input_tester/ тест инпута
ui/                   оверлей, трей, окно ввода
dashboard/            веб-дашборд (server.py + html)
tools/cputemp.cs      исходник хелпера темп CPU (сборка: tools/build_cputemp.ps1)
```

## Лицензии

Код — MIT (`LICENSE`). Сторонние бинарники — см. `THIRDPARTY_NOTICES.md`.
