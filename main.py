import sys
import os
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from config import PICS_DIR

def main():
    # Set app name and other metadata
    app = QApplication(sys.argv)
    app.setApplicationName("PicLic")
    app.setOrganizationName("PicLic")
    
    # Ensure root pics directory exists
    if not os.path.exists(PICS_DIR):
        os.makedirs(PICS_DIR)
        print(f"Created initial pics directory: {PICS_DIR}")

    # Start Main Window
    window = MainWindow(root_path=PICS_DIR)
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
