import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QSplitter, QTreeView, QListView, 
    QVBoxLayout, QHBoxLayout, QWidget, QLabel, QLineEdit, 
    QPushButton, QFrame, QScrollArea, QListWidget, QStatusBar,
    QCompleter, QProgressBar
)
from PyQt6.QtCore import Qt, QSize, QDir, QStringListModel, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QFileSystemModel, QAction, QStandardItemModel, QStandardItem, QIcon

from database import Database
from scanner import Scanner
from thumbnails import ThumbnailManager
from gallery_model import GalleryModel
import config

class ScanWorker(QThread):
    finished = pyqtSignal()
    
    def __init__(self, scanner, root_path):
        super().__init__()
        self.scanner = scanner
        self.root_path = root_path
        
    def run(self):
        self.scanner.scan(self.root_path)
        self.finished.emit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PicLic - Photo Manager")
        self.resize(1200, 800)
        
        # Initialize Core components
        self.db = Database()
        self.scanner = Scanner()
        self.thumbnail_manager = ThumbnailManager()
        self.scan_timer = QTimer()
        self.scan_timer.setInterval(500) # Poll every 500ms
        self.scan_worker = None
        
        # Setup UI
        self._setup_ui()
        self._setup_connections()
        
        # Initialize with root folder
        self.root_pics_path = self.db.normalize_path(config.ROOT_PICS_DIR)
        self.gallery_model.root_pics_dir = self.root_pics_path
        
        if os.path.exists(self.root_pics_path):
            self.folder_tree.setRootIndex(self.folder_model.index(self.root_pics_path))
            self._on_folder_selected_by_path(self.root_pics_path)
            self.statusBar().showMessage(f"Ready. Library root: {self.root_pics_path}")
        else:
            self.statusBar().showMessage("Pics directory not found.")
        
        self._refresh_tag_tree()

    def _setup_ui(self):
        # Central Widget and Splitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # 1. Left Panel: Folder Tree
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("Folders"))
        
        self.folder_tree = QTreeView()
        self.folder_model = QFileSystemModel()
        self.folder_model.setRootPath(QDir.rootPath())
        self.folder_model.setFilter(QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot)
        
        self.folder_tree.setModel(self.folder_model)
        self.folder_tree.setHeaderHidden(True)
        # Hide all columns except the first one (name)
        for i in range(1, self.folder_model.columnCount()):
            self.folder_tree.hideColumn(i)
        
        left_layout.addWidget(self.folder_tree)
        
        # Scan Button and Progress Bar
        self.scan_btn = QPushButton("Scan Library")
        left_layout.addWidget(self.scan_btn)
        
        self.scan_progress = QProgressBar()
        self.scan_progress.setVisible(False)
        self.scan_progress.setMinimum(0)
        self.scan_progress.setMaximum(0) # Indeterminate until we have a count
        self.scan_progress.setTextVisible(True)
        self.scan_progress.setFormat("Scanning... %v found")
        left_layout.addWidget(self.scan_progress)
        
        splitter.addWidget(left_panel)
        
        # 2. Middle Panel: Thumbnail Grid
        mid_panel = QWidget()
        mid_layout = QVBoxLayout(mid_panel)
        mid_layout.addWidget(QLabel("Gallery"))
        
        self.gallery_view = QListView()
        self.gallery_view.setViewMode(QListView.ViewMode.IconMode)
        self.gallery_view.setResizeMode(QListView.ResizeMode.Adjust)
        self.gallery_view.setSelectionMode(QListView.SelectionMode.ExtendedSelection) # Enable multi-select
        self.gallery_view.setIconSize(QSize(config.DEFAULT_THUMBNAIL_SIZE, config.DEFAULT_THUMBNAIL_SIZE))
        self.gallery_view.setGridSize(QSize(config.GRID_ITEM_WIDTH, config.GRID_ITEM_HEIGHT))
        self.gallery_view.setWordWrap(True)
        self.gallery_view.setSpacing(config.GRID_SPACING)
        self.gallery_view.setUniformItemSizes(False)
        self.gallery_view.setContentsMargins(0, 0, 0, 0)
        self.gallery_view.setStyleSheet("QListView::item { margin: 0px; padding: 0px; }")
        
        self.gallery_model = GalleryModel(self.db, self.thumbnail_manager)
        self.gallery_view.setModel(self.gallery_model)
        
        mid_layout.addWidget(self.gallery_view)
        
        splitter.addWidget(mid_panel)
        
        # 3. Right Panel: Tags & Info
        right_panel = QWidget()
        right_panel.setFixedWidth(250)
        right_layout = QVBoxLayout(right_panel)
        
        # Tag Input Section
        right_layout.addWidget(QLabel("Add Tags (path-based)"))
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("e.g. travel/japan/tokyo")
        
        # Setup Tag Completer
        self.tag_completer = QCompleter()
        self.tag_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.tag_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.tag_input.setCompleter(self.tag_completer)
        self._update_tag_completer()
        
        right_layout.addWidget(self.tag_input)
        
        # Selected Image Tags Section
        right_layout.addWidget(QLabel("Selected Image Tags"))
        self.image_tags_view = QTreeView()
        self.image_tags_model = QStandardItemModel()
        self.image_tags_model.setHorizontalHeaderLabels(["Tags"])
        self.image_tags_view.setModel(self.image_tags_model)
        self.image_tags_view.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self.image_tags_view.setHeaderHidden(True)
        right_layout.addWidget(self.image_tags_view)
        
        # Tag Tree Section
        right_layout.addWidget(QLabel("All Tags Explorer"))
        self.tag_tree_view = QTreeView()
        self.tag_tree_model = QStandardItemModel()
        self.tag_tree_model.setHorizontalHeaderLabels(["Tags"])
        self.tag_tree_view.setModel(self.tag_tree_model)
        self.tag_tree_view.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self.tag_tree_view.setHeaderHidden(True)
        right_layout.addWidget(self.tag_tree_view)
        
        # Set stretch factors for the two trees to share space
        right_layout.setStretch(3, 1) # Selected Image Tags tree
        right_layout.setStretch(5, 2) # All Tags Explorer tree
        
        splitter.addWidget(right_panel)
        
        # Splitter sizing
        splitter.setStretchFactor(0, 1) # Folders
        splitter.setStretchFactor(1, 4) # Gallery
        splitter.setStretchFactor(2, 1) # Tags
        
        # Status Bar
        self.setStatusBar(QStatusBar())

    def _setup_connections(self):
        # Folder tree selection -> update gallery
        self.folder_tree.clicked.connect(self._on_folder_selected)
        
        # Gallery selection -> update right panel tags
        self.gallery_view.selectionModel().selectionChanged.connect(self._on_image_selected)
        
        # Gallery double click -> navigation
        self.gallery_view.doubleClicked.connect(self._on_gallery_double_clicked)
        
        # Selected image tags double click -> deletion
        self.image_tags_view.doubleClicked.connect(self._on_image_tag_double_clicked)
        
        # Tag tree selection -> filtering
        self.tag_tree_view.clicked.connect(self._on_tag_tree_selected)
        
        # Scan button and status timer
        self.scan_btn.clicked.connect(self._on_scan_requested)
        self.scan_timer.timeout.connect(self._on_poll_scan_status)
        
        # Tag input enter key
        self.tag_input.returnPressed.connect(self._on_tag_applied)

    def _refresh_tag_tree(self):
        # Prune tags that are no longer used by any image
        self.db.prune_unused_tags()
        
        self.tag_tree_model.clear()
        self.tag_tree_model.setHorizontalHeaderLabels(["Tags"])
        
        tags = self.db.get_all_tags()
        tag_items = {} # id -> QStandardItem
        
        # Sort tags so parents are processed before children (simplified)
        # In a real app we would build a tree properly
        for tag in tags:
            item = QStandardItem(tag['name'])
            item.setData(tag['id'], Qt.ItemDataRole.UserRole)
            tag_items[tag['id']] = item
            
        for tag in tags:
            item = tag_items[tag['id']]
            parent_id = tag['parent_id']
            if parent_id and parent_id in tag_items:
                tag_items[parent_id].appendRow(item)
            else:
                self.tag_tree_model.appendRow(item)
        
        self.tag_tree_view.expandAll()

    def _update_tag_completer(self):
        # In a real app, this would be more complex to handle hierarchical paths
        # For now, let's just get all tag names or full paths
        conn = self.db._get_connection()
        cursor = conn.cursor()
        # This is a simplified version of path optimization mentioned in spec
        cursor.execute("SELECT name FROM tags")
        tags = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        model = QStringListModel(tags)
        self.tag_completer.setModel(model)

    def _on_tag_tree_selected(self, index):
        tag_id = self.tag_tree_model.itemFromIndex(index).data(Qt.ItemDataRole.UserRole)
        # Toggle filter: if already selected, clear it
        if self.gallery_model.filter_tag_id == tag_id:
            self.gallery_model.set_filter_tag(None)
            self.tag_tree_view.selectionModel().clearSelection()
            self.statusBar().showMessage(f"Filter cleared. Viewing: {self.gallery_model.current_folder}")
        else:
            self.gallery_model.set_filter_tag(tag_id)
            tag_name = self.tag_tree_model.itemFromIndex(index).text()
            self.statusBar().showMessage(f"Filtering by tag: {tag_name} in {self.gallery_model.current_folder}")

    def _on_folder_selected(self, index):
        path = self.folder_model.filePath(index)
        self._on_folder_selected_by_path(path)

    def _on_folder_selected_by_path(self, path):
        if os.path.isdir(path):
            self.gallery_model.set_folder(path)
            self.statusBar().showMessage(f"Viewing: {path}")
            
            # Sync folder tree
            idx = self.folder_model.index(path)
            self.folder_tree.setCurrentIndex(idx)
            self.folder_tree.scrollTo(idx)

    def _on_gallery_double_clicked(self, index):
        item = self.gallery_model.data(index, Qt.ItemDataRole.UserRole)
        if item and item['type'] == 'folder':
            self._on_folder_selected_by_path(item['path'])
        elif item and item['type'] == 'image':
            # Open image in system default viewer
            os.startfile(item['path'])

    def _on_image_selected(self):
        indexes = self.gallery_view.selectionModel().selectedIndexes()
        self.image_tags_model.clear()
        self.image_tags_model.setHorizontalHeaderLabels(["Tags"])
        
        if not indexes:
            return

        if len(indexes) > 1:
            # For multi-select, show a placeholder or common tags
            # For now, let's just show how many images are selected
            item_tree = QStandardItem(f"{len(indexes)} images selected")
            item_tree.setEnabled(False)
            self.image_tags_model.appendRow(item_tree)
            return
            
        index = indexes[0]
        item = self.gallery_model.data(index, Qt.ItemDataRole.UserRole)
        
        if item and item['type'] == 'image':
                path = item['path']
                image_id = self.db.get_image_id_by_path(path)
                if image_id:
                    tags = self.db.get_image_tags(image_id)
                    tag_items = {} # id -> QStandardItem
                    
                    # Similar to All Tags Explorer, build nested view
                    for tag in tags:
                        item_tree = QStandardItem(tag['name'])
                        item_tree.setData(tag['id'], Qt.ItemDataRole.UserRole)
                        tag_items[tag['id']] = item_tree
                        
                    for tag in tags:
                        item_tree = tag_items[tag['id']]
                        parent_id = tag['parent_id']
                        if parent_id and parent_id in tag_items:
                            tag_items[parent_id].appendRow(item_tree)
                        else:
                            self.image_tags_model.appendRow(item_tree)
                    
                    self.image_tags_view.expandAll()

    def _on_image_tag_double_clicked(self, index):
        # Get the tag_id from the clicked item
        tag_id = self.image_tags_model.itemFromIndex(index).data(Qt.ItemDataRole.UserRole)
        
        # Get the currently selected image
        indexes = self.gallery_view.selectionModel().selectedIndexes()
        if indexes:
            item = self.gallery_model.data(indexes[0], Qt.ItemDataRole.UserRole)
            if item and item['type'] == 'image':
                path = item['path']
                image_id = self.db.get_image_id_by_path(path)
                if image_id:
                    # Remove from DB
                    self.db.remove_tag_from_image(image_id, tag_id)
                    # Prune tags that are no longer used by any image
                    self.db.prune_unused_tags()
                    # Refresh the views
                    self._update_tag_completer()
                    self._on_image_selected()
                    self.statusBar().showMessage(f"Tag removed from image and cleaned up.")

    def _on_tag_applied(self):
        tag_path = self.tag_input.text().strip()
        if not tag_path:
            return
            
        indexes = self.gallery_view.selectionModel().selectedIndexes()
        if not indexes:
            self.statusBar().showMessage("Select one or more images first.")
            return
            
        # Get or create the tag(s)
        try:
            # Refresh Tag Explorer only when a brand-new tag is created.
            # We detect this by comparing total tag count before/after creation.
            tag_count_before = len(self.db.get_all_tags())
            tag_id = self.db.get_or_create_tag_path(tag_path)
            tag_count_after = len(self.db.get_all_tags())
            new_tag_created = tag_count_after > tag_count_before
            
            # Apply to all selected images
            for index in indexes:
                item = self.gallery_model.data(index, Qt.ItemDataRole.UserRole)
                if item and item['type'] == 'image':
                    path = item['path']
                    image_id = self.db.get_image_id_by_path(path)
                    if image_id:
                        self.db.add_tag_to_image(image_id, tag_id)
            
            self.tag_input.clear()
            self._update_tag_completer()
            if new_tag_created:
                self._refresh_tag_tree()
            self._on_image_selected() # Refresh tags list
            self.statusBar().showMessage(f"Tag '{tag_path}' applied to selected image(s).")
        except Exception as e:
            self.statusBar().showMessage(f"Error applying tag: {e}")

    def _on_scan_requested(self):
        root_path = config.ROOT_PICS_DIR
        if os.path.exists(root_path):
            norm_root = self.db.normalize_path(root_path)
            self.statusBar().showMessage(f"Scanning {norm_root}...")
            
            # Reset and show progress bar
            self.scan_progress.setValue(0)
            self.scan_progress.setMaximum(0) # Busy indicator
            self.scan_progress.setVisible(True)
            self.scan_btn.setEnabled(False)
            
            # Start background worker
            self.scan_worker = ScanWorker(self.scanner, norm_root)
            self.scan_worker.finished.connect(self._on_scan_finished)
            self.scan_worker.start()
            
            # Start polling timer
            self.scan_timer.start()
        else:
            self.statusBar().showMessage("Error: pics directory not found.")

    def _on_poll_scan_status(self):
        status = self.db.get_scan_status()
        if status:
            count = status['scanned_count']
            path = status['current_path']
            # Update progress bar
            if count > self.scan_progress.maximum():
                self.scan_progress.setMaximum(count)
            self.scan_progress.setValue(count)
            self.scan_progress.setFormat(f"Found: {count} images")
            self.statusBar().showMessage(f"Scanning: {path}")

    def _on_scan_finished(self):
        self.scan_timer.stop()
        self.scan_btn.setEnabled(True)
        self.scan_progress.setVisible(False)
        self.statusBar().showMessage("Scan complete.")
        
        # Refresh current folder view if any
        current_idx = self.folder_tree.currentIndex()
        if current_idx.isValid():
            self._on_folder_selected(current_idx)
        else:
            # Refresh root view if nothing selected
            self._on_folder_selected_by_path(self.root_pics_path)

    def _on_scan_requested_old(self): # Keeping for reference of what was replaced
        pass

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
