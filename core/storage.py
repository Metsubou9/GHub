import os
import sqlite3
from datetime import datetime, timezone


def db_path() -> str:
    # exe-сборка: %APPDATA%/GHub, dev: корень проекта
    appdata = os.environ.get("APPDATA")
    if appdata and os.path.basename(os.getcwd()).lower() != "ghub":
        d = os.path.join(appdata, "GHub")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, "data.sqlite")
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "data.sqlite")


def connect() -> sqlite3.Connection:
    path = db_path()
    schema = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
    con = sqlite3.connect(path)
    with open(schema, encoding="utf-8") as f:
        con.executescript(f.read())
    # миграция старых баз: добавляем колонки, которых не было в первых версиях
    cols = [r[1] for r in con.execute("PRAGMA table_info(samples)")]
    if "frame_ms" not in cols:
        con.execute("ALTER TABLE samples ADD COLUMN frame_ms REAL")
        con.commit()
    return con


def start_session(con: sqlite3.Connection, game: str, process: str) -> int:
    cur = con.execute(
        "INSERT INTO sessions(game, process, started_at) VALUES (?,?,?)",
        (game, process, datetime.now(timezone.utc).isoformat()),
    )
    con.commit()
    return cur.lastrowid


def end_session(con: sqlite3.Connection, session_id: int) -> None:
    con.execute(
        "UPDATE sessions SET ended_at=? WHERE id=?",
        (datetime.now(timezone.utc).isoformat(), session_id),
    )
    con.commit()


def insert_sample(con: sqlite3.Connection, session_id: int, s) -> None:
    con.execute(
        """INSERT INTO samples(session_id, ts, fps, ping_ms, loss_pct, cpu_temp,
           cpu_pct, gpu_temp, gpu_pct, vram_used_mb, ram_pct, frame_ms)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            session_id,
            datetime.now(timezone.utc).isoformat(),
            s.fps, s.ping_ms, s.loss_pct, s.cpu_temp, s.cpu_pct,
            s.gpu_temp, s.gpu_pct, s.vram_used_mb, s.ram_pct,
            getattr(s, "frame_ms", None),
        ),
    )
    con.commit()
