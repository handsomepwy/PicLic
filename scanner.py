import os
from collections import defaultdict
from database import DatabaseManager
from config import DB_PATH
from PySide6.QtCore import QObject, Signal, QRunnable

class ScanSignals(QObject):
    progress = Signal(int, int) # current, total
    finished = Signal()
    status = Signal(str)

class ScanWorker(QRunnable):
    def __init__(self, root_dir, db_path=DB_PATH):
        super().__init__()
        self.root_dir = root_dir
        self.db_path = db_path
        self.signals = ScanSignals()

    def run(self):
        self.signals.status.emit(f"Scanning {self.root_dir}...")
        scanner = Scanner(self.root_dir, self.db_path)
        
        def progress_cb(current, total):
            self.signals.progress.emit(current, total)
            self.signals.status.emit(f"Indexing: {current}/{total} images...")

        scanner.scan(progress_callback=progress_cb)
        self.signals.finished.emit()

class Scanner:
    def __init__(self, root_dir="pics", db_path=DB_PATH):
        self.root_dir = os.path.abspath(root_dir)
        self.db = DatabaseManager(db_path)

    def scan(self, progress_callback=None):
        """Recursively walks root_dir and indexes images using batch operations."""
        if not os.path.exists(self.root_dir):
            os.makedirs(self.root_dir)
            print(f"Created root directory: {self.root_dir}")

        total_files_found = 0
        all_images_data = [] # List of (jpg_path, folder_path)
        all_groups = [] # List of (jpg_path, list_of_filenames, dirpath)

        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            groups = defaultdict(list)
            for filename in filenames:
                basename, ext = os.path.splitext(filename)
                groups[basename].append(filename)

            for basename, files in groups.items():
                jpg_file = next((f for f in files if f.lower().endswith(('.jpg', '.jpeg'))), None)
                if jpg_file:
                    jpg_path = os.path.join(dirpath, jpg_file)
                    folder_path = os.path.abspath(dirpath)
                    all_images_data.append((jpg_path, folder_path))
                    all_groups.append((jpg_path, files, dirpath))
                    total_files_found += len(files)

        # Batch process in chunks to keep memory usage reasonable and DB transactions efficient
        CHUNK_SIZE = 1000
        for i in range(0, len(all_images_data), CHUNK_SIZE):
            img_chunk = all_images_data[i:i+CHUNK_SIZE]
            group_chunk = all_groups[i:i+CHUNK_SIZE]
            
            # 1. Add images and get their IDs
            path_to_id = self.db.add_images_batch(img_chunk)
            
            # 2. Prepare files for batch insertion
            files_to_add = []
            for jpg_path, files, dirpath in group_chunk:
                image_id = path_to_id.get(jpg_path)
                if image_id:
                    for filename in files:
                        file_path = os.path.join(dirpath, filename)
                        _, ext = os.path.splitext(filename)
                        file_type = ext.lower().replace('.', '')
                        files_to_add.append((image_id, file_path, file_type))
            
            # 3. Batch insert files
            if files_to_add:
                self.db.add_files_batch(files_to_add)
            
            if progress_callback:
                progress_callback(min(i + CHUNK_SIZE, len(all_images_data)), len(all_images_data))

        print(f"Scan of {self.root_dir} complete. Found {total_files_found} files.")

if __name__ == "__main__":
    scanner = Scanner()
    scanner.scan()
