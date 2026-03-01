"""
Global hotkey registration for Clipy Windows.
Uses the `keyboard` library for system-wide hotkeys.

Three independent hotkeys:
  hotkey_main     — show history + snippets  (default: Ctrl+Shift+V)
  hotkey_history  — show history only        (default: Ctrl+Shift+H)
  hotkey_snippets — show snippets only       (default: Ctrl+Shift+S)
  hotkey_editor   — open snippet editor      (default: Ctrl+Shift+E)
"""


class HotkeyManager:
    def __init__(self, storage, show_all_cb, show_history_cb, show_snippets_cb, open_editor_cb=None):
        self.storage = storage
        self._cb_all      = show_all_cb
        self._cb_history  = show_history_cb
        self._cb_snippets = show_snippets_cb
        self._cb_editor   = open_editor_cb
        self._ids: list = []
        self._running = False

    def start(self):
        self._running = True
        self._register()

    def stop(self):
        self._running = False
        self._unregister()

    def reload(self):
        if self._running:
            self._register()

    # ── Internal ──────────────────────────────────────────────────────────

    def _register(self):
        self._unregister()
        import keyboard

        pairs = [
            ('hotkey_main',     'ctrl+shift+v', self._cb_all),
            ('hotkey_history',  'ctrl+shift+h', self._cb_history),
            ('hotkey_snippets', 'ctrl+shift+s', self._cb_snippets),
            ('hotkey_editor',   'ctrl+shift+e', self._cb_editor),
        ]
        for key, default, cb in pairs:
            hk = self.storage.get_setting(key, default).strip()
            if not hk:
                continue
            try:
                hid = keyboard.add_hotkey(hk, cb, suppress=True)
                self._ids.append(hid)
            except Exception as e:
                print(f'[Clipy] Failed to register hotkey "{hk}" ({key}): {e}')

    def _unregister(self):
        import keyboard
        for hid in self._ids:
            try:
                keyboard.remove_hotkey(hid)
            except Exception:
                pass
        self._ids.clear()

    # ── Accessors ─────────────────────────────────────────────────────────

    def get(self, key: str) -> str:
        defaults = {
            'hotkey_main':     'ctrl+shift+v',
            'hotkey_history':  'ctrl+shift+h',
            'hotkey_snippets': 'ctrl+shift+s',
            'hotkey_editor':   'ctrl+shift+e',
        }
        return self.storage.get_setting(key, defaults.get(key, ''))
