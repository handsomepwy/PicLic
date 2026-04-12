from PyQt6.QtCore import QAbstractListModel, Qt, QSize, pyqtSignal, QModelIndex
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QFileIconProvider
import os
import config

class GalleryModel(QAbstractListModel):
    """
    Virtualized model for the thumbnail grid.
    Shows images from the database and folders from the filesystem.
    """
    def __init__(self, database, thumbnail_manager, parent=None):
        super().__init__(parent)
        self.db = database
        self.thumbnail_manager = thumbnail_manager
        self.items = []  # List of dicts with item info: {type: 'folder'|'image', path: '...', name: '...'}
        self.thumbnail_size = config.DEFAULT_THUMBNAIL_SIZE
        self.current_folder = ""
        self.root_pics_dir = "" # Will be set by main window
        self.filter_tag_id = None # ID of the tag to filter by
        self.icon_provider = QFileIconProvider()
        
        # Connect thumbnail manager signal
        self.thumbnail_manager.thumbnail_ready.connect(self._on_thumbnail_ready)

    def set_filter_tag(self, tag_id):
        self.filter_tag_id = tag_id
        if self.current_folder:
            self.set_folder(self.current_folder)

    def set_folder(self, folder_path):
        """
        Updates the model to show images and folders from a specific folder.
        """
        self.thumbnail_manager.clear_requests() # Clear pending requests for old folder
        self.current_folder = self.db.normalize_path(folder_path)
        self.beginResetModel()
        self.items = []
        
        # 1. Add ".." if not at root
        if self.root_pics_dir and self.current_folder != self.db.normalize_path(self.root_pics_dir):
            parent_path = os.path.dirname(self.current_folder)
            self.items.append({'type': 'folder', 'path': parent_path, 'name': '..'})
            
        # 2. Add subfolders from filesystem
        try:
            for entry in os.scandir(self.current_folder):
                if entry.is_dir():
                    self.items.append({'type': 'folder', 'path': entry.path, 'name': entry.name})
        except Exception as e:
            print(f"Error reading directory {self.current_folder}: {e}")

        # 3. Add images from database
        conn = self.db._get_connection()
        cursor = conn.cursor()
        
        if self.filter_tag_id is None:
            cursor.execute("SELECT id, jpg_path FROM images WHERE folder_path = ?", (self.current_folder,))
        else:
            # Query images with specific tag OR its descendants in the current folder
            tag_ids = self.db.get_tag_descendants(self.filter_tag_id)
            placeholders = ', '.join(['?'] * len(tag_ids))
            query = f"""
                SELECT DISTINCT i.id, i.jpg_path 
                FROM images i
                JOIN image_tags it ON i.id = it.image_id
                WHERE i.folder_path = ? AND it.tag_id IN ({placeholders})
            """
            cursor.execute(query, [self.current_folder] + tag_ids)
            
        rows = cursor.fetchall()
        for row in rows:
            self.items.append({
                'type': 'image', 
                'path': row['jpg_path'], 
                'name': os.path.basename(row['jpg_path']),
                'id': row['id']
            })
        conn.close()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self.items)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.items)):
            return None

        item = self.items[index.row()]
        path = item['path']

        if role == Qt.ItemDataRole.DecorationRole:
            if item['type'] == 'folder':
                # Return a default folder icon
                return self.icon_provider.icon(QFileIconProvider.IconType.Folder)
            
            # Request thumbnail from manager
            thumb = self.thumbnail_manager.cache.get(path, self.thumbnail_size)
            if thumb:
                return QPixmap.fromImage(thumb)
            else:
                self.thumbnail_manager.get_thumbnail(path, self.thumbnail_size)
                return None
        
        elif role == Qt.ItemDataRole.DisplayRole:
            return item['name']
        
        elif role == Qt.ItemDataRole.UserRole:
            return item # Return full item dict

        return None

    def _on_thumbnail_ready(self, path, size, qimage):
        # Find all rows that match this path and update them
        for i, item in enumerate(self.items):
            if item['type'] == 'image' and item['path'] == path and size == self.thumbnail_size:
                idx = self.index(i)
                self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DecorationRole])
