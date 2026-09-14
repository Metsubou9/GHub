"""FPS через PresentMon v2 (без инжекта, безопасно для античита).
Читает CSV из stdout потоком - без временного файла (файл лочится
PresentMon на время захвата и не читается другим процессом).
Требует presentmon.exe рядом и права админа (ETW). Без них - degraded + статус."""

import os
import subprocess
import threading
import time
from collections import deque


class FpsTracker:
    STATUS_NO_BIN = "нет presentmon.exe"
    STATUS_NO_ADMIN = "нужен запуск от админа"
    STATUS_WAIT = "ожидание кадров..."
    STATUS_OK = "ok"

    def __init__(self, process_name: str | None):
        self.process = process_name
        self._fps: float | None = None
        self._frame_ms: float | None = None  # средняя задержка кадра (как ms в счетчике osu!)
        self._status = self.STATUS_WAIT
        self._stop = threading.Event()
        self._proc: subprocess.Popen | None = None
        self._frames: deque[float] = deque(maxlen=120)  # msBetweenPresents
        self._t = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self._t.start()

    def stop(self):
        self._stop.set()
        try:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
        except Exception:
            pass

    def get(self) -> float | None:
        return self._fps

    def frame_ms(self) -> float | None:
        return self._frame_ms

    def status(self) -> str:
        return self._status

    def _exe(self) -> str | None:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        for cand in (os.path.join(os.getcwd(), "presentmon.exe"),
                     os.path.join(base, "presentmon.exe")):
            if os.path.exists(cand):
                return cand
        return None

    def _is_admin(self) -> bool:
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def _loop(self):
        exe = self._exe()
        if exe is None:
            self._status = self.STATUS_NO_BIN
            return
        if not self.process:
            return
        if not self._is_admin():
            self._status = self.STATUS_NO_ADMIN
            return
        err_log = os.path.join(os.environ.get("TEMP", "."), "ghub_presentmon_err.log")
        try:
            err = open(err_log, "w")
        except OSError:
            err = subprocess.DEVNULL
        try:
            self._proc = subprocess.Popen(
                [exe, "--process_name", self.process,
                 "--output_stdout", "--no_console_stats",
                 "--stop_existing_session", "--v1_metrics",
                 "--terminate_on_proc_exit"],
                stdout=subprocess.PIPE, stderr=err,
                text=True, bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            self._status = self.STATUS_NO_BIN
            try:
                if err is not subprocess.DEVNULL:
                    err.close()
            except Exception:
                pass
            return
        try:
            self._read_stream()
        finally:
            try:
                if self._proc and self._proc.poll() is None:
                    self._proc.terminate()
            except Exception:
                pass
            try:
                if err is not subprocess.DEVNULL:
                    err.close()
            except Exception:
                pass

    def _read_stream(self):
        assert self._proc is not None and self._proc.stdout is not None
        header = self._proc.stdout.readline()
        if not header:
            return  # процесс сразу упал (см. ghub_presentmon_err.log)
        cols = [c.strip() for c in header.split(",")]
        idx = None
        for cand in ("msBetweenPresents", "MsBetweenPresents"):
            if cand in cols:
                idx = cols.index(cand)
                break
        for line in self._proc.stdout:
            if self._stop.is_set():
                break
            if idx is None:
                continue
            try:
                v = float(line.split(",")[idx])
            except (ValueError, IndexError):
                continue
            if 0 < v < 1000:
                self._frames.append(v)
                avg = sum(self._frames) / len(self._frames)
                self._frame_ms = round(avg, 2)
                self._fps = round(1000 / avg, 1)
                self._status = self.STATUS_OK
