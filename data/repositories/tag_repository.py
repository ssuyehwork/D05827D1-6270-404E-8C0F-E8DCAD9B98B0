# data/repositories/tag_repository.py

class TagRepository:
    def __init__(self, conn):
        self.conn = conn

    def update_tags_for_idea(self, iid, tags):
        c = self.conn.cursor()
        c.execute('DELETE FROM idea_tags WHERE idea_id=?', (iid,))
        if not tags:
            self.conn.commit()
            return
            
        for t in tags:
            t = t.strip()
            if t:
                c.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (t,))
                c.execute('SELECT id FROM tags WHERE name=?', (t,))
                tid = c.fetchone()[0]
                c.execute('INSERT INTO idea_tags VALUES (?,?)', (iid, tid))
        self.conn.commit()

    def get_tags_for_idea(self, iid):
        c = self.conn.cursor()
        c.execute('SELECT t.name FROM tags t JOIN idea_tags it ON t.id=it.tag_id WHERE it.idea_id=?', (iid,))
        return [r[0] for r in c.fetchall()]

    def get_all_tags_with_counts(self):
        c = self.conn.cursor()
        c.execute('''
            SELECT t.name, COUNT(it.idea_id) as cnt 
            FROM tags t 
            JOIN idea_tags it ON t.id = it.tag_id 
            JOIN ideas i ON it.idea_id = i.id 
            WHERE i.is_deleted = 0 
            GROUP BY t.id 
            ORDER BY cnt DESC, t.name ASC
        ''')
        return c.fetchall()
