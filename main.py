"""GHub entry: отдельная приложуха (python main.py -> позже GHub.exe)."""
import os
import sys
import threading
import time
import tkinter
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config_loader import load_games_config, load_optimizer_config, save_games_config
from modules.optimizer.profiles import get_optimizer
from core.game_detector import entry_for, find_game, ping_hosts_for, settings_for
from core.storage import connect, start_session, end_session, insert_sample
from core.collector_abstract import Sample
from modules.monitoring.collector_win import MonitoringCollectorWin
from modules.monitoring.ping import PingTracker
from modules.monitoring.fps import FpsTracker
from modules.monitoring.match_server import find_match_ip
from ui.overlay import Overlay
from ui.tray import TrayController
from ui.input_window import create_input_window
from dashboard.server import DashboardServer

VERSION = "0.16"


def fmt(s: Sample, game: str | None, entry: dict | None,
        fps_note: str = "", frame_ms: float | None = None,
        match_ip: str | None = None) -> str:
    f = lambda v, u="": ("--" if v is None else f"{v}{u}")
    parts = [game or "idle"]
    parts.append(f"FPS {f(s.fps)}" if s.fps is not None
                 else f"FPS -- ({fps_note})" if fps_note else "FPS --")
    if entry and entry.get("frame_ms") and frame_ms is not None:
        parts.append(f"FRAME {frame_ms}ms")
    if game is not None and (entry is None or entry.get("net", "static") != "off"):
        net = f"PING {f(s.ping_ms,'ms')} loss {f(s.loss_pct,'%')}"
        if match_ip:
            net += " (match)"
        elif entry and entry.get("net") == "match":
            net += " (lobby)"
        parts.append(net)
    parts.append(f"CPU {f(s.cpu_pct,'%')} {f(s.cpu_temp,'C')}")
    parts.append(f"GPU {f(s.gpu_temp,'C')} {f(s.gpu_pct,'%')}")
    return " | ".join(parts)


