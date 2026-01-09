# -*- coding: utf-8 -*-
# data/db_manager.py
import sqlite3
import hashlib
import os
import random
from core.config import DB_NAME, COLORS

class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME)
        self.conn.row_factory = sqlite3.Row
        self.fts5_supported = True  # Assume FTS5 is supported by default
        self._init_schema()
        # 【维护】启动时仅修正回收站数据的格式
        self._fix_trash_consistency()

    def _init_schema(self):
        c = self.conn.cursor()
        
        c.execute(f'''CREATE TABLE IF NOT EXISTS ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, content TEXT, color TEXT DEFAULT '{COLORS['default_note']}',
            is_pinned INTEGER DEFAULT 0, is_favorite INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            category_id INTEGER, is_deleted INTEGER DEFAULT 0
        )''')
        c.execute('CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)')
        c.execute('''CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            name TEXT NOT NULL, 
            parent_id INTEGER, 
            color TEXT DEFAULT "#808080",
            sort_order INTEGER DEFAULT 0
        )''')
        c.execute('CREATE TABLE IF NOT EXISTS idea_tags (idea_id INTEGER, tag_id INTEGER, PRIMARY KEY (idea_id, tag_id))')
        
        # 检查并补充字段
        c.execute("PRAGMA table_info(ideas)")
        cols = [i[1] for i in c.fetchall()]
        
        updates = [
            ('category_id', 'INTEGER'),
            ('is_deleted', 'INTEGER DEFAULT 0'),
            ('item_type', "TEXT DEFAULT 'text'"),
            ('data_blob', 'BLOB'),
            ('content_hash', 'TEXT'),
            ('is_locked', 'INTEGER DEFAULT 0'),
            ('rating', 'INTEGER DEFAULT 0')
        ]
        
        for col, type_def in updates:
            if col not in cols:
                try: c.execute(f'ALTER TABLE ideas ADD COLUMN {col} {type_def}')
                except: pass
        
        if 'content_hash' not in cols:
            try: c.execute('CREATE INDEX IF NOT EXISTS idx_content_hash ON ideas(content_hash)')
            except: pass
        
        c.execute("PRAGMA table_info(categories)")
        cat_cols = [i[1] for i in c.fetchall()]
        if 'sort_order' not in cat_cols:
            try: c.execute('ALTER TABLE categories ADD COLUMN sort_order INTEGER DEFAULT 0')
            except: pass
        if 'preset_tags' not in cat_cols:
            try: c.execute('ALTER TABLE categories ADD COLUMN preset_tags TEXT')
            except: pass
        
        # --- FTS5 Setup ---
        try:
            # Check for FTS5 support
            c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts_test USING fts5(a)")
            c.execute("DROP TABLE fts_test")

            c.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS ideas_fts USING fts5(
                    title, 
                    content, 
                    content='ideas', 
                    content_rowid='id'
                )
            """)
            
            c.execute("""
                CREATE TRIGGER IF NOT EXISTS ideas_after_insert AFTER INSERT ON ideas BEGIN
                    INSERT INTO ideas_fts(rowid, title, content) VALUES (new.id, new.title, new.content);
                END;
            """)
            c.execute("""
                CREATE TRIGGER IF NOT EXISTS ideas_after_delete AFTER DELETE ON ideas BEGIN
                    INSERT INTO ideas_fts(ideas_fts, rowid, title, content) VALUES ('delete', old.id, old.title, old.content);
                END;
            """)
            c.execute("""
                CREATE TRIGGER IF NOT EXISTS ideas_after_update AFTER UPDATE ON ideas BEGIN
                    INSERT INTO ideas_fts(ideas_fts, rowid, title, content) VALUES ('delete', old.id, old.title, old.content);
                    INSERT INTO ideas_fts(rowid, title, content) VALUES (new.id, new.title, new.content);
                END;
            """)
        except sqlite3.OperationalError as e:
            # If FTS5 is not supported, disable it for this session
            if 'no such module' in str(e).lower() or 'fts5' in str(e).lower():
                self.fts5_supported = False
                self.conn.rollback()  # Roll back any partial FTS setup
            else:
                raise  # Re-raise other operational errors

        self.conn.commit()

    def _fix_trash_consistency(self):
        try:
            c = self.conn.cursor()
            trash_color = COLORS.get('trash', '#2d2d2d')
            c.execute('''
                UPDATE ideas 
                SET category_id = NULL, color = ? 
                WHERE is_deleted = 1 AND (category_id IS NOT NULL OR color != ?)
            ''', (trash_color, trash_color))
            self.conn.commit()
        except Exception as e:
            pass

    def empty_trash(self):
        c = self.conn.cursor()
        c.execute('DELETE FROM idea_tags WHERE idea_id IN (SELECT id FROM ideas WHERE is_deleted=1)')
        c.execute('DELETE FROM ideas WHERE is_deleted=1')
        self.conn.commit()

    def set_locked(self, idea_ids, state):
        if not idea_ids: return
        c = self.conn.cursor()
        val = 1 if state else 0
        placeholders = ','.join('?' * len(idea_ids))
        c.execute(f'UPDATE ideas SET is_locked=? WHERE id IN ({placeholders})', (val, *idea_ids))
        self.conn.commit()

    def get_lock_status(self, idea_ids):
        if not idea_ids: return {}
        c = self.conn.cursor()
        placeholders = ','.join('?' * len(idea_ids))
        c.execute(f'SELECT id, is_locked FROM ideas WHERE id IN ({placeholders})', tuple(idea_ids))
        return dict(c.fetchall())

    def add_idea(self, title, content, color=None, tags=[], category_id=None, item_type='text', data_blob=None):
        if color is None: color = COLORS['default_note']
        c = self.conn.cursor()
        c.execute(
            'INSERT INTO ideas (title, content, color, category_id, item_type, data_blob) VALUES (?,?,?,?,?,?)',
            (title, content, color, category_id, item_type, data_blob)
        )
        iid = c.lastrowid
        self._update_tags(iid, tags)
        self.conn.commit()
        return iid

    def update_idea(self, iid, title, content, color, tags, category_id=None, item_type='text', data_blob=None):
        c = self.conn.cursor()
        c.execute(
            'UPDATE ideas SET title=?, content=?, color=?, category_id=?, item_type=?, data_blob=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
            (title, content, color, category_id, item_type, data_blob, iid)
        )
        self._update_tags(iid, tags)
        self.conn.commit()

    def update_field(self, iid, field, value):
        c = self.conn.cursor()
        c.execute(f'UPDATE ideas SET {field} = ? WHERE id = ?', (value, iid))
        self.conn.commit()

    def _update_tags(self, iid, tags):
        c = self.conn.cursor()
        c.execute('DELETE FROM idea_tags WHERE idea_id=?', (iid,))
        if not tags: return
        for t in tags:
            t = t.strip()
            if t:
                c.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (t,))
                c.execute('SELECT id FROM tags WHERE name=?', (t,))
                tid = c.fetchone()[0]
                c.execute('INSERT INTO idea_tags VALUES (?,?)', (iid, tid))

    def _append_tags(self, iid, tags):
        c = self.conn.cursor()
        for t in tags:
            t = t.strip()
            if t:
                c.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (t,))
                c.execute('SELECT id FROM tags WHERE name=?', (t,))
                tid = c.fetchone()[0]
                c.execute('INSERT OR IGNORE INTO idea_tags VALUES (?,?)', (iid, tid))

    def add_tags_to_multiple_ideas(self, idea_ids, tags_list):
        if not idea_ids or not tags_list: return
        c = self.conn.cursor()
        for tag_name in tags_list:
            tag_name = tag_name.strip()
            if not tag_name: continue
            c.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (tag_name,))
            c.execute('SELECT id FROM tags WHERE name=?', (tag_name,))
            tid = c.fetchone()[0]
            for iid in idea_ids:
                c.execute('INSERT OR IGNORE INTO idea_tags (idea_id, tag_id) VALUES (?,?)', (iid, tid))
        self.conn.commit()

    def remove_tag_from_multiple_ideas(self, idea_ids, tag_name):
        if not idea_ids or not tag_name: return
        c = self.conn.cursor()
        c.execute('SELECT id FROM tags WHERE name=?', (tag_name,))
        res = c.fetchone()
        if not res: return
        tid = res[0]
        placeholders = ','.join('?' * len(idea_ids))
        sql = f'DELETE FROM idea_tags WHERE tag_id=? AND idea_id IN ({placeholders})'
        c.execute(sql, (tid, *idea_ids))
        self.conn.commit()

    def get_union_tags(self, idea_ids):
        if not idea_ids: return []
        c = self.conn.cursor()
        placeholders = ','.join('?' * len(idea_ids))
        sql = f'''
            SELECT DISTINCT t.name 
            FROM tags t 
            JOIN idea_tags it ON t.id = it.tag_id 
            WHERE it.idea_id IN ({placeholders})
            ORDER BY t.name ASC
        '''
        c.execute(sql, tuple(idea_ids))
        return [r[0] for r in c.fetchall()]

    def add_clipboard_item(self, item_type, content, data_blob=None, category_id=None):
        c = self.conn.cursor()
        c = self.conn.cursor()
        hasher = hashlib.sha256()
        
        # 【逻辑修正】除去明确的image类型外，其他所有类型(text, pdf, folder...)都按内容字符hash
        if item_type == 'image' and data_blob:
            hasher.update(data_blob)
        else:
            hasher.update(content.encode('utf-8'))
            
        content_hash = hasher.hexdigest()

        c.execute("SELECT id FROM ideas WHERE content_hash = ?", (content_hash,))
        existing_idea = c.fetchone()

        if existing_idea:
            idea_id = existing_idea[0]
            c.execute("UPDATE ideas SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (idea_id,))
            self.conn.commit()
            return idea_id, False 
        else:
            # 【逻辑修正】标题生成逻辑
            if item_type == 'text':
                title = content.strip().split('\n')[0][:50]
            elif item_type == 'image':
                title = "[图片]"
            else:
                # 其他所有类型（file, pdf, folder...）均视为文件类，显示文件名
                # 尝试从内容中获取第一个文件名
                try:
                    first_file = content.split(';')[0]
                    fname = os.path.basename(first_file)
                    title = f"[{item_type}] {fname}"
                except:
                    title = f"[{item_type}]"

            default_color = COLORS['default_note']
            c.execute(
                'INSERT INTO ideas (title, content, item_type, data_blob, category_id, content_hash, color) VALUES (?,?,?,?,?,?,?)',
                (title, content, item_type, data_blob, category_id, content_hash, default_color)
            )
            idea_id = c.lastrowid
            
            self.conn.commit()
            return idea_id, True

    def toggle_field(self, iid, field):
        c = self.conn.cursor()
        c.execute(f'UPDATE ideas SET {field} = NOT {field} WHERE id=?', (iid,))
        self.conn.commit()

    def set_deleted(self, iid, state):
        c = self.conn.cursor()
        if state:
            trash_color = COLORS.get('trash', '#2d2d2d')
            c.execute(
                'UPDATE ideas SET is_deleted=1, category_id=NULL, color=?, updated_at=CURRENT_TIMESTAMP WHERE id=?', 
                (trash_color, iid)
            )
        else:
            uncat_color = COLORS.get('uncategorized', '#0A362F')
            c.execute(
                'UPDATE ideas SET is_deleted=0, category_id=NULL, color=?, updated_at=CURRENT_TIMESTAMP WHERE id=?', 
                (uncat_color, iid)
            )
        self.conn.commit()

    def set_favorite(self, iid, state):
        c = self.conn.cursor()
        c.execute('UPDATE ideas SET is_favorite=? WHERE id=?', (1 if state else 0, iid))
        
        if state:
            bookmark_color = '#ff6b81'
            c.execute('UPDATE ideas SET color=? WHERE id=?', (bookmark_color, iid))
        else:
            c.execute('SELECT category_id FROM ideas WHERE id=?', (iid,))
            res = c.fetchone()
            if res and res[0] is not None:
                cat_id = res[0]
                c.execute('SELECT color FROM categories WHERE id=?', (cat_id,))
                cat_res = c.fetchone()
                if cat_res:
                    c.execute('UPDATE ideas SET color=? WHERE id=?', (cat_res[0], iid))
            else:
                uncat_color = COLORS.get('uncategorized', '#0A362F')
                c.execute('UPDATE ideas SET color=? WHERE id=?', (uncat_color, iid))

        self.conn.commit()

    def set_rating(self, idea_id, rating):
        c = self.conn.cursor()
        rating = max(0, min(5, int(rating)))
        c.execute('UPDATE ideas SET rating=? WHERE id=?', (rating, idea_id))
        self.conn.commit()

    def move_category(self, iid, cat_id):
        c = self.conn.cursor()
        c.execute('UPDATE ideas SET category_id=?, is_deleted=0 WHERE id=?', (cat_id, iid))
        if cat_id is not None:
            c.execute('SELECT color, preset_tags FROM categories WHERE id=?', (cat_id,))
            result = c.fetchone()
            if result:
                cat_color = result[0]
                preset_tags_str = result[1]
                if cat_color:
                    c.execute('UPDATE ideas SET color=? WHERE id=?', (cat_color, iid))
                if preset_tags_str:
                    tags_list = [t.strip() for t in preset_tags_str.split(',') if t.strip()]
                    if tags_list:
                        self._append_tags(iid, tags_list)
        else:
            uncat_color = COLORS.get('uncategorized', '#0A362F')
            c.execute('UPDATE ideas SET color=? WHERE id=?', (uncat_color, iid))
        self.conn.commit()

    def delete_permanent(self, iid):
        c = self.conn.cursor()
        c.execute('DELETE FROM ideas WHERE id=?', (iid,))
        self.conn.commit()

    def get_idea(self, iid, include_blob=False):
        c = self.conn.cursor()
        if include_blob:
            c.execute('''
                SELECT id, title, content, color, is_pinned, is_favorite, 
                       created_at, updated_at, category_id, is_deleted, item_type, 
                       data_blob, content_hash, is_locked, rating
                FROM ideas WHERE id=?
            ''', (iid,))
        else:
            c.execute('''
                SELECT id, title, content, color, is_pinned, is_favorite, 
                       created_at, updated_at, category_id, is_deleted, item_type, 
                       NULL as data_blob, NULL as content_hash, is_locked, rating
                FROM ideas WHERE id=?
            ''', (iid,))
        return c.fetchone()

    # === 核心修改：get_filter_stats 支持上下文 ===
    def _get_all_child_categories(self, cat_id):
        """递归获取所有子分类ID"""
        ids = [cat_id]
        c = self.conn.cursor()
        c.execute("SELECT id FROM categories WHERE parent_id = ?", (cat_id,))
        children = c.fetchall()
        for child_row in children:
            ids.extend(self._get_all_child_categories(child_row[0]))
        return ids

    def get_filter_stats(self, search_text='', filter_type='all', filter_value=None):
        """
        获取当前视图范围内的各项统计，用于填充筛选器
        支持根据搜索文本和过滤类型进行上下文相关统计
        """
        c = self.conn.cursor()
        stats = {
            'stars': {},
            'colors': {},
            'types': {},
            'tags': [],
            'date_create': {}
        }
        
        # 1. 构建基础 WHERE 子句
        where_clauses = ["1=1"]
        params = []
        
        if filter_type == 'trash':
            where_clauses.append("i.is_deleted=1")
        else:
            where_clauses.append("(i.is_deleted=0 OR i.is_deleted IS NULL)")
            
        if filter_type == 'category':
            if filter_value is None:
                where_clauses.append("i.category_id IS NULL")
            else:
                # 递归包含子分类
                cat_ids = self._get_all_child_categories(filter_value)
                placeholders = ','.join('?' * len(cat_ids))
                where_clauses.append(f"i.category_id IN ({placeholders})")
                params.extend(cat_ids)
        elif filter_type == 'today':
            where_clauses.append("date(i.updated_at,'localtime')=date('now','localtime')")
        elif filter_type == 'untagged':
            where_clauses.append("i.id NOT IN (SELECT idea_id FROM idea_tags)")
        elif filter_type == 'bookmark':
            where_clauses.append("i.is_favorite=1")
        
        # 添加搜索文本过滤
        if search_text:
            where_clauses.append("(i.title LIKE ? OR i.content LIKE ?)")
            params.extend([f'%{search_text}%', f'%{search_text}%'])
            
        where_str = " AND ".join(where_clauses)
        
        # 2. 执行统计查询
        
        # 2.1 星级统计
        c.execute(f"SELECT i.rating, COUNT(*) FROM ideas i WHERE {where_str} GROUP BY i.rating", params)
        stats['stars'] = dict(c.fetchall())

        # 2.2 颜色统计
        c.execute(f"SELECT i.color, COUNT(*) FROM ideas i WHERE {where_str} GROUP BY i.color", params)
        stats['colors'] = dict(c.fetchall())

        # 2.3 类型统计
        c.execute(f"SELECT i.item_type, COUNT(*) FROM ideas i WHERE {where_str} GROUP BY i.item_type", params)
        stats['types'] = dict(c.fetchall())

        # 2.4 标签统计 (需要关联)
        tag_sql = f"""
            SELECT t.name, COUNT(it.idea_id) as cnt
            FROM tags t
            JOIN idea_tags it ON t.id = it.tag_id
            JOIN ideas i ON it.idea_id = i.id
            WHERE {where_str}
            GROUP BY t.id
            ORDER BY cnt DESC
        """
        c.execute(tag_sql, params)
        stats['tags'] = c.fetchall()

        # 2.5 日期统计 (创建时间)
        base_date_sql = f"SELECT COUNT(*) FROM ideas i WHERE {where_str} AND "
        
        c.execute(base_date_sql + "date(i.created_at, 'localtime') = date('now', 'localtime')", params)
        stats['date_create']['today'] = c.fetchone()[0]
        
        c.execute(base_date_sql + "date(i.created_at, 'localtime') = date('now', '-1 day', 'localtime')", params)
        stats['date_create']['yesterday'] = c.fetchone()[0]
        
        c.execute(base_date_sql + "date(i.created_at, 'localtime') >= date('now', '-6 days', 'localtime')", params)
        stats['date_create']['week'] = c.fetchone()[0]
        
        c.execute(base_date_sql + "strftime('%Y-%m', i.created_at, 'localtime') = strftime('%Y-%m', 'now', 'localtime')", params)
        stats['date_create']['month'] = c.fetchone()[0]

        return stats

    def get_ideas(self, search, f_type, f_val, page=None, page_size=20, tag_filter=None, filter_criteria=None):
        c = self.conn.cursor()
        
        q = """
            SELECT DISTINCT 
                i.id, i.title, i.content, i.color, i.is_pinned, i.is_favorite, 
                i.created_at, i.updated_at, i.category_id, i.is_deleted, 
                i.item_type, i.data_blob, i.content_hash, i.is_locked, i.rating
            FROM ideas i 
            LEFT JOIN idea_tags it ON i.id=it.idea_id 
            LEFT JOIN tags t ON it.tag_id=t.id 
            WHERE 1=1
        """
        p = []
        
        if f_type == 'trash': q += ' AND i.is_deleted=1'
        else: q += ' AND (i.is_deleted=0 OR i.is_deleted IS NULL)'
        
        if f_type == 'category':
            if f_val is None: 
                q += ' AND i.category_id IS NULL'
            else: 
                # 递归包含子分类
                cat_ids = self._get_all_child_categories(f_val)
                placeholders = ','.join('?' * len(cat_ids))
                q += f" AND i.category_id IN ({placeholders})"
                p.extend(cat_ids)
        elif f_type == 'today': q += " AND date(i.updated_at,'localtime')=date('now','localtime')"
        elif f_type == 'untagged': q += ' AND i.id NOT IN (SELECT idea_id FROM idea_tags)'
        elif f_type == 'bookmark': q += ' AND i.is_favorite=1'
        
        if search:
            if self.fts5_supported:
                # FTS5 search for title/content OR regular search for tag name
                q += " AND (i.id IN (SELECT rowid FROM ideas_fts WHERE ideas_fts MATCH ?) OR t.name LIKE ?)"
                p.append(search)
                p.append(f'%{search}%')
            else:
                # Fallback to LIKE search if FTS5 is not available
                q += ' AND (i.title LIKE ? OR i.content LIKE ? OR t.name LIKE ?)'
                p.extend([f'%{search}%'] * 3)

        if tag_filter:
            q += " AND i.id IN (SELECT idea_id FROM idea_tags WHERE tag_id = (SELECT id FROM tags WHERE name = ?))"
            p.append(tag_filter)

        if filter_criteria:
            if 'stars' in filter_criteria:
                stars = filter_criteria['stars']
                placeholders = ','.join('?' * len(stars))
                q += f" AND i.rating IN ({placeholders})"
                p.extend(stars)
            
            if 'colors' in filter_criteria:
                colors = filter_criteria['colors']
                placeholders = ','.join('?' * len(colors))
                q += f" AND i.color IN ({placeholders})"
                p.extend(colors)

            if 'types' in filter_criteria:
                types = filter_criteria['types']
                placeholders = ','.join('?' * len(types))
                q += f" AND i.item_type IN ({placeholders})"
                p.extend(types)

            if 'tags' in filter_criteria:
                tags = filter_criteria['tags']
                tag_placeholders = ','.join('?' * len(tags))
                q += f" AND i.id IN (SELECT idea_id FROM idea_tags JOIN tags ON idea_tags.tag_id = tags.id WHERE tags.name IN ({tag_placeholders}))"
                p.extend(tags)

            if 'date_create' in filter_criteria:
                date_conditions = []
                for d_opt in filter_criteria['date_create']:
                    if d_opt == 'today':
                        date_conditions.append("date(i.created_at,'localtime')=date('now','localtime')")
                    elif d_opt == 'yesterday':
                        date_conditions.append("date(i.created_at,'localtime')=date('now','-1 day','localtime')")
                    elif d_opt == 'week':
                        date_conditions.append("date(i.created_at,'localtime')>=date('now','-6 days','localtime')")
                    elif d_opt == 'month':
                        date_conditions.append("strftime('%Y-%m',i.created_at,'localtime')=strftime('%Y-%m','now','localtime')")
                
                if date_conditions:
                    q += " AND (" + " OR ".join(date_conditions) + ")"

        if f_type == 'trash':
            q += ' ORDER BY i.updated_at DESC'
        else:
            q += ' ORDER BY i.is_pinned DESC, i.updated_at DESC'
            
        if page is not None and page_size is not None:
            limit = page_size
            offset = (page - 1) * page_size
            q += ' LIMIT ? OFFSET ?'
            p.extend([limit, offset])
            
        c.execute(q, p)
        return c.fetchall()

    def get_ideas_count(self, search, f_type, f_val, tag_filter=None, filter_criteria=None):
        c = self.conn.cursor()
        q = "SELECT COUNT(DISTINCT i.id) FROM ideas i LEFT JOIN idea_tags it ON i.id=it.idea_id LEFT JOIN tags t ON it.tag_id=t.id WHERE 1=1"
        p = []
        
        if f_type == 'trash': q += ' AND i.is_deleted=1'
        else: q += ' AND (i.is_deleted=0 OR i.is_deleted IS NULL)'
        
        if f_type == 'category':
            if f_val is None: q += ' AND i.category_id IS NULL'
            else: q += ' AND i.category_id=?'; p.append(f_val)
        elif f_type == 'today': q += " AND date(i.updated_at,'localtime')=date('now','localtime')"
        elif f_type == 'untagged': q += ' AND i.id NOT IN (SELECT idea_id FROM idea_tags)'
        elif f_type == 'bookmark': q += ' AND i.is_favorite=1'
        
        if search:
            if self.fts5_supported:
                q += " AND (i.id IN (SELECT rowid FROM ideas_fts WHERE ideas_fts MATCH ?) OR t.name LIKE ?)"
                p.append(search)
                p.append(f'%{search}%')
            else:
                q += ' AND (i.title LIKE ? OR i.content LIKE ? OR t.name LIKE ?)'
                p.extend([f'%{search}%'] * 3)

        if tag_filter:
            q += " AND i.id IN (SELECT idea_id FROM idea_tags WHERE tag_id = (SELECT id FROM tags WHERE name = ?))"
            p.append(tag_filter)

        if filter_criteria:
            if 'stars' in filter_criteria:
                stars = filter_criteria['stars']
                placeholders = ','.join('?' * len(stars))
                q += f" AND i.rating IN ({placeholders})"
                p.extend(stars)
            if 'colors' in filter_criteria:
                colors = filter_criteria['colors']
                placeholders = ','.join('?' * len(colors))
                q += f" AND i.color IN ({placeholders})"
                p.extend(colors)
            if 'types' in filter_criteria:
                types = filter_criteria['types']
                placeholders = ','.join('?' * len(types))
                q += f" AND i.item_type IN ({placeholders})"
                p.extend(types)
            if 'tags' in filter_criteria:
                tags = filter_criteria['tags']
                tag_placeholders = ','.join('?' * len(tags))
                q += f" AND i.id IN (SELECT idea_id FROM idea_tags JOIN tags ON idea_tags.tag_id = tags.id WHERE tags.name IN ({tag_placeholders}))"
                p.extend(tags)
            if 'date_create' in filter_criteria:
                date_conditions = []
                for d_opt in filter_criteria['date_create']:
                    if d_opt == 'today': date_conditions.append("date(i.created_at,'localtime')=date('now','localtime')")
                    elif d_opt == 'yesterday': date_conditions.append("date(i.created_at,'localtime')=date('now','-1 day','localtime')")
                    elif d_opt == 'week': date_conditions.append("date(i.created_at,'localtime')>=date('now','-6 days','localtime')")
                    elif d_opt == 'month': date_conditions.append("strftime('%Y-%m',i.created_at,'localtime')=strftime('%Y-%m','now','localtime')")
                if date_conditions:
                    q += " AND (" + " OR ".join(date_conditions) + ")"
            
        c.execute(q, p)
        return c.fetchone()[0]

    def get_tags(self, iid):
        c = self.conn.cursor()
        c.execute('SELECT t.name FROM tags t JOIN idea_tags it ON t.id=it.tag_id WHERE it.idea_id=?', (iid,))
        return [r[0] for r in c.fetchall()]

    def get_all_tags(self):
        c = self.conn.cursor()
        c.execute('SELECT name FROM tags ORDER BY name')
        return [r[0] for r in c.fetchall()]

    def get_categories(self):
        c = self.conn.cursor()
        c.execute('SELECT * FROM categories ORDER BY sort_order ASC, name ASC')
        return c.fetchall()

    def add_category(self, name, parent_id=None):
        c = self.conn.cursor()
        if parent_id is None:
            c.execute("SELECT MAX(sort_order) FROM categories WHERE parent_id IS NULL")
        else:
            c.execute("SELECT MAX(sort_order) FROM categories WHERE parent_id = ?", (parent_id,))
        max_order = c.fetchone()[0]
        new_order = (max_order or 0) + 1
        
        palette = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEEAD',
            '#D4A5A5', '#9B59B6', '#3498DB', '#E67E22', '#2ECC71',
            '#E74C3C', '#F1C40F', '#1ABC9C', '#34495E', '#95A5A6'
        ]
        chosen_color = random.choice(palette)
        
        c.execute(
            'INSERT INTO categories (name, parent_id, sort_order, color) VALUES (?, ?, ?, ?)', 
            (name, parent_id, new_order, chosen_color)
        )
        self.conn.commit()

    def rename_category(self, cat_id, new_name):
        c = self.conn.cursor()
        c.execute('UPDATE categories SET name=? WHERE id=?', (new_name, cat_id))
        self.conn.commit()
    
    def set_category_color(self, cat_id, color):
        c = self.conn.cursor()
        try:
            find_ids_query = """
                WITH RECURSIVE category_tree(id) AS (
                    SELECT ?
                    UNION ALL
                    SELECT c.id FROM categories c JOIN category_tree ct ON c.parent_id = ct.id
                )
                SELECT id FROM category_tree;
            """
            c.execute(find_ids_query, (cat_id,))
            all_ids = [row[0] for row in c.fetchall()]

            if not all_ids:
                return

            placeholders = ','.join('?' * len(all_ids))

            update_ideas_query = f"UPDATE ideas SET color = ? WHERE category_id IN ({placeholders})"
            c.execute(update_ideas_query, (color, *all_ids))

            update_categories_query = f"UPDATE categories SET color = ? WHERE id IN ({placeholders})"
            c.execute(update_categories_query, (color, *all_ids))

            self.conn.commit()
        except Exception as e:
            self.conn.rollback()

    def set_category_preset_tags(self, cat_id, tags_str):
        c = self.conn.cursor()
        c.execute('UPDATE categories SET preset_tags=? WHERE id=?', (tags_str, cat_id))
        self.conn.commit()

    def get_category_preset_tags(self, cat_id):
        c = self.conn.cursor()
        c.execute('SELECT preset_tags FROM categories WHERE id=?', (cat_id,))
        res = c.fetchone()
        return res[0] if res else ""

    def apply_preset_tags_to_category_items(self, cat_id, tags_list):
        if not tags_list: return
        c = self.conn.cursor()
        c.execute('SELECT id FROM ideas WHERE category_id=? AND is_deleted=0', (cat_id,))
        items = c.fetchall()
        for (iid,) in items:
            self._append_tags(iid, tags_list)
        self.conn.commit()

    def delete_category(self, cid):
        c = self.conn.cursor()
        c.execute('UPDATE ideas SET category_id=NULL WHERE category_id=?', (cid,))
        c.execute('DELETE FROM categories WHERE id=?', (cid,))
        self.conn.commit()

    def get_counts(self):
        c = self.conn.cursor()
        d = {}
        queries = {
            'all': "is_deleted=0 OR is_deleted IS NULL",
            'today': "(is_deleted=0 OR is_deleted IS NULL) AND date(updated_at,'localtime')=date('now','localtime')",
            'uncategorized': "(is_deleted=0 OR is_deleted IS NULL) AND category_id IS NULL",
            'untagged': "(is_deleted=0 OR is_deleted IS NULL) AND id NOT IN (SELECT idea_id FROM idea_tags)",
            'bookmark': "(is_deleted=0 OR is_deleted IS NULL) AND is_favorite=1",
            'trash': "is_deleted=1"
        }
        for k, v in queries.items():
            c.execute(f"SELECT COUNT(*) FROM ideas WHERE {v}")
            d[k] = c.fetchone()[0]
            
        c.execute("SELECT category_id, COUNT(*) FROM ideas WHERE (is_deleted=0 OR is_deleted IS NULL) GROUP BY category_id")
        d['categories'] = dict(c.fetchall())
        return d

    def get_top_tags(self):
        c = self.conn.cursor()
        c.execute('''SELECT t.name, COUNT(it.idea_id) as c FROM tags t 
                     JOIN idea_tags it ON t.id=it.tag_id JOIN ideas i ON it.idea_id=i.id 
                     WHERE i.is_deleted=0 GROUP BY t.id ORDER BY c DESC LIMIT 5''')
        return c.fetchall()

    def get_partitions_tree(self):
        class Partition:
            def __init__(self, id, name, color, parent_id, sort_order):
                self.id = id
                self.name = name
                self.color = color
                self.parent_id = parent_id
                self.sort_order = sort_order
                self.children = []

        c = self.conn.cursor()
        c.execute("SELECT id, name, color, parent_id, sort_order FROM categories ORDER BY sort_order ASC, name ASC")
        
        nodes = {row[0]: Partition(*row) for row in c.fetchall()}
        
        tree = []
        for node_id, node in nodes.items():
            if node.parent_id in nodes:
                nodes[node.parent_id].children.append(node)
            else:
                tree.append(node)
                
        return tree

    def get_partition_item_counts(self):
        c = self.conn.cursor()
        counts = {'partitions': {}}

        c.execute("SELECT COUNT(*) FROM ideas WHERE is_deleted=0")
        counts['total'] = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM ideas WHERE is_deleted=0 AND date(updated_at, 'localtime') = date('now', 'localtime')")
        counts['today_modified'] = c.fetchone()[0]
        
        c.execute("SELECT category_id, COUNT(*) FROM ideas WHERE is_deleted=0 GROUP BY category_id")
        for cat_id, count in c.fetchall():
            if cat_id is not None:
                counts['partitions'][cat_id] = count

        # Add missing counts
        c.execute("SELECT COUNT(*) FROM ideas i JOIN idea_tags it ON i.id = it.idea_id JOIN tags t ON it.tag_id = t.id WHERE t.name = '剪贴板' AND i.is_deleted=0")
        counts['clipboard'] = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM ideas WHERE is_favorite=1 AND is_deleted=0")
        counts['bookmark'] = c.fetchone()[0]

        return counts
    
    def save_category_order(self, update_list):
        c = self.conn.cursor()
        try:
            c.execute("BEGIN TRANSACTION")
            for item in update_list:
                c.execute(
                    "UPDATE categories SET sort_order = ?, parent_id = ? WHERE id = ?",
                    (item['sort_order'], item['parent_id'], item['id'])
                )
            c.execute("COMMIT")
        except Exception as e:
            c.execute("ROLLBACK")
            pass
        finally:
            self.conn.commit()

    def rename_tag(self, old_name, new_name):
        new_name = new_name.strip()
        if not new_name or old_name == new_name: return
        c = self.conn.cursor()
        c.execute("SELECT id FROM tags WHERE name=?", (old_name,))
        old_res = c.fetchone()
        if not old_res: return
        old_id = old_res[0]
        c.execute("SELECT id FROM tags WHERE name=?", (new_name,))
        new_res = c.fetchone()
        try:
            if new_res:
                new_id = new_res[0]
                c.execute("UPDATE OR IGNORE idea_tags SET tag_id=? WHERE tag_id=?", (new_id, old_id))
                c.execute("DELETE FROM idea_tags WHERE tag_id=?", (old_id,))
                c.execute("DELETE FROM tags WHERE id=?", (old_id,))
            else:
                c.execute("UPDATE tags SET name=? WHERE id=?", (new_name, old_id))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()

    def delete_tag(self, tag_name):
        c = self.conn.cursor()
        c.execute("SELECT id FROM tags WHERE name=?", (tag_name,))
        res = c.fetchone()
        if res:
            tag_id = res[0]
            c.execute("DELETE FROM idea_tags WHERE tag_id=?", (tag_id,))
            c.execute("DELETE FROM tags WHERE id=?", (tag_id,))
            self.conn.commit()