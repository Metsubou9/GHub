import psutil


def _foreground_process() -> str | None:
    """Имя exe активного окна (только Windows)."""
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return psutil.Process(pid.value).name()
    except Exception:
        return None


def find_game(games_cfg: dict) -> tuple[str, str] | tuple[None, None]:
    """Возвращает (game_name, process) или (None, None). Регистр не важен.
    Игры из конфига - в приоритете. Неизвестное активное окно пишется
    как '? имя' если включен track_unknown и его нет в unknown_ignore."""
    procs = {p.info["name"].lower() for p in psutil.process_iter(["name"]) if p.info["name"]}
    known: set[str] = set()
    for g in games_cfg.get("games", []):
        for want in g.get("processes", []):
            known.add(want.lower())
            if want.lower() in procs:
                return g["name"], want
    defaults = games_cfg.get("defaults", {})
    if defaults.get("track_unknown", False):
        ignore = {str(i).lower() for i in defaults.get("unknown_ignore", [])}
        fg = _foreground_process()
        if fg and fg.lower().endswith(".exe"):
            low = fg.lower()
            if low not in known and low not in ignore and low in procs:
                base = fg[:-4] if low.endswith(".exe") else fg
                return f"? {base}", fg
    return None, None


def ping_hosts_for(games_cfg: dict, game_name: str | None) -> list[str]:
    return settings_for(games_cfg, entry_for(games_cfg, game_name)).get(
        "ping_hosts", ["8.8.8.8"])


def entry_for(games_cfg: dict, game_name: str | None) -> dict | None:
    if not game_name:
        return None
    for g in games_cfg.get("games", []):
        if g["name"] == game_name:
            return g
    return None


def settings_for(games_cfg: dict, entry: dict | None) -> dict:
    """Итоговые настройки: профиль + точечные переопределения из записи игры.
    Игра может переопределить net / frame_ms / ping_hosts поверх профиля."""
    profiles = games_cfg.get("profiles", {})
    base = dict(profiles.get((entry or {}).get("profile", ""), {}))
    if not base:  # старый формат или неизвестный профиль -> mult по умолчанию
        base = {"net": "static", "frame_ms": False}
    for key in ("net", "frame_ms", "ping_hosts"):
        if entry and key in entry:
            base[key] = entry[key]
    return base
