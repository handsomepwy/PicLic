import os
from PySide6.QtWidgets import QListView, QStyledItemDelegate, QStyleOptionViewItem, QStyle, QMenu, QInputDialog
from PySide6.QtCore import Qt, QAbstractListModel, QSize, Signal, QModelIndex, QRect, QPoint
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QPen, QAction

class ImageModel(QAbstractListModel):
    """Model for images and folders in the current directory."""
    def __init__(self, items=None, parent=None):
        super().__init__(parent)
        self._items = items or [] # Each item is a dict: { 'type': 'folder'|'image', 'path': str, 'thumbnail': QPixmap }

    def rowCount(self, parent=QModelIndex()):
        return len(self._items)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        
        item = self._items[index.row()]
        if role == Qt.DisplayRole:
            return item.get('display_name', os.path.basename(item['path']))
        elif role == Qt.UserRole:
            return item
        return None

    def update_items(self, items):
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def update_thumbnail(self, path, pixmap):
        for i, item in enumerate(self._items):
            if item['path'] == path:
                item['thumbnail'] = pixmap
                index = self.index(i)
                self.dataChanged.emit(index, index, [Qt.UserRole])
                break

class ImageDelegate(QStyledItemDelegate):
    """Delegate for drawing thumbnails and labels."""
    def __init__(self, icon_size=128, parent=None):
        super().__init__(parent)
        self.icon_size = icon_size
        self.padding = 10

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        item = index.data(Qt.UserRole)
        if not item:
            return

        painter.save()
        rect = option.rect
        
        # Highlight if selected
        if option.state & QStyle.State_Selected:
            painter.fillRect(rect, option.palette.highlight())
            painter.setPen(option.palette.highlightedText().color())
        else:
            painter.setPen(option.palette.text().color())

        # Draw thumbnail or placeholder
        thumb_rect = QRect(rect.left() + self.padding, rect.top() + self.padding, 
                           self.icon_size, self.icon_size)
        
        if item['thumbnail']:
            # Draw actual thumbnail (scaled to fit thumb_rect)
            pixmap = item['thumbnail']
            scaled_pix = pixmap.scaled(self.icon_size, self.icon_size, 
                                      Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
            # Center the pixmap in the thumb_rect
            dx = (self.icon_size - scaled_pix.width()) // 2
            dy = (self.icon_size - scaled_pix.height()) // 2
            painter.drawPixmap(thumb_rect.left() + dx, thumb_rect.top() + dy, scaled_pix)
        else:
            # Draw placeholder
            painter.setBrush(QColor(200, 200, 200))
            painter.drawRect(thumb_rect)
            painter.setPen(QColor(100, 100, 100))
            if item['type'] == 'folder':
                painter.drawText(thumb_rect, Qt.AlignCenter, "📁")
            else:
                painter.drawText(thumb_rect, Qt.AlignCenter, "🖼️")

        # Draw text (filename or display name)
        text_rect = QRect(rect.left(), rect.top() + self.icon_size + self.padding, 
                          rect.width(), rect.height() - self.icon_size - self.padding)
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        display_name = item.get('display_name', os.path.basename(item['path']))
        painter.drawText(text_rect, Qt.AlignHCenter | Qt.AlignTop, display_name)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(self.icon_size + 2 * self.padding, self.icon_size + 40)

class ImageGrid(QListView):
    """Virtualized grid of images and subfolders."""
    item_opened = Signal(str)
    selection_changed = Signal(list) # Emits list of image IDs
    tag_requested = Signal(list, str) # Emits list of IDs and tag name to add

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setMovement(QListView.Static)
        self.setSpacing(10)
        self.setWordWrap(True)
        self.setWrapping(True)
        self.setLayoutMode(QListView.Batched)
        self.setBatchSize(100)
        self.setSelectionMode(QListView.ExtendedSelection) # Allow multi-select
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        
        self.model = ImageModel()
        self.setModel(self.model)
        
        self.delegate = ImageDelegate()
        self.setItemDelegate(self.delegate)
        
        self.doubleClicked.connect(self._on_double_clicked)
        self.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.customContextMenuRequested.connect(self._on_context_menu)

    def set_zoom(self, size):
        self.delegate.icon_size = size
        self.setGridSize(self.delegate.sizeHint(None, None))
        self.model.layoutChanged.emit()

    def _on_double_clicked(self, index: QModelIndex):
        item = index.data(Qt.UserRole)
        if item:
            self.item_opened.emit(item['path'])

    def _on_selection_changed(self, selected, deselected):
        selected_indexes = self.selectionModel().selectedIndexes()
        image_ids = []
        for index in selected_indexes:
            item = index.data(Qt.UserRole)
            if item and item.get('type') == 'image' and 'id' in item:
                image_ids.append(item['id'])
        self.selection_changed.emit(image_ids)

    def _on_context_menu(self, point: QPoint):
        selected_indexes = self.selectionModel().selectedIndexes()
        if not selected_indexes:
            return
            
        menu = QMenu(self)
        add_tag_action = QAction("Add Tag...", self)
        add_tag_action.triggered.connect(lambda: self._request_tag(selected_indexes))
        menu.addAction(add_tag_action)
        
        menu.exec(self.mapToGlobal(point))

    def _request_tag(self, indexes):
        tag, ok = QInputDialog.getText(self, "Add Tag", "Enter tag name:")
        if ok and tag:
            image_ids = []
            for index in indexes:
                item = index.data(Qt.UserRole)
                if item and item.get('type') == 'image' and 'id' in item:
                    image_ids.append(item['id'])
            if image_ids:
                self.tag_requested.emit(image_ids, tag)
