"""Трей-иконка."""
import threading
try:
    import pystray
    from PIL import Image, ImageDraw
    _OK = True
except ImportError:
    _OK = False

def _icon_image():
    img = Image.new("RGB", (64, 64), "black")
    d = ImageDraw.Draw(img)
    d.rectangle([6, 6, 57, 57], outline="lime", width=5)
    d.line([16, 44, 32, 20, 48, 44], fill="lime", width=5, joint="curve")
    return img

class TrayController:
    def __init__(self, on_toggle_overlay, on_quit,
                 on_open_dashboard=None, on_input_test=None,
                 on_select_profile=None, on_apply_now=None,
                 on_add_config=None, get_current_profile=None):
        self._on_toggle = on_toggle_overlay
        self._on_quit = on_quit
        self._on_dash = on_open_dashboard
        self._on_input = on_input_test
        self.on_select_profile = on_select_profile
        self.on_apply_now = on_apply_now
        self.on_add_config = on_add_config
        self.get_current_profile = get_current_profile
        self._icon = None
        self._t = threading.Thread(target=self._run, daemon=True)

    @staticmethod
    def available():
        return _OK

    def start(self):
        if _OK:
            self._t.start()

    def _run(self):
        def toggle(icon, item): self._on_toggle()
        def quit_(icon, item): self._on_quit()

        def make_selector(name):
            def select(icon, item):
                if self.on_select_profile:
                    self.on_select_profile(name)
            return select

        def apply(icon, item):
            if self.on_apply_now:
                self.on_apply_now()

        def add_cfg(icon, item):
            if self.on_add_config:
                self.on_add_config()

        items = [pystray.MenuItem("Показать/скрыть оверлей", toggle)]
        if self._on_dash:
            items.append(pystray.MenuItem("Открыть дашборд",
                lambda icon, item: self._on_dash()))
        # Профили оптимизатора — отдельные пункты
        if self.on_select_profile:
            for name in ("default", "performance", "aggressive"):
                items.append(pystray.MenuItem(
                    f"Опт: {name}",
                    make_selector(name),
                    checked=self.get_current_profile and
                            (lambda n=name: self.get_current_profile() == n)
                ))
        # Применить сейчас
        if self.on_apply_now:
            items.append(pystray.MenuItem("Применить оптимизацию сейчас", apply))
        # Добавить в конфиг
        if self.on_add_config:
            items.append(pystray.MenuItem("Добавить процесс в конфиг", add_cfg))
        if self._on_input:
            items.append(pystray.MenuItem("Тест инпута (osu!)",
                lambda icon, item: self._on_input()))
        items.append(pystray.MenuItem("Выход", quit_))
        self._icon = pystray.Icon("GHub", _icon_image(), "GHub",
            menu=pystray.Menu(*items))
        self._icon.run()

    def stop(self):
        try:
            if self._icon:
                self._icon.stop()
        except Exception:
            pass
