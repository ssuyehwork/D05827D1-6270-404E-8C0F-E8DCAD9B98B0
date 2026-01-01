# data/schema_migrations.py
import logging

logger = logging.getLogger(__name__)

class SchemaMigration:
    @staticmethod
    def _get_db_version(conn):
        c = conn.cursor()
        try:
            c.execute("PRAGMA user_version")
            version = c.fetchone()[0]
            return version
        except Exception:
            # If user_version does not exist, it's a very old db, treat as version 0
            return 0

    @staticmethod
    def _set_db_version(conn, version):
        c = conn.cursor()
        c.execute(f"PRAGMA user_version = {version}")
        conn.commit()

    @staticmethod
    def apply(conn):
        logger.info("开始检查数据库结构迁移...")
        current_version = SchemaMigration._get_db_version(conn)
        logger.info(f"当前数据库版本: {current_version}")

        if current_version < 1:
            SchemaMigration._migrate_to_v1(conn)
            SchemaMigration._set_db_version(conn, 1)
            logger.info("数据库迁移到 v1")
        
        # Add future migrations here
        # if current_version < 2:
        #     SchemaMigration._migrate_to_v2(conn)
        #     SchemaMigration._set_db_version(conn, 2)
        #     logger.info("数据库迁移到 v2")
            
        logger.info("数据库结构检查完成。")

    @staticmethod
    def _migrate_to_v1(conn):
        c = conn.cursor()
        
        logger.info("v1 迁移: 创建初始表结构...")
        c.execute('''CREATE TABLE IF NOT EXISTS ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, content TEXT, color TEXT DEFAULT '#4a90e2',
            is_pinned INTEGER DEFAULT 0, is_favorite INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            category_id INTEGER, is_deleted INTEGER DEFAULT 0,
            item_type TEXT DEFAULT 'text', data_blob BLOB,
            content_hash TEXT
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
        c.execute('CREATE INDEX IF NOT EXISTS idx_content_hash ON ideas(content_hash)')
        
        # This part is for migrating from even older, pre-versioning schemas
        logger.info("v1 迁移: 检查并添加旧版本可能缺失的列...")
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
            try: c.execute('ALTER TABLE ideas ADD COLUMN content_hash TEXT')
            except: pass
        
        c.execute("PRAGMA table_info(categories)")
        cat_cols = [i[1] for i in c.fetchall()]
        if 'sort_order' not in cat_cols:
            try: c.execute('ALTER TABLE categories ADD COLUMN sort_order INTEGER DEFAULT 0')
            except: pass
            
        conn.commit()
