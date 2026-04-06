import os
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
                                 QSplitter, QStatusBar, QToolBar,
                                 QComboBox, QLabel, QLineEdit, QFileDialog, QProgressBar)
from PySide6.QtCore import Qt, QSize, QThreadPool
from PySide6.QtGui import QIcon, QAction

from ui.folder_tree import FolderTree
from ui.image_grid import ImageGrid
from ui.tag_panel import TagPanel
from database import DatabaseManager
from scanner import Scanner, ScanWorker
from thumbnail import ThumbnailManager
from config import PICS_DIR

class MainWindow(QMainWindow):
    def __init__(self, root_path=PICS_DIR):
        super().__init__()
        self.setWindowTitle("PicLic - High Performance Image Browser")
        self.resize(1024, 768)
        
        self.root_path = os.path.abspath(root_path)
        self.db = DatabaseManager()
        self.scanner = Scanner(self.root_path)
        self.thumbnail_manager = ThumbnailManager()
        self.thumbnail_manager.thumbnail_ready.connect(self._on_thumbnail_ready)
        
        self._init_ui()
        self._load_folder(self.root_path)

    def _init_ui(self):
        # 1. Main layout using QSplitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        self.splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter)
        
        # 2. Left Side: Folder Tree
        self.folder_tree = FolderTree(self.root_path)
        self.folder_tree.folder_selected.connect(self._load_folder)
        self.splitter.addWidget(self.folder_tree)
        
        # 3. Right Side: Image Grid and Toolbar
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        
        # Toolbar (Zoom, Scan, Search)
        toolbar_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search tags (e.g. astro landscape -bad)")
        self.search_input.returnPressed.connect(self._on_search)
        toolbar_layout.addWidget(QLabel("Search:"))
        toolbar_layout.addWidget(self.search_input)
        
        self.zoom_combo = QComboBox()
        self.zoom_combo.addItems(["128px", "256px", "512px"])
        self.zoom_combo.setCurrentIndex(1) # Default to 256px
        self.zoom_combo.currentIndexChanged.connect(self._on_zoom_changed)
        toolbar_layout.addWidget(QLabel("Zoom:"))
        toolbar_layout.addWidget(self.zoom_combo)
        
        self.scan_action = QAction("Scan Folder", self)
        self.scan_action.triggered.connect(self._on_scan)
        self.toolbar = self.addToolBar("Main ToolBar")
        self.toolbar.addAction(self.scan_action)
        
        right_layout.addLayout(toolbar_layout)
        
        self.image_grid = ImageGrid()
        self.image_grid.item_opened.connect(self._on_item_opened)
        right_layout.addWidget(self.image_grid)
        
        self.splitter.addWidget(right_container)
        
        # 4. Far Right Side: Tag Panel
        self.tag_panel = TagPanel(self.db)
        self.tag_panel.search_requested.connect(self._on_search_tags)
        self.splitter.addWidget(self.tag_panel)
        
        self.image_grid.selection_changed.connect(self.tag_panel.set_selected_images)
        self.image_grid.tag_requested.connect(self._on_tag_requested)
        
        self.splitter.setStretchFactor(1, 4) # Make the grid area wider
        self.splitter.setStretchFactor(2, 1) # Make the tag panel narrower
        
        # 5. Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

    def _load_folder(self, folder_path):
        """Loads images and subfolders for the given path."""
        self.current_folder = os.path.abspath(folder_path)
        self.status_bar.showMessage(f"Loading: {self.current_folder}")
        
        items = []
        
        # 0. Add ".." parent directory if not at root
        if self.current_folder != self.root_path:
            parent_path = os.path.dirname(self.current_folder)
            items.append({'type': 'folder', 'path': parent_path, 'thumbnail': None, 'display_name': '..'})

        # 1. Add subfolders (filesystem check for now, can be optimized via DB)
        try:
            for item in sorted(os.listdir(self.current_folder)):
                full_path = os.path.join(self.current_folder, item)
                if os.path.isdir(full_path):
                    items.append({'type': 'folder', 'path': full_path, 'thumbnail': None, 'display_name': item})
        except OSError:
            pass

        # 2. Add images from Database
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, jpg_path FROM images WHERE folder_path = ?', (self.current_folder,))
            for row in sorted(cursor.fetchall()):
                img_id, jpg_path = row
                items.append({'id': img_id, 'type': 'image', 'path': jpg_path, 'thumbnail': None, 'display_name': os.path.basename(jpg_path)})
                # Trigger thumbnail generation (async)
                self.thumbnail_manager.get_thumbnail(jpg_path, self._get_current_zoom_size())

        self.image_grid.model.update_items(items)
        self.status_bar.showMessage(f"Found {len(items)} items in {self.current_folder}")

    def _on_search_tags(self, tag_names, mode="AND"):
        """Displays images that match the selected tags."""
        self.status_bar.showMessage(f"Searching for tags: {', '.join(tag_names)} ({mode})")
        images = self.db.get_images_by_tags(tag_names, mode=mode)
        
        items = []
        for img in images:
            items.append({
                'id': img['id'],
                'type': 'image',
                'path': img['jpg_path'],
                'thumbnail': None,
                'display_name': os.path.basename(img['jpg_path'])
            })
            self.thumbnail_manager.get_thumbnail(img['jpg_path'], self._get_current_zoom_size())
        
        self.image_grid.model.update_items(items)
        self.status_bar.showMessage(f"Found {len(items)} images with tags: {', '.join(tag_names)} ({mode})")

    def _on_tag_requested(self, image_ids, tag_name):
        """Adds a tag to multiple images and refreshes UI."""
        for image_id in image_ids:
            self.db.add_tag_to_image(image_id, tag_name)
        self.tag_panel.refresh_all_tags()
        self.tag_panel.set_selected_images(image_ids)
        self.status_bar.showMessage(f"Added tag '{tag_name}' to {len(image_ids)} images.")

    def _get_current_zoom_size(self):
        text = self.zoom_combo.currentText()
        return int(text.replace('px', ''))

    def _on_zoom_changed(self, index):
        size = self._get_current_zoom_size()
        self.image_grid.set_zoom(size)
        # Re-trigger thumbnails for current visible area if needed
        # (For now, we just update the model and trigger all in _load_folder)

    def _on_scan(self):
        self.scan_action.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_bar.showMessage("Preparing scan...")
        
        worker = ScanWorker(self.root_path)
        worker.signals.progress.connect(self._on_scan_progress)
        worker.signals.status.connect(self._on_scan_status)
        worker.signals.finished.connect(self._on_scan_finished)
        
        QThreadPool.globalInstance().start(worker)

    def _on_scan_progress(self, current, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

    def _on_scan_status(self, message):
        self.status_bar.showMessage(message)

    def _on_scan_finished(self):
        self.scan_action.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage("Scan complete.")
        self._load_folder(self.current_folder)

    def _on_search(self):
        """Parses the search input and displays matching images."""
        query_text = self.search_input.text().strip()
        if not query_text:
            self._load_folder(self.current_folder)
            return

        self.status_bar.showMessage(f"Searching for: {query_text}")
        
        # Determine mode: OR if '|' is present, otherwise AND
        mode = "OR" if "|" in query_text else "AND"
        
        # Clean up the query: replace '|' with spaces so we can split easily
        normalized_query = query_text.replace("|", " ")
        
        include_tags = []
        exclude_tags = []
        
        for word in normalized_query.split():
            if word.startswith('-'):
                exclude_tags.append(word[1:])
            else:
                include_tags.append(word)

        images = self.db.get_images_by_tags(include_tags, exclude_tags, mode=mode)
        
        items = []
        for img in images:
            items.append({
                'id': img['id'],
                'type': 'image',
                'path': img['jpg_path'],
                'thumbnail': None,
                'display_name': os.path.basename(img['jpg_path'])
            })
            self.thumbnail_manager.get_thumbnail(img['jpg_path'], self._get_current_zoom_size())
        
        self.image_grid.model.update_items(items)
        self.status_bar.showMessage(f"Found {len(items)} images matching: {query_text} ({mode})")

    def _on_item_opened(self, path):
        if os.path.isdir(path):
            self._load_folder(path)
        else:
            # TODO: Phase 10: Open via OS default
            import subprocess
            if os.name == 'nt': # Windows
                os.startfile(path)
            else: # Mac/Linux
                subprocess.call(['open', path] if os.uname().sysname == 'Darwin' else ['xdg-open', path])

    def _on_thumbnail_ready(self, path, pixmap):
        self.image_grid.model.update_thumbnail(path, pixmap)

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
