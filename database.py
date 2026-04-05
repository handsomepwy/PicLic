import sqlite3
import os

class DatabaseManager:
    def __init__(self, db_path="piclic.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initializes the SQLite schema as defined in Instruction.md."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Table: images
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS images (
                    id INTEGER PRIMARY KEY,
                    jpg_path TEXT UNIQUE,
                    folder_path TEXT
                )
            ''')

            # 2. Table: files
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY,
                    image_id INTEGER,
                    file_path TEXT UNIQUE,
                    file_type TEXT,
                    FOREIGN KEY (image_id) REFERENCES images(id)
                )
            ''')

            # 3. Table: tags
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY,
                    name TEXT UNIQUE
                )
            ''')

            # 4. Table: image_tags
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS image_tags (
                    image_id INTEGER,
                    tag_id INTEGER,
                    PRIMARY KEY (image_id, tag_id),
                    FOREIGN KEY (image_id) REFERENCES images(id),
                    FOREIGN KEY (tag_id) REFERENCES tags(id)
                )
            ''')

            # 5. Indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_images_folder ON images(folder_path)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_image_tags_tag ON image_tags(tag_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_image_tags_image ON image_tags(image_id)')
            
            conn.commit()

    def add_image(self, jpg_path, folder_path):
        """Adds a new image or returns existing ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('INSERT INTO images (jpg_path, folder_path) VALUES (?, ?)', (jpg_path, folder_path))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                cursor.execute('SELECT id FROM images WHERE jpg_path = ?', (jpg_path,))
                return cursor.fetchone()[0]

    def add_file_to_image(self, image_id, file_path, file_type):
        """Links a file (JPG, RAW, etc.) to an existing image ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('INSERT INTO files (image_id, file_path, file_type) VALUES (?, ?, ?)', 
                               (image_id, file_path, file_type))
                conn.commit()
            except sqlite3.IntegrityError:
                pass # Already exists

    def get_or_create_tag(self, tag_name):
        """Returns tag ID, creating it if it doesn't exist."""
        tag_name = tag_name.lower().strip()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('INSERT INTO tags (name) VALUES (?)', (tag_name,))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                cursor.execute('SELECT id FROM tags WHERE name = ?', (tag_name,))
                return cursor.fetchone()[0]

    def add_tag_to_image(self, image_id, tag_name):
        """Links a tag to an image."""
        tag_id = self.get_or_create_tag(tag_name)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('INSERT INTO image_tags (image_id, tag_id) VALUES (?, ?)', (image_id, tag_id))
                conn.commit()
            except sqlite3.IntegrityError:
                pass # Already tagged

    def remove_tag_from_image(self, image_id, tag_name):
        """Removes a tag from an image."""
        tag_name = tag_name.lower().strip()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM image_tags 
                WHERE image_id = ? AND tag_id = (SELECT id FROM tags WHERE name = ?)
            ''', (image_id, tag_name))
            conn.commit()

    def get_tags_for_image(self, image_id):
        """Returns a list of tag names for a given image ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT name FROM tags
                JOIN image_tags ON tags.id = image_tags.tag_id
                WHERE image_tags.image_id = ?
                ORDER BY name
            ''', (image_id,))
            return [row[0] for row in cursor.fetchall()]

    def get_all_tags(self):
        """Returns all unique tag names in the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT name FROM tags ORDER BY name')
            return [row[0] for row in cursor.fetchall()]

    def get_images_by_tags(self, include_tags, exclude_tags=None, mode="AND"):
        """
        Returns image records that match the given tags.
        mode can be 'AND' or 'OR' for included tags.
        exclude_tags is a list of tag names to exclude.
        """
        if not include_tags and not exclude_tags:
            return []
        
        include_tags = [t.lower().strip() for t in include_tags] if include_tags else []
        exclude_tags = [t.lower().strip() for t in exclude_tags] if exclude_tags else []
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Base query
            query = "SELECT i.* FROM images i "
            params = []

            if include_tags:
                placeholders = ','.join('?' for _ in include_tags)
                if mode.upper() == "OR":
                    query += f'''
                        JOIN image_tags it ON i.id = it.image_id
                        JOIN tags t ON it.tag_id = t.id
                        WHERE t.name IN ({placeholders})
                    '''
                    params.extend(include_tags)
                else: # AND mode
                    query += f'''
                        WHERE i.id IN (
                            SELECT it.image_id FROM image_tags it
                            JOIN tags t ON it.tag_id = t.id
                            WHERE t.name IN ({placeholders})
                            GROUP BY it.image_id
                            HAVING COUNT(DISTINCT t.name) = ?
                        )
                    '''
                    params.extend(include_tags)
                    params.append(len(include_tags))
            else:
                query += " WHERE 1=1 "

            if exclude_tags:
                placeholders = ','.join('?' for _ in exclude_tags)
                query += f'''
                    AND i.id NOT IN (
                        SELECT it.image_id FROM image_tags it
                        JOIN tags t ON it.tag_id = t.id
                        WHERE t.name IN ({placeholders})
                    )
                '''
                params.extend(exclude_tags)

            cursor.execute(query, params)
            
            # Convert to list of dicts
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_images_in_folder(self, folder_path):
        """Returns all images in a specific folder."""
        folder_path = os.path.abspath(folder_path)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM images WHERE folder_path = ?', (folder_path,))
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

if __name__ == "__main__":
    db = DatabaseManager()
    print("Database initialized successfully at:", os.path.abspath(db.db_path))
