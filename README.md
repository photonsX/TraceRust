# 📦 TraceRust: Desktop Asset Library & Migration Deck (v2.0-stable)

> [!NOTE]
> **TraceRust v2.0-stable** is now active, introducing local SQLite persistence, interactive Google Gemini AI metadata lookup, over-scan cover cropping, and recursive folder color highlights.

**TraceRust** is a hybrid desktop application designed for high-performance local asset management, rapid indexing, and multi-drive storage migrations. It pairs a parallel file walking scanner built in Rust with a sleek, responsive, floating-window dashboard shell written in Python (Tkinter).

---

## 🎨 Visual Preview & Design System
The application features a custom, high-contrast desktop shell using a premium **Nord Dark** design system:
- **Canvas Background**: Deep Slate Slate (`#2e3440`)
- **Cards & Elements**: Nord slate dark (`#3b4252`)
- **Accent Highlighting**: Frost Blue (`#88c0d0`) and Frost Teal (`#8fbcbb`)

### Draggable In-App Window System
Rather than traditional tab switches, clicking navigation items in the top-left **Burger Menu (☰)** opens standalone, custom-rendered floating windows. These windows can be dragged across the main dashboard canvas, closed, minimized, or clicked to focus and lift to the front.

---

## 🚀 Key Features

### 1. Radix Indexing Engine (`radix_engine.exe`)
*   **Rust Parallel Search**: Leverages Rust's multithreaded directory iterator to walk massive local disks in seconds.
*   **Configurable Ignored Files**: Skips bypass folders and common patterns (e.g. `.git`, `node_modules`, `target`, `build`) specified in `config.json`.
*   **Text File Indices**: Writes records to `hard_drive_index.txt` using an optimized `<size> | <path>` format for lazy-loading.

### 2. Upgraded Radix Scanner View
*   **Lazy-Loaded Viewport Explorer**: Renders massive index files instantly using recursive path expansions on-demand.
*   **Container Tagging**: Right-click any directory or file and choose **Mark as Container Asset**. These assets are visually flagged with `[BOX]` in green text.
*   **In-place Renaming**: Double-click or select and press enter to physically rename folders/files on your disk directly from the viewport. It updates `hard_drive_index.txt` recursively in-place without needing a full re-scan!

### 3. TraceMover 3-Pane Migration Deck
*   **Panel 1 (Source Trees)**: Displays scanned paths.
*   **Panel 2 (Target Blueprint)**: Virtual layout canvas where you select a target physical drive and build virtual directory blueprints.
*   **Panel 3 (Staging Table Queue)**: Stage any file or directory for movement.
*   **Capacity checks**: Automatically queries destination disk capacity and blocks execution if space is exceeded (**`[INSUFFICIENT SPACE]`** badge).
*   **Sequential Movement Engine**: Executed cuts and moves sequentially. Logs transfers to `tracerust_transfer_log.txt`.

---

## 🔥 New in v2.0-stable

### 💾 1. SQLite Database Architecture (`tracerust.db`)
* Decoupled state storing from configuration files. The app now leverages a relational **SQLite Database** to record custom metadata (titles, tags, descriptions, ratings, website urls, and highlight states).
* Automated backward-compatibility migration of existing `config.json` attributes on start.

### 🤖 2. Google Gemini AI Metadata Autofill
* Right-click any academy asset/folder to select **`🤖 Search Gemini AI`**.
* The app automatically connects via the latest **`gemini-3.1-flash-lite`** model, parses course names, searches Google AI, and retrieves suggested:
  * Official Website links.
  * Search Tags.
  * Course descriptions/descriptions.
* **Interactive Review Dialog**: Displays a preview pop-up letting you review and customize suggestion text before saving to the SQLite database.
* General Settings option to customize/input your own **Gemini API Key**.

### 🎨 3. Cascading Red/Green Custom Highlights
* Right-click options to apply recursive, cascading visual highlights:
  * **🔴 Red Highlight** (Pastel pink/rose `#ff8fa3`)
  * **🟢 Green Highlight** (Pastel Nord green `#a3be8c`)
  * **Clear Highlight** (Resets back to normal theme colors)
* Highlighting a folder recursively propagates the tag down to all child folders and files.

### 📐 4. Over-Scan & Over-Crop Canvas Support
* When cropping custom cover art, non-square and non-HD images are automatically padded into a square canvas with a clean black letterbox background.
* Allows dragging the crop box to the absolute edges of landscape or portrait artwork without clipping.

### 🛎️ 5. In-App Toast Notifications
* Handcrafted slide-in Toast notifications replace obstructive system dialog boxes for progress and success signals.

---

## 🛠️ Tech Stack
- **Core Engine**: Rust (standard file walkways)
- **GUI Desktop Shell**: Python 3 (Tkinter / ttk)
- **Database Backing**: SQLite 3 (`tracerust.db`)
- **Settings Store**: JSON (`config.json`)
- **Logging**: UTF-8 Text (`tracerust_transfer_log.txt`)

---

## 🏁 How to Run Local View
Ensure you have Python 3 installed. You do not need to install extra dependencies as the app relies on Python standard libraries.

1. Clone this repository to your system.
2. Open your terminal in the repository folder.
3. Run the following command:
   ```bash
   python tracerust_app.py
   ```
