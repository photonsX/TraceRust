import os
import sys
import json
import shutil
import string
import datetime
import subprocess
import threading
import queue
import sqlite3
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

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
APP_VERSION = "2.0-stable"
BORDER_COLOR = "#4c566a"      # Intermediate Slate/Border Gray

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
        self.root.title(f"TraceRust Asset Explorer v{APP_VERSION}")
        
        # Maximize screen on start for clean slate
        try:
            self.root.state("zoomed")
        except Exception:
            self.root.geometry("1200x850")
            
        self.root.configure(bg=BG_COLOR)
        self.root.protocol("WM_DELETE_WINDOW", self.on_app_exit)

        # Floating windows registry
        self.open_windows = {}

        # Config state schema
        self.config_data = {
            "scan_targets": [],
            "ignore_exact_folders": [],
            "ignore_folder_names": [".git", "node_modules", "target", "build"],
            "container_paths": [],
            "media_source_paths": []
        }
        self.init_db()

        # Scanner state
        self.scanning = False
        self.scan_queue = queue.Queue()
        self.scan_process = None
        # Tab container on top
        self.tab_container = tk.Frame(self.root, bg=CARD_BG, height=40)
        self.tab_container.pack(fill="x", side="top")
        self.tab_container.pack_propagate(False)
        
        # ☰ Burger Menu Button packed at the very left of the top tab container
        self.burger_btn = tk.Button(
            self.tab_container, 
            text=" ☰ ", 
            command=self.show_burger_menu,
            bg=CARD_BG,
            fg=TEXT_COLOR,
            activebackground=SELECT_BG,
            activeforeground=ACCENT_COLOR,
            relief="flat",
            font=("Segoe UI", 12, "bold"),
            bd=0,
            padx=15
        )
        self.burger_btn.pack(side="left", fill="both")
        self.bind_hover(self.burger_btn, SELECT_BG, CARD_BG)
        
        self.tab_home = tk.Button(
            self.tab_container, 
            text="  🏠 Home Desktop  ", 
            command=self.show_home_tab,
            bg=BG_COLOR, 
            fg=ACCENT_COLOR, 
            activebackground=BG_COLOR, 
            activeforeground=ACCENT_COLOR,
            relief="flat", 
            font=("Segoe UI", 10, "bold"), 
            bd=0, 
            padx=10
        )
        self.tab_home.pack(side="left", fill="both")
        
        self.tab_academy = tk.Button(
            self.tab_container, 
            text="  🎓 Academy Media  ", 
            command=self.show_academy_tab,
            bg=CARD_BG, 
            fg=TEXT_MUTED, 
            activebackground=CARD_BG, 
            activeforeground=TEXT_COLOR,
            relief="flat", 
            font=("Segoe UI", 10, "bold"), 
            bd=0, 
            padx=10
        )
        self.tab_academy.pack(side="left", fill="both")
        
        # Main content container
        self.main_container = tk.Frame(self.root, bg=BG_COLOR)
        self.main_container.pack(fill="both", expand=True)

        # Main background workspace canvas (Home Desktop)
        self.canvas = tk.Frame(self.main_container, bg=BG_COLOR)
        self.canvas.pack(fill="both", expand=True)

        # Academy Workspace Frame
        self.academy_tab_frame = tk.Frame(self.main_container, bg=BG_COLOR)

        # Minimal Watermark logo in center of Home Desktop
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
        # Make toast visible on either canvas (Home Desktop) or academy_tab_frame
        target_parent = self.canvas
        if self.academy_tab_frame.winfo_viewable():
            target_parent = self.academy_tab_frame
            
        if hasattr(self, "active_toast") and self.active_toast and self.active_toast.winfo_exists():
            self.active_toast.destroy()
        self.active_toast = ToastNotification(target_parent, title, message, status_type)

    def show_home_tab(self):
        self.tab_home.config(bg=BG_COLOR, fg=ACCENT_COLOR)
        self.tab_academy.config(bg=CARD_BG, fg=TEXT_MUTED)
        self.academy_tab_frame.pack_forget()
        self.canvas.pack(fill="both", expand=True)

    def show_academy_tab(self):
        self.tab_academy.config(bg=BG_COLOR, fg=ACCENT_COLOR)
        self.tab_home.config(bg=CARD_BG, fg=TEXT_MUTED)
        self.canvas.pack_forget()
        self.academy_tab_frame.pack(fill="both", expand=True)
        
        if not hasattr(self, "academy_view_class") or not self.academy_view_class:
            self.academy_view_class = AcademyViewport(self.academy_tab_frame, self)
        else:
            self.academy_view_class.load_library_view()

    # ==========================================
    # CENTRALIZED APPLICATION SETTINGS (VERTICAL TABS)
    # ==========================================
    def open_settings_window(self):
        if "settings" in self.open_windows:
            self.open_windows["settings"].lift()
            return
            
        win = FloatingWindow(
            self.main_container, 
            "⚙️ TraceRust Application Settings", 
            680, 500, 
            x=200, y=80,
            on_close_callback=lambda: self.open_windows.pop("settings", None)
        )
        self.open_windows["settings"] = win
        self.build_settings_viewport(win.viewport)

    def build_settings_viewport(self, parent):
        sidebar = tk.Frame(parent, bg=CARD_BG, width=170)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        
        content_frame = tk.Frame(parent, bg=BG_COLOR)
        content_frame.pack(side="right", fill="both", expand=True)
        
        self.settings_panels = {}
        self.settings_buttons = {}
        
        panel_general = tk.Frame(content_frame, bg=BG_COLOR, padx=15, pady=15)
        panel_academy = tk.Frame(content_frame, bg=BG_COLOR, padx=15, pady=15)
        panel_tags = tk.Frame(content_frame, bg=BG_COLOR, padx=15, pady=15)
        panel_shortcuts = tk.Frame(content_frame, bg=BG_COLOR, padx=15, pady=15)
        
        self.settings_panels["general"] = panel_general
        self.settings_panels["academy"] = panel_academy
        self.settings_panels["tags"] = panel_tags
        self.settings_panels["shortcuts"] = panel_shortcuts
        
        btn_gen = tk.Button(
            sidebar, text="⚙️ General", bg=BG_COLOR, fg=ACCENT_COLOR,
            font=("Segoe UI", 10, "bold"), relief="flat", bd=0, anchor="w", padx=15, pady=12,
            command=lambda: self.switch_settings_tab("general")
        )
        btn_gen.pack(fill="x", pady=2)
        self.settings_buttons["general"] = btn_gen
        
        btn_acad = tk.Button(
            sidebar, text="🎓 Academy", bg=CARD_BG, fg=TEXT_MUTED,
            font=("Segoe UI", 10, "bold"), relief="flat", bd=0, anchor="w", padx=15, pady=12,
            command=lambda: self.switch_settings_tab("academy")
        )
        btn_acad.pack(fill="x", pady=2)
        self.settings_buttons["academy"] = btn_acad

        btn_tags = tk.Button(
            sidebar, text="🏷️ Tag Manager", bg=CARD_BG, fg=TEXT_MUTED,
            font=("Segoe UI", 10, "bold"), relief="flat", bd=0, anchor="w", padx=15, pady=12,
            command=lambda: self.switch_settings_tab("tags")
        )
        btn_tags.pack(fill="x", pady=2)
        self.settings_buttons["tags"] = btn_tags

        btn_shortcuts = tk.Button(
            sidebar, text="⌨️ Shortcuts", bg=CARD_BG, fg=TEXT_MUTED,
            font=("Segoe UI", 10, "bold"), relief="flat", bd=0, anchor="w", padx=15, pady=12,
            command=lambda: self.switch_settings_tab("shortcuts")
        )
        btn_shortcuts.pack(fill="x", pady=2)
        self.settings_buttons["shortcuts"] = btn_shortcuts
        
        self.populate_general_settings_panel(panel_general)
        self.populate_academy_settings_panel(panel_academy)
        self.populate_tags_settings_panel(panel_tags)
        self.populate_shortcuts_settings_panel(panel_shortcuts)
        
        self.switch_settings_tab("general")

    def switch_settings_tab(self, tab_key):
        for key, btn in self.settings_buttons.items():
            if key == tab_key:
                btn.config(bg=BG_COLOR, fg=ACCENT_COLOR)
            else:
                btn.config(bg=CARD_BG, fg=TEXT_MUTED)
                
        for key, frame in self.settings_panels.items():
            if key == tab_key:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

    def populate_general_settings_panel(self, parent):
        tk.Label(parent, text="GENERAL APP CONFIGURATION", font=("Segoe UI", 11, "bold"), fg=ACCENT_COLOR, bg=BG_COLOR).pack(anchor="w", pady=(0, 10))
        
        # API Key settings section
        tk.Label(parent, text="Api Key for search (Gemini API Key)", font=("Segoe UI", 9, "bold"), fg=TEXT_COLOR, bg=BG_COLOR).pack(anchor="w", pady=(15, 2))
        
        key_frame = tk.Frame(parent, bg=BG_COLOR)
        key_frame.pack(fill="x", pady=5)
        
        # Load current key
        curr_key = self.get_setting("gemini_api_key", "")
        
        self.entry_gemini_api_key = tk.Entry(
            key_frame, bg=CARD_BG, fg=TEXT_COLOR, insertbackground=TEXT_COLOR, 
            relief="flat", font=("Segoe UI", 9), show="*" if curr_key else ""
        )
        self.entry_gemini_api_key.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 10))
        self.entry_gemini_api_key.insert(0, curr_key)
        
        # Eye button to toggle password show/hide
        self.key_visible = False
        def toggle_key_visibility():
            self.key_visible = not self.key_visible
            self.entry_gemini_api_key.config(show="" if self.key_visible else "*")
            btn_show.config(text="👁️ Hide" if self.key_visible else "👁️ Show")
            
        btn_show = tk.Button(
            key_frame, text="👁️ Show", bg=SECONDARY_BG, fg=TEXT_COLOR,
            font=("Segoe UI", 8, "bold"), relief="flat", bd=0, padx=10, command=toggle_key_visibility
        )
        btn_show.pack(side="left", padx=5)
        self.bind_hover(btn_show, HIGHLIGHT, SECONDARY_BG)
        
        btn_save = tk.Button(
            parent, text="💾 Save API Key", bg=SUCCESS_COLOR, fg=BG_COLOR,
            font=("Segoe UI", 9, "bold"), relief="flat", bd=0, padx=15, pady=6,
            command=self.save_gemini_api_key
        )
        btn_save.pack(anchor="w", pady=10)
        self.bind_hover(btn_save, HIGHLIGHT, SUCCESS_COLOR)

    def save_gemini_api_key(self):
        new_key = self.entry_gemini_api_key.get().strip()
        self.set_setting("gemini_api_key", new_key)
        self.show_toast("API Key Saved", "Gemini API key successfully saved.", "success")

    def populate_academy_settings_panel(self, parent):
        tk.Label(parent, text="ACADEMY VIDEO SETTINGS", font=("Segoe UI", 11, "bold"), fg=ACCENT_COLOR, bg=BG_COLOR).pack(anchor="w", pady=(0, 10))
        
        # 1. Media source folders
        tk.Label(parent, text="Media Source Folders", font=("Segoe UI", 9, "bold"), fg=TEXT_COLOR, bg=BG_COLOR).pack(anchor="w", pady=(2, 2))
        
        media_frame = tk.Frame(parent, bg=BG_COLOR)
        media_frame.pack(fill="x", pady=2)
        
        self.acad_folders_list = tk.Listbox(media_frame, height=5, bg=CARD_BG, fg=TEXT_COLOR, relief="flat", highlightthickness=0)
        self.acad_folders_list.pack(side="left", fill="x", expand=True)
        for mp in self.config_data["media_source_paths"]:
            self.acad_folders_list.insert(tk.END, mp)
            
        btn_acad_f = tk.Frame(media_frame, bg=BG_COLOR)
        btn_acad_f.pack(side="right", fill="y", padx=5)
        
        btn_add_mp = tk.Button(btn_acad_f, text="+ Add Folder", bg=SECONDARY_BG, fg=TEXT_COLOR, font=("Segoe UI", 8, "bold"), relief="flat", bd=0, padx=10, pady=2, command=self.settings_add_media_path)
        btn_add_mp.pack(fill="x", pady=2)
        
        btn_rem_mp = tk.Button(btn_acad_f, text="- Remove", bg=SECONDARY_BG, fg=TEXT_COLOR, font=("Segoe UI", 8), relief="flat", bd=0, padx=10, pady=2, command=self.settings_remove_media_path)
        btn_rem_mp.pack(fill="x", pady=2)
        
        # 2. Excluded Paths List
        tk.Label(parent, text="Excluded / Hidden Paths", font=("Segoe UI", 9, "bold"), fg=TEXT_COLOR, bg=BG_COLOR).pack(anchor="w", pady=(10, 2))
        
        excl_frame = tk.Frame(parent, bg=BG_COLOR)
        excl_frame.pack(fill="x", pady=2)
        
        self.acad_excl_list = tk.Listbox(excl_frame, height=4, bg=CARD_BG, fg=TEXT_COLOR, relief="flat", highlightthickness=0)
        self.acad_excl_list.pack(side="left", fill="x", expand=True)
        
        btn_excl_f = tk.Frame(excl_frame, bg=BG_COLOR)
        btn_excl_f.pack(side="right", fill="y", padx=5)
        
        btn_unhide = tk.Button(btn_excl_f, text="🔓 Restore View", bg=SECONDARY_BG, fg=TEXT_COLOR, font=("Segoe UI", 8, "bold"), relief="flat", bd=0, padx=10, pady=2, command=self.settings_restore_excluded_path)
        btn_unhide.pack(fill="x", pady=2)
        
        # Populate exclusions
        self.refresh_settings_exclusions_list()
        
        # 3. Database Sync
        tk.Label(parent, text="Database Sync", font=("Segoe UI", 9, "bold"), fg=TEXT_COLOR, bg=BG_COLOR).pack(anchor="w", pady=(10, 2))
        
        self.btn_acad_scan = tk.Button(
            parent, text="⚡ Scan Media Folders", bg=ACCENT_COLOR, fg=BG_COLOR, font=("Segoe UI", 9, "bold"), relief="flat", bd=0, padx=15, pady=6,
            command=self.settings_trigger_media_scan
        )
        self.btn_acad_scan.pack(anchor="w", pady=5)
        self.bind_hover(self.btn_acad_scan, HIGHLIGHT, ACCENT_COLOR)
        
        # 4. Academy ScreenShot and Notes Options
        tk.Label(parent, text="ScreenShot and Notes", font=("Segoe UI", 9, "bold"), fg=TEXT_COLOR, bg=BG_COLOR).pack(anchor="w", pady=(15, 2))
        
        scr_btn_frame = tk.Frame(parent, bg=BG_COLOR)
        scr_btn_frame.pack(anchor="w", pady=2)
        
        btn_def_scr = tk.Button(
            scr_btn_frame, text="📁 Define ScreenShot and Notes Folder...", bg=SECONDARY_BG, fg=TEXT_COLOR,
            font=("Segoe UI", 9, "bold"), relief="flat", bd=0, padx=15, pady=6,
            command=self.define_screenshot_folder
        )
        btn_def_scr.pack(side="left", padx=(0, 10))
        self.bind_hover(btn_def_scr, HIGHLIGHT, SECONDARY_BG)
        
        btn_reset_scr = tk.Button(
            scr_btn_frame, text="🔄 Reset Screenshot Counter", bg=SECONDARY_BG, fg=TEXT_COLOR,
            font=("Segoe UI", 9, "bold"), relief="flat", bd=0, padx=15, pady=6,
            command=self.reset_screenshot_counter
        )
        btn_reset_scr.pack(side="left")
        self.bind_hover(btn_reset_scr, HIGHLIGHT, SECONDARY_BG)

    def settings_add_media_path(self):
        f = filedialog.askdirectory(title="Select Media Folder Location")
        if f:
            f = os.path.normpath(f)
            if f not in self.config_data["media_source_paths"]:
                self.config_data["media_source_paths"].append(f)
                self.acad_folders_list.insert(tk.END, f)
                self.save_config()

    def settings_remove_media_path(self):
        selected = self.acad_folders_list.curselection()
        for idx in reversed(selected):
            val = self.acad_folders_list.get(idx)
            if val in self.config_data["media_source_paths"]:
                self.config_data["media_source_paths"].remove(val)
            self.acad_folders_list.delete(idx)
        self.save_config()

    def refresh_settings_exclusions_list(self):
        if not hasattr(self, "acad_excl_list"):
            return
        self.acad_excl_list.delete(0, "end")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT path FROM academy_exclusions ORDER BY path")
        rows = cursor.fetchall()
        conn.close()
        for r in rows:
            self.acad_excl_list.insert(tk.END, r[0])

    def settings_restore_excluded_path(self):
        selected = self.acad_excl_list.curselection()
        if not selected:
            messagebox.showinfo("Selection Required", "Please select an excluded path to restore.")
            return
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        for idx in reversed(selected):
            val = self.acad_excl_list.get(idx)
            cursor.execute("DELETE FROM academy_exclusions WHERE path = ?", (val,))
            self.acad_excl_list.delete(idx)
            
        conn.commit()
        conn.close()
        
        self.show_toast("View Restored", "Successfully restored path(s) to Academy view.", "success")
        if hasattr(self, "academy_view_class") and self.academy_view_class:
            self.academy_view_class.load_library_view()

    def settings_trigger_media_scan(self):
        if not self.config_data["media_source_paths"]:
            messagebox.showwarning("Academy Settings", "Please add at least one folder path first.")
            return
            
        self.btn_acad_scan.config(state="disabled", text="SCANNING...")
        threading.Thread(target=self.settings_threaded_media_scan, daemon=True).start()

    def settings_threaded_media_scan(self):
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            exe_path = os.path.join(script_dir, "Radix_Scanner", "radix_engine.exe")
            if not os.path.exists(exe_path):
                exe_path = os.path.join(script_dir, "radix_engine.exe")
                
            temp_config = os.path.join(os.path.dirname(exe_path), "config.json")
            with open(temp_config, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=4)
                
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
            proc = subprocess.Popen(
                [exe_path, "--media"],
                cwd=os.path.dirname(exe_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                startupinfo=startupinfo
            )
            _, _ = proc.communicate()
            
            if os.path.exists(temp_config):
                try:
                    os.remove(temp_config)
                except Exception:
                    pass
            
            index_file = os.path.join(os.path.dirname(exe_path), "media_index.txt")
            if os.path.exists(index_file):
                self.settings_sync_media_txt_to_db(index_file)
                self.root.after(0, lambda: self.show_toast("Media Scan Complete", "Video files successfully indexed and loaded to database.", "success"))
                if hasattr(self, "academy_view_class") and self.academy_view_class:
                    self.root.after(0, self.academy_view_class.load_library_view)
            else:
                self.root.after(0, lambda: self.show_toast("Scan Failed", "No videos indexed. Verify paths or video formats.", "error"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Scan Error", f"Rust engine failed: {e}"))
            
        self.root.after(0, lambda: self.btn_acad_scan.config(state="normal", text="⚡ Scan Media Folders"))

    def settings_sync_media_txt_to_db(self, filepath):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        scanned_paths = set()
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
                    path = line
                    size = 0
                path = os.path.normpath(path)
                scanned_paths.add(path)
                
                cursor.execute("SELECT 1 FROM media_items WHERE path = ?", (path,))
                if not cursor.fetchone():
                    cursor.execute(
                        "INSERT INTO media_items (path, watch_progress_timecode, completion_percentage, total_duration, watched_status, bookmark_1, bookmark_2, custom_title, links, notes, folder_tier_shift, size) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (path, "00:00:00", 0.0, "00:00:00", 0, 0, 0, os.path.basename(path), "", "", 0, size)
                    )
                else:
                    cursor.execute("UPDATE media_items SET size = ? WHERE path = ?", (size, path))
        
        cursor.execute("SELECT path FROM media_items")
        stored = cursor.fetchall()
        for r in stored:
            p = r[0]
            if p not in scanned_paths and not os.path.exists(p):
                cursor.execute("DELETE FROM media_items WHERE path = ?", (p,))
                
        conn.commit()
        conn.close()

    # ==========================================
    # TAG MANAGER SETTINGS PANEL
    # ==========================================
    def populate_tags_settings_panel(self, parent):
        tk.Label(
            parent, text="🏷️ Application Tag Manager", 
            font=("Segoe UI", 11, "bold"), fg=ACCENT_COLOR, bg=BG_COLOR
        ).pack(anchor="w", pady=(0, 10))
        
        tk.Label(
            parent, text="Manage tags used across your courses library. Renaming a tag here will update it on all courses automatically.",
            font=("Segoe UI", 8, "italic"), fg=TEXT_MUTED, bg=BG_COLOR, wraplength=450, justify="left"
        ).pack(anchor="w", pady=(0, 15))
        
        # Split layout: Listbox on left, Control panel on right
        split_frame = tk.Frame(parent, bg=BG_COLOR)
        split_frame.pack(fill="both", expand=True)
        
        left_sub = tk.Frame(split_frame, bg=BG_COLOR)
        left_sub.pack(side="left", fill="both", expand=True)
        
        right_sub = tk.Frame(split_frame, bg=BG_COLOR, width=200, padx=15)
        right_sub.pack(side="right", fill="y")
        right_sub.pack_propagate(False)
        
        # 1. Tags Listbox with scrollbar
        tk.Label(left_sub, text="Available Tags:", font=("Segoe UI", 9, "bold"), fg=TEXT_COLOR, bg=BG_COLOR).pack(anchor="w", pady=2)
        
        list_frame = tk.Frame(left_sub, bg=BG_COLOR)
        list_frame.pack(fill="both", expand=True)
        
        self.tags_listbox = tk.Listbox(
            list_frame, bg=CARD_BG, fg=TEXT_COLOR, 
            selectbackground=SELECT_BG, relief="flat", bd=0, highlightthickness=1, highlightbackground=BORDER_COLOR
        )
        self.tags_listbox.pack(side="left", fill="both", expand=True)
        
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tags_listbox.yview)
        self.tags_listbox.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        
        self.tags_listbox.bind("<<ListboxSelect>>", self.on_tag_list_select)
        
        # 2. Controls Frame
        tk.Label(right_sub, text="Tag Name:", font=("Segoe UI", 9, "bold"), fg=TEXT_COLOR, bg=BG_COLOR).pack(anchor="w", pady=(0, 2))
        self.entry_settings_tag = tk.Entry(right_sub, bg=CARD_BG, fg=TEXT_COLOR, relief="flat", insertbackground=TEXT_COLOR)
        self.entry_settings_tag.pack(fill="x", pady=(0, 15), ipady=3)
        
        # Add Tag Button
        btn_add = tk.Button(
            right_sub, text="➕ Add New Tag", bg=SUCCESS_COLOR, fg=BG_COLOR,
            font=("Segoe UI", 9, "bold"), relief="flat", bd=0, pady=6, command=self.settings_add_tag
        )
        btn_add.pack(fill="x", pady=4)
        self.bind_hover(btn_add, HIGHLIGHT, SUCCESS_COLOR)
        
        # Rename Tag Button
        btn_rename = tk.Button(
            right_sub, text="📝 Rename Selected", bg=ACCENT_COLOR, fg=BG_COLOR,
            font=("Segoe UI", 9, "bold"), relief="flat", bd=0, pady=6, command=self.settings_rename_tag
        )
        btn_rename.pack(fill="x", pady=4)
        self.bind_hover(btn_rename, HIGHLIGHT, ACCENT_COLOR)
        
        # Delete Tag Button
        btn_delete = tk.Button(
            right_sub, text="🗑️ Delete Selected", bg=DANGER_COLOR, fg=TEXT_COLOR,
            font=("Segoe UI", 9, "bold"), relief="flat", bd=0, pady=6, command=self.settings_delete_tag
        )
        btn_delete.pack(fill="x", pady=4)
        self.bind_hover(btn_delete, DANGER_COLOR, DANGER_COLOR)
        
        # Initial population of tags listbox
        self.refresh_settings_tags_list()

    def refresh_settings_tags_list(self):
        self.tags_listbox.delete(0, "end")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM tags ORDER BY name COLLATE NOCASE")
        rows = cursor.fetchall()
        conn.close()
        for r in rows:
            self.tags_listbox.insert("end", r[0])

    def on_tag_list_select(self, event):
        sel = self.tags_listbox.curselection()
        if sel:
            val = self.tags_listbox.get(sel[0])
            self.entry_settings_tag.delete(0, "end")
            self.entry_settings_tag.insert(0, val)

    def settings_add_tag(self):
        val = self.entry_settings_tag.get().strip()
        if not val:
            return
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO tags (name) VALUES (?)", (val,))
            conn.commit()
            self.show_toast("Tag Added", f"Successfully registered new tag '{val}'.", "success")
        except sqlite3.IntegrityError:
            self.show_toast("Tag Already Exists", f"Tag '{val}' is already registered.", "info")
        conn.close()
        
        self.refresh_settings_tags_list()
        if hasattr(self, "academy_view_class") and self.academy_view_class:
            self.academy_view_class.load_library_view()

    def settings_rename_tag(self):
        sel = self.tags_listbox.curselection()
        if not sel:
            messagebox.showinfo("Selection Required", "Please select a tag from the list to rename.")
            return
        old_name = self.tags_listbox.get(sel[0])
        new_name = self.entry_settings_tag.get().strip()
        if not new_name or old_name == new_name:
            return
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (new_name,))
            cursor.execute("DELETE FROM tags WHERE name = ?", (old_name,))
        except Exception as e:
            print(f"Error in tags table rename: {e}")
            
        cursor.execute("SELECT path, tags FROM media_items WHERE tags LIKE ?", (f"%{old_name}%",))
        items = cursor.fetchall()
        for path, tags_str in items:
            if not tags_str:
                continue
            tag_list = [t.strip() for t in tags_str.split(",") if t.strip()]
            updated = []
            for t in tag_list:
                if t.lower() == old_name.lower():
                    updated.append(new_name)
                else:
                    updated.append(t)
            new_tags_str = ", ".join(updated)
            cursor.execute("UPDATE media_items SET tags = ? WHERE path = ?", (new_tags_str, path))
            
        conn.commit()
        conn.close()
        
        self.show_toast("Tag Renamed", f"Renamed tag '{old_name}' to '{new_name}' application-wide.", "success")
        self.refresh_settings_tags_list()
        
        if hasattr(self, "academy_view_class") and self.academy_view_class:
            self.academy_view_class.load_library_view()

    def settings_delete_tag(self):
        sel = self.tags_listbox.curselection()
        if not sel:
            messagebox.showinfo("Selection Required", "Please select a tag from the list to delete.")
            return
        tag_name = self.tags_listbox.get(sel[0])
        
        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the tag '{tag_name}'? It will be removed from all courses."):
            return
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM tags WHERE name = ?", (tag_name,))
        
        cursor.execute("SELECT path, tags FROM media_items WHERE tags LIKE ?", (f"%{tag_name}%",))
        items = cursor.fetchall()
        for path, tags_str in items:
            if not tags_str:
                continue
            tag_list = [t.strip() for t in tags_str.split(",") if t.strip()]
            updated = [t for t in tag_list if t.lower() != tag_name.lower()]
            new_tags_str = ", ".join(updated)
            cursor.execute("UPDATE media_items SET tags = ? WHERE path = ?", (new_tags_str, path))
            
        conn.commit()
        conn.close()
        
        self.show_toast("Tag Deleted", f"Deleted tag '{tag_name}' application-wide.", "success")
        self.entry_settings_tag.delete(0, "end")
        self.refresh_settings_tags_list()
        
        if hasattr(self, "academy_view_class") and self.academy_view_class:
            self.academy_view_class.load_library_view()

    # ==========================================
    # SHORTCUT MANAGER SETTINGS PANEL
    # ==========================================
    def populate_shortcuts_settings_panel(self, parent):
        tk.Label(
            parent, text="⌨️ Keyboard Shortcut Settings", 
            font=("Segoe UI", 11, "bold"), fg=ACCENT_COLOR, bg=BG_COLOR
        ).pack(anchor="w", pady=(0, 10))
        
        tk.Label(
            parent, text="Customize the global keyboard shortcuts used inside the embedded video player window. Click a hotkey button, then press the desired keyboard key combo to bind it.",
            font=("Segoe UI", 8, "italic"), fg=TEXT_MUTED, bg=BG_COLOR, wraplength=450, justify="left"
        ).pack(anchor="w", pady=(0, 15))
        
        # Grid layout for shortcuts
        grid_frame = tk.Frame(parent, bg=BG_COLOR)
        grid_frame.pack(fill="x", pady=5)
        
        shortcut_labels = {
            "play_pause": "Play / Pause Video",
            "seek_forward": "Seek Forward 10s",
            "seek_backward": "Seek Backward 10s",
            "speed_up": "Speed Up Playback",
            "speed_down": "Speed Down Playback",
            "add_time": "Insert Timecode to Notes",
            "bookmark_1": "Toggle Bookmark 1",
            "bookmark_2": "Toggle Bookmark 2",
            "snapshot": "Take Video Snapshot",
            "notes_toggle": "Toggle Notes Panel",
            "fullscreen": "Toggle Fullscreen"
        }
        
        row_idx = 0
        for key, label_text in shortcut_labels.items():
            tk.Label(grid_frame, text=label_text, font=("Segoe UI", 9, "bold"), fg=TEXT_COLOR, bg=BG_COLOR, anchor="w").grid(row=row_idx, column=0, sticky="w", pady=8, padx=(0, 20))
            
            # Fetch current display name
            default_display = {
                "play_pause": "Space",
                "seek_forward": "Right Arrow",
                "seek_backward": "Left Arrow",
                "speed_up": "Up Arrow",
                "speed_down": "Down Arrow",
                "add_time": "Ctrl+T",
                "bookmark_1": "Ctrl+1",
                "bookmark_2": "Ctrl+2",
                "snapshot": "Ctrl+S",
                "notes_toggle": "Ctrl+N",
                "fullscreen": "F"
            }[key]
            
            display_val = self.get_setting(f"shortcut_display_{key}", default_display)
            
            btn = tk.Button(
                grid_frame, text=display_val, bg=SECONDARY_BG, fg=TEXT_COLOR,
                font=("Segoe UI", 9, "bold"), relief="flat", bd=0, padx=12, pady=4
            )
            btn.grid(row=row_idx, column=1, sticky="w", pady=8)
            self.bind_hover(btn, HIGHLIGHT, SECONDARY_BG)
            btn.config(command=lambda k=key, b=btn: self.start_key_capture(k, b))
            
            btn_reset = tk.Button(
                grid_frame, text="🔄 Reset", bg=SECONDARY_BG, fg=TEXT_MUTED,
                font=("Segoe UI", 9), relief="flat", bd=0, padx=8, pady=4
            )
            btn_reset.grid(row=row_idx, column=2, sticky="w", pady=8, padx=10)
            self.bind_hover(btn_reset, HIGHLIGHT, SECONDARY_BG)
            btn_reset.config(command=lambda k=key, b=btn: self.reset_single_shortcut(k, b))
            
            row_idx += 1
            
        # Draw a line under it for the next set of shortcuts
        separator = tk.Frame(parent, bg=BORDER_COLOR, height=1)
        separator.pack(fill="x", pady=(20, 10))
        
        tk.Label(parent, text="Next Set of Shortcuts", font=("Segoe UI", 10, "bold"), fg=TEXT_MUTED, bg=BG_COLOR).pack(anchor="w", pady=5)
        tk.Label(parent, text="Additional app shortcuts will be customizable in a future release.", font=("Segoe UI", 9, "italic"), fg=TEXT_MUTED, bg=BG_COLOR).pack(anchor="w")

    def start_key_capture(self, shortcut_key, button_widget):
        # Disable button during capture
        button_widget.config(text="Press any key...", state="disabled")
        
        # Bind key event to settings window
        settings_win = self.open_windows["settings"]
        
        # Give focus to settings window to ensure keypresses are registered
        settings_win.focus_set()
        
        def on_key(event):
            # Ignore modifier release / press events
            if event.keysym in ("Control_L", "Control_R", "Shift_L", "Shift_R", "Alt_L", "Alt_R", "Win_L", "Win_R"):
                return "break"
                
            # Build keys
            parts = []
            display_parts = []
            
            if event.state & 4:
                parts.append("Control")
                display_parts.append("Ctrl")
            if event.state & 1:
                parts.append("Shift")
                display_parts.append("Shift")
            # Only Alt if 131072 bit is set (ignore lock state Mod1 NumLock bit 8)
            if event.state & 131072:
                parts.append("Alt")
                display_parts.append("Alt")
                
            parts.append(event.keysym)
            
            # Clean keysym display
            clean_display = {
                "space": "Space",
                "Right": "Right Arrow",
                "Left": "Left Arrow",
                "Up": "Up Arrow",
                "Down": "Down Arrow"
            }.get(event.keysym, event.keysym)
            
            display_parts.append(clean_display)
            
            binding_str = "-".join(parts)
            display_str = "+".join(display_parts)
            
            # Save configuration
            self.set_setting(f"shortcut_{shortcut_key}", binding_str)
            self.set_setting(f"shortcut_display_{shortcut_key}", display_str)
            
            # Reset button state
            button_widget.config(text=display_str, state="normal")
            
            # Unbind
            settings_win.unbind("<KeyPress>")
            
            self.show_toast("Shortcut Saved", f"Bound {shortcut_key} to {display_str}", "success")
            return "break"
            
        settings_win.bind("<KeyPress>", on_key)

    def reset_single_shortcut(self, shortcut_key, button_widget):
        DEFAULT_SHORTCUTS = {
            "play_pause": "space",
            "seek_forward": "Right",
            "seek_backward": "Left",
            "speed_up": "Up",
            "speed_down": "Down",
            "add_time": "Control-t",
            "bookmark_1": "Control-1",
            "bookmark_2": "Control-2",
            "snapshot": "Control-s",
            "notes_toggle": "Control-n",
            "fullscreen": "f"
        }
        DEFAULT_DISPLAYS = {
            "play_pause": "Space",
            "seek_forward": "Right Arrow",
            "seek_backward": "Left Arrow",
            "speed_up": "Up Arrow",
            "speed_down": "Down Arrow",
            "add_time": "Ctrl+T",
            "bookmark_1": "Ctrl+1",
            "bookmark_2": "Ctrl+2",
            "snapshot": "Ctrl+S",
            "notes_toggle": "Ctrl+N",
            "fullscreen": "F"
        }
        
        self.set_setting(f"shortcut_{shortcut_key}", DEFAULT_SHORTCUTS[shortcut_key])
        self.set_setting(f"shortcut_display_{shortcut_key}", DEFAULT_DISPLAYS[shortcut_key])
        
        button_widget.config(text=DEFAULT_DISPLAYS[shortcut_key])
        self.show_toast("Shortcut Reset", f"Reset to default: {DEFAULT_DISPLAYS[shortcut_key]}", "success")

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
        # Dropdown popup menu (Home Desktop & Settings shortcuts)
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
        self.burger_menu.add_separator()
        self.burger_menu.add_command(label="⚙️ Application Settings", command=self.open_settings_window)

    def define_screenshot_folder(self):
        curr_dir = self.get_setting("academy_screenshot_dir", "")
        selected = filedialog.askdirectory(
            title="Select Default ScreenShot and Notes Storage Directory",
            initialdir=curr_dir if os.path.exists(curr_dir) else None
        )
        if selected:
            self.set_setting("academy_screenshot_dir", os.path.normpath(selected))
            self.show_toast("ScreenShot and Notes Folder", f"Successfully set folder: {os.path.basename(selected)}", "success")

    def reset_screenshot_counter(self):
        if messagebox.askyesno("Reset Counter", "Are you sure you want to reset the screenshot numbering counter back to 00001?"):
            self.set_setting("academy_screenshot_counter", "1")
            self.show_toast("Counter Reset", "Screenshot counter set back to 00001.", "success")

    def get_setting(self, key, default=None):
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            conn.close()
            if row:
                return row[0]
        except Exception as e:
            print(f"Error getting setting {key}: {e}")
        return default

    def set_setting(self, key, value):
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error setting setting {key}: {e}")

    def show_burger_menu(self):
        # Post directly beneath the burger button
        bx = self.burger_btn.winfo_rootx()
        by = self.burger_btn.winfo_rooty() + self.burger_btn.winfo_height()
        self.burger_menu.post(bx, by)

    def bind_hover(self, btn, hover_bg, normal_bg):
        btn.bind("<Enter>", lambda e: btn.config(bg=hover_bg) if btn["state"] == "normal" else None)
        btn.bind("<Leave>", lambda e: btn.config(bg=normal_bg) if btn["state"] == "normal" else None)

    # Config handlers & SQLite Database Management
    def get_config_filepath(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        scanner_dir = os.path.join(script_dir, "Radix_Scanner")
        if os.path.exists(scanner_dir):
            return os.path.join(scanner_dir, "config.json")
        return os.path.join(script_dir, "config.json")

    def init_db(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        db_dir = os.path.join(script_dir, "Radix_Scanner")
        os.makedirs(db_dir, exist_ok=True)
        self.db_path = os.path.join(db_dir, "tracerust.db")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create settings table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )""")
        
        # Create file_index table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_index (
            path TEXT PRIMARY KEY,
            size INTEGER
        )""")
        
        # Create transfer_history table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS transfer_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            status TEXT,
            source TEXT,
            destination TEXT,
            size INTEGER
        )""")
        
        # Create tags master table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            name TEXT PRIMARY KEY
        )""")
        
        # Create academy_exclusions table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS academy_exclusions (
            path TEXT PRIMARY KEY
        )""")
        
        # Create media_items table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS media_items (
            path TEXT PRIMARY KEY,
            watch_progress_timecode TEXT,
            completion_percentage REAL,
            total_duration TEXT,
            watched_status INTEGER,
            bookmark_1 INTEGER,
            bookmark_2 INTEGER,
            custom_title TEXT,
            links TEXT,
            notes TEXT,
            folder_tier_shift INTEGER,
            size INTEGER DEFAULT 0,
            rating TEXT DEFAULT '',
            image_path TEXT DEFAULT '',
            website TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            highlight_color TEXT DEFAULT ''
        )""")
        
        # Safe alter table for existing databases
        try:
            cursor.execute("ALTER TABLE media_items ADD COLUMN size INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE media_items ADD COLUMN rating TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE media_items ADD COLUMN image_path TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE media_items ADD COLUMN website TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE media_items ADD COLUMN tags TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE media_items ADD COLUMN highlight_color TEXT DEFAULT ''")
        except Exception:
            pass

        conn.commit()
        conn.close()
        
        self.migrate_legacy_data()
        self.load_settings_from_db()

    def migrate_legacy_data(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = self.get_config_filepath()
        log_path = os.path.join(script_dir, "tracerust_transfer_log.txt")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 1. Migrate config.json
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Auto migrations
                if "folders_to_scan" in data and "scan_targets" not in data:
                    data["scan_targets"] = data.pop("folders_to_scan")
                if "folders_to_ignore" in data and "ignore_exact_folders" not in data:
                    data["ignore_exact_folders"] = data.pop("folders_to_ignore")
                    
                for key, val in data.items():
                    cursor.execute(
                        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                        (key, json.dumps(val))
                    )
                conn.commit()
                # Rename config.json to config.json.bak
                os.replace(config_path, config_path + ".bak")
                print("Migrated config.json to SQLite database successfully.")
            except Exception as e:
                print(f"Error migrating config.json: {e}")
                
        # 2. Migrate tracerust_transfer_log.txt
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    for line in f:
                        parts = [p.strip() for p in line.split(" | ")]
                        if len(parts) >= 5:
                            ts, status, src, dest, size_str = parts[:5]
                            size = 0
                            try:
                                num, unit = size_str.split()
                                num = float(num)
                                mult = 1
                                unit = unit.upper()
                                if "KB" in unit: mult = 1024
                                elif "MB" in unit: mult = 1024*1024
                                elif "GB" in unit: mult = 1024*1024*1024
                                elif "TB" in unit: mult = 1024*1024*1024*1024
                                size = int(num * mult)
                            except Exception:
                                size = 0
                                
                            cursor.execute(
                                "INSERT INTO transfer_history (timestamp, status, source, destination, size) VALUES (?, ?, ?, ?, ?)",
                                (ts, status, src, dest, size)
                            )
                conn.commit()
                os.replace(log_path, log_path + ".bak")
                print("Migrated transfer history to SQLite database successfully.")
            except Exception as e:
                print(f"Error migrating transfer logs: {e}")
                
        conn.close()

    def load_settings_from_db(self):
        self.config_data = {
            "scan_targets": [],
            "ignore_exact_folders": [],
            "ignore_folder_names": [".git", "node_modules", "target", "build"],
            "container_paths": [],
            "media_source_paths": []
        }
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        rows = cursor.fetchall()
        for row in rows:
            k, v = row[0], row[1]
            try:
                self.config_data[k] = json.loads(v)
            except Exception:
                pass
        conn.close()
        self.cleanup_missing_container_paths()
        
        # Sync database configuration state to physical config.json file for Rust binary
        binary = self.find_rust_engine_binary()
        if binary:
            config_path = os.path.join(os.path.dirname(binary), "config.json")
            try:
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(self.config_data, f, indent=4)
            except Exception as e:
                print(f"Error syncing config.json on load: {e}")

    def cleanup_missing_container_paths(self):
        existing = []
        for cp in self.config_data["container_paths"]:
            if os.path.exists(cp):
                existing.append(cp)
        if len(existing) != len(self.config_data["container_paths"]):
            self.config_data["container_paths"] = existing
            self.save_config()

    def save_config(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            for k, v in self.config_data.items():
                cursor.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (k, json.dumps(v))
                )
            conn.commit()
            conn.close()
            
            # Synchronize to physical config.json for Rust engine binaries
            binary = self.find_rust_engine_binary()
            if binary:
                config_path = os.path.join(os.path.dirname(binary), "config.json")
                try:
                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump(self.config_data, f, indent=4)
                except Exception as e:
                    print(f"Error syncing config.json: {e}")
            
            # Automatically refresh windows if they are open
            if hasattr(self, "open_windows") and "mover" in self.open_windows:
                self.mover_view_class.populate_mover_source_tree()
        except Exception as e:
            print(f"Error saving settings: {e}")
            messagebox.showerror("Save Config Failed", f"Failed to save settings: {e}")

    # ==========================================
    # WINDOW NODE 1: RADIX SCANNER FLOATING WINDOW
    # ==========================================
    def open_scanner_window(self):
        if "scanner" in self.open_windows:
            self.open_windows["scanner"].lift()
            return
            
        win = FloatingWindow(
            self.main_container, 
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
            self.import_index_to_db(path)
            roots = self.parse_index_from_db()
            self.root.after(0, lambda: self.populate_scanner_explorer_tree(roots))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Parser Error", f"Failed to load index: {e}"))

    def import_index_to_db(self, filepath):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM file_index")
            
            batch = []
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
                    batch.append((path, size))
                    
                    if len(batch) >= 15000:
                        cursor.executemany("INSERT OR REPLACE INTO file_index (path, size) VALUES (?, ?)", batch)
                        batch = []
                        
            if batch:
                cursor.executemany("INSERT OR REPLACE INTO file_index (path, size) VALUES (?, ?)", batch)
                
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error importing index to DB: {e}")
            raise e

    def parse_index_from_db(self):
        root_nodes = {}
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT path, size FROM file_index")
            rows = cursor.fetchall()
            conn.close()
        except Exception as e:
            print(f"Error loading index from DB: {e}")
            return root_nodes

        for path, size in rows:
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
        try:
            if not hasattr(self, "explorer_tree") or not self.explorer_tree.winfo_exists():
                return
        except Exception:
            return
            
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
            self.main_container, 
            "📦 TraceMover Deck Staging Panel", 
            980, 720, 
            x=150, y=50,
            on_close_callback=lambda: self.open_windows.pop("mover", None)
        )
        self.open_windows["mover"] = win
        self.mover_view_class = TraceMoverViewport(win.viewport, self)

    # ==========================================
    # WINDOW NODE 3: ACADEMY VIDEO MEDIA DESK
    # ==========================================
    def open_academy_window(self):
        self.show_academy_tab()

    def on_app_exit(self):
        if hasattr(self, "academy_view_class") and self.academy_view_class:
            try:
                self.academy_view_class.shutdown_player()
            except Exception as e:
                print(f"Error shutting down player: {e}")
        self.root.destroy()

class TraceMoverViewport:
    def __init__(self, parent, controller):
        self.parent = parent
        self.controller = controller
        
        # Grid layout matching 3-Panel design
        self.parent.rowconfigure(0, weight=3) # trees
        self.parent.rowconfigure(1, weight=2) # queue table below
        self.parent.columnconfigure(0, weight=4)
        self.parent.columnconfigure(1, weight=0)
        self.parent.columnconfigure(2, weight=4)

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
        p1.grid(row=0, column=0, sticky="nsew", padx=(12, 0), pady=(12, 6))
        p1.rowconfigure(0, weight=1)
        p1.columnconfigure(0, weight=1)

        self.source_tree = ttk.Treeview(p1, style="Trace.Treeview")
        self.source_tree.heading("#0", text="Folders & Files Structure", anchor="w")
        self.source_tree.grid(row=0, column=0, sticky="nsew")

        s_scroll = ttk.Scrollbar(p1, orient="vertical", command=self.source_tree.yview)
        s_scroll.grid(row=0, column=1, sticky="ns")
        self.source_tree.config(yscrollcommand=s_scroll.set)

        self.source_tree.tag_configure("container", foreground=SUCCESS_COLOR)

        # Lazy load bindings
        self.source_tree.bind("<<TreeviewOpen>>", self.on_source_tree_expand)

        # Right-click context menu on source tree
        self.source_tree.bind("<Button-3>", self.show_source_tree_menu)
        self.source_ctx_menu = tk.Menu(
            self.parent, tearoff=0, bg=CARD_BG, fg=TEXT_COLOR, 
            activebackground=SELECT_BG, activeforeground=ACCENT_COLOR, relief="flat", bd=1
        )

        # ----------------------------------------
        # MIDDLE PANEL: Stage Button Column
        # ----------------------------------------
        mid_frame = tk.Frame(self.parent, bg=BG_COLOR)
        mid_frame.grid(row=0, column=1, sticky="ns", padx=10, pady=12)
        mid_frame.rowconfigure(0, weight=1)
        mid_frame.rowconfigure(1, weight=0)
        mid_frame.rowconfigure(2, weight=1)
        mid_frame.columnconfigure(0, weight=1)

        self.btn_stage_arrow = tk.Button(
            mid_frame, text=" ➡ ", command=self.stage_selected_items_via_button,
            bg=ACCENT_COLOR, fg=BG_COLOR, font=("Segoe UI", 14, "bold"), relief="flat", padx=8, pady=8, bd=0
        )
        self.btn_stage_arrow.grid(row=1, column=0)
        self.controller.bind_hover(self.btn_stage_arrow, HIGHLIGHT, ACCENT_COLOR)

        lbl_stage_arrow = tk.Label(mid_frame, text="STAGE\nASSET", font=("Segoe UI", 7, "bold"), fg=TEXT_MUTED, bg=BG_COLOR)
        lbl_stage_arrow.grid(row=2, column=0, sticky="n", pady=(6, 0))

        # ----------------------------------------
        # PANEL 2 (Right Panel): Target Blueprint Viewport
        # ----------------------------------------
        p2 = tk.LabelFrame(
            self.parent, text=" Target Blueprint Viewport ", font=("Segoe UI", 9, "bold"),
            fg=TEXT_COLOR, bg=CARD_BG, padx=10, pady=10, bd=1, relief="flat"
        )
        p2.grid(row=0, column=2, sticky="nsew", padx=(0, 12), pady=(12, 6))
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
        p3.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=12, pady=(6, 12))
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
        
        threading.Thread(target=self.threaded_mover_db_parse, daemon=True).start()

    def threaded_mover_db_parse(self):
        try:
            roots = self.parse_mover_index_pruned_db(self.controller.config_data["container_paths"])
            self.parent.after(0, lambda: self.populate_source_tree_view(roots))
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("Parser Failed", f"Mover parser error: {e}"))

    def parse_mover_index_pruned_db(self, container_paths):
        norm_containers = [os.path.normcase(cp) for cp in container_paths]
        dir_sizes = {}
        root_nodes = {}

        try:
            conn = sqlite3.connect(self.controller.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT path, size FROM file_index")
            rows = cursor.fetchall()
            conn.close()
        except Exception as e:
            print(f"Error reading file index for Mover: {e}")
            return root_nodes

        # Pass 1: Sum directory recursively
        for path, size in rows:
            # Exclude hidden files
            if any(p.startswith(".") for p in path.split(os.sep)):
                continue
                
            parent = os.path.dirname(path)
            while parent and parent != os.path.dirname(parent):
                dir_sizes[parent] = dir_sizes.get(parent, 0) + size
                parent = os.path.dirname(parent)

        # Pass 2: Map trees pruning container paths
        for path, size in rows:
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
        try:
            if not hasattr(self, "source_tree") or not self.source_tree.winfo_exists():
                return
        except Exception:
            return
            
        self.left_tree_registry.clear()
        try:
            self.source_tree.delete(*self.source_tree.get_children())
        except Exception:
            pass
        
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

    # Stage Selection Mechanics
    def stage_selected_items_via_button(self):
        selected_left = self.source_tree.selection()
        if not selected_left:
            self.controller.show_toast("Staging Blocked", "Please select at least one file or folder on the left.", "error")
            return
            
        selected_right = self.target_tree.selection()
        drive = self.drive_var.get()
        if not selected_right:
            root_item = self.target_tree.get_children()[0]
            dest_path = drive
            dest_item_id = root_item
        else:
            dest_item_id = selected_right[0]
            dest_path = self.get_virtual_dest_path(dest_item_id, drive)

        staged_count = 0
        for item_id in selected_left:
            node = self.left_tree_registry.get(item_id)
            if node:
                self.stage_move_transaction(node, dest_path, dest_item_id)
                staged_count += 1
                    
        if staged_count > 0:
            self.controller.show_toast("Assets Staged", f"Successfully staged {staged_count} item(s) to migration queue.", "success")

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
                    self.update_file_index_for_move(src, dest)
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
        try:
            conn = sqlite3.connect(self.controller.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO transfer_history (timestamp, status, source, destination, size) VALUES (?, ?, ?, ?, ?)",
                (ts, status, src, dest, size)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Log error: {e}")

    def update_file_index_for_move(self, src, dest):
        try:
            conn = sqlite3.connect(self.controller.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "UPDATE file_index SET path = ? WHERE path = ?",
                (dest, src)
            )
            cursor.execute(
                "UPDATE file_index SET path = ? || substr(path, ?) WHERE path LIKE ?",
                (dest, len(src) + 1, src + os.sep + "%")
            )
            conn.commit()
            conn.close()
            
            # Sync to text file in background
            threading.Thread(target=self.controller.sync_db_index_to_text_file, daemon=True).start()
        except Exception as e:
            print(f"Error updating file index DB for move: {e}")

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

# =====================================================================
# FRESH HIGH-PERFORMANCE ACADEMY MEDIA COMPONENT
# =====================================================================

def make_progress_bar(pct):
    filled = int(round(pct / 10.0))
    empty = 10 - filled
    return f"[{'█' * filled}{'░' * empty}] {pct:.1f}%"

class TreeNode:
    def __init__(self, name, is_dir=False):
        self.name = name
        self.is_dir = is_dir
        self.size = 0
        self.completed_pct = 0.0
        self.num_videos = 0
        self.all_video_pcts = []
        self.children = {}
        self.has_notes = False
        self.highlight_color = ""

class GeminiAutofillDialog(tk.Toplevel):
    def __init__(self, parent, course_name, website, tags, description, on_apply_callback):
        super().__init__(parent)
        self.title("🤖 Review Gemini AI Suggestions")
        self.configure(bg=BG_COLOR)
        self.transient(parent)
        self.grab_set()
        
        # Center in parent
        w, h = 500, 480
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_x()
        py = parent.winfo_y()
        self.geometry(f"{w}x{h}+{px + (pw - w)//2}+{py + (ph - h)//2}")
        
        # Header
        tk.Label(
            self, text="🤖 Gemini AI Course Metadata Suggestions",
            font=("Segoe UI", 11, "bold"), fg=ACCENT_COLOR, bg=BG_COLOR
        ).pack(anchor="w", padx=20, pady=(15, 5))
        
        tk.Label(
            self, text=f"Review and modify suggestions for: {course_name}",
            font=("Segoe UI", 8, "italic"), fg=TEXT_MUTED, bg=BG_COLOR
        ).pack(anchor="w", padx=20, pady=(0, 15))
        
        # Inputs frame
        f = tk.Frame(self, bg=BG_COLOR)
        f.pack(fill="both", expand=True, padx=20)
        
        # Website
        tk.Label(f, text="Official Website:", font=("Segoe UI", 9, "bold"), fg=TEXT_COLOR, bg=BG_COLOR).pack(anchor="w", pady=(5, 2))
        self.entry_web = tk.Entry(f, bg=CARD_BG, fg=TEXT_COLOR, insertbackground=TEXT_COLOR, relief="flat", font=("Segoe UI", 9))
        self.entry_web.pack(fill="x", ipady=4)
        self.entry_web.insert(0, website)
        
        # Tags
        tk.Label(f, text="Tags (comma-separated):", font=("Segoe UI", 9, "bold"), fg=TEXT_COLOR, bg=BG_COLOR).pack(anchor="w", pady=(10, 2))
        self.entry_tags = tk.Entry(f, bg=CARD_BG, fg=TEXT_COLOR, insertbackground=TEXT_COLOR, relief="flat", font=("Segoe UI", 9))
        self.entry_tags.pack(fill="x", ipady=4)
        self.entry_tags.insert(0, tags)
        
        # Description
        tk.Label(f, text="Description / Notes:", font=("Segoe UI", 9, "bold"), fg=TEXT_COLOR, bg=BG_COLOR).pack(anchor="w", pady=(10, 2))
        self.txt_desc = tk.Text(f, bg=CARD_BG, fg=TEXT_COLOR, insertbackground=TEXT_COLOR, relief="flat", wrap="word", height=8, font=("Segoe UI", 9))
        self.txt_desc.pack(fill="both", expand=True)
        self.txt_desc.insert("1.0", description)
        
        # Buttons
        btn_frame = tk.Frame(self, bg=BG_COLOR)
        btn_frame.pack(fill="x", side="bottom", padx=20, pady=20)
        
        btn_cancel = tk.Button(
            btn_frame, text="❌ Discard", bg=SECONDARY_BG, fg=TEXT_COLOR,
            font=("Segoe UI", 9, "bold"), relief="flat", bd=0, padx=20, pady=8,
            command=self.destroy
        )
        btn_cancel.pack(side="left")
        
        def on_apply():
            on_apply_callback(
                self.entry_web.get().strip(),
                self.entry_tags.get().strip(),
                self.txt_desc.get("1.0", "end-1c").strip()
            )
            self.destroy()
            
        btn_apply = tk.Button(
            btn_frame, text="💾 Apply & Save Info", bg=SUCCESS_COLOR, fg=BG_COLOR,
            font=("Segoe UI", 9, "bold"), relief="flat", bd=0, padx=20, pady=8,
            command=on_apply
        )
        btn_apply.pack(side="right")

class CroppingWindow(tk.Toplevel):
    def __init__(self, parent, pil_img, on_crop_callback):
        super().__init__(parent)
        self.title("📐 Crop & Frame Cover Image (1:1 Square)")
        self.configure(bg=BG_COLOR)
        self.transient(parent)
        self.grab_set()
        
        # Pad the original image to a square (over-scan / over-crop)
        w, h = pil_img.size
        max_dim = max(w, h)
        padded_img = Image.new("RGB", (max_dim, max_dim), (0, 0, 0)) # black background pad
        x_offset = (max_dim - w) // 2
        y_offset = (max_dim - h) // 2
        padded_img.paste(pil_img, (x_offset, y_offset))
        
        self.orig_img = padded_img
        self.on_crop_callback = on_crop_callback
        
        # Scale for display viewport (max 600x600)
        max_w, max_h = 600, 600
        orig_w, orig_h = self.orig_img.size
        self.scale = min(max_w / orig_w, max_h / orig_h, 1.0)
        self.disp_w = int(orig_w * self.scale)
        self.disp_h = int(orig_h * self.scale)
        
        self.disp_img = self.orig_img.resize((self.disp_w, self.disp_h), Image.Resampling.LANCZOS)
        self.tk_disp_img = ImageTk.PhotoImage(self.disp_img)
        
        # Center the window
        self.geometry(f"{self.disp_w + 40}x{self.disp_h + 120}")
        
        # Top help label
        lbl = tk.Label(
            self, text="Drag the square to move. Drag the bottom-right corner handle to resize.", 
            bg=BG_COLOR, fg=TEXT_MUTED, font=("Segoe UI", 9, "italic")
        )
        lbl.pack(pady=5)
        
        # Canvas
        self.canvas = tk.Canvas(self, width=self.disp_w, height=self.disp_h, bg=BG_COLOR, highlightthickness=0)
        self.canvas.pack(pady=5)
        
        # Draw background image
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_disp_img)
        
        # Selection square coordinates (default centered, size 80% of min dimension)
        self.box_size = int(min(self.disp_w, self.disp_h) * 0.8)
        self.x1 = (self.disp_w - self.box_size) // 2
        self.y1 = (self.disp_h - self.box_size) // 2
        self.x2 = self.x1 + self.box_size
        self.y2 = self.y1 + self.box_size
        
        # Draw overlay objects
        self.rect_id = self.canvas.create_rectangle(
            self.x1, self.y1, self.x2, self.y2, 
            outline=ACCENT_COLOR, width=2, dash=(4, 4)
        )
        self.handle_id = self.canvas.create_rectangle(
            self.x2 - 10, self.y2 - 10, self.x2, self.y2, 
            fill=ACCENT_COLOR, outline=""
        )
        
        # Bindings
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        
        # Actions bar
        actions = tk.Frame(self, bg=BG_COLOR)
        actions.pack(fill="x", side="bottom", pady=10)
        
        btn_cancel = tk.Button(
            actions, text="Cancel", bg=SECONDARY_BG, fg=TEXT_COLOR,
            font=("Segoe UI", 9, "bold"), relief="flat", bd=0, padx=20, pady=6,
            command=self.destroy
        )
        btn_cancel.pack(side="left", padx=20)
        
        btn_crop = tk.Button(
            actions, text="✂️ Crop & Save Cover", bg=ACCENT_COLOR, fg=BG_COLOR,
            font=("Segoe UI", 9, "bold"), relief="flat", bd=0, padx=20, pady=6,
            command=self.perform_crop
        )
        btn_crop.pack(side="right", padx=20)
        
        self.drag_mode = None
        self.drag_start = (0, 0)
        
    def on_press(self, event):
        x, y = event.x, event.y
        # Check if near bottom-right corner handle (within 15px)
        if abs(x - self.x2) < 15 and abs(y - self.y2) < 15:
            self.drag_mode = "resize"
        elif self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2:
            self.drag_mode = "move"
            self.drag_start = (x, y)
        else:
            self.drag_mode = None
            
    def on_drag(self, event):
        if not self.drag_mode:
            return
            
        x, y = event.x, event.y
        
        if self.drag_mode == "move":
            dx = x - self.drag_start[0]
            dy = y - self.drag_start[1]
            
            # Constrain movement within image boundaries
            if self.x1 + dx >= 0 and self.x2 + dx <= self.disp_w:
                self.x1 += dx
                self.x2 += dx
            if self.y1 + dy >= 0 and self.y2 + dy <= self.disp_h:
                self.y1 += dy
                self.y2 += dy
                
            self.drag_start = (x, y)
            
        elif self.drag_mode == "resize":
            # Compute new box size as square relative to x1, y1 anchor
            new_size = max(40, min(x - self.x1, y - self.y1))
            # Constrain within boundaries
            if self.x1 + new_size <= self.disp_w and self.y1 + new_size <= self.disp_h:
                self.box_size = new_size
                self.x2 = self.x1 + new_size
                self.y2 = self.y1 + new_size
                
        # Update canvas overlay drawings
        self.canvas.coords(self.rect_id, self.x1, self.y1, self.x2, self.y2)
        self.canvas.coords(self.handle_id, self.x2 - 10, self.y2 - 10, self.x2, self.y2)
        
    def perform_crop(self):
        # Map crop region back to original image resolution
        orig_x1 = int(self.x1 / self.scale)
        orig_y1 = int(self.y1 / self.scale)
        orig_x2 = int(self.x2 / self.scale)
        orig_y2 = int(self.y2 / self.scale)
        
        # Enforce boundaries just in case
        orig_w, orig_h = self.orig_img.size
        orig_x1 = max(0, min(orig_x1, orig_w))
        orig_y1 = max(0, min(orig_y1, orig_h))
        orig_x2 = max(0, min(orig_x2, orig_w))
        orig_y2 = max(0, min(orig_y2, orig_h))
        
        try:
            cropped = self.orig_img.crop((orig_x1, orig_y1, orig_x2, orig_y2))
            # Scale to standard high-res square cover (400x400)
            final_img = cropped.resize((400, 400), Image.Resampling.LANCZOS)
            self.on_crop_callback(final_img)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Crop Error", f"Failed to crop image: {e}")

class AcademyViewport:
    def __init__(self, parent, controller):
        self.parent = parent
        self.controller = controller
        self.current_inspector_path = None
        self.current_cover_image = None
        self.last_img_path = None

        # 1. Split Panel Viewport Layout
        # Left Panel (30% Width for Inspector)
        self.left_pane = tk.Frame(self.parent, bg=CARD_BG, padx=15, pady=10)
        self.left_pane.place(relx=0.0, rely=0.0, relwidth=0.30, relheight=1.0)
        
        # Right Panel (70% Width for Treeview)
        self.right_pane = tk.Frame(self.parent, bg=BG_COLOR)
        self.right_pane.place(relx=0.30, rely=0.0, relwidth=0.70, relheight=1.0)

        # 2. Build Left Inspector Panel Components
        # Top Header Bar containing title & small Save button
        self.header_bar = tk.Frame(self.left_pane, bg=CARD_BG, height=32)
        self.header_bar.pack(fill="x", side="top")
        self.header_bar.pack_propagate(False)
        
        lbl_hdr = tk.Label(self.header_bar, text="ℹ️ Course Inspector", font=("Segoe UI", 10, "bold"), fg=ACCENT_COLOR, bg=CARD_BG)
        lbl_hdr.pack(side="left")
        
        self.btn_save = tk.Button(
            self.header_bar, text="Save", bg=ACCENT_COLOR, fg=BG_COLOR,
            font=("Segoe UI", 8, "bold"), relief="flat", bd=0, padx=10, pady=2,
            command=self.save_inspector_changes
        )
        self.btn_save.pack(side="right")
        self.controller.bind_hover(self.btn_save, HIGHLIGHT, ACCENT_COLOR)

        # Body container for inspector contents (rely splits)
        self.inspect_body = tk.Frame(self.left_pane, bg=CARD_BG)
        self.inspect_body.pack(fill="both", expand=True, pady=(5, 0))

        # Cover Image Canvas (50% of the body height, edge-to-edge)
        self.cover_canvas = tk.Canvas(self.inspect_body, bg=BG_COLOR, highlightthickness=1, highlightbackground=BORDER_COLOR, cursor="hand2")
        self.cover_canvas.place(relx=0.0, rely=0.0, relwidth=1.0, relheight=0.50)
        self.cover_canvas.bind("<Button-1>", self.select_cover_image)
        self.cover_canvas.bind("<Configure>", self.on_canvas_resize)

        # Middle Content Frame (25% of the body height: Title, Rating, Website URL, Tags)
        self.middle_frame = tk.Frame(self.inspect_body, bg=CARD_BG)
        self.middle_frame.place(relx=0.0, rely=0.50, relwidth=1.0, relheight=0.25)
        
        # Spacer for 2-line height between cover image and title
        tk.Label(self.middle_frame, text="", bg=CARD_BG, font=("Segoe UI", 6), height=2).pack(fill="x")
        
        title_row = tk.Frame(self.middle_frame, bg=CARD_BG)
        title_row.pack(fill="x", anchor="w", pady=(2, 4))
        
        self.lbl_inspect_title = tk.Label(
            title_row, text="No Selection", font=("Segoe UI", 9, "bold"), 
            fg=TEXT_COLOR, bg=CARD_BG, justify="left", anchor="w", wraplength=170
        )
        self.lbl_inspect_title.pack(side="left", fill="x", expand=True)
        
        # Grab/Paste Cover Buttons Frame
        grab_frame = tk.Frame(title_row, bg=CARD_BG)
        grab_frame.pack(side="right")
        
        btn_paste = tk.Button(
            grab_frame, text="📋 Paste", bg=SECONDARY_BG, fg=TEXT_COLOR, 
            font=("Segoe UI", 7, "bold"), relief="flat", bd=0, padx=6, pady=2,
            command=self.paste_image_from_clipboard
        )
        btn_paste.pack(side="left", padx=2)
        self.controller.bind_hover(btn_paste, HIGHLIGHT, SECONDARY_BG)
        
        btn_url = tk.Button(
            grab_frame, text="🌐 URL", bg=SECONDARY_BG, fg=TEXT_COLOR, 
            font=("Segoe UI", 7, "bold"), relief="flat", bd=0, padx=6, pady=2,
            command=self.download_image_from_url
        )
        btn_url.pack(side="left", padx=2)
        self.controller.bind_hover(btn_url, HIGHLIGHT, SECONDARY_BG)
        
        btn_edit = tk.Button(
            grab_frame, text="📝 Edit", bg=SECONDARY_BG, fg=TEXT_COLOR, 
            font=("Segoe UI", 7, "bold"), relief="flat", bd=0, padx=6, pady=2,
            command=self.edit_current_cover
        )
        btn_edit.pack(side="left", padx=2)
        self.controller.bind_hover(btn_edit, HIGHLIGHT, SECONDARY_BG)
        
        btn_remove = tk.Button(
            grab_frame, text="🗑️ Remove", bg=SECONDARY_BG, fg=TEXT_COLOR, 
            font=("Segoe UI", 7, "bold"), relief="flat", bd=0, padx=6, pady=2,
            command=self.remove_current_cover
        )
        btn_remove.pack(side="left", padx=2)
        self.controller.bind_hover(btn_remove, HIGHLIGHT, SECONDARY_BG)

        # Rating selection row
        rf = tk.Frame(self.middle_frame, bg=CARD_BG)
        rf.pack(anchor="w", fill="x", pady=6)
        tk.Label(rf, text="Rating: ", font=("Segoe UI", 8, "bold"), fg=TEXT_MUTED, bg=CARD_BG).pack(side="left")
        self.combo_rating = ttk.Combobox(rf, values=("⭐⭐⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐", "⭐⭐", "⭐", "Unrated"), state="readonly", style="Trace.TCombobox", width=12)
        self.combo_rating.pack(side="left", padx=5)
        self.combo_rating.set("Unrated")

        # Website selection row
        wf = tk.Frame(self.middle_frame, bg=CARD_BG)
        wf.pack(anchor="w", fill="x", pady=6)
        tk.Label(wf, text="Website: ", font=("Segoe UI", 8, "bold"), fg=TEXT_MUTED, bg=CARD_BG).pack(side="left")
        self.entry_website = tk.Entry(wf, bg=BG_COLOR, fg=TEXT_COLOR, relief="flat", insertbackground=TEXT_COLOR, width=18)
        self.entry_website.pack(side="left", padx=5, fill="x", expand=True, ipady=1)
        
        btn_go = tk.Button(wf, text="🌐 Go", bg=SECONDARY_BG, fg=TEXT_COLOR, font=("Segoe UI", 8, "bold"), relief="flat", bd=0, padx=6, command=self.open_website_url)
        btn_go.pack(side="left", padx=(2, 0))
        self.controller.bind_hover(btn_go, HIGHLIGHT, SECONDARY_BG)

        # Tags selection row
        tf = tk.Frame(self.middle_frame, bg=CARD_BG)
        tf.pack(anchor="w", fill="x", pady=6)
        tk.Label(tf, text="Tags: ", font=("Segoe UI", 8, "bold"), fg=TEXT_MUTED, bg=CARD_BG).pack(side="left")
        self.entry_tags = tk.Entry(tf, bg=BG_COLOR, fg=TEXT_COLOR, relief="flat", insertbackground=TEXT_COLOR)
        self.entry_tags.pack(side="left", padx=5, fill="x", expand=True, ipady=1)
        
        # Tag Autocomplete Bindings
        self.entry_tags.bind("<KeyRelease>", self.show_tag_autocomplete)
        self.entry_tags.bind("<FocusOut>", lambda e: self.parent.after(200, self.hide_tag_autocomplete))

        # Info Frame (25% of the body height: Description Notes)
        self.info_frame = tk.Frame(self.inspect_body, bg=CARD_BG)
        self.info_frame.place(relx=0.0, rely=0.75, relwidth=1.0, relheight=0.25)
        
        tk.Label(self.info_frame, text="Description Notes:", font=("Segoe UI", 8, "bold"), fg=TEXT_MUTED, bg=CARD_BG).pack(anchor="w", pady=(6, 2))
        self.text_info = tk.Text(self.info_frame, bg=BG_COLOR, fg=TEXT_COLOR, insertbackground=TEXT_COLOR, relief="flat", wrap="word", font=("Segoe UI", 9))
        self.text_info.pack(fill="both", expand=True, pady=(2, 5))

        # 3. Build Right Viewport Treeview Components
        hdr_right = tk.Frame(self.right_pane, bg=CARD_BG, pady=6, padx=10)
        hdr_right.pack(fill="x")
        tk.Label(hdr_right, text="🎓 Academy Courses Library (Hierarchical Treeview)", font=("Segoe UI", 10, "bold"), fg=ACCENT_COLOR, bg=CARD_BG).pack(side="left")
        
        # Bookmark 2 button
        self.btn_b2 = tk.Button(
            hdr_right, text="🌟 Bookmark 2", bg=SECONDARY_BG, fg=TEXT_COLOR,
            font=("Segoe UI", 8, "bold"), relief="flat", bd=0, padx=12, pady=2,
            command=lambda: self.navigate_to_bookmark(2)
        )
        self.btn_b2.pack(side="right", padx=(5, 0))
        self.controller.bind_hover(self.btn_b2, HIGHLIGHT, SECONDARY_BG)

        # Bookmark 1 button
        self.btn_b1 = tk.Button(
            hdr_right, text="⭐ Bookmark 1", bg=SECONDARY_BG, fg=TEXT_COLOR,
            font=("Segoe UI", 8, "bold"), relief="flat", bd=0, padx=12, pady=2,
            command=lambda: self.navigate_to_bookmark(1)
        )
        self.btn_b1.pack(side="right", padx=(5, 0))
        self.controller.bind_hover(self.btn_b1, HIGHLIGHT, SECONDARY_BG)

        # Treeview Frame
        tree_frame = tk.Frame(self.right_pane, bg=BG_COLOR)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        cols = ("size", "progress", "videos")
        self.tree = ttk.Treeview(
            tree_frame, columns=cols, show="tree headings", 
            style="Trace.Treeview", selectmode="browse"
        )
        
        self.tree.heading("#0", text="Courses & Videos Hierarchy", anchor="w")
        self.tree.heading("size", text="Size", anchor="w")
        self.tree.heading("progress", text="Completed Bar", anchor="w")
        self.tree.heading("videos", text="No. of Videos", anchor="w")
        
        self.tree.column("#0", width=380, minwidth=200, stretch=True, anchor="w")
        self.tree.column("size", width=100, minwidth=70, stretch=False, anchor="w")
        self.tree.column("progress", width=180, minwidth=120, stretch=False, anchor="w")
        self.tree.column("videos", width=100, minwidth=70, stretch=False, anchor="w")
        
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        
        # Configure tag colors for custom manual highlights
        self.tree.tag_configure("highlight_red", foreground="#ff8fa3")
        self.tree.tag_configure("highlight_green", foreground="#a3be8c")
        
        self.tree.bind("<Double-Button-1>", self.on_double_click)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Button-3>", self.show_context_menu)

        # Initialize placeholder cover image
        self.render_cover_image("")
        
        self.load_library_view()

    def get_metadata_path_for_selected(self, item_id):
        # item_id represents the absolute path (either directory or file)
        if not os.path.exists(item_id):
            return item_id
            
        if os.path.isdir(item_id):
            # It is a folder
            return item_id
        else:
            # It is a file. Check its parent directory
            parent_dir = os.path.dirname(item_id)
            
            # Check if parent is a root source directory
            is_parent_root = False
            for r_path in self.controller.config_data.get("media_source_paths", []):
                if os.path.normpath(parent_dir).lower() == os.path.normpath(r_path).lower():
                    is_parent_root = True
                    break
                    
            if is_parent_root:
                # File is directly under root (not in subfolder), so load file metadata
                return item_id
            else:
                # File is inside a subfolder, so load subfolder metadata
                return parent_dir

    def load_metadata_into_inspector(self, target_path):
        self.current_inspector_path = target_path
        
        # Load from SQLite
        conn = sqlite3.connect(self.controller.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT custom_title, notes, rating, image_path, website, tags FROM media_items WHERE path = ?", (target_path,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            title, notes, rating, img_p, website, tags = row
        else:
            title = os.path.basename(target_path)
            notes = ""
            rating = ""
            img_p = ""
            website = ""
            tags = ""
            
        # Update fields
        self.lbl_inspect_title.config(text=title if title else os.path.basename(target_path))
        self.entry_website.delete(0, "end")
        self.entry_website.insert(0, website if website else "")
        self.entry_tags.delete(0, "end")
        self.entry_tags.insert(0, tags if tags else "")
        
        self.text_info.delete("1.0", "end")
        self.text_info.insert("1.0", notes if notes else "")
        
        rating_map = {
            "5": "⭐⭐⭐⭐⭐",
            "4": "⭐⭐⭐⭐",
            "3": "⭐⭐⭐",
            "2": "⭐⭐",
            "1": "⭐"
        }
        display_rating = rating_map.get(rating, "Unrated")
        self.combo_rating.set(display_rating)
        
        self.render_cover_image(img_p)

    def save_inspector_changes(self):
        if not self.current_inspector_path:
            return
            
        target_path = self.current_inspector_path
        website = self.entry_website.get().strip()
        tags = self.entry_tags.get().strip()
        notes = self.text_info.get("1.0", "end-1c").strip()
        
        display_rating = self.combo_rating.get()
        rating_reverse = {
            "⭐⭐⭐⭐⭐": "5",
            "⭐⭐⭐⭐": "4",
            "⭐⭐⭐": "3",
            "⭐⭐": "2",
            "⭐": "1"
        }
        rating = rating_reverse.get(display_rating, "")
        
        # Save to SQLite database
        conn = sqlite3.connect(self.controller.db_path)
        cursor = conn.cursor()
        
        # Check if already exists in media_items
        cursor.execute("SELECT 1 FROM media_items WHERE path = ?", (target_path,))
        exists = cursor.fetchone()
        
        if exists:
            cursor.execute(
                "UPDATE media_items SET website = ?, notes = ?, rating = ?, tags = ? WHERE path = ?",
                (website, notes, rating, tags, target_path)
            )
        else:
            # Insert a new record
            cursor.execute(
                "INSERT INTO media_items (path, custom_title, notes, rating, website, tags, watch_progress_timecode, completion_percentage, total_duration, watched_status, bookmark_1, bookmark_2, folder_tier_shift, size) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (target_path, os.path.basename(target_path), notes, rating, website, tags, "00:00:00", 0.0, "00:00:00", 0, 0, 0, 0, 0)
            )
            
        # Dynamically register any new tags into tags master table
        if tags:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            for tag in tag_list:
                cursor.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
                
        conn.commit()
        conn.close()
        
        self.controller.show_toast("Inspector Saved", "Successfully updated course metadata in database.", "success")
        self.load_library_view()

    def select_cover_image(self, event):
        if not self.current_inspector_path:
            return
            
        file_path = filedialog.askopenfilename(
            title="Select Cover Image",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.gif *.bmp")]
        )
        if file_path:
            file_path = os.path.normpath(file_path)
            
            target_path = self.current_inspector_path
            conn = sqlite3.connect(self.controller.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT 1 FROM media_items WHERE path = ?", (target_path,))
            exists = cursor.fetchone()
            
            if exists:
                cursor.execute("UPDATE media_items SET image_path = ? WHERE path = ?", (file_path, target_path))
            else:
                cursor.execute(
                    "INSERT INTO media_items (path, custom_title, image_path, watch_progress_timecode, completion_percentage, total_duration, watched_status, bookmark_1, bookmark_2, folder_tier_shift, size) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (target_path, os.path.basename(target_path), file_path, "00:00:00", 0.0, "00:00:00", 0, 0, 0, 0, 0)
                )
                
            conn.commit()
            conn.close()
            
            self.render_cover_image(file_path)
            self.controller.show_toast("Cover Image Set", "Successfully updated cover image file path.", "success")

    def render_cover_image(self, img_path):
        self.last_img_path = img_path
        self.cover_canvas.delete("all")
        self.current_cover_image = None
        
        w = self.cover_canvas.winfo_width()
        h = self.cover_canvas.winfo_height()
        if w < 10: w = 240
        if h < 10: h = 200
        
        if img_path and os.path.exists(img_path):
            try:
                if PIL_AVAILABLE:
                    img = Image.open(img_path)
                    img = img.resize((w, h), Image.Resampling.LANCZOS)
                    self.current_cover_image = ImageTk.PhotoImage(img)
                    self.cover_canvas.create_image(w // 2, h // 2, image=self.current_cover_image)
                    return
                else:
                    self.current_cover_image = tk.PhotoImage(file=img_path)
                    self.cover_canvas.create_image(w // 2, h // 2, image=self.current_cover_image)
                    return
            except Exception as e:
                print(f"Error loading cover image: {e}")
                
        # Draw placeholder
        self.cover_canvas.create_rectangle(5, 5, w - 5, h - 5, outline=BORDER_COLOR, dash=(4, 2))
        self.cover_canvas.create_text(w // 2, h // 2 - 15, text="+", font=("Segoe UI", 24), fill=TEXT_MUTED)
        self.cover_canvas.create_text(w // 2, h // 2 + 15, text="Click to Set Cover", font=("Segoe UI", 8, "italic"), fill=TEXT_MUTED)

    def on_canvas_resize(self, event):
        if hasattr(self, "last_img_path") and self.last_img_path:
            self.render_cover_image(self.last_img_path)

    # ==========================================
    # TAG AUTOCOMPLETE POPUP SYSTEM
    # ==========================================
    def show_tag_autocomplete(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape"):
            return
            
        text = self.entry_tags.get()
        parts = text.split(",")
        if not parts:
            self.hide_tag_autocomplete()
            return
            
        last_word = parts[-1].strip()
        if not last_word:
            self.hide_tag_autocomplete()
            return
            
        # Query matching tags from SQLite
        conn = sqlite3.connect(self.controller.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM tags WHERE name LIKE ? LIMIT 5", (last_word + "%",))
        matches = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        if not matches:
            self.hide_tag_autocomplete()
            return
            
        # Create or update listbox popup
        if not hasattr(self, "tag_popup") or not self.tag_popup:
            self.tag_popup = tk.Listbox(
                self.middle_frame, bg=BG_COLOR, fg=TEXT_COLOR, 
                highlightcolor=ACCENT_COLOR, selectbackground=SELECT_BG,
                relief="flat", bd=1, height=len(matches)
            )
            self.tag_popup.bind("<Button-1>", self.on_autocomplete_click)
            self.entry_tags.bind("<KeyPress-Down>", self.navigate_autocomplete)
            self.entry_tags.bind("<KeyPress-Up>", self.navigate_autocomplete)
            self.entry_tags.bind("<Return>", self.on_autocomplete_enter)
            
        # Place listbox popup exactly under entry_tags field
        self.tag_popup.place(x=45, y=65, width=160, height=len(matches) * 18)
        
        self.tag_popup.delete(0, "end")
        for m in matches:
            self.tag_popup.insert("end", m)
            
    def hide_tag_autocomplete(self, event=None):
        if hasattr(self, "tag_popup") and self.tag_popup:
            self.tag_popup.place_forget()
            self.tag_popup = None
            
    def on_autocomplete_click(self, event):
        if not self.tag_popup:
            return
        sel = self.tag_popup.curselection()
        if sel:
            val = self.tag_popup.get(sel[0])
            self.insert_selected_tag(val)
            
    def on_autocomplete_enter(self, event):
        if hasattr(self, "tag_popup") and self.tag_popup:
            sel = self.tag_popup.curselection()
            if sel:
                val = self.tag_popup.get(sel[0])
                self.insert_selected_tag(val)
                return "break"
                
    def navigate_autocomplete(self, event):
        if hasattr(self, "tag_popup") and self.tag_popup:
            size = self.tag_popup.size()
            if size == 0:
                return
            sel = self.tag_popup.curselection()
            curr = sel[0] if sel else -1
            
            if event.keysym == "Down":
                new_sel = (curr + 1) % size
            else:
                new_sel = (curr - 1) % size
                
            self.tag_popup.select_clear(0, "end")
            self.tag_popup.select_set(new_sel)
            self.tag_popup.activate(new_sel)
            return "break"
            
    def insert_selected_tag(self, tag_val):
        text = self.entry_tags.get()
        parts = text.split(",")
        # Replace the last typed tag with selected autocompleted value
        parts[-1] = " " + tag_val if len(parts) > 1 else tag_val
        new_text = ",".join(parts) + ", "
        self.entry_tags.delete(0, "end")
        self.entry_tags.insert(0, new_text)
        self.hide_tag_autocomplete()
        self.entry_tags.focus_set()

    def open_website_url(self):
        url = self.entry_website.get().strip()
        if url:
            if not (url.startswith("http://") or url.startswith("https://")):
                url = "https://" + url
            import webbrowser
            try:
                webbrowser.open(url)
                self.controller.show_toast("Opening Browser", f"Navigating to {url}...", "info")
            except Exception as e:
                messagebox.showerror("Navigation Error", f"Could not open website: {e}")

    def on_tree_select(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        item_id = selected[0]
        target_path = self.get_metadata_path_for_selected(item_id)
        self.load_metadata_into_inspector(target_path)

    def show_context_menu(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
            
        self.tree.selection_set(item_id)
        self.tree.focus(item_id)
        
        menu = tk.Menu(self.tree, tearoff=0)
        
        # Check if folder or file
        is_dir = os.path.isdir(item_id) if os.path.exists(item_id) else False
        
        menu.add_command(label="📂 Open in Explorer", command=lambda: self.context_open_explorer(item_id))
        menu.add_command(label="📝 Rename", command=lambda: self.context_rename(item_id))
        menu.add_separator()
        menu.add_command(label="✅ Mark Complete", command=lambda: self.context_mark_complete(item_id))
        menu.add_command(label="🔄 Start Over", command=lambda: self.context_start_over(item_id))
        menu.add_separator()
        
        # Fetch current bookmarks from DB to show Toggle label properly
        conn = sqlite3.connect(self.controller.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT bookmark_1, bookmark_2 FROM media_items WHERE path = ?", (item_id,))
        row = cursor.fetchone()
        conn.close()
        
        b1 = row[0] if row else 0
        b2 = row[1] if row else 0
        
        lbl_b1 = "⭐ Remove Bookmark 1" if b1 else "⭐ Toggle Bookmark 1"
        lbl_b2 = "🌟 Remove Bookmark 2" if b2 else "🌟 Toggle Bookmark 2"
        
        menu.add_command(label=lbl_b1, command=lambda: self.context_toggle_bookmark(item_id, 1))
        menu.add_command(label=lbl_b2, command=lambda: self.context_toggle_bookmark(item_id, 2))
        menu.add_separator()
        menu.add_command(label="❌ Hide from Academy View", command=lambda: self.context_hide(item_id))
        menu.add_command(label="🗑️ Delete from Disk", command=lambda: self.context_delete(item_id))
        
        # Color Highlight cascade submenu
        menu.add_separator()
        color_menu = tk.Menu(menu, tearoff=0)
        color_menu.add_command(label="🔴 Red Highlight", command=lambda: self.context_set_color(item_id, "red"))
        color_menu.add_command(label="🟢 Green Highlight", command=lambda: self.context_set_color(item_id, "green"))
        color_menu.add_command(label="⚪ Reset to Default", command=lambda: self.context_set_color(item_id, ""))
        menu.add_cascade(label="🎨 Highlight Color", menu=color_menu)
        
        menu.add_separator()
        menu.add_command(label="🔍 Search on Google", command=lambda: self.context_search_google(item_id))
        menu.add_command(label="🤖 Autofill Course Info (Gemini AI)", command=lambda: self.context_search_google_ai(item_id))
        
        menu.post(event.x_root, event.y_root)
        
    def context_open_explorer(self, item_id):
        if not os.path.exists(item_id):
            return
        try:
            if os.path.isdir(item_id):
                os.startfile(item_id)
            else:
                subprocess.Popen(f'explorer /select,"{item_id}"')
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open path: {e}")

    def context_search_google(self, item_id):
        import urllib.parse
        import webbrowser
        name = os.path.basename(item_id)
        if os.path.isfile(item_id):
            name = os.path.splitext(name)[0]
        query = urllib.parse.quote(name)
        url = f"https://www.google.com/search?q={query}"
        try:
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open browser: {e}")

    def context_search_google_ai(self, item_id):
        # 1. Verify Gemini API Key exists
        api_key = self.controller.get_setting("gemini_api_key", "")
        if not api_key:
            messagebox.showwarning("API Key Missing", "Please set your Gemini API Key in Settings first:\nBurger Menu -> Application Settings -> General tab.")
            self.controller.open_settings_window()
            return
            
        import threading
        
        self.controller.show_toast("AI Searching...", "Asking Gemini to fetch metadata in the background...", "info")
        
        def run_api_query():
            import urllib.request
            import json
            
            name = os.path.basename(item_id)
            if os.path.isfile(item_id):
                name = os.path.splitext(name)[0]
                
            # Clean prefixes
            if name.startswith("📁 "):
                name = name[2:]
            elif name.startswith("🎥 "):
                name = name[2:]
                
            prompt = (
                f"Identify the official website, relevant tags (as a comma-separated list), and a brief course description for: \"{name}\".\n"
                f"Provide the response strictly in JSON format matching this schema:\n"
                f'{{"website": "https://...", "tags": "tag1, tag2", "description": "brief description text"}}'
            )
            
            body = {
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }],
                "generationConfig": {
                    "responseMimeType": "application/json"
                }
            }
            
            try:
                req = urllib.request.Request(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={api_key}",
                    data=json.dumps(body).encode('utf-8'),
                    headers={'Content-Type': 'application/json'}
                )
                
                with urllib.request.urlopen(req, timeout=12) as response:
                    res_data = json.loads(response.read().decode('utf-8'))
                    text_out = res_data['candidates'][0]['content']['parts'][0]['text']
                    parsed = json.loads(text_out)
                    
                    website = parsed.get("website", "")
                    tags = parsed.get("tags", "")
                    description = parsed.get("description", "")
                    
                    # Open review dialog in main thread
                    self.tree.after(0, lambda: self.open_gemini_review_dialog(item_id, name, website, tags, description))
            except Exception as e:
                err_msg = str(e)
                self.tree.after(0, lambda: messagebox.showerror("Gemini Query Failed", f"Failed to fetch metadata from Gemini:\n{err_msg}"))
                
        threading.Thread(target=run_api_query, daemon=True).start()

    def open_gemini_review_dialog(self, item_id, course_name, website, tags, description):
        def save_metadata(web, tg, desc):
            try:
                conn = sqlite3.connect(self.controller.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM media_items WHERE path = ?", (item_id,))
                exists = cursor.fetchone()
                
                if not exists:
                    cursor.execute(
                        "INSERT INTO media_items (path, custom_title, website, tags, notes, watch_progress_timecode, completion_percentage, total_duration, watched_status, bookmark_1, bookmark_2, folder_tier_shift, size) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (item_id, os.path.basename(item_id), web, tg, desc, "00:00:00", 0.0, "00:00:00", 0, 0, 0, 0, 0)
                    )
                else:
                    cursor.execute("UPDATE media_items SET website = ?, tags = ?, notes = ? WHERE path = ?", (web, tg, desc, item_id))
                conn.commit()
                conn.close()
                
                # If currently selected, reload inspector viewport
                selected = self.tree.selection()
                if selected and selected[0] == item_id:
                    self.load_metadata_into_inspector(item_id)
                    
                self.load_library_view()
                self.controller.show_toast("Metadata Updated", "Successfully saved Gemini suggestions.", "success")
            except Exception as e:
                messagebox.showerror("Error Saving Info", f"Failed to save metadata: {e}")
                
        GeminiAutofillDialog(self.controller.root, course_name, website, tags, description, save_metadata)

    def context_set_color(self, item_id, color_name):
        try:
            conn = sqlite3.connect(self.controller.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM media_items WHERE path = ?", (item_id,))
            exists = cursor.fetchone()
            
            if not exists:
                cursor.execute(
                    "INSERT INTO media_items (path, custom_title, highlight_color, watch_progress_timecode, completion_percentage, total_duration, watched_status, bookmark_1, bookmark_2, folder_tier_shift, size) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (item_id, os.path.basename(item_id), color_name, "00:00:00", 0.0, "00:00:00", 0, 0, 0, 0, 0)
                )
            else:
                cursor.execute("UPDATE media_items SET highlight_color = ? WHERE path = ?", (color_name, item_id))
            conn.commit()
            conn.close()
            
            # Reload tree view
            self.load_library_view()
            self.controller.show_toast("Highlight Color", f"Successfully set color to {color_name if color_name else 'default'}.", "success")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to set highlight color: {e}")

    def context_rename(self, item_id):
        bbox = self.tree.bbox(item_id, column="#0")
        if not bbox:
            return
        x, y, w, h = bbox
        cur_text = self.tree.item(item_id, "text")
        
        if cur_text.startswith("📁 "):
            cur_text = cur_text[2:]
        elif cur_text.startswith("🎥 "):
            cur_text = cur_text[2:]
            
        self.editing_entry = tk.Entry(self.tree, font=("Segoe UI", 9), bd=0, highlightthickness=1, highlightcolor=HIGHLIGHT)
        self.editing_entry.insert(0, cur_text)
        self.editing_entry.select_range(0, tk.END)
        self.editing_entry.place(x=x + 20, y=y, width=max(w - 20, 160), height=h)
        self.editing_entry.focus_set()
        
        self.editing_item = item_id
        self.editing_entry.bind("<Return>", self.save_tree_rename)
        self.editing_entry.bind("<FocusOut>", self.save_tree_rename)
        self.editing_entry.bind("<Escape>", self.cancel_tree_rename)

    def save_tree_rename(self, event):
        if not hasattr(self, "editing_entry") or not self.editing_entry:
            return
        item_id = self.editing_item
        new_name = self.editing_entry.get().strip()
        self.destroy_tree_editing_box()
        
        if not new_name:
            return
            
        conn = sqlite3.connect(self.controller.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM media_items WHERE path = ?", (item_id,))
        exists = cursor.fetchone()
        
        if exists:
            cursor.execute("UPDATE media_items SET custom_title = ? WHERE path = ?", (new_name, item_id))
        else:
            cursor.execute(
                "INSERT INTO media_items (path, custom_title, watch_progress_timecode, completion_percentage, total_duration, watched_status, bookmark_1, bookmark_2, folder_tier_shift, size) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (item_id, new_name, "00:00:00", 0.0, "00:00:00", 0, 0, 0, 0, 0)
            )
        conn.commit()
        conn.close()
        
        self.controller.show_toast("Renamed", "Successfully updated title in library database.", "success")
        self.load_library_view()

    def cancel_tree_rename(self, event):
        self.destroy_tree_editing_box()

    def destroy_tree_editing_box(self):
        if hasattr(self, "editing_entry") and self.editing_entry:
            self.editing_entry.destroy()
            self.editing_entry = None
            self.editing_item = None

    def context_mark_complete(self, item_id):
        conn = sqlite3.connect(self.controller.db_path)
        cursor = conn.cursor()
        
        if os.path.isdir(item_id):
            cursor.execute("SELECT path FROM media_items WHERE path LIKE ?", (item_id + "%",))
            sub_paths = [r[0] for r in cursor.fetchall()]
            for p in sub_paths:
                cursor.execute("UPDATE media_items SET completion_percentage = 100.0, watched_status = 1 WHERE path = ?", (p,))
        
        cursor.execute("SELECT 1 FROM media_items WHERE path = ?", (item_id,))
        if cursor.fetchone():
            cursor.execute("UPDATE media_items SET completion_percentage = 100.0, watched_status = 1 WHERE path = ?", (item_id,))
        else:
            cursor.execute(
                "INSERT INTO media_items (path, custom_title, completion_percentage, watched_status, watch_progress_timecode, total_duration, bookmark_1, bookmark_2, folder_tier_shift, size) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (item_id, os.path.basename(item_id), 100.0, 1, "00:00:00", "00:00:00", 0, 0, 0, 0)
            )
            
        conn.commit()
        conn.close()
        self.controller.show_toast("Marked Complete", "Set progress to 100% complete.", "success")
        self.load_library_view()

    def context_start_over(self, item_id):
        conn = sqlite3.connect(self.controller.db_path)
        cursor = conn.cursor()
        
        if os.path.isdir(item_id):
            cursor.execute("SELECT path FROM media_items WHERE path LIKE ?", (item_id + "%",))
            sub_paths = [r[0] for r in cursor.fetchall()]
            for p in sub_paths:
                cursor.execute("UPDATE media_items SET completion_percentage = 0.0, watched_status = 0, watch_progress_timecode = '00:00:00' WHERE path = ?", (p,))
                
        cursor.execute("SELECT 1 FROM media_items WHERE path = ?", (item_id,))
        if cursor.fetchone():
            cursor.execute("UPDATE media_items SET completion_percentage = 0.0, watched_status = 0, watch_progress_timecode = '00:00:00' WHERE path = ?", (item_id,))
        else:
            cursor.execute(
                "INSERT INTO media_items (path, custom_title, completion_percentage, watched_status, watch_progress_timecode, total_duration, bookmark_1, bookmark_2, folder_tier_shift, size) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (item_id, os.path.basename(item_id), 0.0, 0, "00:00:00", "00:00:00", 0, 0, 0, 0)
            )
            
        conn.commit()
        conn.close()
        self.controller.show_toast("Started Over", "Reset watched progress states to 0%.", "info")
        self.load_library_view()

    def context_toggle_bookmark(self, item_id, bookmark_num):
        conn = sqlite3.connect(self.controller.db_path)
        cursor = conn.cursor()
        
        col = "bookmark_1" if bookmark_num == 1 else "bookmark_2"
        cursor.execute(f"SELECT {col} FROM media_items WHERE path = ?", (item_id,))
        row = cursor.fetchone()
        
        curr_val = row[0] if row else 0
        new_val = 1 - curr_val
        
        if row:
            cursor.execute(f"UPDATE media_items SET {col} = ? WHERE path = ?", (new_val, item_id))
        else:
            cursor.execute(
                f"INSERT INTO media_items (path, custom_title, {col}, watch_progress_timecode, completion_percentage, total_duration, watched_status, folder_tier_shift, size) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (item_id, os.path.basename(item_id), new_val, "00:00:00", 0.0, "00:00:00", 0, 0, 0)
            )
            
        conn.commit()
        conn.close()
        
        msg = f"Bookmark {bookmark_num} toggled."
        self.controller.show_toast("Bookmarked", msg, "success")
        self.load_library_view()

    def context_hide(self, item_id):
        conn = sqlite3.connect(self.controller.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO academy_exclusions (path) VALUES (?)", (item_id,))
        conn.commit()
        conn.close()
        
        self.controller.show_toast("Path Hidden", "Added to exclusions list.", "success")
        self.load_library_view()
        
        if hasattr(self.controller, "refresh_settings_exclusions_list"):
            self.controller.refresh_settings_exclusions_list()

    def context_delete(self, item_id):
        if not os.path.exists(item_id):
            return
            
        is_dir = os.path.isdir(item_id)
        msg = f"Are you sure you want to permanently delete this folder and all its contents from disk?\n\n{item_id}" if is_dir else f"Are you sure you want to permanently delete this video file from disk?\n\n{item_id}"
        
        if messagebox.askyesno("⚠️ Confirm Permanent Delete", msg, icon="warning"):
            try:
                if is_dir:
                    import shutil
                    shutil.rmtree(item_id)
                else:
                    os.remove(item_id)
                    
                conn = sqlite3.connect(self.controller.db_path)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM media_items WHERE path = ?", (item_id,))
                if is_dir:
                    cursor.execute("DELETE FROM media_items WHERE path LIKE ?", (item_id + "%",))
                conn.commit()
                conn.close()
                
                self.controller.show_toast("Deleted", "Item successfully deleted from disk.", "success")
                self.load_library_view()
            except Exception as e:
                messagebox.showerror("Delete Failed", f"Failed to delete path: {e}")

    def navigate_to_bookmark(self, bookmark_num):
        col = "bookmark_1" if bookmark_num == 1 else "bookmark_2"
        conn = sqlite3.connect(self.controller.db_path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT path FROM media_items WHERE {col} = 1 LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            msg = f"No Bookmark {bookmark_num} set yet. Right-click a course or video to toggle bookmarks!"
            self.controller.show_toast("Bookmark Empty", msg, "info")
            return
            
        target_path = os.path.normpath(row[0])
        
        if self.tree.exists(target_path):
            parent_iid = self.tree.parent(target_path)
            while parent_iid:
                self.tree.item(parent_iid, open=True)
                parent_iid = self.tree.parent(parent_iid)
                
            self.tree.see(target_path)
            self.tree.selection_set(target_path)
            self.tree.focus(target_path)
            
            self.load_metadata_into_inspector(self.get_metadata_path_for_selected(target_path))
            self.controller.show_toast("Navigated", f"Selected bookmarked item in library view.", "success")
        else:
            self.controller.show_toast("Not Found", "Bookmarked path is not present in the current library tree.", "error")

    def paste_image_from_clipboard(self):
        if not self.current_inspector_path:
            return
        try:
            # First, check if the clipboard contains a URL text link
            try:
                clip_text = self.parent.clipboard_get().strip()
                if clip_text.startswith("http://") or clip_text.startswith("https://"):
                    self.download_image_from_url_string(clip_text)
                    return
            except Exception:
                pass # Clipboard does not contain text or clipboard read failed
                
            from PIL import ImageGrab
            img = ImageGrab.grabclipboard()
            if img is None:
                messagebox.showinfo("Paste Failed", "No image or URL link found on clipboard.\nCopy an image or paste a direct image URL first.")
                return
            if isinstance(img, list):
                if img and os.path.exists(img[0]):
                    img = Image.open(img[0])
                else:
                    return
            self.open_cropping_window(img)
        except Exception as e:
            messagebox.showerror("Clipboard Error", f"Failed to grab image from clipboard: {e}")

    def download_image_from_url(self):
        if not self.current_inspector_path:
            return
        url = simpledialog.askstring("Grab Cover from URL", "Paste direct image URL:", parent=self.parent)
        if not url:
            return
        self.download_image_from_url_string(url)

    def download_image_from_url_string(self, url):
        try:
            import urllib.request
            from io import BytesIO
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as response:
                data = response.read()
                img = Image.open(BytesIO(data))
            self.open_cropping_window(img)
        except Exception as e:
            messagebox.showerror("Download Failed", f"Failed to download image: {e}\nMake sure it is a direct link (ending in .jpg, .png, etc.).")

    def edit_current_cover(self):
        if not self.current_inspector_path:
            return
            
        conn = sqlite3.connect(self.controller.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT image_path FROM media_items WHERE path = ?", (self.current_inspector_path,))
        row = cursor.fetchone()
        conn.close()
        
        img_path = row[0] if row else None
        if img_path and os.path.exists(img_path):
            try:
                img = Image.open(img_path)
                self.open_cropping_window(img)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load image for editing: {e}")
        else:
            self.controller.show_toast("No Cover Set", "There is no cover image set for this course to edit.", "info")
            
    def remove_current_cover(self):
        if not self.current_inspector_path:
            return
            
        if messagebox.askyesno("Remove Cover", "Are you sure you want to remove the cover art for this item?"):
            conn = sqlite3.connect(self.controller.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE media_items SET image_path = NULL WHERE path = ?", (self.current_inspector_path,))
            conn.commit()
            conn.close()
            
            self.render_cover_image("")
            self.controller.show_toast("Cover Removed", "Successfully removed cover art.", "success")

    def open_cropping_window(self, pil_img):
        CroppingWindow(self.parent, pil_img, self.save_cropped_cover_image)

    def save_cropped_cover_image(self, cropped_img):
        if not self.current_inspector_path:
            return
        app_dir = os.path.dirname(os.path.abspath(__file__))
        covers_dir = os.path.join(app_dir, "covers")
        os.makedirs(covers_dir, exist_ok=True)
        
        import hashlib
        path_hash = hashlib.md5(self.current_inspector_path.encode('utf-8')).hexdigest()[:12]
        filename = f"cover_{path_hash}.png"
        save_path = os.path.join(covers_dir, filename)
        
        try:
            cropped_img.save(save_path, "PNG")
            
            target_path = self.current_inspector_path
            conn = sqlite3.connect(self.controller.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM media_items WHERE path = ?", (target_path,))
            exists = cursor.fetchone()
            
            if exists:
                cursor.execute("UPDATE media_items SET image_path = ? WHERE path = ?", (save_path, target_path))
            else:
                cursor.execute(
                    "INSERT INTO media_items (path, custom_title, image_path, watch_progress_timecode, completion_percentage, total_duration, watched_status, bookmark_1, bookmark_2, folder_tier_shift, size) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (target_path, os.path.basename(target_path), save_path, "00:00:00", 0.0, "00:00:00", 0, 0, 0, 0, 0)
                )
            conn.commit()
            conn.close()
            
            self.render_cover_image(save_path)
            self.controller.show_toast("Cover Saved", "Cropped image successfully saved to disk.", "success")
        except Exception as e:
            messagebox.showerror("Error Saving Cover", f"Failed to write image file: {e}")



    def load_library_view(self):
        # 1. Record currently open/expanded node paths to preserve collapse state
        open_nodes = set()
        for item in self.tree.get_children(""):
            def collect_open(iid):
                if self.tree.item(iid, "open"):
                    open_nodes.add(os.path.normpath(iid).lower())
                for c in self.tree.get_children(iid):
                    collect_open(c)
            collect_open(item)

        self.tree.delete(*self.tree.get_children())
        
        # 2. Query exclusions
        try:
            conn = sqlite3.connect(self.controller.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT path FROM academy_exclusions")
            excluded = {os.path.normpath(row[0]).lower() for row in cursor.fetchall()}
            conn.close()
        except Exception as e:
            print(f"Error loading exclusions: {e}")
            excluded = set()

        # Query media items from SQLite
        try:
            conn = sqlite3.connect(self.controller.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT path, custom_title, completion_percentage, watched_status, size, notes, highlight_color FROM media_items")
            rows = cursor.fetchall()
            conn.close()
        except Exception as e:
            print(f"Error loading Academy library data: {e}")
            return
            
        if not rows:
            return
            
        # Build tree representation matching media_source_paths
        roots = {}
        for r_path in self.controller.config_data.get("media_source_paths", []):
            norm_root = os.path.normpath(r_path)
            roots[norm_root] = TreeNode(norm_root, is_dir=True)
            
        # Group items under roots
        for path, title, pct, watched, size, notes, h_color in rows:
            path = os.path.normpath(path)
            
            # Check if this path or any parent path matches the exclusion list
            is_excluded = False
            curr_p = path
            while True:
                if curr_p.lower() in excluded:
                    is_excluded = True
                    break
                parent = os.path.dirname(curr_p)
                if parent == curr_p:
                    break
                curr_p = parent
                
            if is_excluded:
                continue
                
            matched_root = None
            for r_path in roots:
                if path.lower() == r_path.lower() or path.lower().startswith(r_path.lower() + os.sep.lower()):
                    matched_root = r_path
                    break
                    
            if not matched_root:
                continue
                
            # Build subdirectories dynamically relative to matched_root
            rel_path = os.path.relpath(path, matched_root)
            components = [c for c in rel_path.split(os.sep) if c]
            
            is_dir_on_disk = os.path.isdir(path)
            
            curr_node = roots[matched_root]
            for i, comp in enumerate(components):
                is_last = (i == len(components) - 1)
                node_is_dir = True
                if is_last:
                    node_is_dir = is_dir_on_disk
                if comp not in curr_node.children:
                    curr_node.children[comp] = TreeNode(comp, is_dir=node_is_dir)
                curr_node = curr_node.children[comp]
                
            # Set properties on node
            if not is_dir_on_disk:
                curr_node.name = title if title else os.path.basename(path)
                curr_node.size = size if size else 0
                curr_node.completed_pct = pct
                curr_node.num_videos = 1
                curr_node.all_video_pcts = [pct]
                curr_node.has_notes = bool(notes and notes.strip())
                curr_node.highlight_color = h_color if h_color else ""
            else:
                if title:
                    curr_node.name = title
                if notes and notes.strip():
                    curr_node.has_notes = True
                curr_node.highlight_color = h_color if h_color else ""

        # Calculate statistics recursively
        def compute_cumulative_stats(node):
            if not node.is_dir:
                return node.size, node.all_video_pcts, node.num_videos, node.has_notes
                
            total_size = 0
            all_pcts = []
            total_videos = 0
            has_notes = node.has_notes
            
            for child in node.children.values():
                c_size, c_pcts, c_vids, c_notes = compute_cumulative_stats(child)
                total_size += c_size
                all_pcts.extend(c_pcts)
                total_videos += c_vids
                if c_notes:
                    has_notes = True
                    
            node.size = total_size
            node.all_video_pcts = all_pcts
            node.num_videos = total_videos
            node.completed_pct = sum(all_pcts) / len(all_pcts) if all_pcts else 0.0
            node.has_notes = has_notes
            
            return total_size, all_pcts, total_videos, has_notes

        # Compute stats for all root node folders
        for root_node in roots.values():
            compute_cumulative_stats(root_node)

        # Populates Treeview rows recursively
        def populate_tree_recursive(parent_iid, node, node_path, parent_highlight=""):
            is_top_root = (parent_iid == "")
            active_highlight = node.highlight_color if node.highlight_color else parent_highlight
            
            tags = ()
            if active_highlight and not is_top_root:
                if active_highlight == "red":
                    tags = ("highlight_red",)
                elif active_highlight == "green":
                    tags = ("highlight_green",)
            
            if node.is_dir:
                size_str = format_size(node.size)
                progress_str = make_progress_bar(node.completed_pct)
                vids_str = f"{node.num_videos} videos"
                
                # Check if it is one of the top root paths
                is_top_root = (parent_iid == "")
                norm_node_path = os.path.normpath(node_path).lower()
                is_open = is_top_root or (norm_node_path in open_nodes)
                
                # Render node display name with notes symbol overlay
                name_suffix = " 📝" if node.has_notes else ""
                
                if is_top_root:
                    display_name = f"{node.name}{name_suffix}"
                    item_id = self.tree.insert(
                        parent_iid, "end", iid=node_path, text=display_name,
                        values=(size_str, progress_str, vids_str), open=is_open, tags=tags
                    )
                else:
                    display_name = f"📁 {node.name}{name_suffix}"
                    item_id = self.tree.insert(
                        parent_iid, "end", iid=node_path, text=display_name,
                        values=(size_str, progress_str, vids_str), open=is_open, tags=tags
                    )
                
                # Sort children: directories first, then files
                sorted_kids = sorted(
                    node.children.items(),
                    key=lambda x: (not x[1].is_dir, x[0].lower())
                )
                for c_name, c_node in sorted_kids:
                    c_path = os.path.join(node_path, c_name)
                    # Pass the active highlight down recursively (exclude passing if it's the top level root drive node)
                    pass_down_highlight = active_highlight if not is_top_root else ""
                    populate_tree_recursive(item_id, c_node, c_path, parent_highlight=pass_down_highlight)
            else:
                size_str = format_size(node.size)
                progress_str = f"{node.completed_pct:.1f}%"
                vids_str = ""
                name_suffix = " 📝" if node.has_notes else ""
                display_name = f"🎥 {node.name}{name_suffix}"
                
                self.tree.insert(
                    parent_iid, "end", iid=node_path, text=display_name,
                    values=(size_str, progress_str, vids_str), tags=tags
                )

        # Draw each root in the tree table
        for r_path, r_node in sorted(roots.items()):
            populate_tree_recursive("", r_node, r_path, parent_highlight="")

    def on_double_click(self, event):
        selected_items = self.tree.selection()
        if not selected_items:
            return
        item_id = selected_items[0]
        # Check if double clicked file is a physical file
        if os.path.exists(item_id) and os.path.isfile(item_id):
            try:
                import vlc
                inst = vlc.Instance()
                player = inst.media_player_new()
                del player
                del inst
                
                # Open inside our high-performance floating player window
                EmbeddedVideoPlayer(self.parent, item_id, self.controller)
            except Exception as e:
                print(f"libvlc load error: {e}")
                msg = "To play videos inside the app, please install VLC Media Player (free & open-source).\n\nWould you like to open the official VLC download page now?"
                if messagebox.askyesno("VLC Player Required", msg):
                    import webbrowser
                    webbrowser.open("https://www.videolan.org/vlc/")
                else:
                    # Fallback to system default media player
                    try:
                        os.startfile(item_id)
                        self.controller.show_toast("Opening Video", f"Opening {os.path.basename(item_id)} in system player.", "success")
                    except Exception as ex:
                        print(f"Error starting video file: {ex}")

    def shutdown_player(self):
        pass

class EmbeddedVideoPlayer(tk.Toplevel):
    def __init__(self, parent, video_path, controller):
        super().__init__(parent)
        self.video_path = video_path
        self.controller = controller
        
        self.title(f"🎥 Playing: {os.path.basename(video_path)}")
        self.configure(bg=BG_COLOR)
        self.transient(parent)
        self.grab_set()
        
        # 90% size of parent window, centered
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        
        if parent_w < 100: parent_w = 1024
        if parent_h < 100: parent_h = 768
        
        w = int(parent_w * 0.90)
        h = int(parent_h * 0.90)
        x = parent_x + (parent_w - w) // 2
        y = parent_y + (parent_h - h) // 2
        
        self.geometry(f"{w}x{h}+{x}+{y}")
        
        # Header bar
        self.header = tk.Frame(self, bg=HEADER_BG, height=36)
        self.header.pack(fill="x", side="top")
        self.header.pack_propagate(False)
        
        self.lbl_title = tk.Label(
            self.header, text=f"🎥 Playing: {os.path.basename(video_path)}", 
            font=("Segoe UI", 10, "bold"), fg=TEXT_COLOR, bg=HEADER_BG
        )
        self.lbl_title.pack(side="left", padx=15)
        
        # Notes Toggle Button
        self.btn_notes_toggle = tk.Button(
            self.header, text="🗒️ Notes", bg=SECONDARY_BG, fg=TEXT_COLOR,
            font=("Segoe UI", 8, "bold"), relief="flat", bd=0, padx=12, pady=4,
            command=self.toggle_notes_panel
        )
        self.btn_notes_toggle.pack(side="right", padx=5)
        self.controller.bind_hover(self.btn_notes_toggle, HIGHLIGHT, SECONDARY_BG)
        
        # Screenshot Button
        btn_snap = tk.Button(
            self.header, text="📸 Snapshot", bg=SECONDARY_BG, fg=TEXT_COLOR,
            font=("Segoe UI", 8, "bold"), relief="flat", bd=0, padx=12, pady=4,
            command=self.take_screenshot
        )
        btn_snap.pack(side="right", padx=5)
        self.controller.bind_hover(btn_snap, HIGHLIGHT, SECONDARY_BG)
        
        # Body
        self.split_frame = tk.Frame(self, bg=BG_COLOR)
        self.split_frame.pack(fill="both", expand=True)
        
        self.canvas_frame = tk.Frame(self.split_frame, bg="#000000")
        self.canvas_frame.pack(side="left", fill="both", expand=True)
        
        self.video_canvas = tk.Canvas(self.canvas_frame, bg="#000000", highlightthickness=0)
        self.video_canvas.pack(fill="both", expand=True)
        
        # Notes sidebar panel
        self.notes_panel = tk.Frame(self.split_frame, bg=CARD_BG, width=320)
        self.notes_panel.pack_propagate(False)
        
        lbl_notes = tk.Label(self.notes_panel, text="🗒️ Video Notes", font=("Segoe UI", 10, "bold"), fg=ACCENT_COLOR, bg=CARD_BG)
        lbl_notes.pack(anchor="w", padx=10, pady=(10, 5))
        
        self.notes_text = tk.Text(self.notes_panel, bg=BG_COLOR, fg=TEXT_COLOR, insertbackground=TEXT_COLOR, relief="flat", wrap="word", font=("Segoe UI", 9))
        self.notes_text.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Quick Timecoded Note Input Frame
        input_frame = tk.Frame(self.notes_panel, bg=CARD_BG)
        input_frame.pack(fill="x", padx=10, pady=5)
        
        btn_add_time = tk.Button(
            input_frame, text="⏱️ Add Time", bg=SECONDARY_BG, fg=TEXT_COLOR,
            font=("Segoe UI", 9, "bold"), relief="flat", bd=0, padx=15, pady=6,
            command=self.add_timecoded_note
        )
        btn_add_time.pack(fill="x", expand=True)
        self.controller.bind_hover(btn_add_time, HIGHLIGHT, SECONDARY_BG)
        
        btn_save_notes = tk.Button(
            self.notes_panel, text="Save Notes", bg=SUCCESS_COLOR, fg=BG_COLOR,
            font=("Segoe UI", 9, "bold"), relief="flat", bd=0, pady=6,
            command=self.save_notes
        )
        btn_save_notes.pack(fill="x", padx=10, pady=10)
        self.controller.bind_hover(btn_save_notes, HIGHLIGHT, SUCCESS_COLOR)
        
        # Controls footer bar
        self.controls = tk.Frame(self, bg=CARD_BG, height=44)
        self.controls.pack(fill="x", side="bottom")
        self.controls.pack_propagate(False)
        
        self.btn_play = tk.Button(
            self.controls, text="⏸️ Pause", bg=SECONDARY_BG, fg=TEXT_COLOR,
            font=("Segoe UI", 8, "bold"), relief="flat", bd=0, padx=15, pady=4,
            command=self.toggle_play
        )
        self.btn_play.pack(side="left", padx=10, pady=8)
        
        self.time_lbl = tk.Label(self.controls, text="00:00:00 / 00:00:00", font=("Segoe UI", 8), fg=TEXT_MUTED, bg=CARD_BG)
        self.time_lbl.pack(side="left", padx=10, pady=8)
        
        self.slider = ttk.Scale(
            self.controls, from_=0, to=1000, orient="horizontal", command=self.on_slider_change
        )
        self.slider.pack(side="left", fill="x", expand=True, padx=15, pady=8)
        
        self.btn_fs = tk.Button(
            self.controls, text="📺 Fullscreen", bg=SECONDARY_BG, fg=TEXT_COLOR,
            font=("Segoe UI", 8, "bold"), relief="flat", bd=0, padx=15, pady=4,
            command=self.toggle_fullscreen
        )
        self.btn_fs.pack(side="right", padx=10, pady=8)
        
        self.is_updating_slider = False
        
        # libvlc player setup
        import vlc
        self.vlc_instance = vlc.Instance()
        self.media_player = self.vlc_instance.media_player_new()
        
        win_id = self.video_canvas.winfo_id()
        if os.name == 'nt':
            self.media_player.set_hwnd(win_id)
        else:
            self.media_player.set_xwindow(win_id)
            
        media = self.vlc_instance.media_new(video_path)
        self.media_player.set_media(media)
        
        # Load progress if we have it
        self.load_progress()
        
        self.media_player.play()
        self.is_playing = True
        self.is_fullscreen = False
        self.notes_open = False
        
        # Load notes
        self.load_notes_content()
        
        # Tracker loop
        self.tracker_active = True
        self.tracker_loop()
        
        # Bind keyboard shortcuts safely
        DEFAULT_SHORTCUTS = {
            "play_pause": "space",
            "seek_forward": "Right",
            "seek_backward": "Left",
            "speed_up": "Up",
            "speed_down": "Down",
            "add_time": "Control-t",
            "bookmark_1": "Control-1",
            "bookmark_2": "Control-2",
            "snapshot": "Control-s",
            "notes_toggle": "Control-n",
            "fullscreen": "f"
        }
        
        def bind_safe(binding_key, callback, focus_check=True):
            binding_str = self.get_setting_helper(f"shortcut_{binding_key}", DEFAULT_SHORTCUTS[binding_key])
            
            def wrapped(event):
                # If focus check is active and focus is inside notes_text, let it edit text instead of triggering hotkeys
                if focus_check and self.focus_get() == self.notes_text:
                    if binding_key in ("play_pause", "seek_forward", "seek_backward", "speed_up", "speed_down", "fullscreen"):
                        return
                callback()
                return "break"
                
            try:
                self.bind(f"<{binding_str}>", wrapped)
            except Exception as e:
                print(f"Error binding key <{binding_str}>: {e}")
                try:
                    self.bind(f"<{DEFAULT_SHORTCUTS[binding_key]}>", wrapped)
                except:
                    pass
                    
        bind_safe("play_pause", self.toggle_play)
        bind_safe("seek_forward", lambda: self.seek_relative(10000))
        bind_safe("seek_backward", lambda: self.seek_relative(-10000))
        bind_safe("speed_up", lambda: self.adjust_speed(0.25))
        bind_safe("speed_down", lambda: self.adjust_speed(-0.25))
        bind_safe("add_time", self.add_timecoded_note, focus_check=False)
        bind_safe("bookmark_1", self.toggle_bookmark_1, focus_check=False)
        bind_safe("bookmark_2", self.toggle_bookmark_2, focus_check=False)
        bind_safe("snapshot", self.take_screenshot, focus_check=False)
        bind_safe("notes_toggle", self.toggle_notes_panel, focus_check=False)
        bind_safe("fullscreen", self.toggle_fullscreen, focus_check=True)
        
        self.protocol("WM_DELETE_WINDOW", self.close_player)
        
    def load_progress(self):
        try:
            conn = sqlite3.connect(self.controller.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT watch_progress_timecode FROM media_items WHERE path = ?", (self.video_path,))
            row = cursor.fetchone()
            conn.close()
            
            if row and row[0]:
                tc = row[0].split(":")
                if len(tc) == 3:
                    ms = (int(tc[0]) * 3600 + int(tc[1]) * 60 + int(tc[2])) * 1000
                    # Wait briefly for media to initialize before setting position
                    self.after(500, lambda: self.media_player.set_time(ms))
        except Exception as e:
            print(f"Error loading progress: {e}")
            
    def save_progress(self):
        try:
            t_ms = self.media_player.get_time()
            length_ms = self.media_player.get_length()
            if t_ms < 0: t_ms = 0
            
            # Convert milliseconds to HH:MM:SS
            s = t_ms // 1000
            h = s // 3600
            m = (s % 3600) // 60
            sec = s % 60
            tc_str = f"{h:02d}:{m:02d}:{sec:02d}"
            
            pct = 0.0
            if length_ms > 0:
                pct = min(100.0, (t_ms / length_ms) * 100.0)
                
            conn = sqlite3.connect(self.controller.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM media_items WHERE path = ?", (self.video_path,))
            exists = cursor.fetchone()
            
            if exists:
                cursor.execute(
                    "UPDATE media_items SET watch_progress_timecode = ?, completion_percentage = ? WHERE path = ?",
                    (tc_str, pct, self.video_path)
                )
            else:
                cursor.execute(
                    "INSERT INTO media_items (path, custom_title, watch_progress_timecode, completion_percentage, total_duration, watched_status, bookmark_1, bookmark_2, folder_tier_shift, size) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (self.video_path, os.path.basename(self.video_path), tc_str, pct, "00:00:00", 0, 0, 0, 0, 0)
                )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error saving progress: {e}")

    def tracker_loop(self):
        if not self.tracker_active:
            return
            
        try:
            t_ms = self.media_player.get_time()
            length_ms = self.media_player.get_length()
            
            if t_ms >= 0 and length_ms > 0:
                # Format current / total time
                cur_s = t_ms // 1000
                tot_s = length_ms // 1000
                
                cur_str = f"{cur_s // 3600:02d}:{(cur_s % 3600) // 60:02d}:{cur_s % 60:02d}"
                tot_str = f"{tot_s // 3600:02d}:{(tot_s % 3600) // 60:02d}:{tot_s % 60:02d}"
                
                self.time_lbl.config(text=f"{cur_str} / {tot_str}")
                
                # Update slider position without triggering recursive seek command
                self.is_updating_slider = True
                pct = (t_ms / length_ms) * 1000.0
                self.slider.set(pct)
                self.is_updating_slider = False
        except Exception as e:
            print(f"Tracker error: {e}")
            
        self.after(1000, self.tracker_loop)

    def on_slider_change(self, val):
        if not hasattr(self, "is_updating_slider") or not self.is_updating_slider:
            try:
                length_ms = self.media_player.get_length()
                if length_ms > 0:
                    pct = float(val) / 1000.0
                    target_ms = int(pct * length_ms)
                    self.media_player.set_time(target_ms)
            except Exception as e:
                print(f"Slider change error: {e}")

    def toggle_play(self):
        if self.is_playing:
            self.media_player.pause()
            self.btn_play.config(text="▶️ Play")
        else:
            self.media_player.play()
            self.btn_play.config(text="⏸️ Pause")
        self.is_playing = not self.is_playing

    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)
        if self.is_fullscreen:
            self.header.pack_forget()
            self.controls.pack_forget()
        else:
            self.header.pack(fill="x", side="top")
            self.controls.pack(fill="x", side="bottom")

    def toggle_notes_panel(self):
        self.notes_open = not self.notes_open
        if self.notes_open:
            self.notes_panel.pack(side="right", fill="y")
        else:
            self.notes_panel.pack_forget()

    def get_setting_helper(self, key, default=None):
        try:
            conn = sqlite3.connect(self.controller.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            conn.close()
            if row:
                return row[0]
        except:
            pass
        return default

    def set_setting_helper(self, key, val):
        try:
            conn = sqlite3.connect(self.controller.db_path)
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(val)))
            conn.commit()
            conn.close()
        except:
            pass

    def add_timecoded_note(self, event=None):
        # Get current timecode
        t_ms = self.media_player.get_time()
        if t_ms < 0: t_ms = 0
        s = t_ms // 1000
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        tc_str = f"{h:02d}:{m:02d}:{sec:02d}"
        
        content = self.notes_text.get("1.0", "end-1c").strip()
        
        # Tutorial and video names
        video_dir = os.path.dirname(self.video_path)
        tutorial_name = os.path.basename(video_dir)
        video_name = os.path.basename(self.video_path)
        
        # If empty, add formatting header
        if not content:
            content = f"#{tutorial_name}\n### {video_name}\n"
            self.notes_text.insert("1.0", content)
            content = content.strip()
            
        # Count existing numbered items (1., 2., etc.)
        num_items = 0
        lines = content.split("\n")
        for line in lines:
            line_s = line.strip()
            if line_s and line_s[0].isdigit():
                dot_idx = line_s.find(".")
                if dot_idx > 0 and line_s[:dot_idx].isdigit():
                    num_items += 1
                    
        next_num = num_items + 1
        new_line = f"\n{next_num}. ({tc_str}) - "
        
        self.notes_text.insert("end", new_line)
        self.notes_text.see("end")
        self.notes_text.focus_set()
        
        # Save notes to MD and DB
        self.save_notes()

    def load_notes_content(self):
        video_dir = os.path.dirname(self.video_path)
        tutorial_name = os.path.basename(video_dir)
        video_name = os.path.basename(self.video_path)
        
        custom_root = self.get_setting_helper("academy_screenshot_dir", "")
        loaded = False
        
        if custom_root and os.path.exists(custom_root):
            save_dir = os.path.join(custom_root, tutorial_name)
            filename = f"{os.path.splitext(video_name)[0]}_Notes.md"
            save_path = os.path.join(save_dir, filename)
            if os.path.exists(save_path):
                try:
                    with open(save_path, "r", encoding="utf-8") as f:
                         content = f.read()
                         self.notes_text.insert("1.0", content)
                         loaded = True
                except Exception as e:
                    print(f"Error loading md notes: {e}")
                    
        if not loaded:
            try:
                conn = sqlite3.connect(self.controller.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT notes FROM media_items WHERE path = ?", (self.video_path,))
                row = cursor.fetchone()
                conn.close()
                if row and row[0]:
                    self.notes_text.insert("1.0", row[0])
            except Exception as e:
                print(f"Error loading notes from DB: {e}")

    def save_notes(self):
        custom_root = self.get_setting_helper("academy_screenshot_dir", "")
        if not custom_root or not os.path.exists(custom_root):
            messagebox.showwarning("Folder Not Set", "Please set the ScreenShot and Notes folder path in:\nBurger Menu -> Application Settings -> Academy tab.")
            self.controller.open_settings_window()
            return
            
        notes_val = self.notes_text.get("1.0", "end-1c").strip()
        video_dir = os.path.dirname(self.video_path)
        tutorial_name = os.path.basename(video_dir)
        video_name = os.path.basename(self.video_path)
        
        # Save to database
        try:
            conn = sqlite3.connect(self.controller.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM media_items WHERE path = ?", (self.video_path,))
            exists = cursor.fetchone()
            if exists:
                cursor.execute("UPDATE media_items SET notes = ? WHERE path = ?", (notes_val, self.video_path))
            else:
                cursor.execute(
                    "INSERT INTO media_items (path, custom_title, notes, watch_progress_timecode, completion_percentage, total_duration, watched_status, bookmark_1, bookmark_2, folder_tier_shift, size) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (self.video_path, os.path.basename(self.video_path), notes_val, "00:00:00", 0.0, "00:00:00", 0, 0, 0, 0, 0)
                )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Database notes save failed: {e}")

        # Save to Markdown File
        try:
            save_dir = os.path.join(custom_root, tutorial_name)
            os.makedirs(save_dir, exist_ok=True)
            filename = f"{os.path.splitext(video_name)[0]}_Notes.md"
            save_path = os.path.join(save_dir, filename)
            
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(notes_val)
                
            self.controller.show_toast("Notes Saved", f"Saved: {filename}", "success")
            
            if hasattr(self.controller, "academy_view_class") and self.controller.academy_view_class:
                self.controller.academy_view_class.load_library_view()
        except Exception as e:
            messagebox.showerror("Save Notes Failed", f"Failed to save Markdown file: {e}")

    def take_screenshot(self):
        custom_root = self.get_setting_helper("academy_screenshot_dir", "")
        if not custom_root or not os.path.exists(custom_root):
            messagebox.showwarning("Folder Not Set", "Please set the ScreenShot and Notes folder path in:\nBurger Menu -> Application Settings -> Academy tab.")
            self.controller.open_settings_window()
            return
            
        video_dir = os.path.dirname(self.video_path)
        folder_name = os.path.basename(video_dir)
        save_dir = os.path.join(custom_root, folder_name)
        os.makedirs(save_dir, exist_ok=True)
        
        counter_str = self.get_setting_helper("academy_screenshot_counter", "1")
        try:
            counter = int(counter_str)
        except:
            counter = 1
            
        filename = f"{folder_name}_{counter:05d}.jpg"
        save_path = os.path.join(save_dir, filename)
        
        while os.path.exists(save_path):
            counter += 1
            filename = f"{folder_name}_{counter:05d}.jpg"
            save_path = os.path.join(save_dir, filename)
            
        try:
            res = self.media_player.video_take_snapshot(0, save_path, 0, 0)
            if res == 0:
                self.controller.show_toast("Screenshot Saved", f"Saved: {filename}", "success")
                self.set_setting_helper("academy_screenshot_counter", str(counter + 1))
            else:
                self.controller.show_toast("Snapshot Triggered", "Sent capture instruction to media engine.", "info")
                self.set_setting_helper("academy_screenshot_counter", str(counter + 1))
        except Exception as e:
            messagebox.showerror("Capture Failed", f"Failed to capture snapshot: {e}")

    def seek_relative(self, delta_ms):
        try:
            cur_time = self.media_player.get_time()
            length = self.media_player.get_length()
            target = cur_time + delta_ms
            if target < 0: target = 0
            if length > 0 and target > length: target = length
            self.media_player.set_time(target)
        except Exception as e:
            print(f"Error seeking: {e}")

    def adjust_speed(self, delta_rate):
        try:
            curr_rate = self.media_player.get_rate()
            target_rate = max(0.25, min(4.0, curr_rate + delta_rate))
            self.media_player.set_rate(target_rate)
            self.controller.show_toast("Playback Speed", f"Speed: {target_rate:.2f}x", "info")
        except Exception as e:
            print(f"Error adjusting speed: {e}")

    def toggle_bookmark_1(self):
        self.toggle_db_bookmark(1)
        
    def toggle_bookmark_2(self):
        self.toggle_db_bookmark(2)
        
    def toggle_db_bookmark(self, num):
        try:
            conn = sqlite3.connect(self.controller.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT bookmark_1, bookmark_2 FROM media_items WHERE path = ?", (self.video_path,))
            row = cursor.fetchone()
            
            if not row:
                b1, b2 = (1, 0) if num == 1 else (0, 1)
                cursor.execute(
                    "INSERT INTO media_items (path, custom_title, bookmark_1, bookmark_2, watch_progress_timecode, completion_percentage, total_duration, watched_status, folder_tier_shift, size) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (self.video_path, os.path.basename(self.video_path), b1, b2, "00:00:00", 0.0, "00:00:00", 0, 0, 0)
                )
                new_state = 1
            else:
                b1, b2 = row[0], row[1]
                if num == 1:
                    new_state = 0 if b1 else 1
                    cursor.execute("UPDATE media_items SET bookmark_1 = ? WHERE path = ?", (new_state, self.video_path))
                else:
                    new_state = 0 if b2 else 1
                    cursor.execute("UPDATE media_items SET bookmark_2 = ? WHERE path = ?", (new_state, self.video_path))
            conn.commit()
            conn.close()
            
            status_text = "Added" if new_state else "Removed"
            self.controller.show_toast(f"Bookmark {num}", f"{status_text} bookmark {num} on video.", "success")
        except Exception as e:
            print(f"Error toggling bookmark: {e}")

    def close_player(self):
        self.tracker_active = False
        self.save_progress()
        self.media_player.stop()
        self.destroy()
        
        if hasattr(self.controller, "academy_view_class") and self.controller.academy_view_class:
            self.controller.academy_view_class.load_library_view()

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
