from PyQt6.QtCore import QCoreApplication, QTimer
from thumbnails import ThumbnailManager, ThumbnailWorker
import os
import sys

def test_thumbnails():
    # Use QCoreApplication for headless testing
    app = QCoreApplication(sys.argv)
    manager = ThumbnailManager()
    
    test_path = "g:\\PicLic\\pics\\IMG_001.jpg"
    if not os.path.exists(test_path):
        print(f"Error: {test_path} not found.")
        return

    def on_thumbnail_ready(image_id, path, size, qimage):
        print(f"SUCCESS: Thumbnail generated for {path}")
        print(f"Size: {qimage.width()}x{qimage.height()}, Format: {qimage.format()}")
        # Check if the size is correct (should be at most the requested size)
        if qimage.width() <= size and qimage.height() <= size:
            print(f"Thumbnail dimensions are within requested size {size}")
        else:
            print(f"ERROR: Thumbnail dimensions ({qimage.width()}x{qimage.height()}) exceed requested size {size}")
        
        app.quit()

    manager.thumbnail_ready.connect(on_thumbnail_ready)
    
    print(f"Requesting 128px thumbnail for {test_path}...")
    manager.get_thumbnail(test_path, 128)
    
    # Timeout after 5 seconds
    QTimer.singleShot(5000, lambda: (print("TIMEOUT: Failed to generate thumbnail"), app.quit()))
    
    app.exec()

if __name__ == "__main__":
    test_thumbnails()
