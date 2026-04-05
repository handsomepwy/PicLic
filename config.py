import os

# Base directory for the images
# You can change this to any path you want to manage.
PICS_DIR = os.path.join(os.getcwd(), "..", "pics")

# Database settings
DB_PATH = "piclic.db"

# Thumbnail settings
THUMBNAIL_CACHE_SIZE = 1000 # Number of thumbnails to keep in memory
DEFAULT_ZOOM_SIZE = 256
