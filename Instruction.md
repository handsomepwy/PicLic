# LOCAL PYTHON PHOTO MANAGER (PyQt + SQLite) — FULL SPECIFICATION

## GOAL
Build a high-performance, local-first desktop photo management application in Python using PyQt (preferably PyQt6). The system must handle large image libraries (10k → 100k+ images), provide extremely fast browsing, hierarchical tagging, and efficient search.

The design prioritizes:
- fast JPEG-only browsing (ignore RAW during browsing)
- folder-based navigation (like Windows Explorer)
- SQLite-based indexing
- in-memory thumbnail caching only (no disk cache)
- async background scanning
- responsive UI at all times

---

# 1. TECH STACK

- Language: Python 3.10+
- GUI: PyQt6 (PyQt preferred over PySide)
- Database: SQLite3
- Image decoding: Pillow-SIMD (or Pillow if unavailable)
- Threading: QThread or Python threading with Qt signals
- Optional: concurrent.futures for worker pools

---

# 2. CORE ARCHITECTURE

Split into 4 modules:

## 2.1 UI LAYER (PyQt)
Responsibilities:
- Folder tree navigation (like Windows Explorer)
- Thumbnail grid view (virtualized)
- Tag panel (tree + search input)
- Image preview/open actions
- Progress display for scanning

Rules:
- NEVER load images directly in UI thread
- NEVER scan filesystem in UI thread

---

## 2.2 INDEXER (SEPARATE PROCESS OR BACKGROUND THREAD)

Responsibilities:
- Walk root "pics" directory
- ONLY index JPEG files (.jpg/.jpeg)
- Group files by basename (ignore extension differences)

Example grouping:
IMG_001.jpg
IMG_001.nef
IMG_001.dng

→ one logical "image entry" with multiple files

Rules:
- RAW files are NOT used for thumbnails
- RAW files are stored as attachments only
- scanning runs in background process or QThread

Batch database writes (IMPORTANT):
- commit every 100–500 files

---

## 2.3 DATABASE (SQLite)

Enable WAL mode:
PRAGMA journal_mode=WAL;

### Tables:

#### images
- id INTEGER PRIMARY KEY
- jpg_path TEXT UNIQUE
- folder_path TEXT INDEXED

#### files
- id INTEGER PRIMARY KEY
- image_id INTEGER
- file_path TEXT
- file_type TEXT (jpg / nef / dng / etc.)

#### tags
- id INTEGER PRIMARY KEY
- name TEXT UNIQUE (case-insensitive)
- parent_id INTEGER NULL

#### image_tags
- image_id INTEGER INDEXED
- tag_id INTEGER INDEXED

#### scan_status
- id INTEGER PRIMARY KEY (always 1 row)
- is_running INTEGER
- scanned_count INTEGER
- current_path TEXT
- last_updated TIMESTAMP

---

# 3. THUMBNAIL SYSTEM

## 3.1 RULES
- ONLY generate thumbnails from JPEG files
- DO NOT use RAW files for rendering
- Use Pillow-SIMD for decoding

## 3.2 CACHING
- in-memory LRU cache only
- key: (file_path, thumbnail_size)
- no disk cache allowed

## 3.3 SIZES
Support 3 zoom levels:
- 128px
- 256px
- 512px

## 3.4 THREADING
Thumbnail generation MUST run in background threads.
UI only receives ready QPixmap objects.

---

# 4. UI DESIGN

## 4.1 MAIN LAYOUT
- Left: Folder Tree (QTreeView)
- Center: Thumbnail Grid (virtualized QListView/QTableView)
- Right: Tag panel + file info

---

## 4.2 GRID BEHAVIOR
- virtualized rendering (only visible items rendered)
- lazy loading thumbnails
- smooth scrolling required

---

## 4.3 IMAGE OPENING
- double click → open system default viewer
- Python: os.startfile(path) (Windows) or equivalent cross-platform

---

# 5. TAGGING SYSTEM

## 5.1 STRUCTURE
Hierarchical tags (tree-based):

Example:
astro
  nebula
    m42
  galaxy
    m31

Tags stored as:
- parent_id relationship
- optional full_path optimization (recommended for autocomplete)

---

## 5.2 TAG ASSIGNMENT UX

PRIMARY METHOD (IMPORTANT):
Use path-based input with autocomplete:

Examples:
- astro/nebula/m42
- travel/japan/tokyo

Rules:
- Each "/" moves one level deeper
- autocomplete restricted to valid children at each level
- Enter applies tag to selected images instantly

SECONDARY METHOD:
- Tree view selection (for browsing only)

---

## 5.3 TAG SEARCH LOGIC

Support:
- AND search: astro nebula
- OR search: astro|landscape
- EXCLUDE: -bad

Rules:
- case-insensitive
- fast SQLite indexed joins
- supports multi-tag queries

---

## 5.4 BATCH TAGGING
- multi-select images
- apply tag in single DB transaction
- must be instant (no blocking UI)

---

# 6. SCANNING SYSTEM

## 6.1 TRIGGER
- manual button: "Scan / Update Library"

## 6.2 BEHAVIOR
- UI remains fully responsive
- scanner runs in background process or QThread
- no UI blocking allowed

## 6.3 PROGRESS REPORTING
Update SQLite scan_status table:

- scanned_count updated every 50–200 files
- current_path updated continuously
- is_running flag maintained

UI polls scan_status every ~300–500ms

---

# 7. PERFORMANCE RULES

CRITICAL:
- never load full images for thumbnails
- never decode RAW files
- never block UI thread with disk I/O
- use batch DB operations only
- use virtualized UI views

Target:
- smooth scrolling at 100k images

---

# 8. SEARCH & FILTERING

Search scope:
- current folder context + optional tag filters

Rules:
- filtering does NOT break folder navigation model
- folder view remains primary structure
- tags act as overlay filter

---

# 9. EXTENSIBILITY REQUIREMENT

System must allow future expansion:
- AI tagging
- similarity search (embeddings)
- additional metadata tables

DO NOT hardcode assumptions preventing extensions.

---

# 10. NON-GOALS (IMPORTANT)

DO NOT IMPLEMENT:
- RAW decoding pipeline
- disk-based thumbnail cache
- cloud sync
- complex editing features
- EXIF-heavy filtering (explicitly unnecessary)

---

# 11. ACCEPTANCE CRITERIA

System is correct if:
- scrolling 10k images is smooth
- thumbnails load instantly during scroll (cached)
- scanning runs in background with visible progress
- tagging is instant and keyboard-driven
- folder navigation behaves like Windows Explorer
- RAW files are accessible only on demand

---

END OF SPEC