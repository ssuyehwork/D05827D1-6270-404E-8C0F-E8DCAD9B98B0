# application/services/idea_service.py
from typing import List, Optional, Any, Dict
from domain.entities import Idea, Tag
from infrastructure.repositories.idea_repository import IdeaRepository
from infrastructure.repositories.tag_repository import TagRepository
from core.config import COLORS

class IdeaService:
    def __init__(self, idea_repository: IdeaRepository, tag_repository: TagRepository):
        self._idea_repo = idea_repository
        self._tag_repo = tag_repository

    def create_idea(self, title: str, content: str, tags: List[str] = None, category_id: Optional[int] = None) -> int:
        # Business logic for creating a new idea
        color = COLORS['default_note']
        
        tag_entities = []
        if tags:
            # This is simplified. In a real scenario, you'd ensure tags exist or create them.
            # For now, we assume tags are just names.
            # A proper implementation would use TagRepository to get or create Tag entities.
            pass

        new_idea = Idea(
            id=0, # ID will be set by the database
            title=title,
            content=content,
            color=color,
            category_id=category_id,
            tags=[] # Tags should be handled properly
        )
        
        # Validation
        errors = new_idea.validate()
        if errors:
            raise ValueError(", ".join(errors))

        idea_id = self._idea_repo.add(new_idea)
        return idea_id

    def get_idea(self, idea_id: int) -> Optional[Idea]:
        return self._idea_repo.get_by_id(idea_id, include_blob=True)

    def find_ideas(self, search: str, f_type: str, f_val: Any, page: Optional[int] = None, page_size: int = 20, tag_filter: Optional[str] = None, filter_criteria: Optional[Dict[str, Any]] = None) -> List[Idea]:
        return self._idea_repo.find(search, f_type, f_val, page, page_size, tag_filter, filter_criteria)
    
    def get_ideas_count(self, search: str, f_type: str, f_val: Any, tag_filter: Optional[str] = None, filter_criteria: Optional[Dict[str, Any]] = None) -> int:
        return self._idea_repo.get_count(search, f_type, f_val, tag_filter, filter_criteria)

    def batch_toggle_favorite(self, idea_ids: List[int]) -> None:
        if not idea_ids:
            return
            
        ideas = [self._idea_repo.get_by_id(iid) for iid in idea_ids if iid]
        ideas = [idea for idea in ideas if idea] # Filter out None

        # Business Rule: if any are not favorited, favorite all. Otherwise, unfavorite all.
        any_not_favorited = any(not idea.is_favorite for idea in ideas)
        target_state = any_not_favorited

        for idea in ideas:
            idea.is_favorite = target_state
            # Business Rule: update color when favorited/unfavorited
            if target_state:
                idea.color = COLORS.get('bookmark', '#ff6b81')
            else:
                # This logic is complex and depends on category color.
                # For now, we simplify it. A full implementation would need CategoryRepository.
                idea.color = COLORS.get('default_note')
            self._idea_repo.update(idea)

    def set_rating(self, idea_ids: List[int], rating: int) -> None:
        if rating < 0 or rating > 5:
            raise ValueError("Rating must be between 0 and 5.")
        for idea_id in idea_ids:
            self._idea_repo.update_field(idea_id, 'rating', rating)
            
    def move_to_category(self, idea_ids: List[int], category_id: Optional[int], category_color: Optional[str] = None) -> None:
        # More complex logic would be needed here involving category preset tags, etc.
        # This is a simplified version.
        locked_statuses = self._idea_repo.get_lock_status(idea_ids)
        
        color = category_color or COLORS.get('uncategorized', '#0A362F')

        for idea_id in idea_ids:
            if not locked_statuses.get(idea_id, False): # Check if not locked
                self._idea_repo.update_field(idea_id, 'category_id', category_id)
                self._idea_repo.update_field(idea_id, 'color', color)
                # Here we should also handle preset tags, which requires TagRepository and CategoryRepository.

    def delete_ideas(self, idea_ids: List[int], permanent: bool = False) -> None:
        locked_statuses = self._idea_repo.get_lock_status(idea_ids)
        trash_color = COLORS.get('trash', '#2d2d2d')
        for idea_id in idea_ids:
            if not locked_statuses.get(idea_id, False) or permanent:
                if not permanent:
                    self._idea_repo.update_field(idea_id, 'color', trash_color)
                self._idea_repo.delete(idea_id, permanent=permanent)

    def restore_ideas(self, idea_ids: List[int]) -> None:
        uncat_color = COLORS.get('uncategorized', '#0A362F')
        for idea_id in idea_ids:
            self._idea_repo.restore(idea_id)
            self._idea_repo.update_field(idea_id, 'color', uncat_color)

    def add_tags_to_ideas(self, idea_ids: List[int], tags: List[str]) -> None:
        self._idea_repo.add_tags_to_ideas(idea_ids, tags)

    def remove_tag_from_ideas(self, idea_ids: List[int], tag: str) -> None:
        self._idea_repo.remove_tag_from_ideas(idea_ids, tag)
