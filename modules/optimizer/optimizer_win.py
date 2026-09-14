"""Optimizer: приоритет, affinity, kill_junk, game_mode для Windows."""
import ctypes
import os
import subprocess
from core.collector_abstract import IOptimizer

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Приоритеты
PRIORITY = {
    "idle": 64,
    "below_normal": 16384,
    "normal": 32,
    "above_normal": 32768,
    "high": 128,
    "realtime": 256,
}


class OptimizerWin(IOptimizer):
    def apply_profile(self, process_name: str, profile: dict) -> None:
        res = self._find_pid(process_name)
        if not res:
            return
        pid = res
        # Приоритет
        prio = profile.get("priority", "normal")
        if prio in PRIORITY:
            try:
                h = kernel32.OpenProcess(0x0200 | 0x0001, False, pid)
                if h:
                    kernel32.SetPriorityClass(h, PRIORITY[prio])
                    kernel32.CloseHandle(h)
            except Exception:
                pass
        # Affinity
        aff = profile.get("affinity")
        if aff is not None:
            try:
                mask = 0
                for c in aff:
                    mask |= 1 << c
                h = kernel32.OpenProcess(0x0200 | 0x0001, False, pid)
                if h:
                    kernel32.SetProcessAffinityMask(h, mask)
                    kernel32.CloseHandle(h)
            except Exception:
                pass
        # Kill junk
        if profile.get("kill_junk"):
            for p in profile.get("kill_list", []):
                try:
                    subprocess.run(
                        ["taskkill", "/f", "/im", p],
                        capture_output=True, timeout=3
                    )
                except Exception:
                    pass
        # Game mode (Windows 10+ Game Mode)
        if profile.get("game_mode"):
            try:
                reg_path = r"HKCU\System\GameConfigStore"
                # Включаем через reg add (если нет — игнор)
                subprocess.run(
                    ["reg", "add", reg_path, "/v", "GameModeEnabled",
                     "/t", "REG_DWORD", "/d", "1", "/f"],
                    capture_output=True, timeout=2
                )
            except Exception:
                pass

    def _find_pid(self, name: str) -> int | None:
        try:
            out = subprocess.run(
                ["tasklist", "/fi", f"imagename eq {name}", "/nh", "/fo", "csv"],
                capture_output=True, text=True
            )
            for line in out.stdout.splitlines():
                parts = line.split(",")
                if len(parts) >= 2:
                    try:
                        return int(parts[1].strip('"'))
                    except ValueError:
                        continue
        except Exception:
            pass
        return None
