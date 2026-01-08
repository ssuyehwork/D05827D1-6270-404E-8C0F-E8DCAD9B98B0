# application/services/category_service.py
from typing import List, Optional
from domain.entities import Category
from infrastructure.repositories.category_repository import CategoryRepository
from infrastructure.repositories.idea_repository import IdeaRepository

class CategoryService:
    def __init__(self, category_repository: CategoryRepository, idea_repository: IdeaRepository):
        self._category_repo = category_repository
        self._idea_repo = idea_repository

    def get_all_categories(self) -> List[Category]:
        return self._category_repo.get_all()
        
    def create_category(self, name: str, parent_id: Optional[int] = None) -> None:
        if not name.strip():
            raise ValueError("Category name cannot be empty.")
        self._category_repo.add(name, parent_id)
        
    def rename_category(self, category_id: int, new_name: str) -> None:
        if not new_name.strip():
            raise ValueError("Category name cannot be empty.")
        self._category_repo.rename(category_id, new_name)
        
    def delete_category(self, category_id: int) -> None:
        # Business Logic: First, decouple all ideas from this category.
        self._idea_repo.connection.cursor().execute(
            'UPDATE ideas SET category_id=NULL WHERE category_id=?',
            (category_id,)
        )
        self._idea_repo.connection.commit()
        
        # Then, delete the category itself.
        self._category_repo.delete(category_id)
        
    def set_category_color(self, category_id: int, color: str) -> None:
        # Business Logic: update color for the category and all its descendants,
        # and also update the color of all ideas within these categories.
        cursor = self._category_repo.connection.cursor()
        try:
            # 1. Find all descendant category IDs (including the parent)
            find_ids_query = """
                WITH RECURSIVE category_tree(id) AS (
                    SELECT ?
                    UNION ALL
                    SELECT c.id FROM categories c JOIN category_tree ct ON c.parent_id = ct.id
                )
                SELECT id FROM category_tree;
            """
            cursor.execute(find_ids_query, (category_id,))
            all_ids = [row[0] for row in cursor.fetchall()]

            if not all_ids:
                return

            placeholders = ','.join('?' * len(all_ids))

            # 2. Tell repositories to update ideas and categories
            update_ideas_query = f"UPDATE ideas SET color = ? WHERE category_id IN ({placeholders})"
            cursor.execute(update_ideas_query, (color, *all_ids))

            update_categories_query = f"UPDATE categories SET color = ? WHERE id IN ({placeholders})"
            cursor.execute(update_categories_query, (color, *all_ids))

            self._category_repo.connection.commit()
        except Exception as e:
            self._category_repo.connection.rollback()
            raise e

    def build_category_tree(self) -> List[Category]:
        categories = self._category_repo.get_all()
        category_map = {cat.id: cat for cat in categories}
        
        tree = []
        for cat in categories:
            if cat.parent_id in category_map:
                parent = category_map[cat.parent_id]
                parent.children.append(cat)
            else:
                tree.append(cat)
        return tree