def notify(title: str, text: str) -> None:
    """Потокобезопасное всплывающее уведомление Windows."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x40 | 0x10000)
    except Exception:
        print(f"[{title}] {text}")


def main():
    cfg = load_games_config()
    interval = cfg.get("defaults", {}).get("sample_interval_ms", 1000) / 1000
    match_scan = cfg.get("defaults", {}).get("match_scan_interval_ms", 10000) / 1000
    con = connect()
    collector = MonitoringCollectorWin()
    overlay = Overlay()
    overlay.start()
    overlay.update(f"GHub v{VERSION}: ожидание игры...")
    quit_event = threading.Event()
    dash = DashboardServer(port=cfg.get("defaults", {}).get("dashboard_port", 8765))
    dash.start()
    optimizer = get_optimizer()
    current_opt_profile = "default"

    import yaml

    def select_prof(name):
        nonlocal current_opt_profile
        current_opt_profile = name
        notify("GHub", f"Выбран профиль оптимизатора: {name}")
        print(f"[optimizer] выбран профиль: {name}")

    def apply_now():
        # Берём игру из детектора (игнорирует GHub оверлей)
        game_name, proc_name = find_game(cfg)
        if game_name and proc_name:
            try:
                opt_cfg_local = load_optimizer_config()
                profile = opt_cfg_local.get("profiles", {}).get(current_opt_profile, {})
                if profile:
                    target_proc = proc_name.get("name", game_name) if isinstance(proc_name, dict) else proc_name
                    optimizer.apply_profile(target_proc, profile)
                    print(f"[optimizer] применено сейчас к {game_name} ({target_proc}): {current_opt_profile}")
                    notify("GHub", f"Применено к {game_name} ({target_proc})\nПрофиль: {current_opt_profile}")
                else:
                    notify("GHub", f"Профиль '{current_opt_profile}' пуст или не найден в optimizer.yaml")
            except Exception as e:
                print(f"[optimizer] ошибка: {e}")
                notify("GHub", f"Ошибка применения оптимизации: {e}")
        else:
            notify("GHub", "Игра не найдена. Убедись, что игра запущена и есть в config/games.yaml")
            print("[optimizer] игра не найдена")

    def add_cfg():
        from core.game_detector import _foreground_process
        fg = _foreground_process()
        if fg:
            profile = "singleplayer"
            print(f"[add_config] добавляю {fg} с профилем {profile} (изменить можно в config/games.yaml)")
            try:
                cfg_y = load_games_config()
                cfg_y.setdefault("games", [])
                cfg_y["games"].append({"name": fg.replace(".exe", ""), "processes": [fg], "profile": profile})
                save_games_config(cfg_y)
                print(f"[add_config] готово: {fg} -> {profile}")
                notify("GHub", f"Процесс добавлен в config/games.yaml\n{fg} -> {profile}")
            except Exception as e:
                print(f"[add_config] ошибка записи: {e}")
                notify("GHub", f"Ошибка сохранения конфига: {e}")
        else:
            print("[add_config] нет активного окна")
            notify("GHub", "Нет активного окна для добавления в конфиг")

    tray = TrayController(
        on_toggle_overlay=overlay.toggle,
        on_open_dashboard=lambda: webbrowser.open(dash.url()),
        on_input_test=lambda: overlay.run_in_ui(create_input_window),
        on_select_profile=select_prof,
        on_apply_now=apply_now,
        on_add_config=add_cfg,
        get_current_profile=lambda: current_opt_profile,
        on_quit=quit_event.set,
    )
    tray.start()
    print(f"GHub v{VERSION} запущен. Дашборд: {dash.url()}")
    print("GHub запущен. Оверлей сверху слева, drag мышью. Выход: трей -> Выход / Ctrl+C.")
    session_id = None
    cur_game = None
    entry = sett = None
    ping_tracker = fps_tracker = None
    match_ip = None
    last_scan = 0.0
    try:
        while not quit_event.is_set():
            game, proc = find_game(cfg)
            if game != cur_game:  # смена игры -> новая сессия, новые трекеры
                if session_id:
                    end_session(con, session_id)
                if ping_tracker:
                    ping_tracker.stop()
                if fps_tracker:
                    fps_tracker.stop()
                cur_game, entry = game, entry_for(cfg, game)
                sett = settings_for(cfg, entry)
                if game and entry is None:  # неизвестная игра -> unknown_profile
                    unk = cfg.get("defaults", {}).get("unknown_profile", "singleplayer")
                    sett = dict(cfg.get("profiles", {}).get(unk, {"net": "off", "frame_ms": True}))
                match_ip, last_scan = None, 0.0
                if game:
                    session_id = start_session(con, game, proc)
                    # Применяем профиль оптимизации при запуске игры
                    profile_name = current_opt_profile
                    opt_cfg = load_optimizer_config()
                    profile = opt_cfg.get("profiles", {}).get(profile_name, {})
                    if profile and isinstance(profile, dict):
                        try:
                            target_proc = proc.get("name", game) if isinstance(proc, dict) else (proc or game)
                            optimizer.apply_profile(target_proc, profile)
                            print(f"[{cur_game}] optimizer: {profile_name} -> priority={profile.get('priority')} affinity={profile.get('affinity')} kill_junk={profile.get('kill_junk')}")
                        except Exception as e:
                            print(f"[{cur_game}] optimizer error: {e}")
                    if sett.get("net", "static") != "off":
                        ping_tracker = PingTracker(ping_hosts_for(cfg, game))
                        ping_tracker.start()
                    else:
                        ping_tracker = None
                    fps_tracker = FpsTracker(proc)
                    fps_tracker.start()
                else:
                    session_id = None
                    ping_tracker = fps_tracker = None
            # режим match: ищем IP сервера катки, перенацеливаем пинг
            if sett and sett.get("net") == "match" and ping_tracker:
                now = time.monotonic()
                if now - last_scan >= match_scan:
                    last_scan = now
                    ip = find_match_ip(entry.get("processes", []))
                    if ip and ping_tracker.set_hosts([ip]):
                        print(f"[{cur_game}] сервер катки: {ip}")
                    match_ip = ip if ip else None
                    if not ip and ping_tracker.current_host() not in ping_hosts_for(cfg, cur_game):
                        ping_tracker.set_hosts(ping_hosts_for(cfg, cur_game))
            s = collector.sample()
            fps_note, frame_ms = "", None
            if ping_tracker:
                s.ping_ms, s.loss_pct = ping_tracker.get()
            if fps_tracker:
                s.fps = fps_tracker.get()
                frame_ms = fps_tracker.frame_ms()
                s.frame_ms = frame_ms
                if s.fps is None:
                    fps_note = fps_tracker.status()
            overlay.update(fmt(s, cur_game, sett, fps_note, frame_ms, match_ip))
            if session_id:
                insert_sample(con, session_id, s)
            else:
                print(fmt(s, None, None))
            quit_event.wait(interval)
    except KeyboardInterrupt:
        pass
    finally:
        if session_id:
            end_session(con, session_id)
        if ping_tracker:
            ping_tracker.stop()
        if fps_tracker:
            fps_tracker.stop()
        tray.stop()
        dash.stop()
        overlay.stop()


def _single_instance() -> bool:
    """Запрет второго экземпляра (иначе два хаба дерутся за PresentMon и базу)."""
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW(None, True, "GHubSingleInstanceMutex")
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            try:
                ctypes.windll.user32.MessageBoxW(
                    None, "GHub уже запущен (иконка в трее).", "GHub", 0x40)
            except Exception:
                pass
            return False
        return True
    except Exception:
        return True


if __name__ == "__main__":
    if _single_instance():
        main()
