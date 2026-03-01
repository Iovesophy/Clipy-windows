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
            'hotkey_main':     'ctrl+shift+v',   # History + Snippets
            'hotkey_history':  'ctrl+shift+h',   # History only
            'hotkey_snippets': 'ctrl+shift+s',   # Snippets only
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

    # ── Windows startup ───────────────────────────────────────────────────

    def apply_startup(self, enabled: bool):
        """Add or remove Clipy from HKCU Run registry key."""
        import winreg, sys
        key_path = r'Software\Microsoft\Windows\CurrentVersion\Run'
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if enabled:
                exe = sys.executable
                winreg.SetValueEx(key, 'Clipy', 0, winreg.REG_SZ, f'"{exe}"')
            else:
                try:
                    winreg.DeleteValue(key, 'Clipy')
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            print(f'[Clipy] startup registry error: {e}')

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

    def get_folders_by_usage(self):
        """Return root folders sorted by total snippet usage (descending), then name."""
        return self._conn.execute('''
            SELECT f.*, COALESCE(SUM(s.times_used), 0) AS total_used
            FROM folders f
            LEFT JOIN snippets s ON s.folder_id = f.id
            WHERE f.parent_id IS NULL
            GROUP BY f.id
            ORDER BY total_used DESC, f.name
        ''').fetchall()

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
                'SELECT * FROM snippets WHERE folder_id=? ORDER BY times_used DESC, title', (folder_id,)
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

    def reset_usage_counts(self):
        self._conn.execute('UPDATE snippets SET times_used=0')
        self._conn.commit()

    def close(self):
        self._conn.close()

    # ── Import / Export (XML format compatible with Clipy macOS) ────────

    def export_snippets_xml(self) -> str:
        """
        Export all snippets and folders to XML format.
        Compatible with Clipy for macOS.
        """
        root = ET.Element('folders')
        
        # Export folders with their snippets
        for folder in self._conn.execute('SELECT * FROM folders ORDER BY sort_order, name').fetchall():
            folder_elem = ET.SubElement(root, 'folder')
            
            # Folder title
            title_elem = ET.SubElement(folder_elem, 'title')
            title_elem.text = folder['name']
            
            # Folder snippets
            snippets_elem = ET.SubElement(folder_elem, 'snippets')
            
            folder_snippets = self._conn.execute(
                'SELECT * FROM snippets WHERE folder_id=? ORDER BY title', (folder['id'],)
            ).fetchall()
            
            for snippet in folder_snippets:
                snippet_elem = ET.SubElement(snippets_elem, 'snippet')
                snippet_title = ET.SubElement(snippet_elem, 'title')
                snippet_title.text = snippet['title']
                snippet_content = ET.SubElement(snippet_elem, 'content')
                snippet_content.text = snippet['content']
        
        # Export root-level snippets as a special folder
        root_snippets = self._conn.execute(
            'SELECT * FROM snippets WHERE folder_id IS NULL ORDER BY title'
        ).fetchall()
        
        if root_snippets:
            root_folder = ET.SubElement(root, 'folder')
            root_title = ET.SubElement(root_folder, 'title')
            root_title.text = 'Root Snippets'
            root_snippets_elem = ET.SubElement(root_folder, 'snippets')
            
            for snippet in root_snippets:
                snippet_elem = ET.SubElement(root_snippets_elem, 'snippet')
                snippet_title = ET.SubElement(snippet_elem, 'title')
                snippet_title.text = snippet['title']
                snippet_content = ET.SubElement(snippet_elem, 'content')
                snippet_content.text = snippet['content']
        
        # Generate XML string with proper formatting
        xml_str = ET.tostring(root, encoding='unicode')
        return self._format_xml(xml_str)

    def _format_xml(self, xml_str: str) -> str:
        """Format XML with proper indentation for readability."""
        try:
            import xml.dom.minidom
            dom = xml.dom.minidom.parseString(xml_str)
            # Remove extra blank lines
            pretty_xml = dom.toprettyxml(indent='  ', encoding='utf-8').decode('utf-8')
            # Add XML declaration matching Clipy format
            lines = [line for line in pretty_xml.split('\n') if line.strip()]
            if lines and lines[0].startswith('<?xml'):
                lines[0] = '<?xml version="1.0" encoding="utf-8" standalone="no"?>'
            return '\n'.join(lines)
        except Exception:
            return '<?xml version="1.0" encoding="utf-8" standalone="no"?>\n' + xml_str

    def import_snippets_xml(self, xml_content: str, merge: bool = False):
        """
        Import snippets from XML format.
        Compatible with Clipy for macOS.
        If merge=False, clears existing snippets first.
        """
        try:
            # Parse XML
            root = ET.fromstring(xml_content)
            
            # Check if root is 'folders' element (Clipy format)
            if root.tag != 'folders':
                raise ValueError('Invalid Clipy XML format: root element must be <folders>')
            
            if not merge:
                self._conn.execute('DELETE FROM snippets')
                self._conn.execute('DELETE FROM folders')
                self._conn.commit()
            
            # Import each folder
            for folder_elem in root.findall('folder'):
                title_elem = folder_elem.find('title')
                if title_elem is None or not title_elem.text:
                    continue
                
                folder_name = title_elem.text
                
                # Skip "Root Snippets" folder - import as root-level snippets
                if folder_name == 'Root Snippets':
                    snippets_elem = folder_elem.find('snippets')
                    if snippets_elem is not None:
                        self._import_snippets_from_xml_elem(snippets_elem, None)
                else:
                    # Create folder
                    folder_id = self.add_folder(folder_name)
                    
                    # Import snippets in this folder
                    snippets_elem = folder_elem.find('snippets')
                    if snippets_elem is not None:
                        self._import_snippets_from_xml_elem(snippets_elem, folder_id)
            
            self._conn.commit()
            return True
            
        except Exception as e:
            self._conn.rollback()
            raise ValueError(f'Failed to import snippets: {str(e)}')

    def _import_snippets_from_xml_elem(self, snippets_elem, folder_id):
        """Import snippets from XML snippets element."""
        for snippet_elem in snippets_elem.findall('snippet'):
            title_elem = snippet_elem.find('title')
            content_elem = snippet_elem.find('content')
            
            if title_elem is None or not title_elem.text:
                continue
            
            title = title_elem.text
            content = content_elem.text if content_elem is not None and content_elem.text else ''
            
            self.add_snippet(title, content, folder_id)
