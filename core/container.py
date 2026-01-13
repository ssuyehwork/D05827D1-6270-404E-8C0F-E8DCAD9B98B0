# -*- coding: utf-8 -*-
# core/container.py
from data.db_context import DBContext
from data.repositories.idea_repository import IdeaRepository
from data.repositories.category_repository import CategoryRepository
from data.repositories.tag_repository import TagRepository
from services.idea_service import IdeaService

class AppContainer:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AppContainer, cls).__new__(cls)
            cls._instance._init_components()
        return cls._instance

    def _init_components(self):
        self.db_context = DBContext()
        
        self.idea_repo = IdeaRepository(self.db_context)
        self.category_repo = CategoryRepository(self.db_context)
        self.tag_repo = TagRepository(self.db_context)

        self.idea_service = IdeaService(self.idea_repo, self.category_repo, self.tag_repo)

    @property
    def service(self):
        return self.idea_service