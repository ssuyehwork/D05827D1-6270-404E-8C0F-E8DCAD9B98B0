# infrastructure/database_setup.py
import sqlite3
import logging

def setup_database(connection: sqlite3.Connection):
    """
    Initializes the database schema, creating tables and adding necessary columns
    if they don't exist.
    """
    logging.info("Setting up database schema...")
    cursor = connection.cursor()

    try:
        # Create core tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ideas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT,
                color TEXT DEFAULT '#FFFFFF',
                is_pinned INTEGER DEFAULT 0,
                is_favorite INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                category_id INTEGER,
                is_deleted INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                name TEXT NOT NULL, 
                parent_id INTEGER, 
                color TEXT DEFAULT "#808080",
                sort_order INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS idea_tags (
                idea_id INTEGER, 
                tag_id INTEGER, 
                PRIMARY KEY (idea_id, tag_id)
            )
        """)

        # --- Add missing columns for backward compatibility ---
        
        # Get existing columns for 'ideas' table
        cursor.execute("PRAGMA table_info(ideas)")
        ideas_cols = [col[1] for col in cursor.fetchall()]
        
        ideas_updates = [
            ('item_type', "TEXT DEFAULT 'text'"),
            ('data_blob', 'BLOB'),
            ('content_hash', 'TEXT'),
            ('is_locked', 'INTEGER DEFAULT 0'),
            ('rating', 'INTEGER DEFAULT 0')
        ]
        for col, type_def in ideas_updates:
            if col not in ideas_cols:
                logging.info(f"Adding column '{col}' to 'ideas' table.")
                cursor.execute(f'ALTER TABLE ideas ADD COLUMN {col} {type_def}')

        # Get existing columns for 'categories' table
        cursor.execute("PRAGMA table_info(categories)")
        cat_cols = [col[1] for col in cursor.fetchall()]
        
        categories_updates = [
            ('preset_tags', 'TEXT')
        ]
        for col, type_def in categories_updates:
            if col not in cat_cols:
                logging.info(f"Adding column '{col}' to 'categories' table.")
                cursor.execute(f'ALTER TABLE categories ADD COLUMN {col} {type_def}')

        connection.commit()
        logging.info("Database schema setup complete.")
        
    except sqlite3.Error as e:
        logging.error(f"Database setup failed: {e}")
        connection.rollback()
        raise e
