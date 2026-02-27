"""
Storage layer for Clipy Windows.
Uses SQLite to persist clipboard history, snippets, and settings.
"""
import sqlite3
import os
from pathlib import Path


class Storage:
    def __init__(self):
        app_dir = Path(os.environ.get('APPDATA', os.path.expanduser('~'))) / 'Clipy'
        app_dir.mkdir(exist_ok=True)
        self.db_path = app_dir / 'clipy.db'
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()
        self._init_default_settings()

    def _create_tables(self):
        self._conn.executescript('''
            CREATE TABLE IF NOT EXISTS clips (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                content     TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                times_used  INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS folders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                parent_id   INTEGER REFERENCES folders(id),
                sort_order  INTEGER DEFAULT 0,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS snippets (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                content     TEXT NOT NULL,
                folder_id   INTEGER REFERENCES folders(id),
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                times_used  INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
        ''')
        self._conn.commit()

    def _init_default_settings(self):
        defaults = {
            'max_history': '100',
            'hotkey_main':     'ctrl+shift+v',   # 履歴+スニペット両方
            'hotkey_history':  'ctrl+shift+h',   # 履歴のみ
            'hotkey_snippets': 'ctrl+shift+s',   # スニペットのみ
            'start_with_windows': 'false',
            'theme': 'dark',
        }
        cur = self._conn.cursor()
        for key, value in defaults.items():
            cur.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (key, value))
        self._conn.commit()

    # ── Settings ──────────────────────────────────────────────────────────

    def get_setting(self, key, default=None):
        row = self._conn.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return row['value'] if row else default

    def set_setting(self, key, value):
        self._conn.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, str(value)))
        self._conn.commit()

    # ── Clipboard history ─────────────────────────────────────────────────

    def add_clip(self, content: str):
        if not content or not content.strip():
            return
        cur = self._conn.cursor()
        existing = cur.execute('SELECT id FROM clips WHERE content=?', (content,)).fetchone()
        if existing:
            cur.execute(
                'UPDATE clips SET created_at=CURRENT_TIMESTAMP, times_used=times_used+1 WHERE id=?',
                (existing['id'],),
            )
        else:
            cur.execute('INSERT INTO clips (content) VALUES (?)', (content,))
            max_hist = int(self.get_setting('max_history', '100'))
            cur.execute(
                'DELETE FROM clips WHERE id NOT IN (SELECT id FROM clips ORDER BY created_at DESC LIMIT ?)',
                (max_hist,),
            )
        self._conn.commit()

    def get_clips(self, limit: int = 0, search: str = None):
        max_hist = int(self.get_setting('max_history', '100'))
        n = limit or max_hist
        if search:
            return self._conn.execute(
                'SELECT * FROM clips WHERE content LIKE ? ORDER BY created_at DESC LIMIT ?',
                (f'%{search}%', n),
            ).fetchall()
        return self._conn.execute(
            'SELECT * FROM clips ORDER BY created_at DESC LIMIT ?', (n,)
        ).fetchall()

    def delete_clip(self, clip_id: int):
        self._conn.execute('DELETE FROM clips WHERE id=?', (clip_id,))
        self._conn.commit()

    def clear_history(self):
        self._conn.execute('DELETE FROM clips')
        self._conn.commit()

    # ── Folders ───────────────────────────────────────────────────────────

    def get_folders(self, parent_id=None):
        if parent_id is None:
            return self._conn.execute(
                'SELECT * FROM folders WHERE parent_id IS NULL ORDER BY sort_order, name'
            ).fetchall()
        return self._conn.execute(
            'SELECT * FROM folders WHERE parent_id=? ORDER BY sort_order, name', (parent_id,)
        ).fetchall()

    def add_folder(self, name: str, parent_id=None) -> int:
        cur = self._conn.execute('INSERT INTO folders (name, parent_id) VALUES (?, ?)', (name, parent_id))
        self._conn.commit()
        return cur.lastrowid

    def update_folder(self, folder_id: int, name: str):
        self._conn.execute('UPDATE folders SET name=? WHERE id=?', (name, folder_id))
        self._conn.commit()

    def delete_folder(self, folder_id: int):
        self._conn.execute('DELETE FROM snippets WHERE folder_id=?', (folder_id,))
        self._conn.execute('DELETE FROM folders WHERE parent_id=?', (folder_id,))
        self._conn.execute('DELETE FROM folders WHERE id=?', (folder_id,))
        self._conn.commit()

    # ── Snippets ──────────────────────────────────────────────────────────

    def get_snippets(self, folder_id=None, search: str = None):
        if search:
            return self._conn.execute(
                'SELECT * FROM snippets WHERE title LIKE ? OR content LIKE ? ORDER BY title',
                (f'%{search}%', f'%{search}%'),
            ).fetchall()
        if folder_id is not None:
            return self._conn.execute(
                'SELECT * FROM snippets WHERE folder_id=? ORDER BY title', (folder_id,)
            ).fetchall()
        return self._conn.execute(
            'SELECT * FROM snippets WHERE folder_id IS NULL ORDER BY title'
        ).fetchall()

    def get_all_snippets(self):
        return self._conn.execute('SELECT * FROM snippets ORDER BY title').fetchall()

    def add_snippet(self, title: str, content: str, folder_id=None) -> int:
        cur = self._conn.execute(
            'INSERT INTO snippets (title, content, folder_id) VALUES (?, ?, ?)',
            (title, content, folder_id),
        )
        self._conn.commit()
        return cur.lastrowid

    def update_snippet(self, snippet_id: int, title: str, content: str, folder_id=None):
        self._conn.execute(
            'UPDATE snippets SET title=?, content=?, folder_id=? WHERE id=?',
            (title, content, folder_id, snippet_id),
        )
        self._conn.commit()

    def delete_snippet(self, snippet_id: int):
        self._conn.execute('DELETE FROM snippets WHERE id=?', (snippet_id,))
        self._conn.commit()

    def increment_snippet_usage(self, snippet_id: int):
        self._conn.execute(
            'UPDATE snippets SET times_used=times_used+1 WHERE id=?', (snippet_id,)
        )
        self._conn.commit()

    def close(self):
        self._conn.close()
