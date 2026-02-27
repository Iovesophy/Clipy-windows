"""
Settings dialog for Clipy Windows.
"""
import tkinter as tk
from tkinter import ttk, messagebox


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, storage, hotkey_manager):
        super().__init__(parent)
        self.storage = storage
        self.hotkey_manager = hotkey_manager
        self.title('Clipy Settings')
        self.resizable(False, False)
        self.grab_set()
        self.attributes('-topmost', True)

        theme = storage.get_setting('theme', 'dark')
        if theme == 'dark':
            self.bg, self.fg, self.entry_bg = '#1e1e1e', '#eeeeee', '#2d2d2d'
            self.btn_bg, self.btn_fg = '#0078d4', '#ffffff'
        else:
            self.bg, self.fg, self.entry_bg = '#f5f5f5', '#1a1a1a', '#ffffff'
            self.btn_bg, self.btn_fg = '#0078d4', '#ffffff'

        self.configure(bg=self.bg)
        self._build()
        self._center()

    def _center(self):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f'{w}x{h}+{(sw-w)//2}+{(sh-h)//2}')

    def _label(self, parent, text):
        tk.Label(parent, text=text, bg=self.bg, fg=self.fg,
                 font=('Segoe UI', 10), anchor='w').pack(anchor='w', pady=(8, 2))

    def _entry(self, parent, var):
        e = tk.Entry(parent, textvariable=var, bg=self.entry_bg, fg=self.fg,
                     insertbackground=self.fg, font=('Segoe UI', 10),
                     relief=tk.FLAT, bd=4, width=32)
        e.pack(anchor='w', pady=(0, 4))
        return e

    def _build(self):
        pad = dict(padx=20, pady=6)
        outer = tk.Frame(self, bg=self.bg)
        outer.pack(fill=tk.BOTH, expand=True, **pad)

        # Title
        tk.Label(outer, text='Clipy Settings', bg=self.bg, fg=self.fg,
                 font=('Segoe UI', 14, 'bold')).pack(anchor='w', pady=(0, 12))

        # ── Hotkeys ──────────────────────────────────────────────────────
        hk_frame = tk.Frame(outer, bg=self.bg)
        hk_frame.pack(fill=tk.X, pady=(4, 0))

        for col, (label, key, default, color) in enumerate([
            ('History + Snippets',  'hotkey_main',     'ctrl+shift+v', '#0078d4'),
            ('History Only',        'hotkey_history',  'ctrl+shift+h', '#107c10'),
            ('Snippets Only',       'hotkey_snippets', 'ctrl+shift+s', '#8764b8'),
        ]):
            cell = tk.Frame(hk_frame, bg=self.bg)
            cell.grid(row=0, column=col, padx=(0, 12), sticky='w')
            badge = tk.Frame(cell, bg=color)
            badge.pack(anchor='w', pady=(0, 3))
            tk.Label(badge, text=f'  {label}  ', bg=color, fg='#ffffff',
                     font=('Segoe UI', 9, 'bold')).pack()
            var = tk.StringVar(value=self.storage.get_setting(key, default))
            setattr(self, f'_hk_{key}', var)
            tk.Entry(cell, textvariable=var, bg=self.entry_bg, fg=self.fg,
                     insertbackground=self.fg, font=('Segoe UI', 10),
                     relief=tk.FLAT, bd=4, width=16).pack()

        tk.Label(outer, text='Example: ctrl+shift+v  /  alt+v  /  ctrl+`  　Empty=disabled',
                 bg=self.bg, fg='#888888', font=('Segoe UI', 8)).pack(anchor='w', pady=(4, 0))

        # ── Max history ──────────────────────────────────────────────────
        self._label(outer, 'Max history count:')
        self._hist_var = tk.StringVar(value=self.storage.get_setting('max_history', '100'))
        self._entry(outer, self._hist_var)

        # ── Theme ────────────────────────────────────────────────────────
        self._label(outer, 'Theme:')
        self._theme_var = tk.StringVar(value=self.storage.get_setting('theme', 'dark'))
        rf = tk.Frame(outer, bg=self.bg)
        rf.pack(anchor='w')
        for val, text in (('dark', 'Dark'), ('light', 'Light')):
            tk.Radiobutton(rf, text=text, variable=self._theme_var, value=val,
                           bg=self.bg, fg=self.fg, selectcolor=self.bg,
                           activebackground=self.bg, activeforeground=self.fg,
                           font=('Segoe UI', 10)).pack(side=tk.LEFT, padx=(0, 12))

        # ── Start with Windows ───────────────────────────────────────────
        self._startup_var = tk.BooleanVar(
            value=self.storage.get_setting('start_with_windows', 'false') == 'true'
        )
        tk.Checkbutton(
            outer, text='Start with Windows',
            variable=self._startup_var,
            bg=self.bg, fg=self.fg, selectcolor=self.bg,
            activebackground=self.bg, activeforeground=self.fg,
            font=('Segoe UI', 10),
        ).pack(anchor='w', pady=(8, 0))

        # ── Usage counts ─────────────────────────────────────────────────
        uf = tk.Frame(outer, bg=self.bg)
        uf.pack(anchor='w', pady=(10, 0), fill=tk.X)
        tk.Label(uf, text='Snippet usage counts (used for folder ordering):',
                 bg=self.bg, fg=self.fg, font=('Segoe UI', 10)).pack(anchor='w')
        tk.Button(uf, text='Reset Usage Counts', command=self._reset_usage,
                  bg=self.entry_bg, fg=self.fg, relief=tk.FLAT,
                  padx=10, pady=4, font=('Segoe UI', 9),
                  cursor='hand2').pack(anchor='w', pady=(4, 0))

        # ── Buttons ──────────────────────────────────────────────────────
        tk.Frame(outer, bg='#3a3a3a' if self.bg == '#1e1e1e' else '#d0d0d0',
                 height=1).pack(fill=tk.X, pady=(16, 8))
        bf = tk.Frame(outer, bg=self.bg)
        bf.pack(anchor='e')
        tk.Button(bf, text='Cancel', command=self.destroy,
                  bg=self.entry_bg, fg=self.fg, relief=tk.FLAT,
                  padx=14, pady=6, font=('Segoe UI', 10),
                  cursor='hand2').pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(bf, text='Save', command=self._save,
                  bg=self.btn_bg, fg=self.btn_fg, relief=tk.FLAT,
                  padx=14, pady=6, font=('Segoe UI', 10, 'bold'),
                  cursor='hand2').pack(side=tk.LEFT)

    def _reset_usage(self):
        if messagebox.askyesno('Confirm', 'Reset all snippet usage counts to zero?\nFolder ordering will revert to alphabetical.', parent=self):
            self.storage.reset_usage_counts()
            messagebox.showinfo('Done', 'Usage counts reset.', parent=self)

    def _save(self):
        try:
            n = int(self._hist_var.get())
            assert 1 <= n <= 10000
        except Exception:
            messagebox.showerror('Error', 'Max history count must be an integer between 1 and 10000.', parent=self)
            return

        # At least one hotkey must be set
        hk_main     = getattr(self, '_hk_hotkey_main',     None)
        hk_history  = getattr(self, '_hk_hotkey_history',  None)
        hk_snippets = getattr(self, '_hk_hotkey_snippets', None)

        # Save all three hotkeys (empty string = disabled)
        for key in ('hotkey_main', 'hotkey_history', 'hotkey_snippets'):
            var = getattr(self, f'_hk_{key}', None)
            if var is not None:
                self.storage.set_setting(key, var.get().strip().lower())

        self.storage.set_setting('max_history', str(n))
        self.storage.set_setting('theme', self._theme_var.get())
        startup = self._startup_var.get()
        self.storage.set_setting('start_with_windows', 'true' if startup else 'false')
        self.storage.apply_startup(startup)
        self.hotkey_manager.reload()
        messagebox.showinfo('Saved', 'Settings saved successfully.\nTheme changes will take effect on next popup display.', parent=self)
        self.destroy()
