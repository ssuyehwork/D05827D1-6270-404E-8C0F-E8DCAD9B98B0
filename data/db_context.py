# -*- coding: utf-8 -*-
# data/db_context.py
import sqlite3
import logging
from core.config import DB_NAME, COLORS

class DBContext:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
        self._fix_trash_consistency()

    def get_cursor(self):
        return self.conn.cursor()

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

    def _init_schema(self):
        c = self.conn.cursor()
        
        c.execute(f'''CREATE TABLE IF NOT EXISTS ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, content TEXT, color TEXT DEFAULT '{COLORS['default_note']}',
            is_pinned INTEGER DEFAULT 0, is_favorite INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            category_id INTEGER, is_deleted INTEGER DEFAULT 0,
            item_type TEXT DEFAULT 'text', data_blob BLOB,
            content_hash TEXT, is_locked INTEGER DEFAULT 0, rating INTEGER DEFAULT 0
        )''')
        c.execute('CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)')
        c.execute('''CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            name TEXT NOT NULL, parent_id INTEGER, 
            color TEXT DEFAULT "#808080", sort_order INTEGER DEFAULT 0, preset_tags TEXT
        )''')
        c.execute('CREATE TABLE IF NOT EXISTS idea_tags (idea_id INTEGER, tag_id INTEGER, PRIMARY KEY (idea_id, tag_id))')
        
        # 补全可能缺失的列
        c.execute("PRAGMA table_info(ideas)")
        cols = [i[1] for i in c.fetchall()]
        updates = [
            ('category_id', 'INTEGER'), ('is_deleted', 'INTEGER DEFAULT 0'),
            ('item_type', "TEXT DEFAULT 'text'"), ('data_blob', 'BLOB'),
            ('content_hash', 'TEXT'), ('is_locked', 'INTEGER DEFAULT 0'),
            ('rating', 'INTEGER DEFAULT 0')
        ]
        for col, type_def in updates:
            if col not in cols:
                try:
                    c.execute(f'ALTER TABLE ideas ADD COLUMN {col} {type_def}')
                    logging.info(f"Added column {col} to ideas table")
                except Exception as e:
                    logging.warning(f"Failed to add column {col} (may already exist): {e}")
        
        if 'content_hash' not in cols:
            try:
                c.execute('CREATE INDEX IF NOT EXISTS idx_content_hash ON ideas(content_hash)')
                logging.info("Created index on content_hash")
            except Exception as e:
                logging.warning(f"Failed to create content_hash index: {e}")
            
        c.execute("PRAGMA table_info(categories)")
        cat_cols = [i[1] for i in c.fetchall()]
        if 'sort_order' not in cat_cols:
            try:
                c.execute('ALTER TABLE categories ADD COLUMN sort_order INTEGER DEFAULT 0')
                logging.info("Added sort_order column to categories table")
            except Exception as e:
                logging.warning(f"Failed to add sort_order column: {e}")
        if 'preset_tags' not in cat_cols:
            try:
                c.execute('ALTER TABLE categories ADD COLUMN preset_tags TEXT')
                logging.info("Added preset_tags column to categories table")
            except Exception as e:
                logging.warning(f"Failed to add preset_tags column: {e}")

        self.conn.commit()

    def _fix_trash_consistency(self):
        try:
            c = self.conn.cursor()
            trash_color = COLORS.get('trash', '#2d2d2d')
            c.execute('UPDATE ideas SET category_id = NULL, color = ? WHERE is_deleted = 1', (trash_color,))
            self.conn.commit()
            logging.debug("Trash consistency check completed")
        except Exception as e:
            logging.error(f"Failed to fix trash consistency: {e}", exc_info=True)