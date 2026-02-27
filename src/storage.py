"""
Storage layer for Clipy Windows.
Uses SQLite to persist clipboard history, snippets, and settings.
"""
import sqlite3
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom


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

    # ── Import / Export (XML plist format compatible with Clipy macOS) ────

    def export_snippets_xml(self) -> str:
        """
        Export all snippets and folders to XML plist format.
        Compatible with Clipy for macOS.
        """
        # Create root plist structure
        plist = ET.Element('plist', version='1.0')
        root_dict = ET.SubElement(plist, 'dict')
        
        # Add version
        ET.SubElement(root_dict, 'key').text = 'version'
        ET.SubElement(root_dict, 'string').text = '1.0'
        
        # Add folders
        ET.SubElement(root_dict, 'key').text = 'folders'
        folders_array = ET.SubElement(root_dict, 'array')
        
        for folder in self._conn.execute('SELECT * FROM folders ORDER BY sort_order, name').fetchall():
            folder_dict = ET.SubElement(folders_array, 'dict')
            
            # Folder name
            ET.SubElement(folder_dict, 'key').text = 'name'
            ET.SubElement(folder_dict, 'string').text = folder['name']
            
            # Folder snippets
            ET.SubElement(folder_dict, 'key').text = 'snippets'
            snippets_array = ET.SubElement(folder_dict, 'array')
            
            folder_snippets = self._conn.execute(
                'SELECT * FROM snippets WHERE folder_id=? ORDER BY title', (folder['id'],)
            ).fetchall()
            
            for snippet in folder_snippets:
                snippet_dict = ET.SubElement(snippets_array, 'dict')
                ET.SubElement(snippet_dict, 'key').text = 'title'
                ET.SubElement(snippet_dict, 'string').text = snippet['title']
                ET.SubElement(snippet_dict, 'key').text = 'content'
                ET.SubElement(snippet_dict, 'string').text = snippet['content']
        
        # Add root-level snippets
        ET.SubElement(root_dict, 'key').text = 'snippets'
        root_snippets_array = ET.SubElement(root_dict, 'array')
        
        root_snippets = self._conn.execute(
            'SELECT * FROM snippets WHERE folder_id IS NULL ORDER BY title'
        ).fetchall()
        
        for snippet in root_snippets:
            snippet_dict = ET.SubElement(root_snippets_array, 'dict')
            ET.SubElement(snippet_dict, 'key').text = 'title'
            ET.SubElement(snippet_dict, 'string').text = snippet['title']
            ET.SubElement(snippet_dict, 'key').text = 'content'
            ET.SubElement(snippet_dict, 'string').text = snippet['content']
        
        # Generate XML string with proper formatting
        xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml_str += '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        xml_str += ET.tostring(plist, encoding='unicode')
        
        return self._format_plist_xml(xml_str)

    def _format_plist_xml(self, xml_str: str) -> str:
        """Format XML with proper indentation for readability."""
        try:
            import xml.dom.minidom
            dom = xml.dom.minidom.parseString(xml_str)
            return dom.toprettyxml(indent='  ', encoding='UTF-8').decode('utf-8')
        except Exception:
            return xml_str

    def import_snippets_xml(self, xml_content: str, merge: bool = False):
        """
        Import snippets from XML plist format.
        Compatible with Clipy for macOS.
        If merge=False, clears existing snippets first.
        """
        try:
            # Parse XML
            root = ET.fromstring(xml_content)
            
            # Find the main dict element
            main_dict = root.find('dict')
            if main_dict is None:
                raise ValueError('Invalid plist format: no dict element found')
            
            if not merge:
                self._conn.execute('DELETE FROM snippets')
                self._conn.execute('DELETE FROM folders')
                self._conn.commit()
            
            # Parse the dict structure
            keys = main_dict.findall('key')
            for i, key in enumerate(keys):
                if key.text == 'folders':
                    # Get the next element which should be the array
                    folders_array = main_dict[i * 2 + 1]
                    if folders_array.tag == 'array':
                        self._import_folders_from_xml(folders_array)
                
                elif key.text == 'snippets':
                    # Get the next element which should be the array
                    snippets_array = main_dict[i * 2 + 1]
                    if snippets_array.tag == 'array':
                        self._import_snippets_from_xml(snippets_array, None)
            
            self._conn.commit()
            return True
            
        except Exception as e:
            self._conn.rollback()
            raise ValueError(f'Failed to import snippets: {str(e)}')

    def _import_folders_from_xml(self, folders_array):
        """Import folders from XML array element."""
        for folder_dict in folders_array.findall('dict'):
            folder_name = None
            snippets_array = None
            
            keys = folder_dict.findall('key')
            for i, key in enumerate(keys):
                if key.text == 'name':
                    name_elem = folder_dict[i * 2 + 1]
                    folder_name = name_elem.text or 'Untitled'
                elif key.text == 'snippets':
                    snippets_array = folder_dict[i * 2 + 1]
            
            if folder_name:
                folder_id = self.add_folder(folder_name)
                if snippets_array is not None and snippets_array.tag == 'array':
                    self._import_snippets_from_xml(snippets_array, folder_id)

    def _import_snippets_from_xml(self, snippets_array, folder_id):
        """Import snippets from XML array element."""
        for snippet_dict in snippets_array.findall('dict'):
            title = None
            content = None
            
            keys = snippet_dict.findall('key')
            for i, key in enumerate(keys):
                if key.text == 'title':
                    title_elem = snippet_dict[i * 2 + 1]
                    title = title_elem.text or 'Untitled'
                elif key.text == 'content':
                    content_elem = snippet_dict[i * 2 + 1]
                    content = content_elem.text or ''
            
            if title and content is not None:
                self.add_snippet(title, content, folder_id)
