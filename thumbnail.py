import os
from PIL import Image
from functools import lru_cache
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool, QSize
from PySide6.QtGui import QImage, QPixmap

class ThumbnailWorker(QRunnable):
    """Worker for asynchronous thumbnail generation."""
    def __init__(self, image_path, size, callback):
        super().__init__()
        self.image_path = image_path
        self.size = size
        self.callback = callback

    def run(self):
        try:
            # Open image using Pillow
            with Image.open(self.image_path) as img:
                # Convert to RGB if necessary (e.g. for CMYK or RGBA)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Use thumbnail() for efficient downscaling
                img.thumbnail((self.size, self.size), Image.Resampling.LANCZOS)
                
                # Convert Pillow image to QImage
                data = img.tobytes("raw", "RGB")
                qimage = QImage(data, img.size[0], img.size[1], QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qimage)
                self.callback(self.image_path, pixmap)
        except Exception as e:
            print(f"Error generating thumbnail for {self.image_path}: {e}")
            # Optionally return a placeholder or None
            self.callback(self.image_path, None)

class ThumbnailManager(QObject):
    """Manages thumbnail generation and caching."""
    thumbnail_ready = Signal(str, QPixmap)

    def __init__(self, cache_size=500):
        super().__init__()
        self.cache_size = cache_size
        self.thread_pool = QThreadPool.globalInstance()
        # In-memory LRU cache for pixmaps
        self._get_cached_pixmap = lru_cache(maxsize=cache_size)(self._load_pixmap)

    def _load_pixmap(self, path, size):
        # This is the synchronous part, we mainly use it via the worker
        pass

    def get_thumbnail(self, image_path, size=256):
        """Request a thumbnail for the given path and size."""
        # For now, we always use the worker for async loading
        worker = ThumbnailWorker(image_path, size, self._on_thumbnail_ready)
        self.thread_pool.start(worker)

    def _on_thumbnail_ready(self, path, pixmap):
        if pixmap:
            self.thumbnail_ready.emit(path, pixmap)

if __name__ == "__main__":
    # Small test (requires a real image or it will fail)
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    manager = ThumbnailManager()
    manager.thumbnail_ready.connect(lambda path, pix: print(f"Thumbnail ready for {path}"))
    # manager.get_thumbnail("pics/IMG_001.jpg") # This will fail if the file is empty
    print("ThumbnailManager initialized.")
