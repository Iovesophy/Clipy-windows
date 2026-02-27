"""
Monitors the Windows clipboard for changes and stores new text clips.
"""
import threading
import time


class ClipboardMonitor:
    INTERVAL = 0.4  # seconds between polls

    def __init__(self, storage):
        self.storage = storage
        self._thread: threading.Thread | None = None
        self._running = False
        self._last = ''

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name='ClipboardMonitor')
        self._thread.start()

    def stop(self):
        self._running = False

    def _read_clipboard(self) -> str:
        """Read text from clipboard using win32 API for reliability."""
        try:
            import win32clipboard
            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                    return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            pass
        # Fallback to pyperclip
        try:
            import pyperclip
            return pyperclip.paste() or ''
        except Exception:
            return ''

    def _run(self):
        try:
            self._last = self._read_clipboard()
        except Exception:
            self._last = ''

        while self._running:
            try:
                current = self._read_clipboard()
                if current and current != self._last:
                    self._last = current
                    self.storage.add_clip(current)
            except Exception:
                pass
            time.sleep(self.INTERVAL)

    def notify_copied(self, text: str):
        """Call this when Clipy itself copies to clipboard so we can skip it."""
        self._last = text
