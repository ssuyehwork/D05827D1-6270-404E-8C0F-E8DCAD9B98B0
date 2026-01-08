# infrastructure/repositories/category_repository.py
import random
import sqlite3
from typing import List, Dict, Any, Optional
from domain.entities import Category
from .base_repository import BaseRepository

class CategoryRepository(BaseRepository):
    
    def get_all(self) -> List[Category]:
        rows = self._fetchall('SELECT * FROM categories ORDER BY sort_order ASC, name ASC')
        return [self._row_to_entity(row) for row in rows]

    def add(self, name: str, parent_id: Optional[int] = None) -> None:
        cursor = self.connection.cursor()
        
        if parent_id is None:
            cursor.execute("SELECT MAX(sort_order) FROM categories WHERE parent_id IS NULL")
        else:
            cursor.execute("SELECT MAX(sort_order) FROM categories WHERE parent_id = ?", (parent_id,))
            
        max_order = cursor.fetchone()[0]
        new_order = (max_order or 0) + 1
        
        palette = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEEAD',
            '#D4A5A5', '#9B59B6', '#3498DB', '#E67E22', '#2ECC71',
            '#E74C3C', '#F1C40F', '#1ABC9C', '#34495E', '#95A5A6'
        ]
        chosen_color = random.choice(palette)
        
        cursor.execute(
            'INSERT INTO categories (name, parent_id, sort_order, color) VALUES (?, ?, ?, ?)', 
            (name, parent_id, new_order, chosen_color)
        )
        self.connection.commit()

    def rename(self, category_id: int, new_name: str) -> None:
        self._execute_script('UPDATE categories SET name=? WHERE id=?', (new_name, category_id))

    def set_color(self, category_id: int, color: str) -> None:
        self._execute_script('UPDATE categories SET color=? WHERE id=?', (color, category_id))

    def set_preset_tags(self, category_id: int, tags_str: str) -> None:
        self._execute_script('UPDATE categories SET preset_tags=? WHERE id=?', (tags_str, category_id))

    def get_preset_tags(self, category_id: int) -> str:
        row = self._fetchone('SELECT preset_tags FROM categories WHERE id=?', (category_id,))
        return row[0] if row else ""

    def delete(self, category_id: int) -> None:
        self._execute_script('DELETE FROM categories WHERE id=?', (category_id,))

    def save_order(self, update_list: List[Dict[str, Any]]) -> None:
        cursor = self.connection.cursor()
        try:
            cursor.execute("BEGIN TRANSACTION")
            for item in update_list:
                cursor.execute(
                    "UPDATE categories SET sort_order = ?, parent_id = ? WHERE id = ?",
                    (item['sort_order'], item['parent_id'], item['id'])
                )
            cursor.execute("COMMIT")
        except Exception as e:
            cursor.execute("ROLLBACK")
            raise e
        finally:
            self.connection.commit()
    
    def _row_to_entity(self, row: sqlite3.Row) -> Category:
        return Category(
            id=row['id'],
            name=row['name'],
            parent_id=row['parent_id'],
            color=row['color'],
            sort_order=row['sort_order'],
            preset_tags=row['preset_tags'] if 'preset_tags' in row.keys() else None
        )
