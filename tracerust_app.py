import os
import sys
import json
import shutil
import string
import datetime
import subprocess
import threading
import queue
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Visual Design Palette (Nord Dark Theme)
BG_COLOR = "#2e3440"          # Primary Canvas Background (Dark Gray/Blue)
CARD_BG = "#3b4252"           # Container/Card Background (Darker Slate)
HEADER_BG = "#434c5e"         # Window Title Bar Background
TEXT_COLOR = "#eceff4"        # Crisp Off-White Text
TEXT_MUTED = "#d8dee9"        # Muted Grayish-White Text
ACCENT_COLOR = "#88c0d0"      # Frost Blue (Accents/Buttons)
SUCCESS_COLOR = "#a3be8c"     # Nord Green (Containers/Movable)
DANGER_COLOR = "#bf616a"      # Nord Red (Blocked/Insufficient Space)
SECONDARY_BG = "#4c566a"      # Intermediate Slate Gray
SELECT_BG = "#4c566a"         # Selected Tree Item Background
HIGHLIGHT = "#8fbcbb"         # Frost Teal (Hover)

class ToastNotification(tk.Frame):
    def __init__(self, parent, title, message, status_type="info"):
        border_color = "#88c0d0"
        if status_type == "success":
            border_color = "#a3be8c"
        elif status_type == "error":
            border_color = "#bf616a"
            
        super().__init__(parent, bg=border_color, bd=1)
        self.parent = parent
        
        self.inner = tk.Frame(self, bg="#3b4252", padx=12, pady=10)
        self.inner.pack(fill="both", expand=True)
        
        self.title_lbl = tk.Label(
            self.inner, text=title, font=("Segoe UI", 9, "bold"), 
            fg="#eceff4", bg="#3b4252"
        )
        self.title_lbl.pack(anchor="w")
        
        self.msg_lbl = tk.Label(
            self.inner, text=message, font=("Segoe UI", 8), 
            fg="#d8dee9", bg="#3b4252", wraplength=250, justify="left"
        )
        self.msg_lbl.pack(anchor="w", pady=(2, 0))
        
        self.width = 280
        self.height = 70
        
        self.current_y = 100
        self.place(relx=1.0, rely=1.0, x=-20, y=self.current_y, anchor="se", width=self.width, height=self.height)
        
        self.slide_in()

    def slide_in(self):
        if not self.winfo_exists():
            return
        if self.current_y > -20:
            self.current_y -= 8
            if self.current_y < -20:
                self.current_y = -20
            self.place(relx=1.0, rely=1.0, x=-20, y=self.current_y, anchor="se", width=self.width, height=self.height)
            self.parent.after(15, self.slide_in)
        else:
            self.parent.after(3500, self.slide_out)

    def slide_out(self):
        if not self.winfo_exists():
            return
        if self.current_y < 120:
            self.current_y += 8
            self.place(relx=1.0, rely=1.0, x=-20, y=self.current_y, anchor="se", width=self.width, height=self.height)
            self.parent.after(15, self.slide_out)
        else:
            self.destroy()

class TreeNode:
    def __init__(self, name, is_dir=True):
        self.name = name
        self.is_dir = is_dir
        self.size = 0
        self.children = {}  # name -> TreeNode
        self.full_path = ""

def format_size(size_in_bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.1f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.1f} PB"

class FloatingWindow(tk.Frame):
    def __init__(self, parent, title, width, height, x=100, y=100, on_close_callback=None):
        # High-contrast border using 1px pad
        super().__init__(parent, bg=SECONDARY_BG, bd=1)
        self.parent = parent
        self.width = width
        self.height = height
        self.on_close_callback = on_close_callback
        
        # Absolute place positioning
        self.place(x=x, y=y, width=width, height=height)
        
        # 1. Custom Title Bar
        self.title_bar = tk.Frame(self, bg=HEADER_BG, height=32)
        self.title_bar.pack(fill="x")
        self.title_bar.pack_propagate(False)
        
        # Title Drag Bindings
        self.title_bar.bind("<Button-1>", self.on_drag_start)
        self.title_bar.bind("<B1-Motion>", self.on_drag_motion)
        
        # Window Title Label
        self.title_label = tk.Label(
            self.title_bar, 
            text=title, 
            font=("Segoe UI", 9, "bold"), 
            fg=TEXT_COLOR, 
            bg=HEADER_BG
        )
        self.title_label.pack(side="left", padx=12)
        self.title_label.bind("<Button-1>", self.on_drag_start)
        self.title_label.bind("<B1-Motion>", self.on_drag_motion)
        
        # Sleek Close Window Button (X)
        self.close_btn = tk.Button(
            self.title_bar, 
            text="✕", 
            command=self.close,
            bg=HEADER_BG,
            fg=TEXT_COLOR,
            activebackground=DANGER_COLOR,
            activeforeground=TEXT_COLOR,
            relief="flat",
            bd=0,
            font=("Segoe UI", 8, "bold"),
            padx=12
        )
        self.close_btn.pack(side="right", fill="y")
        self.close_btn.bind("<Enter>", lambda e: self.close_btn.config(bg=DANGER_COLOR))
        self.close_btn.bind("<Leave>", lambda e: self.close_btn.config(bg=HEADER_BG))

        # 2. Window Viewport Container
        self.viewport = tk.Frame(self, bg=BG_COLOR)
        self.viewport.pack(fill="both", expand=True)
        
        # Click focus management
        self.bind("<Button-1>", lambda e: self.lift())
        self.viewport.bind("<Button-1>", lambda e: self.lift())

    def on_drag_start(self, event):
        self._drag_data = {
            "x_root": event.x_root, 
            "y_root": event.y_root, 
            "win_x": self.winfo_x(), 
            "win_y": self.winfo_y()
        }
        self.lift()

    def on_drag_motion(self, event):
        dx = event.x_root - self._drag_data["x_root"]
        dy = event.y_root - self._drag_data["y_root"]
        new_x = self._drag_data["win_x"] + dx
        new_y = self._drag_data["win_y"] + dy
        
        # Enforce boundary checking so window title bar stays on canvas
        max_x = self.parent.winfo_width() - 50
        max_y = self.parent.winfo_height() - 30
        new_x = max(-self.width + 50, min(new_x, max_x))
        new_y = max(0, min(new_y, max_y))
        
        self.place(x=new_x, y=new_y, width=self.width, height=self.height)

    def close(self):
        if self.on_close_callback:
            self.on_close_callback()
        self.destroy()

class TraceRustApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TraceRust Asset Explorer")
        
        # Maximize screen on start for clean slate
        try:
            self.root.state("zoomed")
        except Exception:
            self.root.geometry("1200x850")
            
        self.root.configure(bg=BG_COLOR)

        # Config state schema
        self.config_data = {
            "scan_targets": [],
            "ignore_exact_folders": [],
            "ignore_folder_names": [".git", "node_modules", "target", "build"],
            "container_paths": []
        }
        self.load_config()

        # Scanner state
        self.scanning = False
        self.scan_queue = queue.Queue()
        self.scan_process = None

        # Floating windows registry
        self.open_windows = {}

        # Main background workspace canvas
        self.canvas = tk.Frame(self.root, bg=BG_COLOR)
        self.canvas.pack(fill="both", expand=True)

        # Minimal Watermark logo in center
        self.watermark_lbl = tk.Label(
            self.canvas, 
            text="TRACERUST", 
            font=("Segoe UI", 32, "bold"), 
            fg="#3b4252", 
            bg=BG_COLOR
        )
        self.watermark_lbl.place(relx=0.5, rely=0.5, anchor="center")

        self.setup_styles()
        self.build_navigation()

    def show_toast(self, title, message, status_type="info"):
        if hasattr(self, "active_toast") and self.active_toast and self.active_toast.winfo_exists():
            self.active_toast.destroy()
        self.active_toast = ToastNotification(self.canvas, title, message, status_type)

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('default')
        
        # Global ttk styles for treeviews and progress bars
        self.style.configure(
            "Trace.Treeview",
            background=CARD_BG,
            fieldbackground=CARD_BG,
            foreground=TEXT_COLOR,
            rowheight=24,
            borderwidth=0
        )
        self.style.map(
            "Trace.Treeview",
            background=[('selected', SELECT_BG)],
            foreground=[('selected', TEXT_COLOR)]
        )
        self.style.configure(
            "Trace.Treeview.Heading",
            background=SECONDARY_BG,
            foreground=TEXT_COLOR,
            font=("Segoe UI", 9, "bold"),
            borderwidth=0
        )
        self.style.configure(
            "Horizontal.TProgressbar",
            troughcolor=BG_COLOR,
            background=ACCENT_COLOR,
            thickness=10,
            borderwidth=0
        )
        self.style.configure(
            "Vertical.TScrollbar",
            troughcolor=BG_COLOR,
            background=SECONDARY_BG,
            arrowcolor=TEXT_COLOR,
            borderwidth=0
        )

    def build_navigation(self):
        # Sleek, minimal Burger Menu Button (☰) pinned at top-left
        self.burger_btn = tk.Button(
            self.canvas, 
            text=" ☰ ", 
            command=self.show_burger_menu,
            bg=CARD_BG,
            fg=TEXT_COLOR,
            activebackground=SELECT_BG,
            activeforeground=ACCENT_COLOR,
            relief="flat",
            font=("Segoe UI", 12, "bold"),
            bd=0,
            padx=10,
            pady=5
        )
        self.burger_btn.place(x=15, y=15)
        self.bind_hover(self.burger_btn, SELECT_BG, CARD_BG)

        # Dropdown popup menu
        self.burger_menu = tk.Menu(
            self.root, 
            tearoff=0, 
            bg=CARD_BG, 
            fg=TEXT_COLOR, 
            activebackground=SELECT_BG, 
            activeforeground=ACCENT_COLOR, 
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            bd=1
        )
        self.burger_menu.add_command(label="🔍 Radix Scanner View", command=self.open_scanner_window)
        self.burger_menu.add_separator()
        self.burger_menu.add_command(label="📦 TraceMover Deck", command=self.open_tracemover_window)

    def show_burger_menu(self):
        # Post directly beneath the burger button
        bx = self.burger_btn.winfo_rootx()
        by = self.burger_btn.winfo_rooty() + self.burger_btn.winfo_height()
        self.burger_menu.post(bx, by)

    def bind_hover(self, btn, hover_bg, normal_bg):
        btn.bind("<Enter>", lambda e: btn.config(bg=hover_bg) if btn["state"] == "normal" else None)
        btn.bind("<Leave>", lambda e: btn.config(bg=normal_bg) if btn["state"] == "normal" else None)

    # Config handlers
    def get_config_filepath(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        scanner_dir = os.path.join(script_dir, "Radix_Scanner")
        if os.path.exists(scanner_dir):
            return os.path.join(scanner_dir, "config.json")
        return os.path.join(script_dir, "config.json")

    def load_config(self):
        config_path = self.get_config_filepath()
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Auto migrations
                if "folders_to_scan" in data and "scan_targets" not in data:
                    data["scan_targets"] = data.pop("folders_to_scan")
                if "folders_to_ignore" in data and "ignore_exact_folders" not in data:
                    data["ignore_exact_folders"] = data.pop("folders_to_ignore")
                
                for key in ["scan_targets", "ignore_exact_folders", "ignore_folder_names", "container_paths"]:
                    if key in data:
                        self.config_data[key] = data[key]
                self.cleanup_missing_container_paths()
            except Exception as e:
                print(f"Error loading config: {e}")

    def cleanup_missing_container_paths(self):
        existing = []
        for cp in self.config_data["container_paths"]:
            if os.path.exists(cp):
                existing.append(cp)
        if len(existing) != len(self.config_data["container_paths"]):
            self.config_data["container_paths"] = existing
            self.save_config()

    def save_config(self):
        config_path = self.get_config_filepath()
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=4)
                
            # Automatically refresh windows if they are open
            if "mover" in self.open_windows:
                self.mover_view_class.populate_mover_source_tree()
        except Exception as e:
            messagebox.showerror("Save Config Failed", f"Failed to save settings: {e}")

    # ==========================================
    # WINDOW NODE 1: RADIX SCANNER FLOATING WINDOW
    # ==========================================
    def open_scanner_window(self):
        if "scanner" in self.open_windows:
            self.open_windows["scanner"].lift()
            return
            
        win = FloatingWindow(
            self.canvas, 
            "🔍 Radix Engine Scanner Config & Explorer", 
            780, 680, 
            x=60, y=80,
            on_close_callback=lambda: self.open_windows.pop("scanner", None)
        )
        self.open_windows["scanner"] = win
        self.build_scanner_layout(win.viewport)

    def build_scanner_layout(self, parent):
        parent.rowconfigure(2, weight=1)
        parent.columnconfigure(0, weight=1)

        # 1. Config Forms Frame (Split into two columns)
        forms_frame = tk.Frame(parent, bg=BG_COLOR, padx=15, pady=15)
        forms_frame.grid(row=0, column=0, sticky="ew")
        forms_frame.columnconfigure(0, weight=1)
        forms_frame.columnconfigure(1, weight=1)

        # Targets Card (Left Col)
        targets_card = tk.LabelFrame(
            forms_frame, 
            text=" Scan Target Paths ", 
            font=("Segoe UI", 9, "bold"),
            fg=TEXT_COLOR, bg=CARD_BG, padx=10, pady=8, bd=1, relief="flat"
        )
        targets_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        targets_card.columnconfigure(0, weight=1)

        self.targets_list = tk.Listbox(
            targets_card, bg=BG_COLOR, fg=TEXT_COLOR, selectbackground=SELECT_BG,
            font=("Segoe UI", 9), bd=0, height=4, highlightthickness=0
        )
        self.targets_list.grid(row=0, column=0, columnspan=2, sticky="ew")
        for st in self.config_data["scan_targets"]:
            self.targets_list.insert(tk.END, st)

        add_tgt = tk.Button(
            targets_card, text="Add Folder", command=self.add_scan_target,
            bg=SECONDARY_BG, fg=TEXT_COLOR, font=("Segoe UI", 8, "bold"), relief="flat", padx=8
        )
        add_tgt.grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.bind_hover(add_tgt, HIGHLIGHT, SECONDARY_BG)

        rem_tgt = tk.Button(
            targets_card, text="Remove Selected", command=self.remove_scan_target,
            bg=SECONDARY_BG, fg=TEXT_COLOR, font=("Segoe UI", 8), relief="flat", padx=8
        )
        rem_tgt.grid(row=1, column=1, sticky="e", pady=(8, 0))
        self.bind_hover(rem_tgt, DANGER_COLOR, SECONDARY_BG)

        # Ignores Card (Right Col)
        ignores_card = tk.LabelFrame(
            forms_frame, 
            text=" Bypass & Ignore Rules ", 
            font=("Segoe UI", 9, "bold"),
            fg=TEXT_COLOR, bg=CARD_BG, padx=10, pady=8, bd=1, relief="flat"
        )
        ignores_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        ignores_card.columnconfigure(0, weight=1)

        self.ignores_list = tk.Listbox(
            ignores_card, bg=BG_COLOR, fg=TEXT_COLOR, selectbackground=SELECT_BG,
            font=("Segoe UI", 9), bd=0, height=2, highlightthickness=0
        )
        self.ignores_list.grid(row=0, column=0, columnspan=2, sticky="ew")
        for ifl in self.config_data["ignore_exact_folders"]:
            self.ignores_list.insert(tk.END, ifl)

        add_ign = tk.Button(
            ignores_card, text="Add Folder Bypass", command=self.add_ignore_folder,
            bg=SECONDARY_BG, fg=TEXT_COLOR, font=("Segoe UI", 8, "bold"), relief="flat", padx=8
        )
        add_ign.grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.bind_hover(add_ign, HIGHLIGHT, SECONDARY_BG)

        rem_ign = tk.Button(
            ignores_card, text="Remove Selected", command=self.remove_ignore_folder,
            bg=SECONDARY_BG, fg=TEXT_COLOR, font=("Segoe UI", 8), relief="flat", padx=8
        )
        rem_ign.grid(row=1, column=1, sticky="e", pady=(8, 0))
        self.bind_hover(rem_ign, DANGER_COLOR, SECONDARY_BG)

        # Ignore Names Input row
        lbl_names = tk.Label(ignores_card, text="Ignore Names:", font=("Segoe UI", 8, "bold"), fg=TEXT_MUTED, bg=CARD_BG)
        lbl_names.grid(row=2, column=0, sticky="w", pady=(8, 0))
        
        self.ign_names_entry = tk.Entry(ignores_card, bg=BG_COLOR, fg=TEXT_COLOR, insertbackground=TEXT_COLOR, bd=0)
        self.ign_names_entry.grid(row=2, column=1, sticky="ew", pady=(8, 0), ipady=1)
        self.ign_names_entry.insert(0, ", ".join(self.config_data["ignore_folder_names"]))

        # 2. Scanner run controllers & progress
        run_frame = tk.Frame(parent, bg=BG_COLOR, padx=15)
        run_frame.grid(row=1, column=0, sticky="ew")
        run_frame.columnconfigure(0, weight=1)

        self.scanner_status_lbl = tk.Label(run_frame, text="Status: Ready", font=("Segoe UI", 9, "bold"), fg=TEXT_COLOR, bg=BG_COLOR)
        self.scanner_status_lbl.grid(row=0, column=0, sticky="w", pady=(0, 4))

        self.scanner_prog_bar = ttk.Progressbar(run_frame, orient="horizontal", mode="indeterminate", style="Horizontal.TProgressbar")
        self.scanner_prog_bar.grid(row=1, column=0, sticky="ew")
        self.scanner_prog_bar.grid_remove()

        self.btn_scanner_execute = tk.Button(
            run_frame, text="RUN HIGH-SPEED SCANNERS", command=self.run_radix_walk_engine,
            bg=ACCENT_COLOR, fg=BG_COLOR, font=("Segoe UI", 11, "bold"), relief="flat", pady=6
        )
        self.btn_scanner_execute.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.bind_hover(self.btn_scanner_execute, HIGHLIGHT, ACCENT_COLOR)

        # 3. Viewport Index Explorer Treeview
        tree_frame = tk.Frame(parent, bg=BG_COLOR, padx=15, pady=15)
        tree_frame.grid(row=2, column=0, sticky="nsew")
        tree_frame.rowconfigure(1, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        tk.Label(tree_frame, text="Lazy-Loaded Index Viewport Explorer", font=("Segoe UI", 9, "bold"), fg=TEXT_MUTED, bg=BG_COLOR).grid(row=0, column=0, sticky="w", pady=(0, 4))

        self.explorer_tree = ttk.Treeview(tree_frame, columns=("Size"), style="Trace.Treeview")
        self.explorer_tree.heading("#0", text="Folder Tree Structure", anchor="w")
        self.explorer_tree.heading("Size", text="Calculated Disk Size", anchor="e")
        self.explorer_tree.column("#0", width=520, stretch=True)
        self.explorer_tree.column("Size", width=120, stretch=False, anchor="e")
        self.explorer_tree.grid(row=1, column=0, sticky="nsew")

        scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self.explorer_tree.yview)
        scroll_y.grid(row=1, column=1, sticky="ns")
        self.explorer_tree.config(yscrollcommand=scroll_y.set)

        self.explorer_tree.bind("<<TreeviewOpen>>", self.on_scanner_tree_expand)
        self.explorer_tree.tag_configure("container", foreground=SUCCESS_COLOR)

        # Bind right-click menu context for containers marking
        self.explorer_tree.bind("<Button-3>", self.show_scanner_viewport_menu)
        self.scanner_vp_menu = tk.Menu(
            parent, tearoff=0, bg=CARD_BG, fg=TEXT_COLOR, 
            activebackground=SELECT_BG, activeforeground=ACCENT_COLOR, relief="flat", bd=1
        )

        self.explorer_registry = {} # item_id -> TreeNode
        self.explorer_roots = {}

        self.reload_scanner_viewport_index()

    # Scanner configuration controls
    def add_scan_target(self):
        f = filedialog.askdirectory(title="Select Scan Root Target")
        if f:
            f = os.path.normpath(f)
            if f not in self.config_data["scan_targets"]:
                self.config_data["scan_targets"].append(f)
                self.targets_list.insert(tk.END, f)
                self.save_config()

    def remove_scan_target(self):
        selected = self.targets_list.curselection()
        for idx in reversed(selected):
            val = self.targets_list.get(idx)
            if val in self.config_data["scan_targets"]:
                self.config_data["scan_targets"].remove(val)
            self.targets_list.delete(idx)
        self.save_config()

    def add_ignore_folder(self):
        f = filedialog.askdirectory(title="Select Folder to Ignore")
        if f:
            f = os.path.normpath(f)
            if f not in self.config_data["ignore_exact_folders"]:
                self.config_data["ignore_exact_folders"].append(f)
                self.ignores_list.insert(tk.END, f)
                self.save_config()

    def remove_ignore_folder(self):
        selected = self.ignores_list.curselection()
        for idx in reversed(selected):
            val = self.ignores_list.get(idx)
            if val in self.config_data["ignore_exact_folders"]:
                self.config_data["ignore_exact_folders"].remove(val)
            self.ignores_list.delete(idx)
        self.save_config()

    def save_scanner_ignore_names(self):
        names_raw = self.ign_names_entry.get()
        self.config_data["ignore_folder_names"] = [n.strip() for n in names_raw.split(",") if n.strip()]
        self.save_config()

    def find_rust_engine_binary(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        paths = [
            os.path.join(script_dir, "radix_engine.exe"),
            os.path.join(script_dir, "Radix_Scanner", "radix_engine.exe"),
            os.path.join(script_dir, "radix_engine", "target", "release", "radix_engine.exe")
        ]
        for p in paths:
            if os.path.exists(p):
                return p
        return None

    def get_index_path(self):
        engine_dir = os.path.dirname(self.find_rust_engine_binary() or "")
        if engine_dir and os.path.exists(os.path.join(engine_dir, "hard_drive_index.txt")):
            return os.path.join(engine_dir, "hard_drive_index.txt")
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "hard_drive_index.txt")

    def run_radix_walk_engine(self):
        if self.scanning:
            return
        if not self.config_data["scan_targets"]:
            messagebox.showwarning("Execution Aborted", "Scan targets list is empty. Add at least one folder path.")
            return

        binary = self.find_rust_engine_binary()
        if not binary:
            messagebox.showerror("Execution Error", "Could not locate radix_engine.exe scanner binary.")
            return

        self.save_scanner_ignore_names()

        # UI state lock
        self.scanning = True
        self.btn_scanner_execute.config(state="disabled", text="SCANNING FILES...", bg=SECONDARY_BG)
        self.scanner_prog_bar.grid()
        self.scanner_prog_bar.start(10)
        self.scanner_status_lbl.config(text="Status: Launching Rust parallel search processes...")

        self.scan_queue = queue.Queue()
        threading.Thread(target=self.threaded_radix_subprocess, args=(binary,), daemon=True).start()
        self.root.after(100, self.poll_radix_progress_updates)

    def threaded_radix_subprocess(self, binary_path):
        try:
            self.scan_process = subprocess.Popen(
                [binary_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=os.path.dirname(binary_path),
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            while True:
                line = self.scan_process.stdout.readline()
                if not line:
                    break
                self.scan_queue.put(("stdout", line.strip()))
            err = self.scan_process.stderr.read()
            if err:
                self.scan_queue.put(("stderr", err.strip()))
            self.scan_process.wait()
            self.scan_queue.put(("done", self.scan_process.returncode))
        except Exception as e:
            self.scan_queue.put(("error", str(e)))

    def poll_radix_progress_updates(self):
        if not self.scanning:
            return
        try:
            while True:
                msg, val = self.scan_queue.get_nowait()
                if msg == "stdout":
                    if val.startswith("Status:"):
                        self.scanner_status_lbl.config(text=val)
                elif msg == "error":
                    messagebox.showerror("Execution Failed", f"Subprocess crash: {val}")
                    self.stop_scanner_controls(False)
                    return
                elif msg == "done":
                    if val == 0:
                        self.scanner_status_lbl.config(text="Status: Indexing finished. Loading explorer...")
                        self.cleanup_missing_container_paths()
                        self.reload_scanner_viewport_index()
                        self.stop_scanner_controls(True)
                    else:
                        self.scanner_status_lbl.config(text=f"Status: Scanner failed with return code {val}")
                        self.stop_scanner_controls(False)
                    return
        except queue.Empty:
            pass
        self.root.after(100, self.poll_radix_progress_updates)

    def stop_scanner_controls(self, success):
        self.scanning = False
        self.scanner_prog_bar.stop()
        self.scanner_prog_bar.grid_remove()
        self.btn_scanner_execute.config(state="normal", text="RUN HIGH-SPEED SCANNERS", bg=ACCENT_COLOR)
        if success:
            self.show_toast("Scan Complete", "Parallel indexing successfully completed! Scan Explorer is reloaded.", "success")

    def reload_scanner_viewport_index(self):
        path = self.get_index_path()
        if os.path.exists(path):
            threading.Thread(target=self.threaded_parse_explorer_index, args=(path,), daemon=True).start()

    def threaded_parse_explorer_index(self, path):
        try:
            roots = self.parse_index_file(path)
            self.root.after(0, lambda: self.populate_scanner_explorer_tree(roots))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Parser Error", f"Failed to parse text index: {e}"))

    def parse_index_file(self, filepath):
        root_nodes = {}
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(" | ", 1)
                if len(parts) == 2:
                    size_str, path = parts
                    try:
                        size = int(size_str)
                    except ValueError:
                        size = 0
                else:
                    size = 0
                    path = line

                path = os.path.normpath(path)
                drive, tail = os.path.splitdrive(path)
                if not drive:
                    drive = "Root"
                if drive not in root_nodes:
                    root_nodes[drive] = TreeNode(drive, is_dir=True)
                    root_nodes[drive].full_path = drive + os.sep

                current = root_nodes[drive]
                components = [c for c in tail.split(os.sep) if c]
                for i, comp in enumerate(components):
                    is_last = (i == len(components) - 1)
                    is_directory = not is_last
                    if comp not in current.children:
                        node = TreeNode(comp, is_dir=is_directory)
                        node.full_path = os.path.join(current.full_path, comp)
                        current.children[comp] = node
                    current = current.children[comp]
                current.is_dir = False
                current.size = size

        for rn in root_nodes.values():
            self.calculate_sizes_recursive(rn)
        return root_nodes

    def calculate_sizes_recursive(self, node):
        if not node.is_dir:
            return node.size
        total = 0
        for c in node.children.values():
            total += self.calculate_sizes_recursive(c)
        node.size = total
        return total

    def populate_scanner_explorer_tree(self, roots):
        self.explorer_roots = roots
        self.explorer_tree.delete(*self.explorer_tree.get_children())
        self.explorer_registry.clear()

        for name, node in sorted(self.explorer_roots.items()):
            is_container = node.full_path in self.config_data["container_paths"]
            display_text = f"{name} [BOX]" if is_container else name
            tag = "container" if is_container else ""
            
            item_id = self.explorer_tree.insert(
                "", "end", text=display_text, values=(format_size(node.size),), tags=(tag,)
            )
            self.explorer_registry[item_id] = node
            if node.children:
                self.explorer_tree.insert(item_id, "end", text="Loading...", tags=("dummy",))

    def on_scanner_tree_expand(self, event):
        item_id = self.explorer_tree.focus()
        if not item_id or item_id not in self.explorer_registry:
            return
        node = self.explorer_registry[item_id]
        children = self.explorer_tree.get_children(item_id)
        
        if children and "dummy" in self.explorer_tree.item(children[0], "tags"):
            self.explorer_tree.delete(children[0])
            sorted_kids = sorted(node.children.values(), key=lambda x: (not x.is_dir, x.name.lower()))
            for kid in sorted_kids:
                is_container = kid.full_path in self.config_data["container_paths"]
                display_text = f"{kid.name} [BOX]" if is_container else kid.name
                tag = "container" if is_container else ""
                
                kid_id = self.explorer_tree.insert(
                    item_id, "end", text=display_text, values=(format_size(kid.size),), tags=(tag,)
                )
                self.explorer_registry[kid_id] = kid
                if kid.is_dir and kid.children:
                    self.explorer_tree.insert(kid_id, "end", text="Loading...", tags=("dummy",))

    def show_scanner_viewport_menu(self, event):
        item_id = self.explorer_tree.identify_row(event.y)
        if not item_id:
            return
        
        current_selection = self.explorer_tree.selection()
        if item_id not in current_selection:
            self.explorer_tree.focus(item_id)
            self.explorer_tree.selection_set(item_id)
            current_selection = (item_id,)
            
        node = self.explorer_registry.get(item_id)
        if node:
            self.scanner_vp_menu.delete(0, "end")
            self.scanner_vp_menu.add_command(
                label="📂 Open in Windows Explorer", 
                command=lambda: self.open_in_explorer(node.full_path)
            )
            if len(current_selection) == 1:
                self.scanner_vp_menu.add_command(
                    label="✏️ Rename File/Folder", 
                    command=lambda: self.trigger_scanner_in_place_rename(item_id)
                )
            self.scanner_vp_menu.add_separator()
            is_container = node.full_path in self.config_data["container_paths"]
            if is_container:
                self.scanner_vp_menu.add_command(
                    label="🔓 Remove Container Asset Tag", 
                    command=self.unmark_explorer_containers_bulk
                )
            else:
                self.scanner_vp_menu.add_command(
                    label="📁 Mark as Container Asset", 
                    command=self.mark_explorer_containers_bulk
                )
            self.scanner_vp_menu.post(event.x_root, event.y_root)

    def open_in_explorer(self, path):
        path = os.path.normpath(path)
        if os.path.exists(path):
            if os.path.isdir(path):
                os.startfile(path)
            else:
                subprocess.Popen(f'explorer /select,"{path}"')

    def trigger_scanner_in_place_rename(self, item_id):
        bbox = self.explorer_tree.bbox(item_id, column="#0")
        if not bbox:
            return
        x, y, w, h = bbox
        
        node = self.explorer_registry.get(item_id)
        if not node:
            return
            
        display_text = self.explorer_tree.item(item_id, "text")
        if display_text.endswith(" [BOX]"):
            cur_name = display_text[:-6]
        else:
            cur_name = display_text
            
        self.scanner_editing_entry = tk.Entry(self.explorer_tree, font=("Segoe UI", 9), bd=0, highlightthickness=1, highlightcolor=HIGHLIGHT)
        self.scanner_editing_entry.insert(0, cur_name)
        self.scanner_editing_entry.select_range(0, tk.END)
        self.scanner_editing_entry.place(x=x, y=y, width=max(w, 200), height=h)
        self.scanner_editing_entry.focus_set()
        
        self.scanner_editing_item = item_id
        self.scanner_editing_entry.bind("<Return>", self.save_scanner_rename)
        self.scanner_editing_entry.bind("<FocusOut>", self.save_scanner_rename)
        self.scanner_editing_entry.bind("<Escape>", self.cancel_scanner_rename)

    def save_scanner_rename(self, event):
        if not hasattr(self, "scanner_editing_entry") or not self.scanner_editing_entry:
            return
        new_name = self.scanner_editing_entry.get().strip()
        item_id = self.scanner_editing_item
        node = self.explorer_registry.get(item_id)
        
        if not node:
            self.cancel_scanner_rename(None)
            return
            
        old_path = node.full_path
        old_name = node.name
        parent_dir = os.path.dirname(old_path)
        new_path = os.path.join(parent_dir, new_name)
        
        # Check invalid chars
        forbidden = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
        if not new_name or any(f in new_name for f in forbidden):
            messagebox.showwarning("Rename Error", "Invalid name. Characters not allowed: \\ / : * ? \" < > |")
            self.cancel_scanner_rename(None)
            return
            
        if old_path.lower() != new_path.lower() and os.path.exists(new_path):
            messagebox.showerror("Rename Error", f"A file or folder already exists at:\n{new_path}")
            self.cancel_scanner_rename(None)
            return

        try:
            os.rename(old_path, new_path)
            self.write_rename_log(old_path, new_path)
            self.update_index_file_for_rename(old_path, new_path)
            self.update_container_paths_for_rename(old_path, new_path)
            
            # Update Treeview text in-place (no collapse!)
            is_container = new_path in self.config_data["container_paths"]
            new_display = f"{new_name} [BOX]" if is_container else new_name
            self.explorer_tree.item(item_id, text=new_display)
            
            # Update node memory paths recursively
            node.name = new_name
            old_prefix = old_path
            new_prefix = new_path
            
            def update_node_paths_recursive(n):
                if n.full_path == old_prefix:
                    n.full_path = new_prefix
                elif n.full_path.startswith(old_prefix + os.sep):
                    relative = n.full_path[len(old_prefix):].lstrip(os.sep)
                    n.full_path = os.path.join(new_prefix, relative)
                for child in n.children.values():
                    update_node_paths_recursive(child)
                    
            update_node_paths_recursive(node)
            
            # Update keys in parent node dictionary
            parent_id = self.explorer_tree.parent(item_id)
            if parent_id == "":
                if old_name in self.explorer_roots:
                    self.explorer_roots[new_name] = self.explorer_roots.pop(old_name)
            else:
                parent_node = self.explorer_registry.get(parent_id)
                if parent_node and old_name in parent_node.children:
                    parent_node.children[new_name] = parent_node.children.pop(old_name)

            self.show_toast("Rename Successful", f"Renamed item to '{new_name}' successfully.", "success")
            
        except Exception as e:
            messagebox.showerror("Rename Failed", f"Could not rename file/folder:\n{e}")
            
        self.destroy_scanner_editing_box()

    def cancel_scanner_rename(self, event):
        self.destroy_scanner_editing_box()

    def destroy_scanner_editing_box(self):
        if hasattr(self, "scanner_editing_entry") and self.scanner_editing_entry:
            self.scanner_editing_entry.destroy()
            self.scanner_editing_entry = None
            self.scanner_editing_item = None

    def write_rename_log(self, old_path, new_path):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracerust_transfer_log.txt")
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"{ts} | RENAME | SUCCESS | {old_path} | {new_path}\n")
        except Exception as e:
            print(f"Log error: {e}")

    def update_container_paths_for_rename(self, old_path, new_path):
        norm_old = os.path.normcase(old_path)
        norm_old_sep = os.path.normcase(old_path + os.sep)
        
        updated = []
        for cp in self.config_data["container_paths"]:
            norm_cp = os.path.normcase(cp)
            if norm_cp == norm_old:
                updated.append(new_path)
            elif norm_cp.startswith(norm_old_sep):
                relative = cp[len(old_path):].lstrip(os.sep)
                updated.append(os.path.join(new_path, relative))
            else:
                updated.append(cp)
        self.config_data["container_paths"] = updated
        self.save_config()

    def update_index_file_for_rename(self, old_path, new_path):
        index_path = self.get_index_path()
        if not os.path.exists(index_path):
            return
        
        norm_old = os.path.normcase(old_path)
        norm_old_sep = os.path.normcase(old_path + os.sep)
        
        new_lines = []
        with open(index_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(" | ", 1)
                if len(parts) == 2:
                    size_str, path = parts
                    norm_path = os.path.normcase(path)
                    if norm_path == norm_old:
                        path = new_path
                    elif norm_path.startswith(norm_old_sep):
                        relative = path[len(old_path):].lstrip(os.sep)
                        path = os.path.join(new_path, relative)
                    new_lines.append(f"{size_str} | {path}")
                else:
                    norm_path = os.path.normcase(line)
                    if norm_path == norm_old:
                        line = new_path
                    elif norm_path.startswith(norm_old_sep):
                        relative = line[len(old_path):].lstrip(os.sep)
                        line = os.path.join(new_path, relative)
                    new_lines.append(line)
                    
        with open(index_path, "w", encoding="utf-8") as f:
            for nl in new_lines:
                f.write(nl + "\n")

    def mark_explorer_containers_bulk(self):
        selected_items = self.explorer_tree.selection()
        count = 0
        for item_id in selected_items:
            node = self.explorer_registry.get(item_id)
            if node:
                p = node.full_path
                if p not in self.config_data["container_paths"]:
                    self.config_data["container_paths"].append(p)
                    self.explorer_tree.item(item_id, text=f"{node.name} [BOX]", tags=("container",))
                    count += 1
        self.save_config()
        if count > 0:
            self.show_toast("Marked Containers", f"Successfully tagged {count} container asset(s).", "success")

    def unmark_explorer_containers_bulk(self):
        selected_items = self.explorer_tree.selection()
        count = 0
        for item_id in selected_items:
            node = self.explorer_registry.get(item_id)
            if node:
                p = node.full_path
                if p in self.config_data["container_paths"]:
                    self.config_data["container_paths"].remove(p)
                    self.explorer_tree.item(item_id, text=node.name, tags=())
                    count += 1
        self.save_config()
        if count > 0:
            self.show_toast("Tags Removed", f"Successfully untagged {count} container asset(s).", "info")

    # ==========================================
    # WINDOW NODE 2: TRACEMOVER 3-PANEL WORKSPACE
    # ==========================================
    def open_tracemover_window(self):
        if "mover" in self.open_windows:
            self.open_windows["mover"].lift()
            return
            
        win = FloatingWindow(
            self.canvas, 
            "📦 TraceMover Deck Staging Panel", 
            980, 720, 
            x=150, y=50,
            on_close_callback=lambda: self.open_windows.pop("mover", None)
        )
        self.open_windows["mover"] = win
        self.mover_view_class = TraceMoverViewport(win.viewport, self)

class TraceMoverViewport:
    def __init__(self, parent, controller):
        self.parent = parent
        self.controller = controller
        
        # Grid layout matching 3-Panel design
        self.parent.rowconfigure(0, weight=3) # trees
        self.parent.rowconfigure(1, weight=2) # queue table below
        self.parent.columnconfigure(0, weight=1)
        self.parent.columnconfigure(1, weight=1)

        self.left_tree_registry = {}
        self.right_tree_registry = {}
        self.drag_data = {"node": None, "item_id": None}
        self.queue_items = []
        
        self.editing_entry = None
        self.editing_item = None

        self.build_mover_interface()
        self.populate_mover_source_tree()
        self.rebuild_blueprint_tree()

    def build_mover_interface(self):
        # ----------------------------------------
        # PANEL 1 (Left Panel): Source Tree Asset Container
        # ----------------------------------------
        p1 = tk.LabelFrame(
            self.parent, text=" Source Tree Asset Container ", font=("Segoe UI", 9, "bold"),
            fg=TEXT_COLOR, bg=CARD_BG, padx=10, pady=10, bd=1, relief="flat"
        )
        p1.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=(12, 6))
        p1.rowconfigure(0, weight=1)
        p1.columnconfigure(0, weight=1)

        self.source_tree = ttk.Treeview(p1, style="Trace.Treeview")
        self.source_tree.heading("#0", text="Folders & Files Structure", anchor="w")
        self.source_tree.grid(row=0, column=0, sticky="nsew")

        s_scroll = ttk.Scrollbar(p1, orient="vertical", command=self.source_tree.yview)
        s_scroll.grid(row=0, column=1, sticky="ns")
        self.source_tree.config(yscrollcommand=s_scroll.set)

        self.source_tree.tag_configure("container", foreground=SUCCESS_COLOR)

        # Drag & lazy load bindings
        self.source_tree.bind("<<TreeviewOpen>>", self.on_source_tree_expand)
        self.source_tree.bind("<ButtonPress-1>", self.on_mover_drag_start)
        self.source_tree.bind("<B1-Motion>", self.on_mover_drag_motion)
        self.source_tree.bind("<ButtonRelease-1>", self.on_mover_drag_release)

        # Right-click context menu on source tree
        self.source_tree.bind("<Button-3>", self.show_source_tree_menu)
        self.source_ctx_menu = tk.Menu(
            self.parent, tearoff=0, bg=CARD_BG, fg=TEXT_COLOR, 
            activebackground=SELECT_BG, activeforeground=ACCENT_COLOR, relief="flat", bd=1
        )

        # ----------------------------------------
        # PANEL 2 (Right Panel): Target Blueprint Viewport
        # ----------------------------------------
        p2 = tk.LabelFrame(
            self.parent, text=" Target Blueprint Viewport ", font=("Segoe UI", 9, "bold"),
            fg=TEXT_COLOR, bg=CARD_BG, padx=10, pady=10, bd=1, relief="flat"
        )
        p2.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=(12, 6))
        p2.rowconfigure(1, weight=1)
        p2.columnconfigure(0, weight=1)

        # Target Drive Selector Combobox
        combo_frame = tk.Frame(p2, bg=CARD_BG)
        combo_frame.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        
        tk.Label(combo_frame, text="Select Drive:", font=("Segoe UI", 9, "bold"), fg=TEXT_MUTED, bg=CARD_BG).pack(side="left", padx=(0, 6))
        
        self.drives = self.get_win_drives()
        self.drive_var = tk.StringVar()
        
        self.drive_combo = ttk.Combobox(combo_frame, textvariable=self.drive_var, values=self.drives, state="readonly", width=10)
        self.drive_combo.pack(side="left")
        if self.drives:
            self.drive_combo.current(0)
        self.drive_combo.bind("<<ComboboxSelected>>", self.on_drive_selection_changed)

        self.target_tree = ttk.Treeview(p2, style="Trace.Treeview")
        self.target_tree.heading("#0", text="Virtual Blueprint Directory Tree", anchor="w")
        self.target_tree.grid(row=1, column=0, sticky="nsew")

        t_scroll = ttk.Scrollbar(p2, orient="vertical", command=self.target_tree.yview)
        t_scroll.grid(row=1, column=1, sticky="ns")
        self.target_tree.config(yscrollcommand=t_scroll.set)

        # Blueprint context menu
        self.target_tree.bind("<Button-3>", self.show_blueprint_menu)
        self.blueprint_ctx_menu = tk.Menu(
            self.parent, tearoff=0, bg=CARD_BG, fg=TEXT_COLOR, 
            activebackground=SELECT_BG, activeforeground=ACCENT_COLOR, relief="flat", bd=1
        )
        self.blueprint_ctx_menu.add_command(label="📁 Create Virtual Folder", command=self.create_virtual_blueprint_node)
        self.blueprint_ctx_menu.add_command(label="✏️ Rename", command=self.rename_virtual_blueprint_node)
        self.blueprint_ctx_menu.add_command(label="❌ Delete Node", command=self.delete_virtual_blueprint_node)

        # ----------------------------------------
        # PANEL 3 (Bottom Panel): Stage Migration Queue Deck
        # ----------------------------------------
        p3 = tk.LabelFrame(
            self.parent, text=" Stage Migration Queue Deck ", font=("Segoe UI", 9, "bold"),
            fg=TEXT_COLOR, bg=CARD_BG, padx=10, pady=10, bd=1, relief="flat"
        )
        p3.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=12, pady=(6, 12))
        p3.rowconfigure(0, weight=1)
        p3.columnconfigure(0, weight=1)

        # Transaction queue table
        self.queue_tree = ttk.Treeview(p3, columns=("Source", "Target", "Size", "Status"), style="Trace.Treeview")
        self.queue_tree.heading("#0", text="ID", anchor="w")
        self.queue_tree.heading("Source", text="Source Path", anchor="w")
        self.queue_tree.heading("Target", text="Virtual Destination Path", anchor="w")
        self.queue_tree.heading("Size", text="Size", anchor="e")
        self.queue_tree.heading("Status", text="Status", anchor="center")

        self.queue_tree.column("#0", width=40, stretch=False)
        self.queue_tree.column("Source", width=340, stretch=True)
        self.queue_tree.column("Target", width=340, stretch=True)
        self.queue_tree.column("Size", width=90, stretch=False, anchor="e")
        self.queue_tree.column("Status", width=180, stretch=False, anchor="center")
        self.queue_tree.grid(row=0, column=0, sticky="nsew")

        q_scroll = ttk.Scrollbar(p3, orient="vertical", command=self.queue_tree.yview)
        q_scroll.grid(row=0, column=1, sticky="ns")
        self.queue_tree.config(yscrollcommand=q_scroll.set)

        self.queue_tree.tag_configure("movable", foreground=SUCCESS_COLOR)
        self.queue_tree.tag_configure("blocked", foreground=DANGER_COLOR)

        # Exec controls frame
        ctrl_frame = tk.Frame(p3, bg=CARD_BG)
        ctrl_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        self.queue_status_lbl = tk.Label(
            ctrl_frame, text="Staged Transactions: 0 | Execution state: Idle", 
            font=("Segoe UI", 9, "bold"), fg=TEXT_MUTED, bg=CARD_BG
        )
        self.queue_status_lbl.pack(side="left")

        self.btn_clear_staged = tk.Button(
            ctrl_frame, text="Clear Queue", command=self.clear_staged_queue,
            bg=SECONDARY_BG, fg=TEXT_COLOR, font=("Segoe UI", 9), relief="flat", padx=12, pady=4
        )
        self.btn_clear_staged.pack(side="right", padx=(10, 0))
        self.controller.bind_hover(self.btn_clear_staged, DANGER_COLOR, SECONDARY_BG)

        self.btn_execute_staging = tk.Button(
            ctrl_frame, text="⚡ EXECUTE CUT & MOVE", command=self.execute_staged_transfers,
            bg=ACCENT_COLOR, fg=BG_COLOR, font=("Segoe UI", 10, "bold"), relief="flat", padx=16, pady=4
        )
        self.btn_execute_staging.pack(side="right")
        self.controller.bind_hover(self.btn_execute_staging, HIGHLIGHT, ACCENT_COLOR)

    def get_win_drives(self):
        drives = []
        for l in string.ascii_uppercase:
            drv = f"{l}:\\"
            if os.path.exists(drv):
                drives.append(drv)
        return drives

    def on_drive_selection_changed(self, event):
        self.rebuild_blueprint_tree()
        self.validate_queue_disk_space()

    def rebuild_blueprint_tree(self):
        self.target_tree.delete(*self.target_tree.get_children())
        self.right_tree_registry.clear()
        
        drv = self.drive_var.get()
        if drv:
            root_id = self.target_tree.insert("", "end", text=f"{drv} (Virtual Root)", open=True)
            self.right_tree_registry[root_id] = drv

    # Source tree populations (solid [BOX] container paths, ignores dotfiles)
    def populate_mover_source_tree(self):
        self.source_tree.delete(*self.source_tree.get_children())
        self.left_tree_registry.clear()
        
        path = self.controller.get_index_path()
        if os.path.exists(path):
            threading.Thread(target=self.threaded_mover_index_parse, args=(path,), daemon=True).start()

    def threaded_mover_index_parse(self, filepath):
        try:
            roots = self.parse_mover_index_pruned(filepath, self.controller.config_data["container_paths"])
            self.parent.after(0, lambda: self.populate_source_tree_view(roots))
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("Parser Failed", f"Mover parser error: {e}"))

    def parse_mover_index_pruned(self, filepath, container_paths):
        norm_containers = [os.path.normcase(cp) for cp in container_paths]
        dir_sizes = {}
        root_nodes = {}

        # Pass 1: Sum directory recursively
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(" | ", 1)
                if len(parts) != 2:
                    continue
                size = int(parts[0])
                path = os.path.normpath(parts[1])
                
                # Exclude hidden files
                if any(p.startswith(".") for p in path.split(os.sep)):
                    continue
                    
                parent = os.path.dirname(path)
                while parent and parent != os.path.dirname(parent):
                    dir_sizes[parent] = dir_sizes.get(parent, 0) + size
                    parent = os.path.dirname(parent)

        # Pass 2: Map trees pruning container paths
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(" | ", 1)
                if len(parts) != 2:
                    continue
                size = int(parts[0])
                path = os.path.normpath(parts[1])
                
                if any(p.startswith(".") for p in path.split(os.sep)):
                    continue
                    
                drive, tail = os.path.splitdrive(path)
                if not drive:
                    drive = "Root"
                    
                # Match scan targets
                matches_target = False
                for st in self.controller.config_data["scan_targets"]:
                    if path.lower().startswith(st.lower()):
                        matches_target = True
                        break
                if not matches_target:
                    continue

                if drive not in root_nodes:
                    root_nodes[drive] = TreeNode(drive, is_dir=True)
                    root_nodes[drive].full_path = drive + os.sep

                current = root_nodes[drive]
                components = [c for c in tail.split(os.sep) if c]
                
                pruned = False
                for i, comp in enumerate(components):
                    is_last = (i == len(components) - 1)
                    is_directory = not is_last
                    
                    check_path = os.path.join(current.full_path, comp)
                    
                    if os.path.normcase(check_path) in norm_containers:
                        if comp not in current.children:
                            node = TreeNode(comp, is_dir=is_directory)
                            node.full_path = check_path
                            node.size = dir_sizes.get(check_path, 0) if is_directory else size
                            current.children[comp] = node
                        pruned = True
                        break
                        
                    if comp not in current.children:
                        node = TreeNode(comp, is_dir=is_directory)
                        node.full_path = check_path
                        current.children[comp] = node
                    current = current.children[comp]

                if not pruned:
                    current.is_dir = False
                    current.size = size

        # Update standard folder size sum
        def sum_sizes(node):
            if not node.is_dir:
                return node.size
            if os.path.normcase(node.full_path) in norm_containers:
                return node.size
            total = sum(sum_sizes(c) for c in node.children.values())
            node.size = total
            return total

        for rn in root_nodes.values():
            sum_sizes(rn)
            
        return root_nodes

    def populate_source_tree_view(self, roots):
        self.left_tree_registry.clear()
        
        for scan_target in sorted(self.controller.config_data["scan_targets"]):
            drive, tail = os.path.splitdrive(scan_target)
            if drive in roots:
                components = [c for c in tail.split(os.sep) if c]
                current = roots[drive]
                found = True
                
                for comp in components:
                    if comp in current.children:
                        current = current.children[comp]
                    else:
                        found = False
                        break
                        
                if found:
                    is_container = current.full_path in self.controller.config_data["container_paths"]
                    display_text = f"{current.name} [BOX]" if is_container else current.name
                    tag = "container" if is_container else ""
                    
                    item_id = self.source_tree.insert(
                        "", "end", text=display_text, values=(format_size(current.size),), tags=(tag,)
                    )
                    self.left_tree_registry[item_id] = current
                    
                    # Do not expand container boxes
                    if current.is_dir and not is_container and current.children:
                        self.source_tree.insert(item_id, "end", text="Loading...", tags=("dummy",))

    def on_source_tree_expand(self, event):
        item_id = self.source_tree.focus()
        if not item_id or item_id not in self.left_tree_registry:
            return
        node = self.left_tree_registry[item_id]
        children = self.source_tree.get_children(item_id)
        
        if children and "dummy" in self.source_tree.item(children[0], "tags"):
            self.source_tree.delete(children[0])
            sorted_kids = sorted(node.children.values(), key=lambda x: (not x.is_dir, x.name.lower()))
            for kid in sorted_kids:
                is_container = kid.full_path in self.controller.config_data["container_paths"]
                display_text = f"{kid.name} [BOX]" if is_container else kid.name
                tag = "container" if is_container else ""
                
                kid_id = self.source_tree.insert(
                    item_id, "end", text=display_text, values=(format_size(kid.size),), tags=(tag,)
                )
                self.left_tree_registry[kid_id] = kid
                
                # Expandable if directory and not container
                if kid.is_dir and not is_container and kid.children:
                    self.source_tree.insert(kid_id, "end", text="Loading...", tags=("dummy",))

    # Drag and Drop Mechanics
    def on_mover_drag_start(self, event):
        item_id = self.source_tree.identify_row(event.y)
        if not item_id:
            return
        node = self.left_tree_registry.get(item_id)
        
        # Staging rules: Only allow dragging folder nodes with container tag
        if node and node.full_path in self.controller.config_data["container_paths"]:
            self.drag_data["node"] = node
            self.drag_data["item_id"] = item_id
            self.source_tree.config(cursor="hand2")

    def on_mover_drag_motion(self, event):
        if not self.drag_data["node"]:
            return
        x, y = event.x_root, event.y_root
        widget = self.source_tree.winfo_containing(x, y)
        if widget == self.target_tree:
            self.target_tree.config(cursor="plus")
        else:
            self.source_tree.config(cursor="no")

    def on_mover_drag_release(self, event):
        self.source_tree.config(cursor="")
        self.target_tree.config(cursor="")
        
        node = self.drag_data["node"]
        if not node:
            return
            
        x, y = event.x_root, event.y_root
        widget = self.source_tree.winfo_containing(x, y)
        if widget == self.target_tree:
            rx = x - self.target_tree.winfo_rootx()
            ry = y - self.target_tree.winfo_rooty()
            dest_item_id = self.target_tree.identify_row(ry)
            
            drive = self.drive_var.get()
            if not dest_item_id:
                root_item = self.target_tree.get_children()[0]
                dest_path = drive
                dest_item_id = root_item
            else:
                dest_path = self.get_virtual_dest_path(dest_item_id, drive)
                
            self.stage_move_transaction(node, dest_path, dest_item_id)

        self.drag_data["node"] = None
        self.drag_data["item_id"] = None

    def get_virtual_dest_path(self, item_id, drive):
        components = []
        current = item_id
        while current:
            text = self.target_tree.item(current, "text")
            if "(Virtual Root)" in text:
                break
            components.append(text)
            current = self.target_tree.parent(current)
        components.reverse()
        return os.path.join(drive, *components)

    def stage_move_transaction(self, node, virtual_dir, dest_item_id):
        final_dest = os.path.join(virtual_dir, node.name)
        for item in self.queue_items:
            if item["src"] == node.full_path and item["dest"] == final_dest:
                return

        idx = len(self.queue_items) + 1
        item_id = self.queue_tree.insert(
            "", "end", text=str(idx), 
            values=(node.full_path, final_dest, format_size(node.size), "Staged")
        )
        self.queue_items.append({
            "id": idx,
            "item_id": item_id,
            "src": node.full_path,
            "dest": final_dest,
            "size": node.size,
            "status": "Staged"
        })
        self.validate_queue_disk_space()

    def validate_queue_disk_space(self):
        target_drive = self.drive_var.get()
        if not target_drive:
            return

        try:
            _, _, free = shutil.disk_usage(target_drive)
        except Exception:
            free = 0

        staged_accumulated = 0
        execution_blocked = False
        
        for item in self.queue_items:
            drv, _ = os.path.splitdrive(item["dest"])
            if drv.upper() == target_drive.upper():
                staged_accumulated += item["size"]
                if staged_accumulated > free:
                    item["status"] = "Blocked"
                    self.queue_tree.item(
                        item["item_id"], 
                        values=(item["src"], item["dest"], format_size(item["size"]), "INSUFFICIENT SPACE"), 
                        tags=("blocked",)
                    )
                    execution_blocked = True
                else:
                    item["status"] = "Staged"
                    self.queue_tree.item(
                        item["item_id"], 
                        values=(item["src"], item["dest"], format_size(item["size"]), "Staged"), 
                        tags=("movable",)
                    )

        self.queue_status_lbl.config(
            text=f"Staged Transactions: {len(self.queue_items)} | Staged Size: {format_size(staged_accumulated)} | Available: {format_size(free)}"
        )
        if execution_blocked:
            self.btn_execute_staging.config(state="disabled", bg=SECONDARY_BG, text="⚠️ SPACE BLOCKED")
        else:
            self.btn_execute_staging.config(state="normal", bg=ACCENT_COLOR, text="⚡ EXECUTE CUT & MOVE")

    def clear_staged_queue(self):
        self.queue_tree.delete(*self.queue_tree.get_children())
        self.queue_items.clear()
        self.validate_queue_disk_space()

    # Right-Click Target Blueprint Controls
    def show_blueprint_menu(self, event):
        item_id = self.target_tree.identify_row(event.y)
        self.target_tree.focus(item_id)
        if item_id:
            self.target_tree.selection_set(item_id)
        self.blueprint_ctx_menu.post(event.x_root, event.y_root)

    def create_virtual_blueprint_node(self):
        parent_id = self.target_tree.focus()
        if not parent_id:
            parent_id = self.target_tree.get_children()[0]
        new_id = self.target_tree.insert(parent_id, "end", text="New Virtual Folder", open=True)
        self.target_tree.item(parent_id, open=True)
        self.trigger_in_place_rename(new_id)

    def rename_virtual_blueprint_node(self):
        item_id = self.target_tree.focus()
        if not item_id:
            return
        txt = self.target_tree.item(item_id, "text")
        if "(Virtual Root)" in txt:
            return
        self.trigger_in_place_rename(item_id)

    def delete_virtual_blueprint_node(self):
        item_id = self.target_tree.focus()
        if not item_id:
            return
        txt = self.target_tree.item(item_id, "text")
        if "(Virtual Root)" in txt:
            return
        self.target_tree.delete(item_id)
        self.validate_queue_disk_space()

    # In-place Renaming text inputs overlay
    def trigger_in_place_rename(self, item_id):
        bbox = self.target_tree.bbox(item_id, column="#0")
        if not bbox:
            return
        x, y, w, h = bbox
        cur_text = self.target_tree.item(item_id, "text")
        
        self.editing_entry = tk.Entry(self.target_tree, font=("Segoe UI", 9), bd=0, highlightthickness=1, highlightcolor=HIGHLIGHT)
        self.editing_entry.insert(0, cur_text)
        self.editing_entry.select_range(0, tk.END)
        self.editing_entry.place(x=x, y=y, width=max(w, 160), height=h)
        self.editing_entry.focus_set()
        
        self.editing_item = item_id
        self.editing_entry.bind("<Return>", self.save_rename)
        self.editing_entry.bind("<FocusOut>", self.save_rename)
        self.editing_entry.bind("<Escape>", self.cancel_rename)

    def save_rename(self, event):
        if not self.editing_entry:
            return
        new_name = self.editing_entry.get().strip()
        forbidden = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
        if not new_name or any(f in new_name for f in forbidden):
            messagebox.showwarning("Rename Error", "Invalid directory name. Characters not allowed: \\ / : * ? \" < > |")
            self.cancel_rename(None)
            return
        self.target_tree.item(self.editing_item, text=new_name)
        self.destroy_editing_box()
        self.validate_queue_disk_space()

    def cancel_rename(self, event):
        self.destroy_editing_box()

    def destroy_editing_box(self):
        if self.editing_entry:
            self.editing_entry.destroy()
            self.editing_entry = None
            self.editing_item = None

    # Migration sequential execution per Source Drive
    def execute_staged_transfers(self):
        if not self.queue_items:
            return

        # Check for missing paths:
        missing_paths = []
        for task in self.queue_items:
            if not os.path.exists(task["src"]):
                missing_paths.append(task["src"])

        if missing_paths:
            paths_str = "\n".join(missing_paths[:5])
            if len(missing_paths) > 5:
                paths_str += f"\n... and {len(missing_paths)-5} more."
            messagebox.showerror(
                "Missing Source Paths", 
                f"The following staged files/folders are missing from your disk:\n\n{paths_str}\n\n"
                f"They may have been deleted, moved, or renamed outside the application.\n"
                f"Please run a high-speed scan in the Radix Scanner first to synchronize the file index."
            )
            return

        if messagebox.askyesno("Staging Deck", f"Execute {len(self.queue_items)} queued migrations now?"):
            self.btn_execute_staging.config(state="disabled", text="⚠️ STAGING...")
            self.btn_clear_staged.config(state="disabled")
            threading.Thread(target=self.threaded_transfers_executor, daemon=True).start()

    def threaded_transfers_executor(self):
        # Group tasks by Source Drive letter
        tasks_grouped = {}
        for task in self.queue_items:
            drv, _ = os.path.splitdrive(task["src"])
            drv = drv.upper()
            if drv not in tasks_grouped:
                tasks_grouped[drv] = []
            tasks_grouped[drv].append(task)

        total = len(self.queue_items)
        done = 0

        # Execute drive tasks sequentially
        for drv, tasks in tasks_grouped.items():
            self.update_log_msg(f"Processing source drive queue: {drv}...")
            for task in tasks:
                src = task["src"]
                dest = task["dest"]
                item_id = task["item_id"]
                
                self.queue_tree.item(item_id, values=(src, dest, format_size(task["size"]), "Moving..."))
                
                try:
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    shutil.move(src, dest)
                    self.write_mover_log("SUCCESS", src, dest, task["size"])
                    self.queue_tree.item(item_id, values=(src, dest, format_size(task["size"]), "Completed"))
                    task["status"] = "Completed"
                except Exception as e:
                    self.write_mover_log(f"ERROR: {str(e)}", src, dest, task["size"])
                    self.queue_tree.item(item_id, values=(src, dest, format_size(task["size"]), "Failed"), tags=("blocked",))
                    task["status"] = "Failed"

                done += 1
                self.update_log_msg(f"Queue Progress: {done}/{total} | Active Source: {drv}")

        self.update_log_msg("All queued staging operations completed!")
        self.parent.after(0, self.on_staging_complete)

    def write_mover_log(self, status, src, dest, size):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracerust_transfer_log.txt")
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"{ts} | {status} | {src} | {dest} | {format_size(size)}\n")
        except Exception as e:
            print(f"Log error: {e}")

    def update_log_msg(self, msg):
        self.parent.after(0, lambda: self.queue_status_lbl.config(text=msg))

    def on_staging_complete(self):
        self.controller.show_toast("Staging Executed", "Sequential staging transfers successfully completed.", "success")
        
        # Remove successful migrations from tree view queue
        remaining = []
        self.queue_tree.delete(*self.queue_tree.get_children())
        for idx, item in enumerate(self.queue_items):
            if item["status"] == "Failed":
                item["id"] = len(remaining) + 1
                row_id = self.queue_tree.insert(
                    "", "end", text=str(item["id"]),
                    values=(item["src"], item["dest"], format_size(item["size"]), "Failed"),
                    tags=("blocked",)
                )
                item["item_id"] = row_id
                remaining.append(item)
                
        self.queue_items = remaining
        self.populate_mover_source_tree()
        self.validate_queue_disk_space()
        
        self.btn_clear_staged.config(state="normal")

    def show_source_tree_menu(self, event):
        item_id = self.source_tree.identify_row(event.y)
        if not item_id:
            return
        
        current_selection = self.source_tree.selection()
        if item_id not in current_selection:
            self.source_tree.focus(item_id)
            self.source_tree.selection_set(item_id)
            current_selection = (item_id,)
            
        node = self.left_tree_registry.get(item_id)
        if node:
            self.source_ctx_menu.delete(0, "end")
            self.source_ctx_menu.add_command(
                label="📂 Open in Windows Explorer", 
                command=lambda: self.controller.open_in_explorer(node.full_path)
            )
            self.source_ctx_menu.add_separator()
            is_container = node.full_path in self.controller.config_data["container_paths"]
            if is_container:
                self.source_ctx_menu.add_command(
                    label="🔓 Remove Container Asset Tag", 
                    command=self.unmark_mover_containers_bulk
                )
            else:
                self.source_ctx_menu.add_command(
                    label="📁 Mark as Container Asset", 
                    command=self.mark_mover_containers_bulk
                )
            self.source_ctx_menu.post(event.x_root, event.y_root)

    def mark_mover_containers_bulk(self):
        selected_items = self.source_tree.selection()
        for item_id in selected_items:
            node = self.left_tree_registry.get(item_id)
            if node:
                p = node.full_path
                if p not in self.controller.config_data["container_paths"]:
                    self.controller.config_data["container_paths"].append(p)
        self.controller.save_config()
        self.populate_mover_source_tree()

    def unmark_mover_containers_bulk(self):
        selected_items = self.source_tree.selection()
        for item_id in selected_items:
            node = self.left_tree_registry.get(item_id)
            if node:
                p = node.full_path
                if p in self.controller.config_data["container_paths"]:
                    self.controller.config_data["container_paths"].remove(p)
        self.controller.save_config()
        self.populate_mover_source_tree()

def main():
    root = tk.Tk()
    try:
        root.option_add("*Font", "SegoeUI 9")
    except Exception:
        pass
    app = TraceRustApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
