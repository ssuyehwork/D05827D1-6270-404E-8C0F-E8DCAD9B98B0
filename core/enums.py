# core/enums.py
from enum import Enum

class FilterType(Enum):
    ALL = "all"
    TODAY = "today"
    CATEGORY = "category"
    CLIPBOARD = "clipboard"
    UNCATEGORIZED = "uncategorized"
    UNTAGGED = "untagged"
    FAVORITE = "favorite"
    TRASH = "trash"
