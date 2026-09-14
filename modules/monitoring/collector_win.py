import os
import subprocess
import threading
import time

import psutil
from core.collector_abstract import ICollector, Sample

_nv_init = False
_cpu_temp_state = {"v": None}
_cpu_thread_started = False
_cpu_lock = threading.Lock()


def _nv_handle():
    global _nv_init
    try:
        import pynvml
        if not _nv_init:
            pynvml.nvmlInit()
            _nv_init = True
        return pynvml.nvmlDeviceGetHandleByIndex(0), pynvml
    except Exception:
        return None, None


def _helper_path() -> str | None:
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for cand in (os.path.join(os.getcwd(), "tools", "cputemp.exe"),
                 os.path.join(base, "tools", "cputemp.exe")):
        if os.path.exists(cand):
            return cand
    return None


def _diag_log(msg: str) -> None:
    try:
        with open(os.path.join(os.environ.get("TEMP", "."), "ghub_cpu.log"),
                  "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S") + " " + msg + "\n")
    except OSError:
        pass


def _cpu_temp_refresher() -> None:
    """Фон: дергает хелпер раз в 5 сек. sample() только читает кэш и не блокируется.
    Таймаут 60 сек: первая загрузка драйвера после перезагрузки бывает долгой,
    убивать процесс раньше - значит вечно начинать сначала и не получить ничего."""
    while True:
        exe = _helper_path()
        if exe is not None:
            try:
                r = subprocess.run(
                    [exe], capture_output=True, text=True, timeout=60,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                out = (r.stdout or "").strip()
                v = float(out)
                if 1 < v < 130:
                    with _cpu_lock:
                        _cpu_temp_state["v"] = round(v, 1)
                else:
                    _diag_log(f"out of range: {out!r} rc={r.returncode}")
            except (ValueError, OSError, subprocess.SubprocessError) as e:
                _diag_log(f"fail exe={exe} err={type(e).__name__}: {e}")
        time.sleep(5)


def _cpu_temp() -> float | None:
    """Температура CPU через LibreHardwareMonitor-хелпер (нужен админ для драйвера).
    Без админа/хелпера -> None (degraded mode)."""
    global _cpu_thread_started
    if not _cpu_thread_started:
        _cpu_thread_started = True
        threading.Thread(target=_cpu_temp_refresher, daemon=True).start()
        _diag_log("refresher started")
    with _cpu_lock:
        return _cpu_temp_state["v"]


class MonitoringCollectorWin(ICollector):
    """Windows: CPU/RAM через psutil, GPU через NVML (NVIDIA),
    CPU-температура через LHM-хелпер (админ)."""

    def sample(self) -> Sample:
        s = Sample()
        s.cpu_pct = psutil.cpu_percent(interval=None)
        s.cpu_temp = _cpu_temp()
        s.ram_pct = psutil.virtual_memory().percent
        h, pynvml = _nv_handle()
        if h:
            try:
                s.gpu_temp = float(pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU))
                util = pynvml.nvmlDeviceGetUtilizationRates(h)
                s.gpu_pct = float(util.gpu)
                mem = pynvml.nvmlDeviceGetMemoryInfo(h)
                s.vram_used_mb = round(mem.used / 1024 / 1024, 1)
            except Exception:
                pass
        return s
