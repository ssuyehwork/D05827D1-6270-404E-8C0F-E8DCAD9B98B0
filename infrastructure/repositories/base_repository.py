# infrastructure/repositories/base_repository.py
import sqlite3
from core.config import DB_NAME

class BaseRepository:
    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    @property
    def connection(self) -> sqlite3.Connection:
        return self._connection

    def _execute_script(self, query: str, params: tuple = ()):
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        self.connection.commit()
        return cursor

    def _fetchall(self, query: str, params: tuple = ()) -> list:
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

    def _fetchone(self, query: str, params: tuple = ()):
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()
