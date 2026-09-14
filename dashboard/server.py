"""Локальный дашборд GHub: http://127.0.0.1:8765 . Только stdlib, без зависимостей.
Отдает страницу + JSON API из SQLite + экспорт CSV."""
import csv
import io
import json
import os
import sqlite3
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_HERE = os.path.dirname(os.path.abspath(__file__))


def _db():
    # импорт здесь, чтобы работало и в frozen-сборке, и при запуске напрямую
    import sys
    base = os.path.dirname(_HERE)
    if base not in sys.path:
        sys.path.insert(0, base)
    from core.storage import db_path
    con = sqlite3.connect(db_path())
    con.row_factory = sqlite3.Row
    return con


class _Handler(BaseHTTPRequestHandler):
    server_version = "GHubDash/1"

    def log_message(self, *a):
        pass

    def _send(self, body: bytes, ctype: str, filename: str | None = None):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        try:
            if u.path in ("/", "/dashboard", "/dashboard.html"):
                with open(os.path.join(_HERE, "dashboard.html"), "rb") as f:
                    return self._send(f.read(), "text/html; charset=utf-8")
            if u.path == "/api/sessions":
                con = _db()
                rows = [dict(r) for r in con.execute(
                    """SELECT s.id, s.game, s.process, s.started_at, s.ended_at,
                       (SELECT COUNT(*) FROM samples WHERE session_id=s.id) AS n
                       FROM sessions s ORDER BY s.id DESC LIMIT 50""")]
                con.close()
                return self._send(json.dumps(rows).encode(), "application/json")
            if u.path == "/api/samples":
                sid = int(q.get("session_id", 0))
                lim = min(int(q.get("limit", 5000)), 20000)
                con = _db()
                rows = [dict(r) for r in con.execute(
                    """SELECT ts, fps, ping_ms, cpu_temp, cpu_pct, gpu_temp, gpu_pct,
                       vram_used_mb, ram_pct, frame_ms
                       FROM samples WHERE session_id=? ORDER BY id LIMIT ?""", (sid, lim))]
                con.close()
                return self._send(json.dumps(rows).encode(), "application/json")
            if u.path == "/export.csv":
                sid = int(q.get("session_id", 0))
                con = _db()
                rows = con.execute(
                    "SELECT * FROM samples WHERE session_id=? ORDER BY id", (sid,))
                buf = io.StringIO()
                w = csv.writer(buf)
                w.writerow([d[0] for d in rows.description])
                w.writerows(rows)
                con.close()
                return self._send(buf.getvalue().encode(), "text/csv",
                                  f"ghub_session_{sid}.csv")
        except (OSError, ValueError, sqlite3.Error):
            pass
        self.send_error(404)


class DashboardServer:
    def __init__(self, port: int = 8765):
        self.port = port
        self._srv: ThreadingHTTPServer | None = None
        self._t = threading.Thread(target=self._run, daemon=True)

    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"

    def start(self):
        self._t.start()

    def _run(self):
        try:
            self._srv = ThreadingHTTPServer(("127.0.0.1", self.port), _Handler)
            self._srv.serve_forever()
        except OSError:
            pass  # порт занят - дашборд недоступен, хаб работает дальше

    def stop(self):
        try:
            if self._srv:
                self._srv.shutdown()
        except Exception:
            pass
