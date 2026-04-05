import sys
import os
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow

def main():
    # Set app name and other metadata
    app = QApplication(sys.argv)
    app.setApplicationName("PicLic")
    app.setOrganizationName("PicLic")
    
    # Ensure root pics directory exists
    root_pics = os.path.join(os.getcwd(), "pics")
    if not os.path.exists(root_pics):
        os.makedirs(root_pics)
        print(f"Created initial pics directory: {root_pics}")

    # Start Main Window
    window = MainWindow(root_path=root_pics)
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
