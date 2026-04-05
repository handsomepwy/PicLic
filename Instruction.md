# High-Performance Local Image Browser (Design Spec)

## 1. Overview

This project is a **local, high-performance image browsing application** designed to efficiently navigate and tag large collections of JPEG images.

The system prioritizes:
- Fast folder-based navigation (Explorer-like)
- Very fast thumbnail browsing (JPEG-only)
- Tag-based retrieval (AND / OR / EXCLUDE)
- Minimal overhead (no EXIF, no RAW decoding in browsing)

RAW files are treated as **supplementary assets** and are only accessed on demand.

---

## 2. Core Principles

1. **JPEG-first design**
   - Only `.jpg/.jpeg` are used for browsing and thumbnails
   - RAW files are ignored during browsing

2. **Folder-first navigation**
   - UI mirrors filesystem structure
   - Tags act as filters, not replacements for navigation

3. **No disk caching**
   - Only in-memory thumbnail caching (LRU)

4. **Minimal metadata**
   - No EXIF parsing
   - No camera info
   - No deduplication

5. **Responsiveness over completeness**
   - Prioritize fast scrolling and interaction

---

## 3. File System Assumptions

- Root directory: `pics/`
- Arbitrary nested subfolders
- Files grouped by filename:
  ```
  IMG_001.jpg
  IMG_001.nef
  IMG_001.dng
  ```

Rules:
- A "photo" is defined by the existence of a `.jpg`
- All files sharing the same basename belong to that photo

---

## 4. Data Model (SQLite)

### 4.1 Tables

#### images
```sql
id INTEGER PRIMARY KEY
jpg_path TEXT UNIQUE
folder_path TEXT
```

#### files
```sql
id INTEGER PRIMARY KEY
image_id INTEGER
file_path TEXT
file_type TEXT
```

#### tags
```sql
id INTEGER PRIMARY KEY
name TEXT UNIQUE
```

#### image_tags
```sql
image_id INTEGER
tag_id INTEGER
PRIMARY KEY (image_id, tag_id)
```

---

### 4.2 Indexes

```sql
CREATE INDEX idx_images_folder ON images(folder_path);
CREATE INDEX idx_image_tags_tag ON image_tags(tag_id);
CREATE INDEX idx_image_tags_image ON image_tags(image_id);
```

---

## 5. Indexing System

### 5.1 Behavior

- Manual trigger: **"Scan / Update" button**
- No automatic filesystem watching

### 5.2 Scan Algorithm

1. Recursively walk `pics/`
2. Group files by basename
3. For each group:
   - If `.jpg` exists:
     - create/update image entry
     - attach all files in group to `files` table
   - otherwise ignore

### 5.3 Simplifications

- No rename tracking
- No deletion tracking required (optional)

---

## 6. Thumbnail System

### 6.1 Rules

- Only generate thumbnails from JPEG
- Ignore RAW completely

### 6.2 Implementation

- Use `Pillow-SIMD`
- Use `.thumbnail()` or equivalent downscaling
- Sizes:
  - Small: 128px
  - Medium: 256px
  - Large: 512px

### 6.3 Caching

- In-memory LRU cache
- Suggested size: 200–500 images

### 6.4 Performance Requirements

- Load only visible thumbnails
- Asynchronous loading
- Prefetch next viewport

---

## 7. UI Design

### 7.1 Layout

Three main regions:

1. **Folder Tree (left)**
   - Mirrors filesystem
   - Click to navigate

2. **Image Grid (center)**
   - Shows:
     - subfolders (first)
     - images (second)

3. **Tag/Search Input (top or side)**

---

### 7.2 Grid Behavior

- Virtualized rendering (only visible items)
- Keyboard navigation:
  - Arrow keys → move
  - Shift/Ctrl → multi-select

### 7.3 Zoom Levels

- 2–3 discrete levels:
  - 128px
  - 256px
  - 512px

---

## 8. Tagging System

### 8.1 Rules

- Flat tags (no hierarchy)
- Case-insensitive (stored lowercase)
- Unique names

### 8.2 Operations

- Apply tag instantly (no confirmation)
- Batch tagging supported
- No undo/redo (manual correction)

---

## 9. Search System

### 9.1 Supported Queries

Examples:
```
astro night
astro|landscape night
astro night -bad
```

### 9.2 Semantics

- Space = AND
- `|` = OR
- `-tag` = EXCLUDE

### 9.3 Execution Model

- Filter = (current folder scope) AND (tag query)

### 9.4 SQL Strategy

- AND → multiple joins
- OR → union or IN clause
- EXCLUDE → NOT EXISTS

---

## 10. File Opening

### 10.1 Default Action

- Double-click → open JPG via OS default

### 10.2 RAW Access

- Show list of associated files:
  ```
  IMG_001.jpg
  IMG_001.nef
  IMG_001.dng
  ```
- User selects which to open

---

## 11. Sorting

Default:
1. Folders first
2. Images next
3. Sort by filename

---

## 12. Performance Requirements

Target scale:
- 10k → 100k images

Constraints:
- Smooth scrolling
- No UI blocking
- Fast query (<100ms typical)

---

## 13. Architecture (Suggested Modules)

### 13.1 scanner.py
- Directory traversal
- Database update

### 13.2 database.py
- SQLite connection
- Query helpers

### 13.3 thumbnail.py
- Thumbnail generation
- LRU cache

### 13.4 ui/
- main_window.py
- folder_tree.py
- image_grid.py
- tag_input.py

### 13.5 controller.py
- Connect UI + database
- Handle events

---

## 14. Key Risks

1. Blocking UI thread during thumbnail loading  
2. Rendering too many widgets (no virtualization)  
3. Inefficient tag query joins  

---

## 15. Development Strategy

### Phase 1 (MVP)
- Folder navigation
- JPEG display
- Basic thumbnails

### Phase 2
- SQLite indexing
- Tagging system

### Phase 3
- Search (AND / OR / EXCLUDE)

### Phase 4
- Performance optimization
- Async thumbnail loading

---

## 16. Non-Goals

- No EXIF parsing  
- No RAW decoding for thumbnails  
- No cloud sync  
- No duplicate detection  