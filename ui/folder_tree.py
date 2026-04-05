import os
from PySide6.QtWidgets import QTreeView, QFileSystemModel, QHeaderView
from PySide6.QtCore import Signal, QModelIndex, QDir
from config import PICS_DIR

class FolderTree(QTreeView):
    """File system navigation for folders only."""
    folder_selected = Signal(str)

    def __init__(self, root_path=PICS_DIR, parent=None):
        super().__init__(parent)
        self.root_path = os.path.abspath(root_path)
        
        self.model = QFileSystemModel()
        self.model.setRootPath(self.root_path)
        self.model.setFilter(QDir.Dirs | QDir.NoDotAndDotDot)
        
        self.setModel(self.model)
        self.setRootIndex(self.model.index(self.root_path))
        
        # Hide columns except Name
        for column in range(1, self.model.columnCount()):
            self.hideColumn(column)
            
        self.header().setSectionResizeMode(QHeaderView.Stretch)
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self, index: QModelIndex):
        path = self.model.filePath(index)
        self.folder_selected.emit(path)
