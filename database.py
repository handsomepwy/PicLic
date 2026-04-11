import sqlite3
import os
from datetime import datetime

class Database:
    def __init__(self, db_path="piclic.db"):
        self.db_path = db_path
        self._init_db()

    @staticmethod
    def normalize_path(path):
        if not path:
            return ""
        # On Windows, os.path.normcase converts drive letter to lower and slashes to backslashes
        return os.path.normpath(os.path.normcase(os.path.abspath(path)))

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Enable WAL mode
        cursor.execute("PRAGMA journal_mode=WAL;")
        
        # Create tables based on specification
        cursor.executescript("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jpg_path TEXT UNIQUE,
            folder_path TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_images_folder_path ON images(folder_path);

        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_id INTEGER,
            file_path TEXT UNIQUE,
            file_type TEXT,
            FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE COLLATE NOCASE,
            parent_id INTEGER NULL,
            FOREIGN KEY (parent_id) REFERENCES tags(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS image_tags (
            image_id INTEGER,
            tag_id INTEGER,
            PRIMARY KEY (image_id, tag_id),
            FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_image_tags_image_id ON image_tags(image_id);
        CREATE INDEX IF NOT EXISTS idx_image_tags_tag_id ON image_tags(tag_id);

        CREATE TABLE IF NOT EXISTS scan_status (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            is_running INTEGER DEFAULT 0,
            scanned_count INTEGER DEFAULT 0,
            current_path TEXT,
            last_updated TIMESTAMP
        );
        """)
        
        # Initialize scan_status if it doesn't exist
        cursor.execute("INSERT OR IGNORE INTO scan_status (id, is_running, scanned_count, current_path, last_updated) VALUES (1, 0, 0, '', ?)", (datetime.now(),))
        
        conn.commit()
        conn.close()

    def update_scan_status(self, is_running=None, scanned_count=None, current_path=None):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        updates = []
        params = []
        if is_running is not None:
            updates.append("is_running = ?")
            params.append(1 if is_running else 0)
        if scanned_count is not None:
            updates.append("scanned_count = ?")
            params.append(scanned_count)
        if current_path is not None:
            updates.append("current_path = ?")
            params.append(self.normalize_path(current_path))
        
        updates.append("last_updated = ?")
        params.append(datetime.now())
        
        if updates:
            query = f"UPDATE scan_status SET {', '.join(updates)} WHERE id = 1"
            cursor.execute(query, params)
            conn.commit()
        conn.close()

    def get_scan_status(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scan_status WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def add_image_with_files(self, jpg_path, folder_path, files):
        """
        files is a list of tuples (file_path, file_type)
        """
        jpg_path = self.normalize_path(jpg_path)
        folder_path = self.normalize_path(folder_path)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Insert image entry
            cursor.execute("INSERT OR IGNORE INTO images (jpg_path, folder_path) VALUES (?, ?)", (jpg_path, folder_path))
            cursor.execute("SELECT id FROM images WHERE jpg_path = ?", (jpg_path,))
            image_id = cursor.fetchone()[0]
            
            # Insert associated files
            for file_path, file_type in files:
                norm_file_path = self.normalize_path(file_path)
                cursor.execute("INSERT OR IGNORE INTO files (image_id, file_path, file_type) VALUES (?, ?, ?)", (image_id, norm_file_path, file_type))
            
            conn.commit()
            return image_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def clear_database(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM images")
        cursor.execute("DELETE FROM files")
        cursor.execute("DELETE FROM image_tags")
        cursor.execute("UPDATE scan_status SET scanned_count = 0, current_path = '', is_running = 0 WHERE id = 1")
        conn.commit()
        conn.close()

    def get_or_create_tag_path(self, tag_path):
        """
        tag_path is a string like "travel/japan/tokyo"
        Returns the id of the last tag in the path.
        """
        parts = tag_path.strip("/").split("/")
        conn = self._get_connection()
        cursor = conn.cursor()
        
        parent_id = None
        last_id = None
        
        try:
            for part in parts:
                cursor.execute("SELECT id FROM tags WHERE name = ? AND (parent_id = ? OR (parent_id IS NULL AND ? IS NULL))", (part, parent_id, parent_id))
                row = cursor.fetchone()
                if row:
                    last_id = row[0]
                else:
                    cursor.execute("INSERT INTO tags (name, parent_id) VALUES (?, ?)", (part, parent_id))
                    last_id = cursor.lastrowid
                parent_id = last_id
            
            conn.commit()
            return last_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def add_tag_to_image(self, image_id, tag_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT OR IGNORE INTO image_tags (image_id, tag_id) VALUES (?, ?)", (image_id, tag_id))
            conn.commit()
        finally:
            conn.close()

    def get_image_tags(self, image_id):
        """
        Returns all tags associated with the image, including their ancestors 
        to allow building a hierarchical view.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 1. Get direct tags
        cursor.execute("""
            SELECT t.id, t.name, t.parent_id 
            FROM tags t
            JOIN image_tags it ON t.id = it.tag_id
            WHERE it.image_id = ?
        """, (image_id,))
        direct_tags = [dict(row) for row in cursor.fetchall()]
        
        # 2. Find all ancestors
        all_tag_ids = {tag['id'] for tag in direct_tags}
        to_check = [tag['parent_id'] for tag in direct_tags if tag['parent_id'] is not None]
        
        all_tags_dict = {tag['id']: tag for tag in direct_tags}
        
        while to_check:
            current_parent_id = to_check.pop(0)
            if current_parent_id in all_tag_ids:
                continue
                
            cursor.execute("SELECT id, name, parent_id FROM tags WHERE id = ?", (current_parent_id,))
            row = cursor.fetchone()
            if row:
                tag = dict(row)
                all_tag_ids.add(tag['id'])
                all_tags_dict[tag['id']] = tag
                if tag['parent_id'] is not None:
                    to_check.append(tag['parent_id'])
        
        conn.close()
        return list(all_tags_dict.values())

    def get_child_tags(self, parent_id=None):
        conn = self._get_connection()
        cursor = conn.cursor()
        if parent_id is None:
            cursor.execute("SELECT id, name FROM tags WHERE parent_id IS NULL")
        else:
            cursor.execute("SELECT id, name FROM tags WHERE parent_id = ?", (parent_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_all_tags(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, parent_id FROM tags")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def remove_tag_from_image(self, image_id, tag_id):
        """
        Removes the specific tag AND all its descendants from the image.
        """
        descendants = self.get_tag_descendants(tag_id)
        placeholders = ', '.join(['?'] * len(descendants))
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            query = f"DELETE FROM image_tags WHERE image_id = ? AND tag_id IN ({placeholders})"
            cursor.execute(query, [image_id] + descendants)
            conn.commit()
        finally:
            conn.close()

    def prune_unused_tags(self):
        """
        Recursively deletes tags that are not assigned to any images AND have no children.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            while True:
                # Find tags with no children and no image associations
                cursor.execute("""
                    SELECT id FROM tags 
                    WHERE id NOT IN (SELECT parent_id FROM tags WHERE parent_id IS NOT NULL)
                    AND id NOT IN (SELECT tag_id FROM image_tags)
                """)
                rows = cursor.fetchall()
                if not rows:
                    break
                
                # Delete those tags
                ids_to_delete = [row[0] for row in rows]
                placeholders = ', '.join(['?'] * len(ids_to_delete))
                cursor.execute(f"DELETE FROM tags WHERE id IN ({placeholders})", ids_to_delete)
                conn.commit()
        finally:
            conn.close()

    def get_tag_descendants(self, tag_id):
        """
        Returns a list of tag IDs including the given tag_id and all its descendants.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        descendants = [tag_id]
        to_process = [tag_id]
        
        while to_process:
            current_id = to_process.pop(0)
            cursor.execute("SELECT id FROM tags WHERE parent_id = ?", (current_id,))
            children = [row[0] for row in cursor.fetchall()]
            descendants.extend(children)
            to_process.extend(children)
            
        conn.close()
        return descendants

    def get_image_id_by_path(self, jpg_path):
        jpg_path = self.normalize_path(jpg_path)
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM images WHERE jpg_path = ?", (jpg_path,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
