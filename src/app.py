"""
Main application controller for Clipy Windows.
Coordinates storage, clipboard monitoring, hotkeys, tray, and UI.
"""
import sys
import threading
import tkinter as tk

from .storage import Storage
from .clipboard_monitor import ClipboardMonitor
from .hotkeys import HotkeyManager
from .ui.tray import TrayIcon
from .ui.popup import PopupMenu


class ClipyApp:
    def __init__(self):
        self.storage = Storage()

        # Hidden root window — all Toplevel dialogs are children of this
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title('Clipy for Windows')
        self.root.protocol('WM_DELETE_WINDOW', self.quit)

        # Core UI
        self.popup = PopupMenu(self.root, self.storage, self._paste_content)

        # Backend services
        self.clipboard_monitor = ClipboardMonitor(self.storage)
        self.hotkey_manager = HotkeyManager(
            self.storage,
            show_all_cb=self.show_popup,
            show_history_cb=self.show_popup_history,
            show_snippets_cb=self.show_popup_snippets,
            open_editor_cb=self.open_snippet_editor,
        )
        self.tray = TrayIcon(self)

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def run(self):
        self.clipboard_monitor.start()
        self.hotkey_manager.start()
        threading.Thread(target=self.tray.run, daemon=True, name='TrayIcon').start()
        self.root.mainloop()

    def quit(self):
        self.clipboard_monitor.stop()
        self.hotkey_manager.stop()
        try:
            self.tray.stop()
        except Exception:
            pass
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass
        sys.exit(0)

    # ── Actions (thread-safe via root.after) ──────────────────────────────

    def show_popup(self):
        """Show both history + snippets"""
        self.root.after(0, lambda: self.popup.show(mode='all'))

    def show_popup_history(self):
        """Show history only"""
        self.root.after(0, lambda: self.popup.show(mode='history'))

    def show_popup_snippets(self):
        """Show snippets only"""
        self.root.after(0, lambda: self.popup.show(mode='snippets'))

    def open_settings(self):
        from .ui.settings import SettingsDialog
        self.root.after(0, lambda: SettingsDialog(self.root, self.storage, self.hotkey_manager))

    def open_snippet_editor(self):
        from .ui.snippet_editor import SnippetEditor
        self.root.after(0, lambda: SnippetEditor(self.root, self.storage))

    def clear_history(self):
        self.storage.clear_history()

    # ── Paste logic ────────────────────────────────────────────────────────

    def _paste_content(self, content: str, source_id=None, source_type='clip'):
        """
        After popup closes, copy `content` to clipboard and send Ctrl+V
        to whichever window was previously focused.
        """
        def _do():
            import time
            import pyperclip
            import keyboard

            # Tell the monitor this is our own copy so it isn't re-recorded
            self.clipboard_monitor.notify_copied(content)
            pyperclip.copy(content)
            time.sleep(0.08)   # Let the popup fully close & focus restore
            keyboard.send('ctrl+v')

            if source_type == 'snippet' and source_id is not None:
                self.storage.increment_snippet_usage(source_id)

        threading.Thread(target=_do, daemon=True).start()
