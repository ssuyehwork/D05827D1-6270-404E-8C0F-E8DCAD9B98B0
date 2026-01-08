# infrastructure/repositories/tag_repository.py
from typing import List
from domain.entities import Tag
from .base_repository import BaseRepository

class TagRepository(BaseRepository):
    def get_by_idea_id(self, idea_id: int) -> List[Tag]:
        query = '''
            SELECT t.id, t.name FROM tags t
            JOIN idea_tags it ON t.id = it.tag_id
            WHERE it.idea_id = ?
        '''
        rows = self._fetchall(query, (idea_id,))
        return [Tag(id=row['id'], name=row['name']) for row in rows]

    def get_all(self) -> List[Tag]:
        query = 'SELECT id, name FROM tags ORDER BY name'
        rows = self._fetchall(query)
        return [Tag(id=row['id'], name=row['name']) for row in rows]

    def get_top_tags(self, limit: int = 5) -> List[dict]:
        query = '''
            SELECT t.name, COUNT(it.idea_id) as c FROM tags t 
            JOIN idea_tags it ON t.id=it.tag_id 
            JOIN ideas i ON it.idea_id=i.id 
            WHERE i.is_deleted=0 
            GROUP BY t.id 
            ORDER BY c DESC 
            LIMIT ?
        '''
        return self._fetchall(query, (limit,))
        
    def rename(self, old_name: str, new_name: str) -> None:
        new_name = new_name.strip()
        if not new_name or old_name == new_name:
            return

        cursor = self.connection.cursor()
        
        # Find old and new tag IDs
        cursor.execute("SELECT id FROM tags WHERE name=?", (old_name,))
        old_res = cursor.fetchone()
        if not old_res:
            return
        old_id = old_res[0]

        cursor.execute("SELECT id FROM tags WHERE name=?", (new_name,))
        new_res = cursor.fetchone()

        try:
            if new_res:
                # If new tag name already exists, merge them
                new_id = new_res[0]
                cursor.execute("UPDATE OR IGNORE idea_tags SET tag_id=? WHERE tag_id=?", (new_id, old_id))
                cursor.execute("DELETE FROM idea_tags WHERE tag_id=?", (old_id,))
                cursor.execute("DELETE FROM tags WHERE id=?", (old_id,))
            else:
                # Otherwise, just rename
                cursor.execute("UPDATE tags SET name=? WHERE id=?", (new_name, old_id))
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            raise e

    def delete(self, tag_name: str) -> None:
        cursor = self.connection.cursor()
        cursor.execute("SELECT id FROM tags WHERE name=?", (tag_name,))
        res = cursor.fetchone()
        if res:
            tag_id = res[0]
            cursor.execute("DELETE FROM idea_tags WHERE tag_id=?", (tag_id,))
            cursor.execute("DELETE FROM tags WHERE id=?", (tag_id,))
            self.connection.commit()

    def get_union_tags_for_ideas(self, idea_ids: List[int]) -> List[str]:
        if not idea_ids:
            return []
        placeholders = ','.join('?' * len(idea_ids))
        sql = f'''
            SELECT DISTINCT t.name 
            FROM tags t 
            JOIN idea_tags it ON t.id = it.tag_id 
            WHERE it.idea_id IN ({placeholders})
            ORDER BY t.name ASC
        '''
        rows = self._fetchall(sql, tuple(idea_ids))
        return [row[0] for row in rows]
