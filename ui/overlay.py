"""Внешний topmost-оверлей, только цифры. Без инжекта - безопасно для античита."""
import queue
import threading
import tkinter as tk


class Overlay:
    def __init__(self):
        self._text = "GHub: ожидание игры..."
        self._stop = threading.Event()
        self._visible = True
        self._tasks: queue.Queue = queue.Queue()  # колбэки для Tk-потока
        self._t = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._t.start()

    def stop(self):
        self._stop.set()

    def update(self, line: str):
        self._text = line

    def toggle(self):
        self._visible = not self._visible

    def run_in_ui(self, fn) -> None:
        """Выполнить fn в Tk-потоке (создание окон и т.п.)."""
        self._tasks.put(fn)

    def _run(self):
        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.85)
        root.geometry("+20+20")
        try:  # окно не забирает фокус: клики/драг не делают GHub активным окном
            import ctypes
            hwnd = root.winfo_id()
            GWL_EXSTYLE, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW = -20, 0x08000000, 0x80
            get = ctypes.windll.user32.GetWindowLongW
            set_ = ctypes.windll.user32.SetWindowLongW
            ex = get(hwnd, GWL_EXSTYLE)
            set_(hwnd, GWL_EXSTYLE, ex | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
        except Exception:
            pass
        label = tk.Label(root, text=self._text, font=("Consolas", 11),
                         bg="black", fg="lime", justify="left", padx=8, pady=6)
        label.pack()
        # drag
        def start_move(e):
            root._x, root._y = e.x, e.y
        def move(e):
            root.geometry(f"+{root.winfo_x() + e.x - root._x}+{root.winfo_y() + e.y - root._y}")
        label.bind("<Button-1>", start_move)
        label.bind("<B1-Motion>", move)

        def tick():
            if self._stop.is_set():
                root.destroy()
                return
            while True:
                try:
                    fn = self._tasks.get_nowait()
                except queue.Empty:
                    break
                try:
                    fn(root)
                except Exception:
                    pass
            if self._visible:
                try:
                    if not root.winfo_viewable():
                        root.deiconify()
                except tk.TclError:
                    pass
            else:
                try:
                    if root.winfo_viewable():
                        root.withdraw()
                except tk.TclError:
                    pass
            label.config(text=self._text)
            root.after(500, tick)
        tick()
        root.mainloop()
