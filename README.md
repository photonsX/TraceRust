# 📦 TraceRust: Desktop Asset Library & Migration Deck

> [!WARNING]
> **Work In Progress (WIP)**: This project is under active development. Features are being built, tested, and updated frequently.

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
*   **Text File Indices**: Writes records to `hard_drive_index.txt` using a optimized `<size> | <path>` format for lazy-loading.

### 2. Upgraded Radix Scanner View
*   **Lazy-Loaded Viewport Explorer**: Renders massive index files instantly using recursive path expansions on-demand.
*   **Container Tagging**: Right-click any directory or file and choose **Mark as Container Asset**. These assets are visually flagged with `[BOX]` in green text.
*   **In-place Renaming**: Double-click or select and press enter to physically rename folders/files on your disk directly from the viewport. It updates `hard_drive_index.txt` recursively in-place without needing a full re-scan!

### 3. TraceMover 3-Pane Migration Deck
*   **Panel 1 (Source Trees)**: Displays scanned paths. Marked container assets (`[BOX]`) are treated as solid, non-expandable leaf nodes to prevent unnecessary directory crawling.
*   **Panel 2 (Target Blueprint)**: Virtual layout canvas where you select a target physical drive and build virtual directory blueprints (create, rename in-place, and delete virtual folders).
*   **Panel 3 (Staging Table Queue)**: Drag container assets from Panel 1 and drop them onto virtual folders in Panel 2 to stage them for movement.
*   **Capacity checks**: Automatically queries destination disk capacity, adjusting for currently staged queues, and blocks execution if space is exceeded (**`[INSUFFICIENT SPACE]`** badge).
*   **Sequential Movement Engine**: Groups staging queue items by their physical *Source Drive* to avoid disk-head contention, executing cuts and moves sequentially. Logs transfers to `tracerust_transfer_log.txt`.

---

## 🛠️ Tech Stack
- **Core Engine**: Rust (standard file walkways)
- **GUI Desktop Shell**: Python 3 (Tkinter / ttk)
- **Settings Store**: JSON (`config.json`)
- **Logging & Verification**: UTF-8 Text (`tracerust_transfer_log.txt`)

---

## 🏁 How to Run Local View
Ensure you have Python 3 installed. You do not need to install extra dependencies as the app relies on Python standard libraries.

1. Clone this repository to your system.
2. Open your terminal in the repository folder.
3. Run the following command:
   ```bash
   python tracerust_app.py
   ```
