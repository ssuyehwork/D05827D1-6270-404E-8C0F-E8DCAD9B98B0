# data/repositories/category_repository.py

class CategoryRepository:
    def __init__(self, conn):
        self.conn = conn

    def get_all(self):
        c = self.conn.cursor()
        c.execute('SELECT * FROM categories ORDER BY sort_order ASC, name ASC')
        return c.fetchall()

    def add(self, name, parent_id=None):
        c = self.conn.cursor()
        if parent_id is None:
            c.execute("SELECT MAX(sort_order) FROM categories WHERE parent_id IS NULL")
        else:
            c.execute("SELECT MAX(sort_order) FROM categories WHERE parent_id = ?", (parent_id,))
        max_order = c.fetchone()[0]
        new_order = (max_order or 0) + 1
        
        c.execute('INSERT INTO categories (name, parent_id, sort_order) VALUES (?, ?, ?)', (name, parent_id, new_order))
        self.conn.commit()

    def rename(self, cat_id, new_name):
        c = self.conn.cursor()
        c.execute('UPDATE categories SET name=? WHERE id=?', (new_name, cat_id))
        self.conn.commit()

    def delete(self, cid):
        c = self.conn.cursor()
        # Note: Moving ideas should be a service-level concern
        c.execute('UPDATE ideas SET category_id=NULL WHERE category_id=?', (cid,))
        c.execute('DELETE FROM categories WHERE id=?', (cid,))
        self.conn.commit()

    def get_tree(self):
        class Partition:
            def __init__(self, id, name, color, parent_id, sort_order):
                self.id = id
                self.name = name
                self.color = color
                self.parent_id = parent_id
                self.sort_order = sort_order
                self.children = []

        c = self.conn.cursor()
        c.execute("SELECT id, name, color, parent_id, sort_order FROM categories ORDER BY sort_order ASC, name ASC")
        
        nodes = {row[0]: Partition(*row) for row in c.fetchall()}
        
        tree = []
        for node_id, node in nodes.items():
            if node.parent_id in nodes:
                nodes[node.parent_id].children.append(node)
            else:
                tree.append(node)
                
        return tree

    def save_order(self, update_list):
        c = self.conn.cursor()
        try:
            c.execute("BEGIN TRANSACTION")
            for item in update_list:
                c.execute(
                    "UPDATE categories SET sort_order = ?, parent_id = ? WHERE id = ?",
                    (item['sort_order'], item['parent_id'], item['id'])
                )
            c.execute("COMMIT")
        except Exception as e:
            c.execute("ROLLBACK")
            # Should raise this exception to be handled by the service layer
            raise e
