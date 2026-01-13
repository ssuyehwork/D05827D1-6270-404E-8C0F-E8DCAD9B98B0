# -*- coding: utf-8 -*-
# data/repositories/tag_repository.py

class TagRepository:
    def __init__(self, db_context):
        self.db = db_context

    def get_by_idea(self, iid):
        c = self.db.get_cursor()
        c.execute('SELECT t.name FROM tags t JOIN idea_tags it ON t.id=it.tag_id WHERE it.idea_id=?', (iid,))
        return [r[0] for r in c.fetchall()]

    def get_all(self):
        c = self.db.get_cursor()
        c.execute('SELECT name FROM tags ORDER BY name')
        return [r[0] for r in c.fetchall()]

    def update_tags(self, iid, tags):
        c = self.db.get_cursor()
        c.execute('DELETE FROM idea_tags WHERE idea_id=?', (iid,))
        if tags:
            for t in tags:
                t = t.strip()
                if t:
                    c.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (t,))
                    c.execute('SELECT id FROM tags WHERE name=?', (t,))
                    res = c.fetchone()
                    if res:
                        tid = res[0]
                        c.execute('INSERT OR IGNORE INTO idea_tags VALUES (?,?)', (iid, tid))
        self.db.commit()

    def add_to_multiple(self, idea_ids, tags):
        if not idea_ids or not tags: return
        c = self.db.get_cursor()
        for t in tags:
            t = t.strip()
            if t:
                c.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (t,))
                c.execute('SELECT id FROM tags WHERE name=?', (t,))
                res = c.fetchone()
                if res:
                    tid = res[0]
                    for iid in idea_ids:
                        c.execute('INSERT OR IGNORE INTO idea_tags (idea_id, tag_id) VALUES (?,?)', (iid, tid))
        self.db.commit()

    def remove_from_multiple(self, idea_ids, tag_name):
        if not idea_ids or not tag_name: return
        c = self.db.get_cursor()
        c.execute('SELECT id FROM tags WHERE name=?', (tag_name,))
        res = c.fetchone()
        if not res: return
        tid = res[0]
        placeholders = ','.join('?' * len(idea_ids))
        sql = f'DELETE FROM idea_tags WHERE tag_id=? AND idea_id IN ({placeholders})'
        c.execute(sql, (tid, *idea_ids))
        self.db.commit()

    def get_top_tags(self):
        c = self.db.get_cursor()
        c.execute('''SELECT t.name, COUNT(it.idea_id) as c FROM tags t 
                     JOIN idea_tags it ON t.id=it.tag_id JOIN ideas i ON it.idea_id=i.id 
                     WHERE i.is_deleted=0 GROUP BY t.id ORDER BY c DESC LIMIT 5''')
        return c.fetchall()