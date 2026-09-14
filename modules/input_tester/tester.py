"""Тестер инпута для osu!: polling rate мыши/планшета, дребезг кнопок, клавиши.

Мышь: Raw Input (WM_INPUT) + perf_counter_ns — единственный способ увидеть
честные 1000 Гц. WH_MOUSE_LL для замера частоты НЕ годится: очередь сообщений
коалесцирует движения + тик MSLLHOOKSTRUCT.time имеет разрешение ~1 мс.
Клавиатура/клики: LowLevel-хуки через ctypes, без инжекта в игру.
"""
import ctypes
import ctypes.wintypes as wt
import math
import statistics
import threading
import time
from collections import Counter

from core.collector_abstract import IInputTester

WH_MOUSE_LL = 14
WH_KEYBOARD_LL = 13
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_INPUT = 0x00FF
RID_INPUT = 0x10000003
RIDEV_INPUTSINK = 0x00000100

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Явные сигнатуры обязательны на x64: иначе LPARAM/указатели режутся до 32 бит.
HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int,
                              ctypes.c_size_t, ctypes.c_ssize_t)
WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, wt.UINT,
                             wt.WPARAM, wt.LPARAM)
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, ctypes.c_void_p,
                                     ctypes.c_void_p, wt.DWORD]
user32.SetWindowsHookExW.restype = ctypes.c_void_p
user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                  ctypes.c_size_t, ctypes.c_ssize_t]
user32.CallNextHookEx.restype = ctypes.c_ssize_t
user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
user32.PeekMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND,
                                wt.UINT, wt.UINT, wt.UINT]
user32.PeekMessageW.restype = wt.BOOL
user32.MapVirtualKeyW.argtypes = [wt.UINT, wt.UINT]
user32.MapVirtualKeyW.restype = wt.UINT
user32.GetKeyNameTextW.argtypes = [wt.LONG, wt.LPWSTR, ctypes.c_int]
user32.GetKeyNameTextW.restype = ctypes.c_int
try:
    user32.RegisterRawInputDevices.argtypes = [ctypes.c_void_p, wt.UINT, wt.UINT]
    user32.RegisterRawInputDevices.restype = wt.BOOL
    user32.GetRawInputData.argtypes = [ctypes.c_void_p, wt.UINT, ctypes.c_void_p,
                                       ctypes.POINTER(wt.UINT), wt.UINT]
    user32.GetRawInputData.restype = wt.UINT
    user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    user32.DefWindowProcW.restype = ctypes.c_ssize_t
    user32.DestroyWindow.argtypes = [wt.HWND]
    user32.DestroyWindow.restype = wt.BOOL
    kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wt.HMODULE
except Exception:
    pass


def vk_name(vk: int) -> str:
    """Читаемое имя клавиши по VK-коду (раскладкозависимо), иначе hex."""
    try:
        scan = user32.MapVirtualKeyW(vk, 0)
        if scan:
            buf = ctypes.create_unicode_buffer(32)
            if user32.GetKeyNameTextW(scan << 16, buf, 32):
                return buf.value
    except Exception:
        pass
    return hex(vk)


class _MSLL(ctypes.Structure):
    _fields_ = [("x", wt.LONG), ("y", wt.LONG),
                ("mouseData", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("extra", ctypes.c_size_t)]


class _KBDLL(ctypes.Structure):
    _fields_ = [("vk", wt.DWORD), ("scan", wt.DWORD),
                ("flags", wt.DWORD), ("time", wt.DWORD),
                ("extra", ctypes.c_size_t)]


class _RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [("usUsagePage", wt.USHORT), ("usUsage", wt.USHORT),
                ("dwFlags", wt.DWORD), ("hwndTarget", wt.HWND)]


class _WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wt.UINT), ("lpfnWndProc", ctypes.c_void_p),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wt.HINSTANCE), ("hIcon", wt.HANDLE),
                ("hCursor", wt.HANDLE), ("hbrBackground", wt.HANDLE),
                ("lpszMenuName", wt.LPCWSTR), ("lpszClassName", wt.LPCWSTR)]


class _RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [("dwType", wt.DWORD), ("dwSize", wt.DWORD),
                ("hDevice", wt.HANDLE), ("wParam", wt.WPARAM)]


def _diff(a: int, b: int) -> int:
    return (b - a) & 0xFFFFFFFF  # тики GetTickCount заворачиваются


