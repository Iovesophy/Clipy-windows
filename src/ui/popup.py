"""
Popup menu — the main Clipy UI.

Layout (monochrome flat design):
  ┌─────────────────────────────┐
  │ History + Snippets          │ ← thin mode bar
  │ Search...                   │
  ├─────────────────────────────┤
  │ CLIPBOARD HISTORY           │
  │  ◦ item 1  (selected)       │
  │    item 2                   │
  ├─────────────────────────────┤
  │ SNIPPETS                    │
  │  root_snippet               │
  │  Folder A               ▶   │ ← hover → submenu flies out to the right
  └─────────────────────────────┘
      ↓ hover on folder
  ┌─────────────────────────────┐
  │ Folder A                    │
  │  snippet 1                  │
  │  snippet 2                  │
  └─────────────────────────────┘
"""

import tkinter as tk

# ── Monochrome flat themes ─────────────────────────────────────────────────────
DARK = dict(
    bg='#1e1e1e',        fg='#dddddd',
    header_bg='#252525', header_fg='#666666',
    select_bg='#333333', select_fg='#ffffff',
    hover_bg='#2a2a2a',
    search_bg='#252525', search_fg='#cccccc', search_cursor='#cccccc',
    border='#333333',
    footer_bg='#191919', footer_fg='#444444',
    folder_fg='#888888',
    mode_bg='#252525',   mode_fg='#555555',
    sub_bg='#1e1e1e',    sub_border='#3a3a3a',
)
LIGHT = dict(
    bg='#ffffff',        fg='#1a1a1a',
    header_bg='#f0f0f0', header_fg='#555555',
    select_bg='#daeeff', select_fg='#000000',
    hover_bg='#eef6ff',
    search_bg='#f8f8f8', search_fg='#1a1a1a', search_cursor='#1a1a1a',
    border='#d0d0d0',
    footer_bg='#f5f5f5', footer_fg='#777777',
    folder_fg='#444444',
    mode_bg='#f0f0f0',   mode_fg='#555555',
    sub_bg='#ffffff',    sub_border='#c0c0c0',
)

WIN_W, WIN_H = 380, 500
SUB_W = 240          # submenu width
MAX_DISPLAY = 75     # chars per item line
HOVER_DELAY  = 140   # ms before submenu appears
LEAVE_DELAY  = 250   # ms before submenu closes
CONTENT_DELAY = 400  # ms before content appears

class _Entry:
    __slots__ = ('kind', 'item_id', 'label', 'content')

    def __init__(self, kind, item_id=None, label='', content=''):
        self.kind    = kind       # 'header' | 'folder' | 'clip' | 'snippet'
        self.item_id = item_id
        self.label   = label
        self.content = content

    @property
    def selectable(self):
        return self.kind in ('clip', 'snippet')


