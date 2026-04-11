import os
from PIL import Image
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import QRunnable, pyqtSignal, QObject, QThreadPool, pyqtSlot
from collections import OrderedDict
import threading

class ThumbnailSignals(QObject):
    """
    Signals for the thumbnail worker.
    """
    loaded = pyqtSignal(str, int, QImage)  # path, size, image
    error = pyqtSignal(str, str)           # path, error message

class ThumbnailWorker(QRunnable):
    """
    Worker thread for generating thumbnails from JPEG files.
    """
    def __init__(self, path, size):
        super().__init__()
        self.path = path
        self.size = size
        self.signals = ThumbnailSignals()

    @pyqtSlot()
    def run(self):
        try:
            # Open image using Pillow
            with Image.open(self.path) as img:
                # Convert to RGB if necessary
                if img.mode != "RGB":
                    img = img.convert("RGB")
                
                # Resize using NEAREST filter for maximum speed (quality is not a priority)
                resample_filter = getattr(Image, 'Resampling', Image).NEAREST if hasattr(Image, 'Resampling') else Image.NEAREST
                img.thumbnail((self.size, self.size), resample_filter)
                
                # Convert Pillow image to QImage
                # QImage needs the data to stay alive during its lifetime if created from buffer
                # So we use the copy() method to ensure it owns its data
                data = img.tobytes("raw", "RGB")
                qimage = QImage(data, img.size[0], img.size[1], QImage.Format.Format_RGB888).copy()
                
                self.signals.loaded.emit(self.path, self.size, qimage)
        except Exception as e:
            self.signals.error.emit(self.path, str(e))

class ThumbnailCache:
    """
    In-memory LRU cache for thumbnails.
    """
    def __init__(self, max_size=500):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.lock = threading.Lock()

    def get(self, path, size):
        key = (path, size)
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                return self.cache[key]
        return None

    def put(self, path, size, qimage):
        key = (path, size)
        with self.lock:
            self.cache[key] = qimage
            self.cache.move_to_end(key)
            if len(self.cache) > self.max_size:
                self.cache.popitem(last=False)

class ThumbnailManager(QObject):
    """
    Manager for thumbnail requests and caching.
    """
    thumbnail_ready = pyqtSignal(str, int, QImage)

    def __init__(self, cache_size=1000):
        super().__init__()
        self.cache = ThumbnailCache(max_size=cache_size)
        self.thread_pool = QThreadPool.globalInstance()
        # Set a reasonable number of threads for thumbnail generation
        # Too many can lead to I/O bottlenecks
        self.thread_pool.setMaxThreadCount(max(2, os.cpu_count() or 2))
        self.pending_requests = set()
        self.lock = threading.Lock()

    def get_thumbnail(self, path, size):
        """
        Requests a thumbnail of a given size.
        If cached, emits thumbnail_ready immediately.
        Otherwise, schedules a background worker.
        """
        # Normalize path before using as key
        # Note: We don't have access to Database.normalize_path here without circular import
        # So we use a simple normalization that matches our database logic
        path = os.path.normpath(os.path.normcase(os.path.abspath(path)))
        
        cached_img = self.cache.get(path, size)
        if cached_img:
            self.thumbnail_ready.emit(path, size, cached_img)
            return

        # Check if already requested to avoid duplicate workers
        request_key = (path, size)
        with self.lock:
            if request_key in self.pending_requests:
                return
            self.pending_requests.add(request_key)

        # Create and start worker
        worker = ThumbnailWorker(path, size)
        worker.signals.loaded.connect(self._on_thumbnail_loaded)
        worker.signals.error.connect(self._on_thumbnail_error)
        self.thread_pool.start(worker)

    def _on_thumbnail_loaded(self, path, size, qimage):
        with self.lock:
            self.pending_requests.discard((path, size))
        
        self.cache.put(path, size, qimage)
        self.thumbnail_ready.emit(path, size, qimage)

    def _on_thumbnail_error(self, path, error_msg):
        with self.lock:
            # We use a special key for size to clear pending requests if needed
            # For now just discard
            # Find all sizes that might have failed for this path
            to_remove = [req for req in self.pending_requests if req[0] == path]
            for req in to_remove:
                self.pending_requests.discard(req)
        
        print(f"Error loading thumbnail for {path}: {error_msg}")

if __name__ == "__main__":
    # Simple test for ThumbnailManager
    from PyQt6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    manager = ThumbnailManager()

    def on_ready(path, size, qimage):
        print(f"Thumbnail ready: {path} ({qimage.width()}x{qimage.height()})")
        # If this was the last expected test, we could exit
        # app.quit()

    manager.thumbnail_ready.connect(on_ready)
    
    # Replace with a real path from your pics directory for testing
    test_path = "g:\\PicLic\\pics\\IMG_001.jpg"
    if os.path.exists(test_path):
        print(f"Testing thumbnail generation for: {test_path}")
        manager.get_thumbnail(test_path, 256)
    else:
        print(f"Test path not found: {test_path}")

    # For testing purposes, we'll exit after a few seconds
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(5000, app.quit)
    
    sys.exit(app.exec())
