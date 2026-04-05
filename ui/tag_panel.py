from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
                             QPushButton, QLabel, QListWidget, QListWidgetItem, 
                             QFrame, QAbstractItemView, QComboBox)
from PySide6.QtCore import Qt, Signal

class TagPanel(QWidget):
    tag_added = Signal(str)      # Emitted when a new tag is added
    tag_removed = Signal(str)    # Emitted when a tag is removed
    search_requested = Signal(list, str) # Emitted when tags are used to search (tags, mode)

    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.current_image_ids = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 1. Current Tags Label
        layout.addWidget(QLabel("<b>Selected Image Tags:</b>"))

        # 2. Tag List for currently selected images
        self.current_tags_list = QListWidget()
        self.current_tags_list.setFixedHeight(150)
        self.current_tags_list.setSelectionMode(QAbstractItemView.NoSelection)
        layout.addWidget(self.current_tags_list)

        # 3. Add Tag Section
        add_layout = QHBoxLayout()
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("New tag...")
        self.tag_input.returnPressed.connect(self._on_add_clicked)
        self.add_button = QPushButton("+")
        self.add_button.setFixedWidth(30)
        self.add_button.clicked.connect(self._on_add_clicked)
        add_layout.addWidget(self.tag_input)
        add_layout.addWidget(self.add_button)
        layout.addLayout(add_layout)

        # 4. Remove Tag Button
        self.remove_button = QPushButton("Remove Selected Tag")
        self.remove_button.clicked.connect(self._on_remove_clicked)
        layout.addWidget(self.remove_button)

        layout.addWidget(QFrame(frameShape=QFrame.HLine))

        # 5. All Tags Section (Library)
        layout.addWidget(QLabel("<b>All Tags (Library):</b>"))
        self.all_tags_list = QListWidget()
        self.all_tags_list.itemDoubleClicked.connect(self._on_all_tag_double_clicked)
        self.all_tags_list.setSelectionMode(QAbstractItemView.ExtendedSelection) # Multi-select for library
        layout.addWidget(self.all_tags_list)
        
        # 6. Search Controls
        search_layout = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["AND (Match All)", "OR (Match Any)"])
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self._on_search_clicked)
        search_layout.addWidget(self.mode_combo)
        search_layout.addWidget(self.search_button)
        layout.addLayout(search_layout)

        self.refresh_all_tags()

    def set_selected_images(self, image_ids):
        # ...
        self.current_image_ids = image_ids
        self.current_tags_list.clear()
        
        if not image_ids:
            self.tag_input.setEnabled(False)
            self.add_button.setEnabled(False)
            self.remove_button.setEnabled(False)
            return

        self.tag_input.setEnabled(True)
        self.add_button.setEnabled(True)
        self.remove_button.setEnabled(True)

        # If only one image, show its specific tags
        if len(image_ids) == 1:
            tags = self.db.get_tags_for_image(image_ids[0])
            for tag in tags:
                self.current_tags_list.addItem(tag)
        else:
            # For multiple images, show "multiple selected" or common tags
            self.current_tags_list.addItem(f"({len(image_ids)} images selected)")

    def refresh_all_tags(self):
        # ...
        self.all_tags_list.clear()
        tags = self.db.get_all_tags()
        for tag in tags:
            self.all_tags_list.addItem(tag)

    def _on_add_clicked(self):
        # ...
        tag_name = self.tag_input.text().strip()
        if not tag_name or not self.current_image_ids:
            return
        
        for image_id in self.current_image_ids:
            self.db.add_tag_to_image(image_id, tag_name)
        
        self.tag_input.clear()
        self.set_selected_images(self.current_image_ids)
        self.refresh_all_tags()
        self.tag_added.emit(tag_name)

    def _on_remove_clicked(self):
        # ...
        selected_item = self.current_tags_list.currentItem()
        if not selected_item or not self.current_image_ids:
            return
        
        tag_name = selected_item.text()
        for image_id in self.current_image_ids:
            self.db.remove_tag_from_image(image_id, tag_name)
        
        self.set_selected_images(self.current_image_ids)
        self.tag_removed.emit(tag_name)

    def _on_all_tag_double_clicked(self, item):
        # ...
        if not self.current_image_ids:
            return
        tag_name = item.text()
        for image_id in self.current_image_ids:
            self.db.add_tag_to_image(image_id, tag_name)
        self.set_selected_images(self.current_image_ids)

    def _on_search_clicked(self):
        selected_items = self.all_tags_list.selectedItems()
        if not selected_items:
            return
        tag_names = [item.text() for item in selected_items]
        mode = "AND" if self.mode_combo.currentIndex() == 0 else "OR"
        self.search_requested.emit(tag_names, mode)
