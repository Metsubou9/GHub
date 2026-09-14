"""Пинг в отдельном потоке, чтобы не блокировать опрос сенсоров."""
import threading
import time
from collections import deque

try:
    from ping3 import ping
except ImportError:
    ping = None


class PingTracker:
    def __init__(self, hosts: list[str], interval_ms: int = 2000):
        self.hosts = hosts
        self.interval = interval_ms / 1000
        self._lock = threading.Lock()
        self._ping: float | None = None
        self._loss: float | None = None
        self._hist: deque[bool] = deque(maxlen=20)
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self._t.start()

    def stop(self):
        self._stop.set()

    def get(self) -> tuple[float | None, float | None]:
        with self._lock:
            return self._ping, self._loss

    def current_host(self) -> str | None:
        with self._lock:
            return self.hosts[0] if self.hosts else None

    def set_hosts(self, hosts: list[str]) -> bool:
        """Перенацелить на другие хосты (напр. найденный IP катки).
        Возвращает True если хосты реально сменились."""
        with self._lock:
            if hosts == self.hosts:
                return False
            self.hosts = hosts
            self._hist.clear()
            self._ping, self._loss = None, None
            return True

    def _loop(self):
        while not self._stop.is_set():
            if ping is None:
                time.sleep(self.interval)
                continue
            host = self.hosts[0] if self.hosts else "8.8.8.8"
            try:
                r = ping(host, timeout=2, unit="ms")
                ok = r is not None and r is not False
                self._hist.append(ok)
                with self._lock:
                    self._ping = round(float(r), 1) if ok else None
                    fails = sum(1 for x in self._hist if not x)
                    self._loss = round(fails / len(self._hist) * 100, 1)
            except Exception:
                self._hist.append(False)
            time.sleep(self.interval)
