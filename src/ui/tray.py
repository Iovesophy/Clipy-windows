"""
System tray icon for Clipy Windows.
"""
import pystray
from PIL import Image, ImageDraw


def _make_icon(size: int = 64) -> Image.Image:
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Clipboard body
    margin = size // 8
    clip_h = size // 8
    body_top = size // 6
    d.rounded_rectangle(
        [margin, body_top, size - margin, size - margin],
        radius=size // 12,
        fill='#4A90E2',
    )

    # Clip (top bar)
    clip_w = size // 3
    cx = size // 2
    d.rounded_rectangle(
        [cx - clip_w // 2, margin - clip_h // 2, cx + clip_w // 2, body_top + clip_h // 2],
        radius=size // 14,
        fill='#1a5fa8',
    )

    # Lines representing text
    lm = margin + size // 8
    rm = size - margin - size // 8
    line_color = 'white'
    line_h = max(2, size // 20)
    for row, (x2, y_off) in enumerate([(rm, 0), (rm - size // 8, 1), (rm, 2), (rm - size // 6, 3)]):
        y = body_top + size // 5 + row * (line_h + size // 14)
        d.rectangle([lm, y, x2, y + line_h], fill=line_color)

    return img


class TrayIcon:
    def __init__(self, app):
        self.app = app
        self._icon: pystray.Icon | None = None

    def run(self):
        img = _make_icon()
        menu = pystray.Menu(
            pystray.MenuItem('Clipy for Windows', None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Show Clipboard History', self._show_popup, default=True),
            pystray.MenuItem('Snippet Manager', self._open_snippets),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Settings', self._open_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Clear History', self._clear_history),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Quit', self._quit),
        )
        self._icon = pystray.Icon('Clipy', img, 'Clipy for Windows', menu=menu)
        self._icon.run()

    def stop(self):
        if self._icon:
            self._icon.stop()

    def _show_popup(self, *_):
        self.app.show_popup()

    def _open_snippets(self, *_):
        self.app.open_snippet_editor()

    def _open_settings(self, *_):
        self.app.open_settings()

    def _clear_history(self, *_):
        self.app.clear_history()

    def _quit(self, *_):
        self.app.quit()
