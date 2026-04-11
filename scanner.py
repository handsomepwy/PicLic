import os
import sqlite3
from collections import defaultdict
from database import Database

class Scanner:
    def __init__(self, db_path="piclic.db"):
        self.db = Database(db_path)
        self.supported_extensions = {'.jpg', '.jpeg', '.nef', '.dng', '.cr2', '.arw'}

    def scan(self, root_dir):
        if not os.path.exists(root_dir):
            print(f"Error: Directory {root_dir} does not exist.")
            return

        self.db.update_scan_status(is_running=True, scanned_count=0, current_path=root_dir)
        total_scanned = 0
        
        # Batching database writes
        batch_size = 100
        current_batch = []

        for root, dirs, files in os.walk(root_dir):
            # Group files by basename
            file_groups = defaultdict(list)
            for filename in files:
                name, ext = os.path.splitext(filename)
                ext = ext.lower()
                if ext in self.supported_extensions:
                    file_groups[name].append((filename, ext))
            
            for name, file_list in file_groups.items():
                # Find if there's a JPEG
                jpg_file = None
                for filename, ext in file_list:
                    if ext in {'.jpg', '.jpeg'}:
                        jpg_file = filename
                        break
                
                if jpg_file:
                    jpg_path = os.path.join(root, jpg_file)
                    folder_path = root
                    
                    # All files in this group
                    files_to_add = []
                    for filename, ext in file_list:
                        file_path = os.path.join(root, filename)
                        file_type = ext.lstrip('.')
                        files_to_add.append((file_path, file_type))
                    
                    # Add to current batch
                    current_batch.append((jpg_path, folder_path, files_to_add))
                    total_scanned += 1
                    
                    # Commit batch if reached size
                    if len(current_batch) >= batch_size:
                        self._commit_batch(current_batch)
                        current_batch = []
                        self.db.update_scan_status(scanned_count=total_scanned, current_path=root)
            
            # Update status for each folder even if no images found
            self.db.update_scan_status(scanned_count=total_scanned, current_path=root)

        # Final commit for remaining items
        if current_batch:
            self._commit_batch(current_batch)
            self.db.update_scan_status(scanned_count=total_scanned, current_path=root_dir)
        
        self.db.update_scan_status(is_running=False)
        print(f"Scanning complete. Total images found: {total_scanned}")

    def _commit_batch(self, batch):
        """
        Commits a batch of images and their files to the database in a single transaction.
        """
        conn = self.db._get_connection()
        cursor = conn.cursor()
        try:
            for jpg_path, folder_path, files_to_add in batch:
                jpg_path = self.db.normalize_path(jpg_path)
                folder_path = self.db.normalize_path(folder_path)
                
                # Insert image entry
                cursor.execute("INSERT OR IGNORE INTO images (jpg_path, folder_path) VALUES (?, ?)", (jpg_path, folder_path))
                cursor.execute("SELECT id FROM images WHERE jpg_path = ?", (jpg_path,))
                image_id = cursor.fetchone()[0]
                
                # Insert associated files
                for file_path, file_type in files_to_add:
                    file_path = self.db.normalize_path(file_path)
                    cursor.execute("INSERT OR IGNORE INTO files (image_id, file_path, file_type) VALUES (?, ?, ?)", (image_id, file_path, file_type))
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error committing batch: {e}")
        finally:
            conn.close()

if __name__ == "__main__":
    scanner = Scanner()
    scanner.scan("g:\\PicLic\\pics")
