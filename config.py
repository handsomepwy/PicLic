import os

# --- PATHS ---
# Root directory where photos are stored
ROOT_PICS_DIR = os.path.join(os.getcwd(), "..", "pics")

# SQLite database file path
DB_FILE = "piclic.db"

# --- THUMBNAILS ---
# Maximum number of thumbnails to keep in memory (LRU cache)
THUMBNAIL_CACHE_SIZE = 100

# Default zoom size (side length in pixels)
# Supported levels per spec: 128, 256, 512
DEFAULT_THUMBNAIL_SIZE = 160

# --- UI SETTINGS ---
# Grid layout spacing and sizes
GRID_SPACING = 0
GRID_ITEM_WIDTH = 160
GRID_ITEM_HEIGHT = 190
