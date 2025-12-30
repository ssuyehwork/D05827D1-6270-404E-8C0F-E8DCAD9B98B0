# data/db_manager.py
import sqlite3
import hashlib
import os
from core.config import DB_NAME

class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME)
        self._init_schema()

    def _init_schema(self):
        c = self.conn.cursor()
        
        # 1. 优先创建表
        c.execute('''CREATE TABLE IF NOT EXISTS ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, content TEXT, color TEXT DEFAULT '#4a90e2',
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
        
        # 2. 检查迁移
        # 迁移 ideas 表
        c.execute("PRAGMA table_info(ideas)")
        cols = [i[1] for i in c.fetchall()]
        if 'category_id' not in cols:
            try: c.execute('ALTER TABLE ideas ADD COLUMN category_id INTEGER')
            except: pass
        if 'is_deleted' not in cols:
            try: c.execute('ALTER TABLE ideas ADD COLUMN is_deleted INTEGER DEFAULT 0')
            except: pass
        if 'item_type' not in cols:
            try: c.execute("ALTER TABLE ideas ADD COLUMN item_type TEXT DEFAULT 'text'")
            except: pass
        if 'data_blob' not in cols:
            try: c.execute('ALTER TABLE ideas ADD COLUMN data_blob BLOB')
            except: pass
        if 'content_hash' not in cols:
            try:
                c.execute('ALTER TABLE ideas ADD COLUMN content_hash TEXT')
                c.execute('CREATE INDEX IF NOT EXISTS idx_content_hash ON ideas(content_hash)')
            except: pass
        
        # 迁移 categories 表
        c.execute("PRAGMA table_info(categories)")
        cat_cols = [i[1] for i in c.fetchall()]
        if 'sort_order' not in cat_cols:
            try:
                c.execute('ALTER TABLE categories ADD COLUMN sort_order INTEGER DEFAULT 0')
            except:
                pass
            
        self.conn.commit()

    # --- 核心 CRUD ---
    def add_idea(self, title, content, color, tags, cat_id):
        c = self.conn.cursor()
        c.execute('INSERT INTO ideas (title, content, color, category_id) VALUES (?,?,?,?)', (title, content, color, cat_id))
        iid = c.lastrowid
        self._update_tags(iid, tags)
        self.conn.commit()
        return iid  # 返回新建的ID

    def update_idea(self, iid, title, content, color, tags, cat_id):
        c = self.conn.cursor()
        c.execute('UPDATE ideas SET title=?, content=?, color=?, category_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?', (title, content, color, cat_id, iid))
        self._update_tags(iid, tags)
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

    def add_clipboard_item(self, item_type, content, data_blob=None, category_id=None):
        """
        专门用于剪贴板项目的新接口，包含去重和自动标记功能。
        """
        c = self.conn.cursor()

        # 1. 计算哈希值
        hasher = hashlib.sha256()
        if item_type == 'text' or item_type == 'file':
            hasher.update(content.encode('utf-8'))
        elif item_type == 'image' and data_blob:
            hasher.update(data_blob)
        content_hash = hasher.hexdigest()

        # 2. 检查内容是否已存在
        c.execute("SELECT id FROM ideas WHERE content_hash = ?", (content_hash,))
        existing_idea = c.fetchone()

        if existing_idea:
            # 内容已存在，更新时间戳
            idea_id = existing_idea[0]
            c.execute("UPDATE ideas SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (idea_id,))
            self.conn.commit()
            print(f"[DEBUG] 内容已存在，更新时间戳，ID={idea_id}")
            return idea_id
        else:
            # 内容不存在，创建新记录
            # 自动生成标题
            if item_type == 'text':
                title = content.strip().split('\n')[0][:50]
            elif item_type == 'image':
                title = "[图片]"
            elif item_type == 'file':
                title = f"[文件] {os.path.basename(content.split(';')[0])}"
            else:
                title = "未命名"

            # 插入数据
            c.execute(
                'INSERT INTO ideas (title, content, item_type, data_blob, category_id, content_hash) VALUES (?,?,?,?,?,?)',
                (title, content, item_type, data_blob, category_id, content_hash)
            )
            idea_id = c.lastrowid
            
            # 自动添加 "剪贴板" 标签
            self._update_tags(idea_id, ["剪贴板"])
            
            self.conn.commit()
            print(f"[DEBUG] 新增剪贴板内容，ID={idea_id}")
            return idea_id

    # --- 状态管理 ---
    def toggle_field(self, iid, field):
        c = self.conn.cursor()
        c.execute(f'UPDATE ideas SET {field} = NOT {field} WHERE id=?', (iid,))
        self.conn.commit()

    def set_deleted(self, iid, state):
        c = self.conn.cursor()
        c.execute('UPDATE ideas SET is_deleted=? WHERE id=?', (1 if state else 0, iid))
        self.conn.commit()

    def set_favorite(self, iid, state):
        c = self.conn.cursor()
        c.execute('UPDATE ideas SET is_favorite=? WHERE id=?', (1 if state else 0, iid))
        self.conn.commit()

    def move_category(self, iid, cat_id):
        c = self.conn.cursor()
        c.execute('UPDATE ideas SET category_id=? WHERE id=?', (cat_id, iid))
        self.conn.commit()

    def delete_permanent(self, iid):
        c = self.conn.cursor()
        c.execute('DELETE FROM ideas WHERE id=?', (iid,))
        self.conn.commit()

    # --- 查询 ---
    def get_idea(self, iid):
        c = self.conn.cursor()
        c.execute('SELECT * FROM ideas WHERE id=?', (iid,))
        return c.fetchone()

    def get_ideas(self, search, f_type, f_val):
        c = self.conn.cursor()
        q = "SELECT DISTINCT i.* FROM ideas i LEFT JOIN idea_tags it ON i.id=it.idea_id LEFT JOIN tags t ON it.tag_id=t.id WHERE 1=1"
        p = []
        
        if f_type == 'trash': q += ' AND i.is_deleted=1'
        else: q += ' AND (i.is_deleted=0 OR i.is_deleted IS NULL)'
        
        if f_type == 'category':
            if f_val is None: q += ' AND i.category_id IS NULL'
            else: q += ' AND i.category_id=?'; p.append(f_val)
        elif f_type == 'today': q += " AND date(i.updated_at,'localtime')=date('now','localtime')"
        elif f_type == 'clipboard': q += " AND i.id IN (SELECT idea_id FROM idea_tags WHERE tag_id = (SELECT id FROM tags WHERE name = '剪贴板'))"
        elif f_type == 'untagged': q += ' AND i.id NOT IN (SELECT idea_id FROM idea_tags)'
        elif f_type == 'favorite': q += ' AND i.is_favorite=1'
        
        if search:
            q += ' AND (i.title LIKE ? OR i.content LIKE ? OR t.name LIKE ?)'
            p.extend([f'%{search}%']*3)
            
        q += ' ORDER BY i.is_pinned DESC, i.updated_at DESC'
        c.execute(q, p)
        return c.fetchall()

    def get_tags(self, iid):
        c = self.conn.cursor()
        c.execute('SELECT t.name FROM tags t JOIN idea_tags it ON t.id=it.tag_id WHERE it.idea_id=?', (iid,))
        return [r[0] for r in c.fetchall()]

    # --- 统计与分类 ---
    def get_categories(self):
        c = self.conn.cursor()
        c.execute('SELECT * FROM categories ORDER BY sort_order ASC, name ASC')
        return c.fetchall()

    def add_category(self, name, parent_id=None):
        c = self.conn.cursor()
        # 查找当前父级下最大的 sort_order
        if parent_id is None:
            c.execute("SELECT MAX(sort_order) FROM categories WHERE parent_id IS NULL")
        else:
            c.execute("SELECT MAX(sort_order) FROM categories WHERE parent_id = ?", (parent_id,))
        max_order = c.fetchone()[0]
        new_order = (max_order or 0) + 1
        
        c.execute('INSERT INTO categories (name, parent_id, sort_order) VALUES (?, ?, ?)', (name, parent_id, new_order))
        self.conn.commit()

    def rename_category(self, cat_id, new_name):
        c = self.conn.cursor()
        c.execute('UPDATE categories SET name=? WHERE id=?', (new_name, cat_id))
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
            'clipboard': "(is_deleted=0 OR is_deleted IS NULL) AND id IN (SELECT idea_id FROM idea_tags WHERE tag_id = (SELECT id FROM tags WHERE name = '剪贴板'))",
            'uncategorized': "(is_deleted=0 OR is_deleted IS NULL) AND category_id IS NULL",
            'untagged': "(is_deleted=0 OR is_deleted IS NULL) AND id NOT IN (SELECT idea_id FROM idea_tags)",
            'favorite': "(is_deleted=0 OR is_deleted IS NULL) AND is_favorite=1",
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
        """查询并构建一个层级的分类树"""
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
        
        # 使用字典来快速查找节点
        nodes = {row[0]: Partition(*row) for row in c.fetchall()}
        
        tree = []
        for node_id, node in nodes.items():
            if node.parent_id in nodes:
                nodes[node.parent_id].children.append(node)
            else:
                # 顶层节点
                tree.append(node)
                
        return tree

    def get_partition_item_counts(self):
        """获取用于快速窗口的各种计数"""
        c = self.conn.cursor()
        counts = {'partitions': {}}

        # 1. 总项目数 (未删除)
        c.execute("SELECT COUNT(*) FROM ideas WHERE is_deleted=0")
        counts['total'] = c.fetchone()[0]

        # 2. 今日修改数 (未删除)
        c.execute("SELECT COUNT(*) FROM ideas WHERE is_deleted=0 AND date(updated_at, 'localtime') = date('now', 'localtime')")
        counts['today_modified'] = c.fetchone()[0]
        
        # 3. 按分区 (category) 统计
        c.execute("SELECT category_id, COUNT(*) FROM ideas WHERE is_deleted=0 GROUP BY category_id")
        for cat_id, count in c.fetchall():
            # 在这个简化版本中，我们将 category_id 直接用作 partition_id
            if cat_id is not None:
                counts['partitions'][cat_id] = count

        return counts
    
    def save_category_order(self, order_list):
        """
        保存分类的新顺序。
        :param order_list: 一个元组列表,每个元组为 (category_id, new_sort_order)
        """
        c = self.conn.cursor()
        try:
            c.execute("BEGIN TRANSACTION")
            for cat_id, order in order_list:
                c.execute("UPDATE categories SET sort_order = ? WHERE id = ?", (order, cat_id))
            c.execute("COMMIT")
            print(f"[DEBUG] 分类顺序已保存: {order_list}")
        except Exception as e:
            c.execute("ROLLBACK")
            print(f"[ERROR] 保存分类顺序失败: {e}")
        finally:
            self.conn.commit()