class PopupMenu:
    def __init__(self, root: tk.Tk, storage, paste_callback):
        self.root           = root
        self.storage        = storage
        self.paste_callback = paste_callback

        self._win:  tk.Toplevel | None = None
        self._sub:  tk.Toplevel | None = None   # folder submenu
        self._sub_folder_id: int | None = None

        self._entries:    list[_Entry] = []
        self._row_frames: list[tuple]  = []
        self._sel = -1

        self._search_var  = tk.StringVar()
        self._after_search = None
        self._hover_timer  = None
        self._leave_timer  = None
        self._C: dict = {}
        self._mode = 'all'
        self._tooltip      = None
        self._tooltip_after = None

    # ── Public ────────────────────────────────────────────────────────────

    def show(self, mode: str = 'all'):
        self._mode = mode
        if self._win and self._win.winfo_exists():
            if getattr(self, '_current_mode', None) != mode:
                self.hide()
            else:
                self._win.lift()
                self._win.focus_force()
                return
        self._build_window()

    def hide(self):
        self._close_sub()
        if self._win and self._win.winfo_exists():
            self._win.destroy()
        self._win = None

    # ── Window construction ────────────────────────────────────────────────

    def _build_window(self):
        theme = self.storage.get_setting('theme', 'dark')
        self._C = DARK if theme == 'dark' else LIGHT
        C = self._C
        self._current_mode = self._mode

        win = tk.Toplevel(self.root)
        self._win = win
        win.withdraw()
        win.overrideredirect(True)
        win.attributes('-topmost', True)
        win.configure(bg=C['border'])

        # ── Position ──────────────────────────────────────────────────────
        scr_w = win.winfo_screenwidth()
        scr_h = win.winfo_screenheight()
        px, py = self.root.winfo_pointerx(), self.root.winfo_pointery()
        x = max(4, min(px, scr_w - WIN_W - 4))
        y = max(4, min(py, scr_h - WIN_H - 48))
        win.geometry(f'{WIN_W}x{WIN_H}+{x}+{y}')

        outer = tk.Frame(win, bg=C['bg'])
        outer.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # ── Mode bar (minimal, monochrome) ────────────────────────────────
        mode_label = {
            'all':      'History + Snippets',
            'history':  'Clipboard History',
            'snippets': 'Snippets',
        }.get(self._mode, '')
        mb = tk.Frame(outer, bg=C['mode_bg'], padx=10, pady=4)
        mb.pack(fill=tk.X)
        tk.Label(mb, text=mode_label, bg=C['mode_bg'], fg=C['mode_fg'],
                 font=('Segoe UI', 8)).pack(side=tk.LEFT)

        # ── Search bar ────────────────────────────────────────────────────
        sf = tk.Frame(outer, bg=C['search_bg'], padx=8, pady=6)
        sf.pack(fill=tk.X)
        tk.Label(sf, text='Search', bg=C['search_bg'], fg=C['mode_fg'],
                 font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(0, 6))
        self._search_var.set('')
        self._search_entry = tk.Entry(
            sf, textvariable=self._search_var,
            bg=C['search_bg'], fg=C['search_fg'],
            insertbackground=C['search_cursor'],
            font=('Segoe UI', 11), relief=tk.FLAT, bd=0,
        )
        self._search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._search_entry.focus_set()
        tk.Frame(outer, bg=C['border'], height=1).pack(fill=tk.X)

        # ── Scrollable list ───────────────────────────────────────────────
        lc = tk.Frame(outer, bg=C['bg'])
        lc.pack(fill=tk.BOTH, expand=True)
        self._canvas = tk.Canvas(lc, bg=C['bg'], highlightthickness=0, bd=0)
        sb = tk.Scrollbar(lc, orient=tk.VERTICAL, command=self._canvas.yview)
        self._inner = tk.Frame(self._canvas, bg=C['bg'])
        self._inner.bind('<Configure>',
                         lambda e: self._canvas.configure(
                             scrollregion=self._canvas.bbox('all')))
        self._cw = self._canvas.create_window((0, 0), window=self._inner, anchor='nw')
        self._canvas.configure(yscrollcommand=sb.set)
        self._canvas.bind('<Configure>', lambda e: self._canvas.itemconfig(self._cw, width=e.width))
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        # ── Footer ────────────────────────────────────────────────────────
        tk.Frame(outer, bg=C['border'], height=1).pack(fill=tk.X)
        foot = tk.Frame(outer, bg=C['footer_bg'], padx=8, pady=3)
        foot.pack(fill=tk.X)
        tk.Label(foot, text='↑↓  Enter/Click: Paste   Esc: Close',
                 bg=C['footer_bg'], fg=C['footer_fg'], font=('Segoe UI', 8)).pack()

        # ── Bindings ─────────────────────────────────────────────────────
        for w in (win, self._search_entry):
            w.bind('<Escape>', lambda e: self.hide())
            w.bind('<Up>',     lambda e: self._move(-1))
            w.bind('<Down>',   lambda e: self._move(1))
            w.bind('<Return>', lambda e: self._activate())
        win.bind('<MouseWheel>',
                 lambda e: self._canvas.yview_scroll(-1 * (e.delta // 120), 'units'))
        win.bind('<FocusOut>', self._on_focus_out)
        self._search_var.trace_add('write', lambda *_: self._schedule_search())

        self._load_items()
        win.deiconify()
        win.lift()
        win.focus_force()

    # ── Focus handling ────────────────────────────────────────────────────

    def _on_focus_out(self, _event=None):
        self.root.after(120, self._check_focus)

    def _check_focus(self):
        try:
            if not (self._win and self._win.winfo_exists()):
                return
            focused = self._win.focus_get()
            # Keep open if focus is inside main popup or submenu
            if focused is not None:
                fs = str(focused)
                if fs.startswith(str(self._win)):
                    return
                if self._sub and self._sub.winfo_exists() and fs.startswith(str(self._sub)):
                    return
            self.hide()
        except Exception:
            self.hide()

    # ── Item loading ──────────────────────────────────────────────────────

    def _schedule_search(self):
        if self._after_search:
            self.root.after_cancel(self._after_search)
        self._after_search = self.root.after(120, self._load_items)

    def _load_items(self):
        self._close_sub()
        for w in self._inner.winfo_children():
            w.destroy()
        self._entries = []
        self._row_frames = []
        self._sel = -1

        search = self._search_var.get().strip() or None
        C = self._C
        mode = self._mode

        # ── History ───────────────────────────────────────────────────────
        if mode in ('all', 'history'):
            clips = self.storage.get_clips(search=search)
            if clips:
                self._add_section('CLIPBOARD HISTORY')
                for clip in clips:
                    text = clip['content'][:MAX_DISPLAY].replace('\n', ' ').strip()
                    if len(clip['content']) > MAX_DISPLAY:
                        text += '…'
                    self._add_row(_Entry('clip', clip['id'], text, clip['content']))

        # ── Snippets ─────────────────────────────────────────────────────
        if mode in ('all', 'snippets'):
            if search:
                snips = self.storage.get_snippets(search=search)
                if snips:
                    self._add_section('SNIPPETS')
                    for s in snips:
                        self._add_row(_Entry('snippet', s['id'], s['title'], s['content']))
            else:
                folders = self.storage.get_folders_by_usage()
                if folders:
                    self._add_section('SNIPPETS')
                    for folder in folders:
                        # Only show folder if it has snippets
                        if self.storage.get_snippets(folder_id=folder['id']):
                            self._add_folder_row(folder['id'], folder['name'])

        if not self._entries:
            msg = 'No results found' if search else (
                'Clipboard is empty' if mode in ('all', 'history') else
                'No snippets registered'
            )
            tk.Label(self._inner, text=msg, bg=C['bg'], fg=C['header_fg'],
                     font=('Segoe UI', 10), pady=28).pack()
            return

        for i, e in enumerate(self._entries):
            if e.selectable:
                self._set_selection(i)
                break

    def _add_section(self, text: str):
        C = self._C
        f = tk.Frame(self._inner, bg=C['header_bg'], padx=10, pady=3)
        f.pack(fill=tk.X)
        tk.Label(f, text=text, bg=C['header_bg'], fg=C['header_fg'],
                 font=('Segoe UI', 8)).pack(anchor='w')
        self._entries.append(_Entry('header', label=text))
        self._row_frames.append((None, None))

    def _add_row(self, entry: _Entry):
        C   = self._C
        idx = len(self._entries)
        icon = '◦' if entry.kind == 'clip' else '·'
        f = tk.Frame(self._inner, bg=C['bg'], padx=10, pady=4, cursor='hand2')
        f.pack(fill=tk.X)
        lbl = tk.Label(
            f, text=f'{icon}  {entry.label}',
            bg=C['bg'], fg=C['fg'],
            font=('Segoe UI', 10), anchor='w',
            wraplength=WIN_W - 32, justify=tk.LEFT,
        )
        lbl.pack(anchor='w', fill=tk.X)
        for w in (f, lbl):
            w.bind('<Button-1>', lambda e, i=idx: self._on_click(i))
            w.bind('<Enter>',    lambda e, i=idx: self._on_hover(i))
            w.bind('<Leave>',    lambda e, i=idx: self._on_leave(i))
        self._entries.append(entry)
        self._row_frames.append((f, lbl))

    # ── Folder row (with ▶ and submenu on hover) ──────────────────────────

    def _add_folder_row(self, folder_id: int, name: str):
        C   = self._C
        idx = len(self._entries)
        f   = tk.Frame(self._inner, bg=C['bg'], padx=10, pady=4, cursor='hand2')
        f.pack(fill=tk.X)
        lbl = tk.Label(f, text=f'  {name}', bg=C['bg'], fg=C['folder_fg'],
                       font=('Segoe UI', 10), anchor='w')
        lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
        arrow = tk.Label(f, text='▶', bg=C['bg'], fg=C['folder_fg'],
                         font=('Segoe UI', 8))
        arrow.pack(side=tk.RIGHT)

        for w in (f, lbl, arrow):
            w.bind('<Enter>', lambda e, fid=folder_id, fn=name, fr=f:
                   self._folder_enter(fid, fn, fr))
            w.bind('<Leave>', lambda e, fr=f: self._folder_leave(fr))
            w.bind('<Button-1>', lambda e, fid=folder_id, fn=name, fr=f:
                   self._open_sub(fid, fn, fr))

        self._entries.append(_Entry('folder', folder_id, name))
        self._row_frames.append((f, lbl))

    # ── Submenu ───────────────────────────────────────────────────────────

    def _folder_enter(self, folder_id: int, name: str, frame):
        self._cancel_hover_timer()
        C = self._C
        frame.configure(bg=C['select_bg'])
        for child in frame.winfo_children():
            if isinstance(child, tk.Label):
                child.configure(bg=C['select_bg'], fg=C['fg'])
        self._hover_timer = self.root.after(
            HOVER_DELAY, lambda: self._open_sub(folder_id, name, frame)
        )

    def _folder_leave(self, frame=None):
        self._cancel_hover_timer()
        if frame:
            C = self._C
            frame.configure(bg=C['bg'])
            for child in frame.winfo_children():
                if isinstance(child, tk.Label):
                    child.configure(bg=C['bg'], fg=C['folder_fg'])
        self._leave_timer = self.root.after(LEAVE_DELAY, self._maybe_close_sub)

    def _maybe_close_sub(self):
        if not (self._sub and self._sub.winfo_exists()):
            return
        try:
            mx, my = self.root.winfo_pointerx(), self.root.winfo_pointery()
            sx, sy = self._sub.winfo_x(), self._sub.winfo_y()
            sw, sh = self._sub.winfo_width(), self._sub.winfo_height()
            if sx <= mx <= sx + sw and sy <= my <= sy + sh:
                return  # Mouse inside submenu — keep open
            # Also keep open if mouse is over the main popup
            if self._win and self._win.winfo_exists():
                wx, wy = self._win.winfo_x(), self._win.winfo_y()
                ww, wh = self._win.winfo_width(), self._win.winfo_height()
                if wx <= mx <= wx + ww and wy <= my <= wy + wh:
                    return
        except Exception:
            pass
        self._close_sub()

    def _open_sub(self, folder_id: int, name: str, frame):
        self._cancel_hover_timer()
        if self._sub_folder_id == folder_id and self._sub and self._sub.winfo_exists():
            return  # Already showing this folder's submenu
        self._close_sub()
        self._sub_folder_id = folder_id

        snippets = self.storage.get_snippets(folder_id=folder_id)
        if not snippets:
            return

        C = self._C
        sub = tk.Toplevel(self.root)
        self._sub = sub
        sub.withdraw()
        sub.overrideredirect(True)
        sub.attributes('-topmost', True)
        sub.configure(bg=C['sub_border'])

        outer = tk.Frame(sub, bg=C['bg'])
        outer.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Header
        hf = tk.Frame(outer, bg=C['header_bg'], padx=10, pady=4)
        hf.pack(fill=tk.X)
        tk.Label(hf, text=f'  {name}', bg=C['header_bg'], fg=C['folder_fg'],
                 font=('Segoe UI', 8)).pack(anchor='w')
        tk.Frame(outer, bg=C['border'], height=1).pack(fill=tk.X)

        # Scrollable snippet list
        SUB_MAX_H = 320
        lc = tk.Frame(outer, bg=C['bg'])
        lc.pack(fill=tk.BOTH, expand=True)
        sub_canvas = tk.Canvas(lc, bg=C['bg'], highlightthickness=0, bd=0)
        sb = tk.Scrollbar(lc, orient=tk.VERTICAL, command=sub_canvas.yview)
        inner = tk.Frame(sub_canvas, bg=C['bg'])
        inner.bind('<Configure>', lambda e: sub_canvas.configure(
            scrollregion=sub_canvas.bbox('all')))
        cw = sub_canvas.create_window((0, 0), window=inner, anchor='nw')
        sub_canvas.configure(yscrollcommand=sb.set)
        sub_canvas.bind('<Configure>', lambda e: sub_canvas.itemconfig(cw, width=e.width))

        for s in snippets:
            entry = _Entry('snippet', s['id'], s['title'], s['content'])
            self._add_sub_item(inner, entry, C)

        sub_canvas.update_idletasks()
        items_h = inner.winfo_reqheight()
        sub_canvas.configure(height=min(items_h, SUB_MAX_H))
        sub_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        if items_h > SUB_MAX_H:
            sb.pack(side=tk.RIGHT, fill=tk.Y)
        sub.bind('<MouseWheel>',
                 lambda e: sub_canvas.yview_scroll(-1 * (e.delta // 120), 'units'))

        # Position: to the right of the main popup at the folder row's y
        sub.update_idletasks()
        sub_h = sub.winfo_reqheight()
        scr_w = sub.winfo_screenwidth()
        scr_h = sub.winfo_screenheight()
        popup_x = self._win.winfo_x()
        popup_y = self._win.winfo_y()
        frame_y = frame.winfo_rooty()

        x = popup_x + WIN_W + 2
        if x + SUB_W > scr_w - 4:
            x = popup_x - SUB_W - 2   # Flip to left if no space
        y = frame_y
        if y + sub_h > scr_h - 40:
            y = scr_h - sub_h - 40
        y = max(y, 4)

        sub.geometry(f'{SUB_W}x{sub_h}+{x}+{y}')

        sub.bind('<Enter>', lambda e: self._cancel_leave_timer())
        sub.bind('<Leave>', lambda e: self._sub_leave())
        sub.bind('<Escape>', lambda e: self.hide())

        sub.deiconify()
        sub.lift()

    def _add_sub_item(self, parent, entry: _Entry, C: dict):
        f = tk.Frame(parent, bg=C['bg'], padx=10, pady=5, cursor='hand2')
        f.pack(fill=tk.X)
        lbl = tk.Label(f, text=f'  {entry.label}', bg=C['bg'], fg=C['fg'],
                       font=('Segoe UI', 10), anchor='w',
                       wraplength=SUB_W - 24)
        lbl.pack(anchor='w', fill=tk.X)
        for w in (f, lbl):
            w.bind('<Button-1>', lambda e, en=entry: self._sub_select(en))
            w.bind('<Enter>',    lambda e, fr=f, lb=lbl, ct=entry.content:
                   self._sub_item_enter(fr, lb, ct, C))
            w.bind('<Leave>',    lambda e, fr=f, lb=lbl:
                   self._sub_item_leave(fr, lb, C))

    def _sub_item_enter(self, frame, lbl, content: str, C: dict):
        frame.configure(bg=C['select_bg'])
        lbl.configure(bg=C['select_bg'], fg=C['select_fg'])
        self._schedule_tooltip(content, frame)

    def _sub_item_leave(self, frame, lbl, C: dict):
        frame.configure(bg=C['bg'])
        lbl.configure(bg=C['bg'], fg=C['fg'])
        self._hide_tooltip()

    # ── Tooltip ───────────────────────────────────────────────────────────

    def _schedule_tooltip(self, content: str, widget):
        self._hide_tooltip()
        self._tooltip_after = self.root.after(
            CONTENT_DELAY, lambda: self._show_tooltip(content, widget)
        )

    def _show_tooltip(self, content: str, widget):
        self._tooltip_after = None
        if not (self._sub and self._sub.winfo_exists()):
            return
        C = self._C

        # Build preview: max 8 lines, max 60 chars per line
        lines = content.split('\n')
        preview_lines = []
        for line in lines[:8]:
            preview_lines.append(line[:60] + ('…' if len(line) > 60 else ''))
        if len(lines) > 8:
            preview_lines.append('…')
        preview = '\n'.join(preview_lines)

        tip = tk.Toplevel(self.root)
        self._tooltip = tip
        tip.withdraw()
        tip.overrideredirect(True)
        tip.attributes('-topmost', True)
        tip.configure(bg=C['border'])

        inner = tk.Frame(tip, bg=C['header_bg'], padx=10, pady=8)
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        tk.Label(inner, text=preview, bg=C['header_bg'], fg=C['fg'],
                 font=('Segoe UI', 9), anchor='w', justify=tk.LEFT).pack(anchor='w')

        tip.update_idletasks()
        tip_w = tip.winfo_reqwidth()
        tip_h = tip.winfo_reqheight()
        scr_w = tip.winfo_screenwidth()
        scr_h = tip.winfo_screenheight()

        try:
            sub_x = self._sub.winfo_x()
            sub_w = self._sub.winfo_width()
            wy    = widget.winfo_rooty()
        except Exception:
            return

        x = sub_x + sub_w + 4
        if x + tip_w > scr_w - 4:
            x = sub_x - tip_w - 4
        y = wy
        if y + tip_h > scr_h - 40:
            y = scr_h - tip_h - 40
        y = max(y, 4)

        tip.geometry(f'{tip_w}x{tip_h}+{x}+{y}')
        tip.deiconify()
        tip.lift()

    def _hide_tooltip(self):
        if self._tooltip_after:
            self.root.after_cancel(self._tooltip_after)
            self._tooltip_after = None
        if self._tooltip and self._tooltip.winfo_exists():
            self._tooltip.destroy()
        self._tooltip = None

    def _sub_select(self, entry: _Entry):
        self._close_sub()
        self.hide()
        self.paste_callback(entry.content, source_id=entry.item_id, source_type=entry.kind)

    def _sub_leave(self):
        self._cancel_leave_timer()
        self._leave_timer = self.root.after(LEAVE_DELAY, self._maybe_close_sub)

    def _close_sub(self):
        self._cancel_hover_timer()
        self._cancel_leave_timer()
        self._hide_tooltip()
        if self._sub and self._sub.winfo_exists():
            self._sub.destroy()
        self._sub = None
        self._sub_folder_id = None

    def _cancel_hover_timer(self):
        if self._hover_timer:
            self.root.after_cancel(self._hover_timer)
            self._hover_timer = None

    def _cancel_leave_timer(self):
        if self._leave_timer:
            self.root.after_cancel(self._leave_timer)
            self._leave_timer = None

    # ── Selection / navigation ────────────────────────────────────────────

    def _set_selection(self, idx: int):
        C = self._C
        if 0 <= self._sel < len(self._row_frames):
            pf, pl = self._row_frames[self._sel]
            if pf:
                pf.configure(bg=C['bg'])
                if pl:
                    pl.configure(bg=C['bg'], fg=C['fg'])
        self._sel = idx
        if 0 <= idx < len(self._row_frames):
            nf, nl = self._row_frames[idx]
            if nf:
                nf.configure(bg=C['select_bg'])
                if nl:
                    nl.configure(bg=C['select_bg'], fg=C['select_fg'])
                nf.update_idletasks()
                self._canvas.yview_moveto(
                    nf.winfo_y() / max(1, self._inner.winfo_height())
                )

    def _move(self, delta: int):
        sel = [i for i, e in enumerate(self._entries) if e.selectable]
        if not sel:
            return
        if self._sel not in sel:
            self._set_selection(sel[0])
            return
        pos = sel.index(self._sel)
        self._set_selection(sel[(pos + delta) % len(sel)])

    def _activate(self):
        if 0 <= self._sel < len(self._entries):
            e = self._entries[self._sel]
            if e.selectable:
                self._paste(e)

    def _on_click(self, idx: int):
        if 0 <= idx < len(self._entries):
            e = self._entries[idx]
            if e.selectable:
                self._set_selection(idx)
                self._paste(e)

    def _on_hover(self, idx: int):
        self._close_sub()
        if idx != self._sel:
            C = self._C
            f, l = self._row_frames[idx]
            if f:
                f.configure(bg=C['hover_bg'])
                if l:
                    l.configure(bg=C['hover_bg'])

    def _on_leave(self, idx: int):
        if idx != self._sel:
            C = self._C
            f, l = self._row_frames[idx]
            if f:
                f.configure(bg=C['bg'])
                if l:
                    l.configure(bg=C['bg'], fg=C['fg'])

    # ── Paste ─────────────────────────────────────────────────────────────

    def _paste(self, entry: _Entry):
        self.hide()
        self.paste_callback(entry.content, source_id=entry.item_id, source_type=entry.kind)
