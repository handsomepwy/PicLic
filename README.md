# PicLic Quick Code Guide

PicLic is a local-first desktop photo manager built with Python, PyQt6, and SQLite.  
It focuses on fast browsing of JPEG libraries while keeping RAW files as linked attachments.

## What This Project Does

- Scans a photo root folder and indexes image groups into SQLite
- Treats one JPEG + matching RAW files (same basename) as one logical image entry
- Shows folder navigation plus a virtualized gallery grid
- Generates thumbnails in background threads with an in-memory LRU cache
- Supports hierarchical tags (`a/b/c`) and tag-based filtering

## Entry Point

- Run the app from `main.py`
- Main window class: `MainWindow`

## Code Map (Where Things Live)

- `main.py`
  - Builds the full UI (folder tree, gallery, tags panel)
  - Starts background scanning via `ScanWorker` (`QThread`)
  - Polls `scan_status` every 500ms to update progress UI
  - Handles folder navigation, double-click open, tag apply/remove

- `gallery_model.py`
  - `GalleryModel` (`QAbstractListModel`) for the center gallery
  - Combines:
    - subfolders from filesystem
    - image rows from DB (`images` table)
  - Requests thumbnails lazily and reacts to `thumbnail_ready` updates

- `thumbnails.py`
  - `ThumbnailManager`: async thumbnail pipeline + LRU cache
  - Cache key: `(path, size)`
  - Uses worker threads and a LIFO-style queue to prioritize current visible items
  - Emits Qt signal when a thumbnail is ready

- `scanner.py`
  - Walks folder tree and groups files by basename
  - Accepts file types: jpg/jpeg + common RAW extensions
  - Indexes only groups that include a JPEG
  - Commits in batches (`batch_size = 100`)
  - Updates DB `scan_status` during scan

- `database.py`
  - Creates schema and enables WAL
  - Handles:
    - image/file indexing
    - scan status read/write
    - hierarchical tag creation (`get_or_create_tag_path`)
    - image-tag linking/unlinking
    - descendant lookup for tree filtering
    - pruning unused tags

- `config.py`
  - Runtime configuration (root path, DB file, thumbnail/grid defaults)

- `verify_db.py`
  - Simple DB inspection script

- `verify_thumbnails.py`
  - Headless thumbnail generation test

## Data Model (SQLite)

Main tables:

- `images`: one row per logical image (keyed by `jpg_path`)
- `files`: all grouped files per image (jpg/raw/etc.)
- `tags`: hierarchical tag nodes (`parent_id`)
- `image_tags`: many-to-many link table
- `scan_status`: single-row scan progress/state

DB file defaults to `piclic.db` in project root.

## Runtime Flow

1. App starts and initializes DB + services
2. User selects folder in tree
3. `GalleryModel` loads folder entries + DB images
4. Visible image cells request thumbnails
5. Background thumbnail workers decode and emit results
6. Scan button starts background indexer; UI polls progress and remains responsive

## How To Run

1. Install dependencies (Python 3.10+):
   - `PyQt6`
   - `Pillow` (or Pillow-SIMD if available)
2. Set photo root if needed in `config.py` (`ROOT_PICS_DIR`)
3. Start app:
   - `python main.py`

Optional checks:

- `python verify_db.py`
- `python verify_thumbnails.py`

## Notes for New Contributors

- Keep heavy I/O and image decoding off the UI thread
- Use normalized paths when writing/querying DB
- Tag operations rely on parent/child relationships and descendant expansion
- Gallery behavior is driven by `GalleryModel`, not direct widget item insertion
