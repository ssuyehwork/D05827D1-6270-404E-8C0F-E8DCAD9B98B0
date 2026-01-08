# domain/entities.py
from __future__ import annotations
import dataclasses
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

@dataclass
class Tag:
    id: int
    name: str

@dataclass
class Category:
    id: int
    name: str
    parent_id: Optional[int]
    color: str
    sort_order: int
    preset_tags: Optional[str] = None
    children: List[Category] = field(default_factory=list)

@dataclass
class Idea:
    id: int
    title: str
    content: str
    color: str
    is_pinned: bool = False
    is_favorite: bool = False # Corresponds to 'bookmark'
    is_locked: bool = False
    rating: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    category_id: Optional[int] = None
    is_deleted: bool = False
    item_type: str = 'text'
    data_blob: Optional[bytes] = None
    content_hash: Optional[str] = None
    tags: List[Tag] = field(default_factory=list)

    def can_delete(self) -> bool:
        """业务规则：锁定的不能删除"""
        return not self.is_locked

    def validate(self) -> List[str]:
        """数据验证"""
        errors = []
        if not self.title:
            errors.append("标题不能为空")
        if self.rating < 0 or self.rating > 5:
            errors.append("星级必须在 0-5 之间")
        return errors