class InputTester(IInputTester):
    """start(duration) - неблокирующий, опрос через poll()."""
    def __init__(self):
        self._t0 = 0.0
        self.duration = 0
        self.done = threading.Event()
        # moves: наносекунды perf_counter_ns из Raw Input (точный замер)
        self.moves: list[int] = []
        # fallback с LL-хука (тики ~1мс), если Raw Input не завелся
        self._ll_moves: list[int] = []
        self.clicks: list[tuple[str, int]] = []  # (L/R, tick)
        self.keys: list[tuple[int, int]] = []    # (vk, tick)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._cb_m = None
        self._cb_k = None
        self._hook_m = None
        self._hook_k = None
        self._wndproc = None
        self._hwnd = None
        self.raw_ok = False
        self._dev_counts: dict[int, int] = {}  # hDevice -> событий

    def start(self, duration: int = 10) -> None:
        if self._thread and self._thread.is_alive():
            return
        self.duration = duration
        self._t0 = time.monotonic()
        self.done.clear()
        self._stop.clear()
        self.moves.clear()
        self._ll_moves.clear()
        self.clicks.clear()
        self.keys.clear()
        self.raw_ok = False
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    # --- хуки ---
    def _on_mouse(self, code, wp, lp):
        if code >= 0:
            m = ctypes.cast(lp, ctypes.POINTER(_MSLL)).contents
            if wp == WM_MOUSEMOVE:
                self._ll_moves.append(m.time)
            elif wp == WM_LBUTTONDOWN:
                self.clicks.append(("L", m.time))
            elif wp == WM_RBUTTONDOWN:
                self.clicks.append(("R", m.time))
        return user32.CallNextHookEx(self._hook_m, code, wp, lp)

    def _on_key(self, code, wp, lp):
        if code >= 0 and wp in (WM_KEYDOWN, WM_SYSKEYDOWN):
            k = ctypes.cast(lp, ctypes.POINTER(_KBDLL)).contents
            if k.vk not in (0x10, 0x11, 0x12):  # игнор чистых модификаторов
                self.keys.append((k.vk, k.time))
        return user32.CallNextHookEx(self._hook_k, code, wp, lp)

    def _on_wnd(self, hwnd, msg, wp, lp):
        if msg == WM_INPUT:
            # Каждый WM_INPUT от мыши = один USB-репорт. Время — сразу,
            # с наносекундным разрешением, до разбора пакета.
            self.moves.append(time.perf_counter_ns())
            # Дренируем очередь Raw Input + фиксируем hDevice источника:
            # если источников >1 (вторая мышь, тачпад, виртуальный драйвер) —
            # пары событий объясняются именно этим.
            try:
                hdr_size = ctypes.sizeof(_RAWINPUTHEADER)
                size = wt.UINT(0)
                user32.GetRawInputData(ctypes.c_void_p(lp), RID_INPUT,
                                       None, ctypes.byref(size), hdr_size)
                if 0 < size.value < 4096:
                    buf = ctypes.create_string_buffer(size.value)
                    if user32.GetRawInputData(ctypes.c_void_p(lp), RID_INPUT,
                                              buf, ctypes.byref(size),
                                              hdr_size) == size.value:
                        hdr = _RAWINPUTHEADER.from_buffer_copy(buf.raw[:hdr_size])
                        if hdr.dwType == 0:  # RIM_TYPEMOUSE
                            h = int(hdr.hDevice or 0)
                            self._dev_counts[h] = self._dev_counts.get(h, 0) + 1
            except Exception:
                pass
            return 0
        return user32.DefWindowProcW(hwnd, msg, wp, lp)

    def _create_raw_window(self):
        """Скрытое окно в потоке пампа + регистрация Raw Input мыши."""
        cls_name = "GHubRawInput"
        self._wndproc = WNDPROC(self._on_wnd)
        hinst = kernel32.GetModuleHandleW(None)
        wc = _WNDCLASSW()
        wc.lpfnWndProc = ctypes.cast(self._wndproc, ctypes.c_void_p)
        wc.hInstance = hinst
        wc.lpszClassName = cls_name
        try:
            user32.RegisterClassW(ctypes.byref(wc))
        except Exception:
            pass  # класс уже зарегистрирован — нормально
        user32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR,
                                           wt.DWORD, ctypes.c_int, ctypes.c_int,
                                           ctypes.c_int, ctypes.c_int,
                                           wt.HWND, wt.HMENU, wt.HINSTANCE,
                                           ctypes.c_void_p]
        user32.CreateWindowExW.restype = wt.HWND
        hwnd = user32.CreateWindowExW(0, cls_name, "GHubRaw", 0,
                                      0, 0, 0, 0, None, None, hinst, None)
        if not hwnd:
            return None
        rid = _RAWINPUTDEVICE()
        rid.usUsagePage = 1
        rid.usUsage = 2  # мышь
        rid.dwFlags = RIDEV_INPUTSINK  # ловим даже в фоне
        rid.hwndTarget = hwnd
        ok = user32.RegisterRawInputDevices(ctypes.byref(rid), 1,
                                            ctypes.sizeof(rid))
        if not ok:
            try:
                user32.DestroyWindow(hwnd)
            except Exception:
                pass
            return None
        self.raw_ok = True
        return hwnd

    def _pump(self):
        self._cb_m = HOOKPROC(self._on_mouse)
        self._cb_k = HOOKPROC(self._on_key)
        # LL-хуки живут в нашем потоке: hMod строго NULL (иначе 126)
        self._hook_m = user32.SetWindowsHookExW(WH_MOUSE_LL, self._cb_m, None, 0)
        self._hook_k = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._cb_k, None, 0)
        try:
            self._hwnd = self._create_raw_window()
        except Exception:
            self._hwnd = None
        try:
            msg = wt.MSG()
            while not self._stop.is_set():
                while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                if time.monotonic() - self._t0 >= self.duration:
                    break
                time.sleep(0.001)
        finally:
            if self._hook_m:
                user32.UnhookWindowsHookEx(self._hook_m)
            if self._hook_k:
                user32.UnhookWindowsHookEx(self._hook_k)
            self._hook_m = self._hook_k = None
            if self._hwnd:
                try:
                    user32.DestroyWindow(self._hwnd)
                except Exception:
                    pass
                self._hwnd = None
            # Fallback: Raw не завелся, а LL что-то поймал — пересчитаем
            # тики (~1мс) в псевдо-наносекунды, чтобы отчет построился.
            if len(self.moves) < 2 and len(self._ll_moves) >= 2:
                base = time.perf_counter_ns()
                t0 = self._ll_moves[0]
                self.moves = [base + _diff(t0, t) * 1_000_000
                              for t in self._ll_moves]
                self.raw_ok = False
            self.done.set()

    # --- анализ ---
    def elapsed(self) -> float:
        return time.monotonic() - self._t0

    def report(self) -> dict:
        # Предпочитаем Raw Input (наносекунды), fallback — LL-тики.
        use_raw = len(self.moves) >= 2
        ticks = self.moves if use_raw else []
        if use_raw:
            diffs_ns = [b - a for a, b in zip(ticks, ticks[1:]) if b > a]
            iv = [d / 1_000_000 for d in diffs_ns]  # в мс
            span_s = (ticks[-1] - ticks[0]) / 1_000_000_000
            total = len(ticks)
            # скользящее окно 1с по наносекундным меткам
            best, j = 0, 0
            for i in range(len(ticks)):
                while ticks[i] - ticks[j] >= 1_000_000_000:
                    j += 1
                best = max(best, i - j + 1)
        else:
            iv = InputTester._ll_intervals(self._ll_moves)
            gaps = max(len(self._ll_moves) - 1, 0)
            total = len(self._ll_moves)
            span_s = 0.0
            if len(self._ll_moves) >= 2:
                span_s = _diff(self._ll_moves[0], self._ll_moves[-1]) / 1000
            best = 0
            if len(self._ll_moves) >= 2:
                b2, j = 0, 0
                for i in range(len(self._ll_moves)):
                    while _diff(self._ll_moves[j], self._ll_moves[i]) >= 1000:
                        j += 1
                    b2 = max(b2, i - j + 1)
                best = b2
        gaps = max(total - 1, 0)
        rep: dict = {
            "moves": total,
            "clicks_L": sum(1 for b, _ in self.clicks if b == "L"),
            "clicks_R": sum(1 for b, _ in self.clicks if b == "R"),
            "keys": len(self.keys),
            "raw": use_raw,
        }
        if total >= 2 and span_s > 0:
            rep["poll_hz"] = round(total / span_s, 1)
            rep["span_s"] = round(span_s, 2)
        else:
            rep["poll_hz"] = None
        if iv:
            # доля интервалов <1мс — при 1000 Гц их должно быть много
            sub = sum(1 for d in iv if d < 1.0)
            rep["sub_ms_pct"] = round(sub / len(iv) * 100, 1)
            rep["burst_hz"] = best
        else:
            if total >= 2:
                rep["burst_hz"] = best
        if iv:
            rep["interval_avg_ms"] = round(statistics.fmean(iv), 3)
            rep["interval_med_ms"] = round(statistics.median(iv), 3)
            rep["interval_max_ms"] = round(max(iv), 2)
            rep["jitter_ms"] = round(statistics.pstdev(iv), 3) if len(iv) > 1 else 0.0
            # p95: 95% интервалов короче этого — устойчив к одиночным выбросам
            srt = sorted(iv)
            idx = min(max(math.ceil(0.95 * len(srt)) - 1, 0), len(srt) - 1)
            rep["interval_p95_ms"] = round(srt[idx], 3)
            # чистый джиттер: без пауз >5мс (остановки руки, а не мыши)
            clean = [d for d in iv if d <= 5.0]
            rep["pauses"] = len(iv) - len(clean)
            rep["jitter_clean_ms"] = (round(statistics.pstdev(clean), 3)
                                      if len(clean) > 1 else 0.0)
            # гистограмма интервалов (мс): для чистых 1000 Гц почти все в 0.9-1.3
            bounds = [0.5, 0.9, 1.3, 2.0, 5.0]
            hist = [0] * (len(bounds) + 1)
            for d in iv:
                for i, b in enumerate(bounds):
                    if d < b:
                        hist[i] += 1
                        break
                else:
                    hist[-1] += 1
            rep["hist"] = hist
            # батчинг: репорты идут пачками (пары через 0.1-0.2мс с дырками ~2мс).
            # Классика 2.4ГГц-свистка в USB3-порту / помех / ретрансмитов:
            # медиана рушится к ~0.2мс, а среднее остается ~1.2мс.
            tiny_share = hist[0] / len(iv)
            mean_iv = statistics.fmean(iv)
            rep["batching"] = (use_raw and len(iv) > 100
                               and tiny_share > 0.30 and 0.7 <= mean_iv <= 1.6)
        # дребезг: повторный даун той же кнопки быстрее 12 мс
        chatter = 0
        last: dict[str, int] = {}
        for b, t in self.clicks:
            if b in last and _diff(last[b], t) < 12:
                chatter += 1
            last[b] = t
        rep["chatter"] = chatter
        if self.keys:
            top = Counter(vk for vk, _ in self.keys).most_common(3)
            rep["top_keys"] = [(vk_name(vk), n) for vk, n in top]
        return rep

    @staticmethod
    def _ll_intervals(ticks: list[int]) -> list[float]:
        return [d for a, b in zip(ticks, ticks[1:])
                if (d := _diff(a, b)) > 0]

    @staticmethod
    def _intervals(ticks: list[int]) -> list[float]:
        # Совместимость: если прилетят старые мс-тики — как раньше.
        return InputTester._ll_intervals(ticks)

    def report_text(self) -> str:
        r = self.report()
        lines = [f"движений: {r['moves']}, кликов Л/П: {r['clicks_L']}/{r['clicks_R']}, "
                 f"клавиш: {r['keys']}"]
        if r["poll_hz"] is None:
            lines.append("мышь/стилус не двигались - polling rate не измерен")
        else:
            src = "Raw Input" if r.get("raw") else "LL-хук (неточно)"
            lines.append(f"polling rate: ~{r['poll_hz']} Гц "
                         f"(событий: {r['moves']} за {r.get('span_s', '?')} с, {src}"
                         + (f", <1мс: {r['sub_ms_pct']}%" if r.get("sub_ms_pct") is not None else "") + ")")
            if r.get("burst_hz"):
                lines.append(f"пик девайса: ~{r['burst_hz']} событий/с в лучшую секунду")
            if "interval_med_ms" in r:
                lines.append(f"интервалы: медиана {r['interval_med_ms']} мс, "
                             f"среднее {r['interval_avg_ms']} мс, "
                             f"p95 {r.get('interval_p95_ms', '?')} мс, "
                             f"макс {r['interval_max_ms']} мс, "
                             f"джиттер {r['jitter_ms']} мс "
                             f"(чистый {r.get('jitter_clean_ms', '?')} мс, "
                             f"пауз >5мс: {r.get('pauses', 0)})")
            if r.get("hist"):
                h = r["hist"]
                lines.append(f"гистограмма: <0.5:{h[0]} 0.5-0.9:{h[1]} "
                             f"0.9-1.3:{h[2]} 1.3-2:{h[3]} 2-5:{h[4]} >5:{h[5]}")
            if r.get("batching"):
                lines.append("батчинг: репорты идут пачками (пары через ~0.2мс) — "
                             "это радиотракт 2.4ГГц, а не сенсор. Проверь свисток/провод")
            dev = max(r["poll_hz"], r.get("burst_hz") or 0)
            if r.get("batching"):
                # при батчинге пик/среднее занижены кучностью — классифицируем
                # по среднему интервалу: ~1.2мс это 1000 Гц с потерями доставки
                lines.append("похоже на 1000 Гц с потерями доставки (батчинг)")
            else:
                for ref, name in ((1000, "1000 Гц геймерская"),
                                  (500, "500 Гц"), (250, "250 Гц"), (125, "офисная 125 Гц")):
                    if dev >= ref * 0.9:
                        lines.append(f"похоже на {name}")
                        break
            if not r.get("raw"):
                lines.append("внимание: Raw Input не завелся, замер через LL-хук занижает частоту")
        lines.append("дребезг кнопок: " +
                     ("ЧИСТО" if r["chatter"] == 0 else f"{r['chatter']} подозрительных даблов!"))
        if "top_keys" in r:
            lines.append("частые клавиши: " + ", ".join(f"{k}x{n}" for k, n in r["top_keys"]))
        return "\n".join(lines)
