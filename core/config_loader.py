import os
import yaml


def load_games_config(path: str = "config/games.yaml") -> dict:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for cand in (path, os.path.join(base, path), os.path.join(base, "config", "games.yaml")):
        if os.path.exists(cand):
            with open(cand, encoding="utf-8") as f:
                return yaml.safe_load(f)
    raise FileNotFoundError("games.yaml not found")
