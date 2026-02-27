"""
Snippet manager dialog.
Lets users create/edit/delete snippets and folders.
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog


class SnippetEditor(tk.Toplevel):
    def __init__(self, parent, storage):
        super().__init__(parent)
        self.storage = storage
        self.title('Clipy for Windows — Snippet Manager')
        self.geometry('760x620')
        self.minsize(640, 520)
        self.grab_set()
        self.attributes('-topmost', True)

        theme = storage.get_setting('theme', 'dark')
        if theme == 'dark':
            self.C = dict(
                bg='#1e1e1e', fg='#eeeeee',
                panel='#252525', item_bg='#2a2a2a',
                select='#0078d4', select_fg='#ffffff',
                border='#3a3a3a', btn='#333333',
                text_bg='#2d2d2d', muted='#888888',
                new_badge='#1a5fa8', edit_badge='#1a7a4a',
            )
        else:
            self.C = dict(
                bg='#f5f5f5', fg='#1a1a1a',
                panel='#ffffff', item_bg='#efefef',
                select='#0078d4', select_fg='#ffffff',
                border='#c8c8c8', btn='#d8d8d8',
                text_bg='#ffffff', muted='#555555',
                new_badge='#0078d4', edit_badge='#107c10',
            )

        self.configure(bg=self.C['bg'])
        self._current_folder: int | None = None
        self._editing_snip: int | None = None
        self._folder_ids: list = []
        self._snip_ids: list = []
        self._combo_folder_ids: list = []
        self._build()
        self._refresh()
        self._set_new_mode()
        self._center()

    def _center(self):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f'{w}x{h}+{(sw-w)//2}+{(sh-h)//2}')

    # ── Layout ────────────────────────────────────────────────────────────

    def _build(self):
        C = self.C
        main = tk.Frame(self, bg=C['bg'])
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # ── Left: folder tree ────────────────────────────────────────────
        left = tk.Frame(main, bg=C['panel'], width=220, relief=tk.FLAT)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 4))
        left.pack_propagate(False)

        tk.Label(left, text='Folders', bg=C['panel'], fg=C['fg'],
                 font=('Segoe UI', 10, 'bold'), anchor='w', padx=8, pady=6).pack(fill=tk.X)
        tk.Frame(left, bg=C['border'], height=1).pack(fill=tk.X)

        self._folder_lb = tk.Listbox(
            left, bg=C['panel'], fg=C['fg'],
            selectbackground=C['select'], selectforeground=C['select_fg'],
            font=('Segoe UI', 10), relief=tk.FLAT, bd=0, activestyle='none',
        )
        self._folder_lb.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self._folder_lb.bind('<<ListboxSelect>>', self._on_folder_select)

        fb = tk.Frame(left, bg=C['panel'])
        fb.pack(fill=tk.X, pady=4, padx=4)
        for text, cmd in (('+ Folder', self._add_folder), ('Rename', self._rename_folder), ('Delete', self._del_folder)):
            tk.Button(fb, text=text, command=cmd, bg=C['btn'], fg=C['fg'],
                      relief=tk.FLAT, padx=6, pady=3,
                      font=('Segoe UI', 9), cursor='hand2').pack(side=tk.LEFT, padx=2)

        # Import/Export buttons
        tk.Frame(left, bg=C['border'], height=1).pack(fill=tk.X, pady=2)
        ieb = tk.Frame(left, bg=C['panel'])
        ieb.pack(fill=tk.X, pady=4, padx=4)
        tk.Button(ieb, text='Import', command=self._import_snippets, bg=C['btn'], fg=C['fg'],
                  relief=tk.FLAT, padx=6, pady=3,
                  font=('Segoe UI', 9), cursor='hand2').pack(side=tk.LEFT, padx=2)
        tk.Button(ieb, text='Export', command=self._export_snippets, bg=C['btn'], fg=C['fg'],
                  relief=tk.FLAT, padx=6, pady=3,
                  font=('Segoe UI', 9), cursor='hand2').pack(side=tk.LEFT, padx=2)

        # ── Right: snippet list + editor (vertically resizable via PanedWindow) ──
        right = tk.Frame(main, bg=C['bg'])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Toolbar — packed first at bottom so it is always visible
        tk.Frame(right, bg=C['border'], height=1).pack(side=tk.BOTTOM, fill=tk.X)
        tb = tk.Frame(right, bg=C['bg'])
        tb.pack(side=tk.BOTTOM, fill=tk.X, padx=2, pady=4)
        tk.Button(tb, text='Save & Next', command=self._new_snippet_action,
                  bg=C['select'], fg='#ffffff',
                  relief=tk.FLAT, padx=10, pady=4,
                  font=('Segoe UI', 9, 'bold'), cursor='hand2').pack(side=tk.LEFT, padx=(0, 4))
        tk.Button(tb, text='Delete', command=self._del_snippet,
                  bg=C['btn'], fg=C['fg'],
                  relief=tk.FLAT, padx=8, pady=4,
                  font=('Segoe UI', 9), cursor='hand2').pack(side=tk.LEFT, padx=(0, 4))
        self._save_btn = tk.Button(
            tb, text='+ Add', command=self._save_snippet,
            bg='#0078d4', fg='#ffffff', relief=tk.FLAT,
            padx=10, pady=4, font=('Segoe UI', 9, 'bold'), cursor='hand2',
        )
        self._save_btn.pack(side=tk.LEFT)

        # PanedWindow takes all remaining space above the toolbar
        paned = tk.PanedWindow(
            right, orient=tk.VERTICAL,
            bg=C['border'], sashwidth=5, sashrelief=tk.FLAT,
            handlesize=0, opaqueresize=True,
        )
        paned.pack(fill=tk.BOTH, expand=True)

        # ── Top pane: snippet list ────────────────────────────────────────
        top_pane = tk.Frame(paned, bg=C['bg'])
        paned.add(top_pane, minsize=60, stretch='always')

        list_frame = tk.Frame(top_pane, bg=C['panel'])
        list_frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(list_frame, text='Snippets', bg=C['panel'], fg=C['fg'],
                 font=('Segoe UI', 10, 'bold'), anchor='w', padx=8, pady=5).pack(fill=tk.X)
        tk.Frame(list_frame, bg=C['border'], height=1).pack(fill=tk.X)

        self._snip_lb = tk.Listbox(
            list_frame, bg=C['panel'], fg=C['fg'],
            selectbackground=C['select'], selectforeground=C['select_fg'],
            font=('Segoe UI', 10), relief=tk.FLAT, bd=0, activestyle='none',
        )
        self._snip_lb.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self._snip_lb.bind('<<ListboxSelect>>', self._on_snip_select)

        # ── Bottom pane: editor form ──────────────────────────────────────
        bot_pane = tk.Frame(paned, bg=C['bg'])
        paned.add(bot_pane, minsize=100, stretch='always')

        # Mode indicator bar
        mode_bar = tk.Frame(bot_pane, bg=C['bg'])
        mode_bar.pack(fill=tk.X, pady=(6, 2))
        self._mode_badge = tk.Label(
            mode_bar, text='', bg=C['new_badge'], fg='#ffffff',
            font=('Segoe UI', 8, 'bold'), padx=6, pady=2,
        )
        self._mode_badge.pack(side=tk.LEFT)
        self._mode_label = tk.Label(
            mode_bar, text='', bg=C['bg'], fg=C['muted'],
            font=('Segoe UI', 9),
        )
        self._mode_label.pack(side=tk.LEFT, padx=(6, 0))

        # Folder selector
        style = ttk.Style(self)
        style.theme_use('default')
        style.configure('Folder.TCombobox',
            fieldbackground=C['text_bg'], background=C['btn'],
            foreground=C['fg'], selectbackground=C['text_bg'],
            selectforeground=C['fg'], arrowcolor=C['fg'],
        )
        style.map('Folder.TCombobox',
            fieldbackground=[('readonly', C['text_bg'])],
            selectbackground=[('readonly', C['text_bg'])],
            selectforeground=[('readonly', C['fg'])],
        )
        folder_row = tk.Frame(bot_pane, bg=C['bg'])
        folder_row.pack(fill=tk.X, padx=2, pady=(0, 5))
        tk.Label(folder_row, text='Folder:', bg=C['bg'], fg=C['fg'],
                 font=('Segoe UI', 9), width=8, anchor='w').pack(side=tk.LEFT)
        self._folder_var = tk.StringVar()
        self._folder_combo = ttk.Combobox(
            folder_row, textvariable=self._folder_var,
            state='readonly', font=('Segoe UI', 10), style='Folder.TCombobox',
        )
        self._folder_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Title
        tk.Label(bot_pane, text='Title:', bg=C['bg'], fg=C['fg'],
                 font=('Segoe UI', 9), anchor='w').pack(anchor='w', padx=2)
        self._title_var = tk.StringVar()
        self._title_entry = tk.Entry(
            bot_pane, textvariable=self._title_var,
            bg=C['text_bg'], fg=C['fg'], insertbackground=C['fg'],
            font=('Segoe UI', 10), relief=tk.FLAT, bd=4,
        )
        self._title_entry.pack(fill=tk.X, padx=2, pady=(0, 5))

        # Content
        tk.Label(bot_pane, text='Content (Template Text):', bg=C['bg'], fg=C['fg'],
                 font=('Segoe UI', 9), anchor='w').pack(anchor='w', padx=2)
        self._content_txt = tk.Text(
            bot_pane, bg=C['text_bg'], fg=C['fg'],
            insertbackground=C['fg'], font=('Segoe UI', 10),
            relief=tk.FLAT, bd=4, wrap=tk.WORD,
        )
        self._content_txt.pack(fill=tk.BOTH, expand=True, padx=2, pady=(0, 6))

        # Ctrl+Return shortcut to save
        self.bind('<Control-Return>', lambda e: self._save_snippet())

    # ── Mode helpers ──────────────────────────────────────────────────────

    def _set_new_mode(self):
        """Switch editor to 'create new' state."""
        C = self.C
        self._editing_snip = None
        self._mode_badge.configure(text=' NEW ', bg=C['new_badge'])
        self._mode_label.configure(text='Create a new snippet')
        self._save_btn.configure(text='+ Add')
        self._title_var.set('')
        self._content_txt.delete('1.0', tk.END)
        self._snip_lb.selection_clear(0, tk.END)
        self._set_combo_folder(self._current_folder)
        self._title_entry.focus_set()

    def _set_edit_mode(self, title: str):
        """Switch editor to 'editing existing' state."""
        C = self.C
        self._mode_badge.configure(text=' EDIT ', bg=C['edit_badge'])
        disp = title[:28] + '…' if len(title) > 28 else title
        self._mode_label.configure(text=f'Editing: {disp}')
        self._save_btn.configure(text='Update')

    # ── Data ──────────────────────────────────────────────────────────────

    def _refresh_folder_combo(self):
        folders = self.storage.get_folders()
        self._combo_folder_ids = [None] + [f['id'] for f in folders]
        self._folder_combo['values'] = ['(No folder)'] + [f['name'] for f in folders]

    def _set_combo_folder(self, folder_id):
        try:
            idx = self._combo_folder_ids.index(folder_id)
        except ValueError:
            idx = 0
        self._folder_combo.current(idx)

    def _refresh(self):
        self._folder_lb.delete(0, tk.END)
        self._folder_ids = [None]
        self._folder_lb.insert(tk.END, '  All')
        for folder in self.storage.get_folders():
            self._folder_lb.insert(tk.END, f'  {folder["name"]}')
            self._folder_ids.append(folder['id'])
        self._folder_lb.selection_set(0)
        self._refresh_folder_combo()
        self._load_snippets(None)

    def _load_snippets(self, folder_id):
        self._snip_lb.delete(0, tk.END)
        self._snip_ids = []
        snips = (
            self.storage.get_all_snippets()
            if folder_id is None
            else self.storage.get_snippets(folder_id=folder_id)
        )
        for s in snips:
            self._snip_lb.insert(tk.END, f'  {s["title"]}')
            self._snip_ids.append(s['id'])

    def _on_folder_select(self, _event=None):
        sel = self._folder_lb.curselection()
        if not sel:
            return
        self._current_folder = self._folder_ids[sel[0]]
        self._load_snippets(self._current_folder)
        self._set_new_mode()

    def _on_snip_select(self, _event=None):
        sel = self._snip_lb.curselection()
        if not sel:
            return
        snip_id = self._snip_ids[sel[0]]
        self._editing_snip = snip_id
        row = self.storage._conn.execute(
            'SELECT title, content, folder_id FROM snippets WHERE id=?', (snip_id,)
        ).fetchone()
        if row:
            self._title_var.set(row['title'])
            self._content_txt.delete('1.0', tk.END)
            self._content_txt.insert('1.0', row['content'])
            self._set_combo_folder(row['folder_id'])
            self._set_edit_mode(row['title'])

    # ── Actions ───────────────────────────────────────────────────────────

    def _new_snippet_action(self):
        """
        '+ New Snippet' button behavior:
          - If form has title & content → save then switch to new mode
          - If form is empty → just switch to new mode (clear form & focus)
        """
        title = self._title_var.get().strip()
        content = self._content_txt.get('1.0', tk.END).rstrip('\n')

        if title and content:
            # If filled, save then clear
            idx = self._folder_combo.current()
            folder_id = self._combo_folder_ids[idx] if 0 <= idx < len(self._combo_folder_ids) else None
            if self._editing_snip is not None:
                self.storage.update_snippet(self._editing_snip, title, content, folder_id)
                saved_msg = f'"{title}" updated'
            else:
                self.storage.add_snippet(title, content, folder_id)
                saved_msg = f'"{title}" added'
            self._load_snippets(folder_id)
            self._set_new_mode()
            # Show temporary message
            self._mode_label.configure(text=f'✓  {saved_msg}. Enter next snippet.')
            self.after(2500, lambda: self._mode_label.configure(text='Create a new snippet'))
        else:
            # If empty, just reset
            self._set_new_mode()

    def _add_folder(self):
        name = simpledialog.askstring('Add Folder', 'Enter folder name:', parent=self)
        if name and name.strip():
            self.storage.add_folder(name.strip())
            self._refresh()

    def _rename_folder(self):
        sel = self._folder_lb.curselection()
        if not sel or sel[0] == 0:
            messagebox.showinfo('Info', 'Please select a folder to rename.', parent=self)
            return
        folder_id = self._folder_ids[sel[0]]
        current_name = self._folder_lb.get(sel[0]).strip()
        new_name = simpledialog.askstring(
            'Rename Folder', 'Enter new folder name:',
            initialvalue=current_name, parent=self,
        )
        if new_name and new_name.strip() and new_name.strip() != current_name:
            self.storage.update_folder(folder_id, new_name.strip())
            self._refresh()
            # Re-select the renamed folder
            if folder_id in self._folder_ids:
                idx = self._folder_ids.index(folder_id)
                self._folder_lb.selection_set(idx)

    def _del_folder(self):
        sel = self._folder_lb.curselection()
        if not sel or sel[0] == 0:
            messagebox.showinfo('Info', 'Please select a folder to delete.', parent=self)
            return
        folder_id = self._folder_ids[sel[0]]
        if messagebox.askyesno('Confirm', 'Delete this folder and all its snippets?', parent=self):
            self.storage.delete_folder(folder_id)
            self._refresh()
            self._set_new_mode()

    def _del_snippet(self):
        if self._editing_snip is None:
            messagebox.showinfo('Info', 'Please select a snippet from the list to delete.', parent=self)
            return
        if messagebox.askyesno('Confirm', 'Delete this snippet?', parent=self):
            self.storage.delete_snippet(self._editing_snip)
            self._load_snippets(self._current_folder)
            self._set_new_mode()

    # ── Import / Export ───────────────────────────────────────────────────

    def _export_snippets(self):
        """Export all snippets to XML plist file (Clipy macOS compatible)."""
        try:
            file_path = filedialog.asksaveasfilename(
                parent=self,
                title='Export Snippets',
                defaultextension='.xml',
                filetypes=[
                    ('XML Plist Files', '*.xml'),
                    ('Plist Files', '*.plist'),
                    ('All Files', '*.*')
                ],
                initialfile='clipy_snippets.xml'
            )
            
            if not file_path:
                return
            
            xml_content = self.storage.export_snippets_xml()
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            
            messagebox.showinfo(
                'Export Successful',
                f'Snippets exported successfully to:\n{file_path}',
                parent=self
            )
        except Exception as e:
            messagebox.showerror(
                'Export Failed',
                f'Failed to export snippets:\n{str(e)}',
                parent=self
            )

    def _import_snippets(self):
        """Import snippets from XML plist file (Clipy macOS compatible)."""
        try:
            file_path = filedialog.askopenfilename(
                parent=self,
                title='Import Snippets',
                filetypes=[
                    ('XML Plist Files', '*.xml'),
                    ('Plist Files', '*.plist'),
                    ('All Files', '*.*')
                ]
            )
            
            if not file_path:
                return
            
            # Ask if user wants to merge or replace
            merge = messagebox.askyesno(
                'Import Mode',
                'Do you want to merge with existing snippets?\n\n'
                'Yes: Keep existing snippets and add imported ones\n'
                'No: Replace all existing snippets with imported ones',
                parent=self
            )
            
            with open(file_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            self.storage.import_snippets_xml(xml_content, merge=merge)
            
            # Refresh the UI
            self._refresh()
            self._set_new_mode()
            
            messagebox.showinfo(
                'Import Successful',
                f'Snippets imported successfully from:\n{file_path}',
                parent=self
            )
        except Exception as e:
            messagebox.showerror(
                'Import Failed',
                f'Failed to import snippets:\n{str(e)}',
                parent=self
            )

    def _save_snippet(self):
        title = self._title_var.get().strip()
        content = self._content_txt.get('1.0', tk.END).rstrip('\n')

        if not title:
            messagebox.showerror('Input Error', 'Please enter a title.', parent=self)
            self._title_entry.focus_set()
            return
        if not content:
            messagebox.showerror('Input Error', 'Please enter content.', parent=self)
            self._content_txt.focus_set()
            return

        idx = self._folder_combo.current()
        folder_id = self._combo_folder_ids[idx] if 0 <= idx < len(self._combo_folder_ids) else None

        if self._editing_snip is not None:
            # Update existing
            self.storage.update_snippet(self._editing_snip, title, content, folder_id)
            msg = f'"{title}" updated.'
        else:
            # Create new
            new_id = self.storage.add_snippet(title, content, folder_id)
            self._editing_snip = new_id
            msg = f'"{title}" added.'

        self._load_snippets(self._current_folder)

        # Re-select the saved snippet in the listbox
        if self._editing_snip in self._snip_ids:
            idx = self._snip_ids.index(self._editing_snip)
            self._snip_lb.selection_set(idx)
            self._snip_lb.see(idx)
            self._set_edit_mode(title)

        # Show brief status in mode label instead of blocking dialog
        self._mode_label.configure(text=f'✓  {msg}')
        self.after(2500, lambda: self._mode_label.configure(
            text=f'Editing: {title[:28]}{"…" if len(title) > 28 else ""}'
        ))
