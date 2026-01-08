# application/services/statistics_service.py
import sqlite3
from typing import Dict, Any

class StatisticsService:
    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    def get_sidebar_counts(self) -> Dict[str, Any]:
        c = self._connection.cursor()
        d = {}
        queries = {
            'all': "is_deleted=0 OR is_deleted IS NULL",
            'today': "(is_deleted=0 OR is_deleted IS NULL) AND date(updated_at,'localtime')=date('now','localtime')",
            'uncategorized': "(is_deleted=0 OR is_deleted IS NULL) AND category_id IS NULL",
            'untagged': "(is_deleted=0 OR is_deleted IS NULL) AND id NOT IN (SELECT idea_id FROM idea_tags)",
            'bookmark': "(is_deleted=0 OR is_deleted IS NULL) AND is_favorite=1",
            'trash': "is_deleted=1"
        }
        for k, v in queries.items():
            c.execute(f"SELECT COUNT(*) FROM ideas WHERE {v}")
            d[k] = c.fetchone()[0]
            
        c.execute("SELECT category_id, COUNT(*) FROM ideas WHERE (is_deleted=0 OR is_deleted IS NULL) GROUP BY category_id")
        d['categories'] = dict(c.fetchall())
        return d

    def get_filter_panel_stats(self, search_text: str = '', filter_type: str = 'all', filter_value: Any = None) -> Dict[str, Any]:
        c = self._connection.cursor()
        stats = {
            'stars': {},
            'colors': {},
            'types': {},
            'tags': [],
            'date_create': {}
        }
        
        where_clauses = ["1=1"]
        params = []
        
        if filter_type == 'trash':
            where_clauses.append("i.is_deleted=1")
        else:
            where_clauses.append("(i.is_deleted=0 OR i.is_deleted IS NULL)")
            
        if filter_type == 'category':
            if filter_value is None:
                where_clauses.append("i.category_id IS NULL")
            else:
                where_clauses.append("i.category_id=?")
                params.append(filter_value)
        elif filter_type == 'today':
            where_clauses.append("date(i.updated_at,'localtime')=date('now','localtime')")
        elif filter_type == 'untagged':
            where_clauses.append("i.id NOT IN (SELECT idea_id FROM idea_tags)")
        elif filter_type == 'bookmark':
            where_clauses.append("i.is_favorite=1")
        
        if search_text:
            where_clauses.append("(i.title LIKE ? OR i.content LIKE ?)")
            params.extend([f'%{search_text}%', f'%{search_text}%'])
            
        where_str = " AND ".join(where_clauses)
        
        # Star ratings
        c.execute(f"SELECT i.rating, COUNT(*) FROM ideas i WHERE {where_str} GROUP BY i.rating", params)
        stats['stars'] = dict(c.fetchall())

        # Colors
        c.execute(f"SELECT i.color, COUNT(*) FROM ideas i WHERE {where_str} GROUP BY i.color", params)
        stats['colors'] = dict(c.fetchall())

        # Types
        c.execute(f"SELECT i.item_type, COUNT(*) FROM ideas i WHERE {where_str} GROUP BY i.item_type", params)
        stats['types'] = dict(c.fetchall())

        # Tags
        tag_sql = f"""
            SELECT t.name, COUNT(it.idea_id) as cnt
            FROM tags t
            JOIN idea_tags it ON t.id = it.tag_id
            JOIN ideas i ON it.idea_id = i.id
            WHERE {where_str}
            GROUP BY t.id
            ORDER BY cnt DESC
        """
        c.execute(tag_sql, params)
        stats['tags'] = c.fetchall()

        # Dates
        base_date_sql = f"SELECT COUNT(*) FROM ideas i WHERE {where_str} AND "
        c.execute(base_date_sql + "date(i.created_at, 'localtime') = date('now', 'localtime')", params)
        stats['date_create']['today'] = c.fetchone()[0]
        c.execute(base_date_sql + "date(i.created_at, 'localtime') = date('now', '-1 day', 'localtime')", params)
        stats['date_create']['yesterday'] = c.fetchone()[0]
        c.execute(base_date_sql + "date(i.created_at, 'localtime') >= date('now', '-6 days', 'localtime')", params)
        stats['date_create']['week'] = c.fetchone()[0]
        c.execute(base_date_sql + "strftime('%Y-%m', i.created_at, 'localtime') = strftime('%Y-%m', 'now', 'localtime')", params)
        stats['date_create']['month'] = c.fetchone()[0]

        return stats
