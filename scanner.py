import os
from collections import defaultdict
from database import DatabaseManager

class Scanner:
    def __init__(self, root_dir="pics", db_path="piclic.db"):
        self.root_dir = os.path.abspath(root_dir)
        self.db = DatabaseManager(db_path)

    def scan(self):
        """Recursively walks root_dir and indexes images."""
        if not os.path.exists(self.root_dir):
            os.makedirs(self.root_dir)
            print(f"Created root directory: {self.root_dir}")

        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            # Group files by their basename (filename without extension)
            groups = defaultdict(list)
            for filename in filenames:
                basename, ext = os.path.splitext(filename)
                groups[basename].append(filename)

            # Process each group
            for basename, files in groups.items():
                # Check if a .jpg/.jpeg exists in the group
                jpg_file = next((f for f in files if f.lower().endswith(('.jpg', '.jpeg'))), None)
                
                if jpg_file:
                    jpg_path = os.path.join(dirpath, jpg_file)
                    folder_path = os.path.abspath(dirpath)
                    
                    # Add image to database
                    image_id = self.db.add_image(jpg_path, folder_path)
                    
                    # Add all files in the group to the 'files' table
                    for filename in files:
                        file_path = os.path.join(dirpath, filename)
                        _, ext = os.path.splitext(filename)
                        file_type = ext.lower().replace('.', '')
                        self.db.add_file_to_image(image_id, file_path, file_type)

        print(f"Scan of {self.root_dir} complete.")

if __name__ == "__main__":
    scanner = Scanner()
    scanner.scan()
