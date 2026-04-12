import os
from PIL import Image
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import QRunnable, pyqtSignal, QObject, QThreadPool, pyqtSlot
from collections import OrderedDict, deque
import threading
import config
import queue

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
    def __init__(self, max_size=config.THUMBNAIL_CACHE_SIZE):
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
    Uses a custom LIFO queue to handle high-frequency requests during scrolling.
    """
    thumbnail_ready = pyqtSignal(str, int, QImage)

    def __init__(self, cache_size=config.THUMBNAIL_CACHE_SIZE):
        super().__init__()
        self.cache = ThumbnailCache(max_size=cache_size)
        
        # We use a custom worker system instead of QThreadPool for better control
        self.request_queue = deque()
        self.pending_paths = set()
        self.lock = threading.Lock()
        
        # Fixed number of worker threads to avoid disk thrashing
        # 2 threads is usually optimal for HDD/SSD read without blocking too much
        self.num_workers = 2
        self.workers = []
        self.running = True
        
        for _ in range(self.num_workers):
            t = threading.Thread(target=self._worker_loop, daemon=True)
            t.start()
            self.workers.append(t)

    def get_thumbnail(self, path, size):
        """
        Requests a thumbnail. If cached, emits immediately.
        Otherwise, adds to the FRONT of the queue (LIFO).
        """
        path = os.path.normpath(os.path.normcase(os.path.abspath(path)))
        
        cached_img = self.cache.get(path, size)
        if cached_img:
            self.thumbnail_ready.emit(path, size, cached_img)
            return

        with self.lock:
            if (path, size) in self.pending_paths:
                return
            
            # Add to front of queue (LIFO) so current visible items are processed first
            self.request_queue.appendleft((path, size))
            self.pending_paths.add((path, size))
            
            # Limit the queue size to avoid processing thousands of stale requests
            if len(self.request_queue) > 200:
                old_path, old_size = self.request_queue.pop() # Remove from back (oldest)
                self.pending_paths.discard((old_path, old_size))

    def clear_requests(self):
        """
        Clears all pending thumbnail requests.
        Useful when changing folders.
        """
        with self.lock:
            self.request_queue.clear()
            self.pending_paths.clear()

    def _worker_loop(self):
        while self.running:
            request = None
            with self.lock:
                if self.request_queue:
                    request = self.request_queue.popleft()
            
            if not request:
                import time
                time.sleep(0.01) # Small sleep when idle
                continue
            
            path, size = request
            try:
                # Pillow-SIMD or Pillow decoding
                with Image.open(path) as img:
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    
                    resample_filter = getattr(Image, 'Resampling', Image).NEAREST if hasattr(Image, 'Resampling') else Image.NEAREST
                    img.thumbnail((size, size), resample_filter)
                    
                    data = img.tobytes("raw", "RGB")
                    qimage = QImage(data, img.size[0], img.size[1], QImage.Format.Format_RGB888).copy()
                    
                    # Store in cache and emit
                    self.cache.put(path, size, qimage)
                    self.thumbnail_ready.emit(path, size, qimage)
            except Exception as e:
                print(f"Error loading thumbnail for {path}: {e}")
            finally:
                with self.lock:
                    self.pending_paths.discard((path, size))

    def stop(self):
        self.running = False
        for t in self.workers:
            t.join()

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
