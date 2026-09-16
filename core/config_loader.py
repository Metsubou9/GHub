import os
import sys
import yaml


def get_base_dir() -> str:
    """Определяет базовую директорию проекта (работает в исходниках и в pyinstaller)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_games_config(path: str = "config/games.yaml") -> dict:
    base = get_base_dir()
    for cand in (path, os.path.join(base, path), os.path.join(base, "config", "games.yaml")):
        if os.path.exists(cand):
            with open(cand, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    raise FileNotFoundError("games.yaml not found")


def load_optimizer_config(path: str = "config/optimizer.yaml") -> dict:
    base = get_base_dir()
    for cand in (path, os.path.join(base, path), os.path.join(base, "config", "optimizer.yaml")):
        if os.path.exists(cand):
            try:
                with open(cand, encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                pass
    return {"profiles": {"default": {}}}


def save_games_config(cfg: dict, path: str = "config/games.yaml") -> None:
    base = get_base_dir()
    target = path if os.path.isabs(path) else os.path.join(base, path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, sort_keys=False)

