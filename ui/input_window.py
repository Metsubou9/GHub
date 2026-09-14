"""Окно теста инпута: открывается из трея, живет в Tk-потоке оверлея."""
import tkinter as tk
from tkinter import ttk

from modules.input_tester.tester import InputTester


def create_input_window(root: tk.Tk) -> None:
    for w in root.winfo_children():
        if getattr(w, "_ghub_input_win", False):
            w.deiconify()
            w.lift()
            return
    win = tk.Toplevel(root)
    win._ghub_input_win = True
    win.title("GHub - тест инпута")
    win.geometry("460x380+100+100")
    win.attributes("-topmost", True)

    tester = InputTester()
    state = {"running": False}

    tk.Label(win, text="Двигай мышью/стилусом, кликай, жми клавиши.\n"
                       "Замер 10 секунд.", justify="left").pack(pady=6)
    bar = ttk.Progressbar(win, length=400, maximum=10)
    bar.pack(pady=4)
    status = tk.Label(win, text="готов")
    status.pack()
    out = tk.Text(win, height=12, width=54, font=("Consolas", 10))
    out.pack(pady=6, padx=8)

    def poll():
        if not state["running"]:
            return
        el = tester.elapsed()
        bar["value"] = min(el, 10)
        live = (f"движений: {len(tester.moves)}  "
                f"клики Л/П: {sum(1 for b, _ in tester.clicks if b == 'L')}/"
                f"{sum(1 for b, _ in tester.clicks if b == 'R')}  "
                f"клавиш: {len(tester.keys)}")
        status.config(text=f"замер... {el:.1f}с   {live}")
        if tester.done.is_set():
            state["running"] = False
            btn.config(state="normal")
            out.delete("1.0", "end")
            out.insert("end", tester.report_text())
            r = tester.report()
            if r["moves"] == 0:
                out.insert("end", "\n\nподсказка: движений не увидел - "
                                  "подвигай мышью во время замера")
            status.config(text="готово")
            return
        win.after(150, poll)

    def on_start():
        if state["running"]:
            return
        tester.start(10)
        state["running"] = True
        btn.config(state="disabled")
        out.delete("1.0", "end")
        bar["value"] = 0
        win.after(150, poll)

    btn = tk.Button(win, text="Старт (10 сек)", command=on_start)
    btn.pack(pady=4)
