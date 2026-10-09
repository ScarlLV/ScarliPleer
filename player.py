import os
import io
import csv
import sys
import json
import time
import random
import webbrowser
import threading
from collections import OrderedDict, Counter
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import pygame
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB
from PIL import Image, ImageTk, ImageDraw

try:
    from tkinterdnd2 import DND_FILES
    DND_AVAILABLE = True
except Exception:
    DND_AVAILABLE = False

try:
    import pystray
    from pystray import MenuItem as TrayItem, Menu as TrayMenu
    TRAY_AVAILABLE = True
except Exception:
    TRAY_AVAILABLE = False


# ---------------- CONFIG ----------------
APP_NAME = "ScarliPleer"
APP_VERSION = "0.1.0"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LIBRARY_FILE = os.path.join(BASE_DIR, "library.json")
ICO_FILE = os.path.join(BASE_DIR, "scarli.ico")
STATS_FILE = os.path.join(BASE_DIR, "stats.json")

SUPPORT_URL = "https://dalink.to/fleurdev"

COLOR_BG       = "#121212"
COLOR_SIDEBAR  = "#0A0A0A"
COLOR_CARD     = "#181818"
COLOR_CARD_HOV = "#282828"
COLOR_TEXT     = "#FFFFFF"
COLOR_TEXT_DIM = "#B3B3B3"
COLOR_ACCENT   = "#8B5CF6"
COLOR_ACCENT_H = "#A78BFA"
COLOR_ACCENT_D = "#7C3AED"
COLOR_DANGER   = "#EF4444"
COLOR_TRACK    = "#2a2a2a"

ACCENT_PRESETS = [
    ("Purple",  "#8B5CF6", "#A78BFA", "#7C3AED"),
    ("Blue",    "#3B82F6", "#60A5FA", "#2563EB"),
    ("Green",   "#10B981", "#34D399", "#059669"),
    ("Pink",    "#EC4899", "#F472B6", "#DB2777"),
    ("Orange",  "#F97316", "#FB923C", "#EA580C"),
    ("Red",     "#EF4444", "#F87171", "#DC2626"),
]


# ---------------- HELPERS ----------------
def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*[max(0, min(255, int(c))) for c in rgb])


def lerp_color(a, b, t):
    ra, ga, ba = hex_to_rgb(a)
    rb, gb, bb = hex_to_rgb(b)
    return rgb_to_hex((ra + (rb - ra) * t,
                       ga + (gb - ga) * t,
                       ba + (bb - ba) * t))


def fuzzy_match(query, text):
    if not query:
        return True
    q = query.lower()
    t = text.lower()
    if q in t:
        return True
    it = iter(t)
    return all(ch in it for ch in q)


# ---------------- TOOLTIP ----------------
class Tooltip:
    _tip = None

    def __init__(self, widget, text, delay=450):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._id = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _=None):
        self._cancel()
        self._id = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self._id:
            try: self.widget.after_cancel(self._id)
            except Exception: pass
            self._id = None

    def _show(self):
        if Tooltip._tip:
            try: Tooltip._tip.destroy()
            except Exception: pass
            Tooltip._tip = None
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")
        tip.attributes("-topmost", True)
        frame = tk.Frame(tip, bg=COLOR_ACCENT, bd=0)
        frame.pack()
        tk.Label(frame, text=self.text, bg=COLOR_CARD, fg=COLOR_TEXT,
                 font=("Segoe UI", 9), padx=10, pady=5,
                 bd=0).pack(padx=1, pady=1)
        Tooltip._tip = tip

    def _hide(self, _=None):
        self._cancel()
        if Tooltip._tip:
            try: Tooltip._tip.destroy()
            except Exception: pass
            Tooltip._tip = None


# ---------------- PURPLE SLIDER ----------------
class PurpleSlider(tk.Frame):
    def __init__(self, parent, command=None, length=400, thickness=22,
                 bg=COLOR_CARD, initial=0, live_command=None, accent=None):
        super().__init__(parent, bg=bg, bd=0, highlightthickness=0,
                         width=length, height=thickness)
        self.pack_propagate(False)
        self.grid_propagate(False)
        self.command = command
        self.live_command = live_command
        self._slider_w = length
        self._slider_h = thickness
        self._value = float(initial)
        self._dragging = False
        self._track_h = 4
        self._thumb_r = 7
        self._hover = False
        self._ready = False
        self._accent = accent or COLOR_ACCENT
        self._accent_h = self._accent

        self.canvas = tk.Canvas(self, width=length, height=thickness,
                                bg=bg, bd=0, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Enter>", lambda e: self._redraw(hover=True))
        self.canvas.bind("<Leave>", lambda e: self._redraw(hover=False))
        self.after(0, self._first_draw)

    def set_accent(self, color, hcolor=None):
        self._accent = color
        self._accent_h = hcolor or color
        self._redraw()

    def _first_draw(self):
        self._ready = True
        self._redraw()

    def _on_resize(self, event):
        self._slider_w = event.width
        self._slider_h = event.height
        if self._ready:
            self._redraw()

    def _xy_for_value(self):
        pad = self._thumb_r + 2
        usable = self._slider_w - pad * 2
        return pad + usable * (self._value / 100.0), self._slider_h / 2

    def _value_for_x(self, x):
        pad = self._thumb_r + 2
        usable = self._slider_w - pad * 2
        if usable <= 0:
            return 0.0
        v = (x - pad) / usable * 100.0
        return max(0.0, min(100.0, v))

    def _redraw(self, hover=None):
        if not self._ready:
            return
        if hover is not None:
            self._hover = hover
        c = self.canvas
        c.delete("all")
        cy = self._slider_h / 2
        pad = self._thumb_r + 2
        if self._slider_w <= pad * 2:
            return
        c.create_line(pad, cy, self._slider_w - pad, cy,
                      fill=COLOR_TRACK, width=self._track_h,
                      capstyle="round")
        tx, _ = self._xy_for_value()
        c.create_line(pad, cy, tx, cy, fill=self._accent,
                      width=self._track_h, capstyle="round")
        r = self._thumb_r + (2 if self._hover or self._dragging else 0)
        c.create_oval(tx - r, cy - r, tx + r, cy + r,
                      fill=self._accent_h if self._hover else self._accent,
                      outline="")

    def _on_press(self, event):
        self._dragging = True
        self._set_from_x(event.x, live=True)

    def _on_drag(self, event):
        if self._dragging:
            self._set_from_x(event.x, live=True)

    def _on_release(self, event):
        self._dragging = False
        self._set_from_x(event.x, live=False)
        self._redraw()

    def _set_from_x(self, x, live=False):
        self._value = self._value_for_x(x)
        self._redraw()
        if live and self.live_command:
            self.live_command(self._value)
        elif not live and self.command:
            self.command(self._value)

    def set(self, value):
        self._value = max(0.0, min(100.0, float(value)))
        self._redraw()

    def get(self):
        return self._value


# ---------------- HOVER BUTTON ----------------
class HoverButton(tk.Label):
    def __init__(self, parent, text, command,
                 bg=COLOR_CARD, fg=COLOR_TEXT_DIM, hover_fg=COLOR_ACCENT,
                 font=("Segoe UI", 18), padx=8, pady=2, tooltip=None):
        super().__init__(parent, text=text, bg=bg, fg=fg,
                         font=font, padx=padx, pady=pady, cursor="hand2")
        self.command = command
        self._fg = fg
        self._hover_fg = hover_fg
        self._state_fg = None
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        if tooltip:
            Tooltip(self, tooltip)

    def _on_enter(self, e=None):
        self.configure(fg=COLOR_ACCENT_H if self._state_fg else self._hover_fg)

    def _on_leave(self, e=None):
        self.configure(fg=self._state_fg or self._fg)

    def _on_press(self, e):
        self.configure(fg=COLOR_ACCENT_D)

    def _on_release(self, e):
        self._on_enter()
        if self.command:
            self.command()

    def set_state(self, active):
        self._state_fg = self._hover_fg if active else None
        self.configure(fg=self._state_fg or self._fg)

    def set_colors(self, fg, hover_fg):
        self._fg = fg
        self._hover_fg = hover_fg
        self.configure(fg=self._state_fg or fg)


# ---------------- MAIN APP ----------------
class ScarliPleer(ttk.Window):
    def __init__(self):
        super().__init__(themename="darkly")

        self.title(APP_NAME)
        self.geometry("1180x760")
        self.minsize(1000, 660)
        self.configure(bg=COLOR_BG)

        # accent
        self.accent = COLOR_ACCENT
        self.accent_h = COLOR_ACCENT_H
        self.accent_d = COLOR_ACCENT_D

        # state
        self.playlist = []
        self.filtered = []
        self.current_index = -1
        self.is_playing = False
        self.is_paused = False
        self.song_length = 0
        self.start_time = 0
        self.paused_at = 0
        self.shuffle = False
        self.repeat = False
        self._seeking = False
        self._last_cover = None
        self._album_default = None
        self._cover_size = 300
        self._volume_value = 70.0
        self._last_volume = 70.0
        self._muted = False
        self._placeholder_active = False
        self._loading = False
        self._loading_frame = 0
        self._base_title = APP_NAME
        self.favorites = set()
        self.show_favorites_only = False
        self.sort_mode = "title"
        self.compact = False
        self.play_counts = {}
        self._icon_img = None
        self.accent_choice = tk.StringVar(value="Purple")

        # caches
        self._cover_cache = OrderedDict()
        self._cover_cache_max = 60

        # play tracking
        self._played_seconds = 0
        self._counted_path = None

        # settings
        self.opt_show_duration = True
        self.opt_show_heart = True
        self.opt_show_playcount = False
        self.opt_autostart = False

        # sleep timer
        self._sleep_timer_id = None
        self._sleep_end_time = None

        # stats
        self.stats = {}

        # fullscreen cover
        self._fs_win = None

        # tray
        self._tray_icon = None
        self._tray_thread = None
        self._really_quit = False

        # win32 taskbar
        try:
            if os.name == "nt":
                import ctypes
                self._win32 = ctypes.windll
            else:
                self._win32 = None
        except Exception:
            self._win32 = None

        # style + audio
        self._style_accent()
        try:
            pygame.mixer.pre_init(44100, -16, 2, 512)
            pygame.mixer.init()
        except Exception as e:
            print("audio init error:", e)

        # build
        self._build_ui()
        self._apply_window_icon()
        self.update_idletasks()
        self.after(60, self._apply_window_icon)

        self._bind_hotkeys()
        self._enable_dnd()
        self._load_library()
        self._load_stats()

        self.protocol("WM_DELETE_WINDOW", self._on_close_button)
        self._tick()
        self._loading_tick()

    # ---------------- ICON ----------------
    def _build_icon_pil(self, size=256):
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((size*0.03, size*0.03, size*0.97, size*0.97),
                            radius=int(size*0.22), fill=self.accent)
        d.rectangle((size*0.44, size*0.28, size*0.51, size*0.72),
                    fill="#0A0A0A")
        d.ellipse((size*0.28, size*0.62, size*0.50, size*0.82),
                  fill="#0A0A0A")
        return img

    def _apply_window_icon(self):
        try:
            base = self._build_icon_pil(256)
            base.save(ICO_FILE, format="ICO",
                      sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
            try:
                self.iconbitmap(default=ICO_FILE)
            except Exception:
                try: self.iconbitmap(ICO_FILE)
                except Exception: pass
            self._icon_img = ImageTk.PhotoImage(
                base.resize((64, 64), Image.LANCZOS))
            try:
                self.iconphoto(True, self._icon_img)
            except Exception:
                pass
        except Exception as e:
            print("icon error:", e)

    # ---------------- STYLE ----------------
    def _style_accent(self):
        s = self.style
        s.configure("Accent.TButton",
                    background=self.accent, foreground="white",
                    borderwidth=0, focusthickness=0, focuscolor=self.accent,
                    font=("Segoe UI", 11, "bold"))
        s.map("Accent.TButton",
              background=[("active", self.accent_h), ("pressed", self.accent_d)])
        s.configure("Card.TButton",
                    background=COLOR_CARD, foreground=COLOR_TEXT,
                    borderwidth=0, focusthickness=0, focuscolor=COLOR_CARD,
                    font=("Segoe UI", 10))
        s.map("Card.TButton",
              background=[("active", COLOR_CARD_HOV), ("pressed", "#1f1f1f")])
        s.configure("Danger.TButton",
                    background="#1a0e0e", foreground=COLOR_DANGER,
                    borderwidth=1, focusthickness=0, focuscolor="#1a0e0e",
                    font=("Segoe UI", 10))
        s.map("Danger.TButton",
              background=[("active", "#2a1212"), ("pressed", "#2a1212")])

    # ---------------- UI ----------------
    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_main()

    def _build_sidebar(self):
        self.sidebar = tk.Frame(self, bg=COLOR_SIDEBAR, width=300)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_propagate(False)

        logo_row = tk.Frame(self.sidebar, bg=COLOR_SIDEBAR)
        logo_row.pack(fill="x", pady=(24, 20), padx=20)

        self.logo_label = tk.Label(logo_row, text="◉  ScarliPleer",
                                   bg=COLOR_SIDEBAR, fg=self.accent,
                                   font=("Segoe UI", 18, "bold"))
        self.logo_label.pack(side="left")

        self.gear_btn = HoverButton(logo_row, text="⚙",
                                    command=self._open_settings,
                                    bg=COLOR_SIDEBAR, fg=COLOR_TEXT_DIM,
                                    hover_fg=self.accent,
                                    font=("Segoe UI", 16), padx=4, pady=0,
                                    tooltip="Settings")
        self.gear_btn.pack(side="right")

        # search
        search_wrap = tk.Frame(self.sidebar, bg=COLOR_CARD)
        search_wrap.pack(fill="x", padx=16, pady=(0, 4), ipady=2)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._apply_filter())
        self.search_entry = tk.Entry(search_wrap, textvariable=self.search_var,
                                     bg=COLOR_CARD, fg=COLOR_TEXT,
                                     insertbackground=self.accent,
                                     relief="flat", bd=0, font=("Segoe UI", 11))
        self.search_entry.pack(fill="x", padx=10, pady=8)
        try: self.search_entry.configure(cursor="xterm")
        except Exception: pass
        self._search_placeholder = "Search..."
        self._placeholder_active = False
        self._show_placeholder()
        self.search_entry.bind("<FocusIn>", self._hide_placeholder)
        self.search_entry.bind("<FocusOut>", self._show_placeholder)
        self.search_entry.bind("<Escape>", lambda e: self._clear_search())

        # tabs
        header_row = tk.Frame(self.sidebar, bg=COLOR_SIDEBAR)
        header_row.pack(fill="x", padx=20, pady=(14, 4))
        self.playlist_tab = tk.Label(header_row, text="Playlist",
                                     bg=COLOR_SIDEBAR, fg=self.accent,
                                     font=("Segoe UI", 10, "bold"),
                                     cursor="hand2")
        self.playlist_tab.pack(side="left")
        self.playlist_tab.bind("<Button-1>",
                               lambda e: self._set_favorites_filter(False))
        self.fav_tab = tk.Label(header_row, text="  Favorites",
                                bg=COLOR_SIDEBAR, fg=COLOR_TEXT_DIM,
                                font=("Segoe UI", 10, "bold"),
                                cursor="hand2")
        self.fav_tab.pack(side="left")
        self.fav_tab.bind("<Button-1>",
                          lambda e: self._set_favorites_filter(True))
        self.sort_btn = HoverButton(header_row, text="⇅",
                                    command=self._cycle_sort,
                                    bg=COLOR_SIDEBAR, fg=COLOR_TEXT_DIM,
                                    hover_fg=self.accent,
                                    font=("Segoe UI", 12), padx=4, pady=0,
                                    tooltip="Sort")
        self.sort_btn.pack(side="right")

        # listbox
        lb_frame = tk.Frame(self.sidebar, bg=COLOR_SIDEBAR)
        lb_frame.pack(fill="both", expand=True, padx=12, pady=(0, 4))
        scrollbar = ttk.Scrollbar(lb_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        self.listbox = tk.Listbox(lb_frame, bg=COLOR_SIDEBAR, fg=COLOR_TEXT,
                                  selectbackground=self.accent,
                                  selectforeground="white",
                                  bd=0, highlightthickness=0,
                                  activestyle="none",
                                  font=("Segoe UI", 10),
                                  yscrollcommand=scrollbar.set,
                                  selectmode="extended")
        self.listbox.pack(fill="both", expand=True)
        self.listbox.bind("<Double-Button-1>", self._play_selected)
        self.listbox.bind("<Return>", self._play_selected)
        self.listbox.bind("<Delete>", lambda e: self._delete_selected())
        self.listbox.bind("<Button-3>", self._show_context_menu)
        scrollbar.config(command=self.listbox.yview)

        self.counter_lbl = tk.Label(self.sidebar, text="0 tracks · 0h 0m",
                                    bg=COLOR_SIDEBAR, fg=COLOR_TEXT_DIM,
                                    font=("Segoe UI", 9))
        self.counter_lbl.pack(anchor="w", padx=20, pady=(0, 8))

        # buttons
        btns = tk.Frame(self.sidebar, bg=COLOR_SIDEBAR)
        btns.pack(fill="x", padx=16, pady=(0, 20))
        self.btn_add = ttk.Button(btns, text="+ Add Files",
                                  style="Accent.TButton",
                                  command=self._add_files)
        self.btn_add.pack(fill="x", pady=4, ipady=6)
        self.btn_folder = ttk.Button(btns, text="📂 Add Folder",
                                     style="Card.TButton",
                                     command=self._add_folder)
        self.btn_folder.pack(fill="x", pady=4, ipady=6)
        self.btn_clear = ttk.Button(btns, text="Clear",
                                    style="Danger.TButton",
                                    command=self._clear)
        self.btn_clear.pack(fill="x", pady=(8, 0), ipady=5)

    def _build_main(self):
        self.main_frame = tk.Frame(self, bg=COLOR_BG)
        self.main_frame.grid(row=0, column=1, sticky="nsew")
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        top = tk.Frame(self.main_frame, bg=COLOR_BG)
        top.grid(row=0, column=0, sticky="nsew")
        top.grid_rowconfigure(0, weight=1)
        top.grid_rowconfigure(6, weight=1)
        top.grid_columnconfigure(0, weight=1)

        self.now_playing_lbl = tk.Label(top, text="NOW PLAYING",
                                        bg=COLOR_BG, fg=COLOR_TEXT_DIM,
                                        font=("Segoe UI", 9, "bold"))
        self.now_playing_lbl.grid(row=1, column=0, pady=(40, 14))

        cover_wrap = tk.Frame(top, bg=COLOR_BG)
        cover_wrap.grid(row=2, column=0)

        self._album_default = self._make_default_cover(self._cover_size)
        self.cover_label = tk.Label(cover_wrap, image=self._album_default,
                                    bg=COLOR_BG, bd=0, cursor="hand2")
        self.cover_label.pack()
        self.cover_label.bind("<Double-Button-1>",
                              lambda e: self._open_fullscreen_cover())
        Tooltip(self.cover_label, "Double-click for fullscreen cover")

        self.title_label = tk.Label(top, text="No track selected",
                                    bg=COLOR_BG, fg=COLOR_TEXT,
                                    font=("Segoe UI", 20, "bold"))
        self.title_label.grid(row=3, column=0, pady=(18, 2))

        self.artist_label = tk.Label(top, text="", bg=COLOR_BG,
                                     fg=COLOR_TEXT_DIM,
                                     font=("Segoe UI", 12))
        self.artist_label.grid(row=4, column=0, pady=(0, 12))

        self.status_label = tk.Label(top, text="", bg=COLOR_BG,
                                     fg=self.accent, font=("Segoe UI", 9))
        self.status_label.grid(row=5, column=0, pady=(0, 4))

        self._build_controls(self.main_frame)

    def _build_controls(self, parent):
        bar = tk.Frame(parent, bg=COLOR_CARD, height=140)
        bar.grid(row=1, column=0, sticky="ew")
        bar.pack_propagate(False)

        prog = tk.Frame(bar, bg=COLOR_CARD)
        prog.pack(fill="x", padx=30, pady=(18, 4))
        self.time_now = tk.Label(prog, text="00:00", width=6,
                                 bg=COLOR_CARD, fg=COLOR_TEXT_DIM,
                                 font=("Segoe UI", 10))
        self.time_now.pack(side="left")
        self.progress = PurpleSlider(prog, command=self._seek_release,
                                     live_command=self._seek_live,
                                     length=600, thickness=22,
                                     bg=COLOR_CARD, initial=0,
                                     accent=self.accent)
        self.progress.pack(side="left", fill="x", expand=True, padx=12)
        self.time_end = tk.Label(prog, text="00:00", width=6,
                                 bg=COLOR_CARD, fg=COLOR_TEXT_DIM,
                                 font=("Segoe UI", 10))
        self.time_end.pack(side="left")

        row = tk.Frame(bar, bg=COLOR_CARD)
        row.pack(fill="x", padx=30, pady=(6, 18))

        left = tk.Frame(row, bg=COLOR_CARD)
        left.pack(side="left")
        self.shuffle_btn = HoverButton(left, text="🔀",
                                       command=self._toggle_shuffle,
                                       bg=COLOR_CARD, fg=COLOR_TEXT_DIM,
                                       hover_fg=self.accent,
                                       font=("Segoe UI", 14), padx=8, pady=4,
                                       tooltip="Shuffle (S)")
        self.shuffle_btn.pack(side="left", padx=4)
        self.repeat_btn = HoverButton(left, text="🔁",
                                      command=self._toggle_repeat,
                                      bg=COLOR_CARD, fg=COLOR_TEXT_DIM,
                                      hover_fg=self.accent,
                                      font=("Segoe UI", 14), padx=8, pady=4,
                                      tooltip="Repeat (R)")
        self.repeat_btn.pack(side="left", padx=4)

        center = tk.Frame(row, bg=COLOR_CARD)
        center.pack(side="left", expand=True)
        HoverButton(center, text="⏮", command=self._prev,
                    bg=COLOR_CARD, fg=COLOR_TEXT, hover_fg=self.accent_h,
                    font=("Segoe UI", 22), padx=10, pady=2,
                    tooltip="Previous").pack(side="left", padx=8)

        self.play_btn = tk.Button(center, text="▶", command=self._toggle_play,
                                  bg=self.accent, fg="white",
                                  activebackground=self.accent_h,
                                  activeforeground="white",
                                  bd=0, relief="flat",
                                  font=("Segoe UI", 18, "bold"),
                                  width=3, height=1, cursor="hand2")
        self.play_btn.pack(side="left", padx=8, ipady=4)
        self.play_btn.bind("<Enter>",
                           lambda e: self.play_btn.configure(bg=self.accent_h))
        self.play_btn.bind("<Leave>",
                           lambda e: self.play_btn.configure(bg=self.accent))
        Tooltip(self.play_btn, "Play / Pause (Space)")

        HoverButton(center, text="⏭", command=self._next,
                    bg=COLOR_CARD, fg=COLOR_TEXT, hover_fg=self.accent_h,
                    font=("Segoe UI", 22), padx=10, pady=2,
                    tooltip="Next").pack(side="left", padx=8)

        right = tk.Frame(row, bg=COLOR_CARD)
        right.pack(side="right")

        self.vol_icon = HoverButton(right, text="🔊",
                                    command=self._toggle_mute,
                                    bg=COLOR_CARD, fg=COLOR_TEXT_DIM,
                                    hover_fg=self.accent,
                                    font=("Segoe UI", 13), padx=4, pady=2,
                                    tooltip="Mute (M)")
        self.vol_icon.pack(side="left", padx=(0, 8))

        self.volume = PurpleSlider(right, command=self._set_volume,
                                   length=140, thickness=22,
                                   bg=COLOR_CARD,
                                   initial=self._volume_value,
                                   accent=self.accent)
        self.volume.pack(side="left")

    # ---------------- FULLSCREEN COVER ----------------
    def _open_fullscreen_cover(self):
        if self._fs_win and self._fs_win.winfo_exists():
            self._fs_win.destroy()
            self._fs_win = None
            return
        if self.current_index < 0:
            return
        path = self.playlist[self.current_index]["path"]
        img = self._cover_to_pil(path) or self._cover_to_pil_default()
        win = tk.Toplevel(self)
        win.title(self.playlist[self.current_index]["title"])
        win.configure(bg="#000000")
        win.attributes("-fullscreen", True)
        try: win.iconbitmap(ICO_FILE)
        except Exception: pass
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        size = min(sw, sh) - 80
        photo = ImageTk.PhotoImage(img.resize((size, size), Image.LANCZOS))
        lbl = tk.Label(win, image=photo, bg="#000000", bd=0)
        lbl.image = photo
        lbl.pack(expand=True)
        lbl.bind("<Button-1>", lambda e: self._close_fs())
        win.bind("<Escape>", lambda e: self._close_fs())
        self._fs_win = win

    def _close_fs(self):
        if self._fs_win and self._fs_win.winfo_exists():
            self._fs_win.destroy()
            self._fs_win = None

    def _cover_to_pil(self, path):
        try:
            audio = MP3(path, ID3=ID3)
            if audio.tags:
                for tag in audio.tags.values():
                    if isinstance(tag, APIC):
                        return Image.open(io.BytesIO(tag.data)).convert("RGB")
        except Exception:
            pass
        return None

    def _cover_to_pil_default(self):
        size = 600
        img = Image.new("RGB", (size, size), "#1a1a1a")
        d = ImageDraw.Draw(img)
        for r in range(size // 2 - 6, 40, -18):
            d.ellipse([size//2 - r, size//2 - r, size//2 + r, size//2 + r],
                      outline="#2b2140")
        r = size // 5
        d.ellipse([size//2 - r, size//2 - r, size//2 + r, size//2 + r],
                  fill=self.accent)
        d.rectangle([size//2 - 5, size//2 - 44, size//2 + 5, size//2 + 20],
                    fill="#1a1a1a")
        return img

    # ---------------- SETTINGS ----------------
    def _open_settings(self):
        win = tk.Toplevel(self)
        win.title("Settings")
        win.configure(bg=COLOR_BG)
        win.geometry("560x620")
        win.resizable(False, False)
        win.transient(self)
        try: win.iconbitmap(ICO_FILE)
        except Exception: pass

        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 560) // 2
        y = self.winfo_y() + (self.winfo_height() - 620) // 2
        win.geometry(f"+{x}+{y}")

        canvas = tk.Canvas(win, bg=COLOR_BG, bd=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COLOR_BG)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # --- mouse wheel scrolling ---
        def _on_mousewheel(event):
            delta = -1 if event.delta > 0 else 1
            canvas.yview_scroll(delta * 3, "units")

        def _bind_wheel(_=None):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_wheel(_=None):
            canvas.unbind_all("<MouseWheel>")

        # bind wheel when cursor enters the settings window
        win.bind("<Enter>", _bind_wheel)
        win.bind("<Leave>", _unbind_wheel)
        inner.bind("<Enter>", _bind_wheel)
        canvas.bind("<Enter>", _bind_wheel)
        _bind_wheel()

        # header
        header = tk.Frame(inner, bg=COLOR_BG)
        header.pack(fill="x", padx=24, pady=(20, 10))
        tk.Label(header, text="⚙", bg=COLOR_BG, fg=self.accent,
                 font=("Segoe UI", 22, "bold")).pack(side="left")
        tk.Label(header, text="Settings", bg=COLOR_BG,
                 fg=COLOR_TEXT, font=("Segoe UI", 16, "bold")
                 ).pack(side="left", padx=10)

        # accent
        sec2 = self._settings_section(inner, "Accent color")
        preset_row = tk.Frame(sec2, bg=COLOR_CARD)
        preset_row.pack(anchor="w", padx=14, pady=(0, 8))
        for name, h, hh, hd in ACCENT_PRESETS:
            b = tk.Label(preset_row, text="  ", bg=h, width=3, height=1,
                         bd=2, relief="ridge", cursor="hand2")
            b.pack(side="left", padx=3)
            Tooltip(b, name)
            b.bind("<Button-1>", lambda e, n=name, c=h, h2=hh, d=hd:
                   self._animate_accent(c, h2, d, n))
        ttk.Button(sec2, text="🎨  Custom color", style="Card.TButton",
                   command=self._pick_custom_accent
                   ).pack(anchor="w", padx=14, pady=(0, 6), ipady=3)

        # appearance
        sec3 = self._settings_section(inner, "Appearance")
        self._make_toggle(sec3, "Show duration in list",
                          self.opt_show_duration, self._toggle_show_duration)
        self._make_toggle(sec3, "Show ♥ icon",
                          self.opt_show_heart, self._toggle_show_heart)
        self._make_toggle(sec3, "Show play count",
                          self.opt_show_playcount, self._toggle_show_playcount)

        # sleep timer
        sec4 = self._settings_section(inner, "Sleep timer")
        self._sleep_lbl = tk.Label(sec4, text="Off", bg=COLOR_CARD,
                                   fg=COLOR_TEXT_DIM, font=("Segoe UI", 9))
        self._sleep_lbl.pack(anchor="w", padx=14, pady=(0, 6))
        sleep_row = tk.Frame(sec4, bg=COLOR_CARD)
        sleep_row.pack(anchor="w", padx=14, pady=(0, 8))
        for mins in (15, 30, 60, 120):
            tk.Button(sleep_row, text=f"{mins}m", bd=0, relief="flat",
                      bg=COLOR_BG, fg=self.accent, font=("Segoe UI", 9),
                      cursor="hand2",
                      command=lambda m=mins: self._start_sleep_timer(m)
                      ).pack(side="left", padx=(0, 6), ipadx=8, ipady=4)
        tk.Button(sleep_row, text="Off", bd=0, relief="flat",
                  bg=COLOR_BG, fg=COLOR_DANGER, font=("Segoe UI", 9),
                  cursor="hand2",
                  command=self._cancel_sleep_timer
                  ).pack(side="left", ipadx=8, ipady=4)

        # system
        sec5 = self._settings_section(inner, "System")
        self._make_toggle(sec5, "Start with Windows",
                          self.opt_autostart, self._toggle_autostart)

        # hotkeys
        sec6 = self._settings_section(inner, "Hotkeys")
        for key, desc in [("Space", "Play / Pause"),
                          ("← / →", "Seek ±5s"),
                          ("↑ / ↓", "Volume ±5"),
                          ("S / R", "Shuffle / Repeat"),
                          ("M", "Mute"),
                          ("Ctrl+O", "Add files"),
                          ("Ctrl+L", "Clear"),
                          ("F11", "Fullscreen"),
                          ("Dbl-click cover", "Fullscreen cover")]:
            r = tk.Frame(sec6, bg=COLOR_CARD)
            r.pack(fill="x", padx=14, pady=1)
            tk.Label(r, text=key, bg=COLOR_CARD, fg=self.accent,
                     font=("Consolas", 9, "bold"), width=14, anchor="w"
                     ).pack(side="left")
            tk.Label(r, text=desc, bg=COLOR_CARD, fg=COLOR_TEXT_DIM,
                     font=("Segoe UI", 9), anchor="w").pack(side="left")

        # about
        sec7 = self._settings_section(inner, "About")
        tk.Label(sec7, text=f"ScarliPleer  v{APP_VERSION}", bg=COLOR_CARD,
                 fg=self.accent, font=("Segoe UI", 11, "bold")
                 ).pack(anchor="w", padx=14)
        tk.Label(sec7, text="Made with ❤ by ScarliPleer",
                 bg=COLOR_CARD, fg=COLOR_TEXT_DIM, font=("Segoe UI", 9)
                 ).pack(anchor="w", padx=14, pady=(0, 6))

        # footer
        footer = tk.Frame(inner, bg=COLOR_BG)
        footer.pack(fill="x", padx=24, pady=(10, 20))

        def safe_close():
            try: win.grab_release()
            except Exception: pass
            try: win.destroy()
            except Exception: pass

        ttk.Button(footer, text="❤  Support", style="Card.TButton",
                   command=lambda: webbrowser.open(SUPPORT_URL)
                   ).pack(side="left", ipady=4, ipadx=6)
        ttk.Button(footer, text="Close", style="Accent.TButton",
                   command=safe_close).pack(side="right", ipady=4, ipadx=12)

        try:
            win.grab_set()
        except Exception:
            pass
        win.protocol("WM_DELETE_WINDOW", safe_close)

    def _settings_section(self, parent, title):
        sec = tk.Frame(parent, bg=COLOR_CARD)
        sec.pack(fill="x", padx=20, pady=6, ipady=8)
        tk.Label(sec, text=title, bg=COLOR_CARD, fg=COLOR_TEXT,
                 font=("Segoe UI", 11, "bold")
                 ).pack(anchor="w", padx=14, pady=(6, 6))
        return sec

    def _make_toggle(self, parent, label, value, command):
        row = tk.Frame(parent, bg=COLOR_CARD)
        row.pack(fill="x", padx=14, pady=3)
        tk.Label(row, text=label, bg=COLOR_CARD, fg=COLOR_TEXT_DIM,
                 font=("Segoe UI", 10), anchor="w"
                 ).pack(side="left", fill="x", expand=True)
        var = tk.BooleanVar(value=value)
        chk = tk.Checkbutton(row, variable=var,
                             command=lambda: command(var.get()),
                             bg=COLOR_CARD, activebackground=COLOR_CARD,
                             fg=self.accent, selectcolor=COLOR_BG,
                             bd=0, highlightthickness=0,
                             activeforeground=self.accent)
        chk.pack(side="right")

    def _pick_custom_accent(self):
        c = colorchooser.askcolor(title="Pick accent color")[1]
        if c:
            self._animate_accent(c, c, c, "Custom")

    # ---------------- TOGGLES ----------------
    def _toggle_show_duration(self, on):
        self.opt_show_duration = on
        self._apply_filter()

    def _toggle_show_heart(self, on):
        self.opt_show_heart = on
        self._apply_filter()

    def _toggle_show_playcount(self, on):
        self.opt_show_playcount = on
        self._apply_filter()

    def _toggle_autostart(self, on):
        self.opt_autostart = on
        self._set_autostart(on)

    def _set_autostart(self, enable):
        if os.name != "nt":
            return
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            app_path = os.path.abspath(sys.argv[0])
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path,
                                 0, winreg.KEY_SET_VALUE)
            if enable:
                winreg.SetValueEx(key, "ScarliPleer", 0, winreg.REG_SZ,
                                  f'"{sys.executable}" "{app_path}"')
            else:
                try: winreg.DeleteValue(key, "ScarliPleer")
                except FileNotFoundError: pass
            winreg.CloseKey(key)
        except Exception as e:
            print("autostart error:", e)

    # ---------------- ACCENT ANIMATION ----------------
    def _animate_accent(self, c, ch, cd, name):
        start_c, start_h, start_d = self.accent, self.accent_h, self.accent_d
        frames = 14

        def step(i):
            t = i / frames
            e = 1 - (1 - t) ** 2
            self.accent = lerp_color(start_c, c, e)
            self.accent_h = lerp_color(start_h, ch, e)
            self.accent_d = lerp_color(start_d, cd, e)
            self._repaint_ui(light=True)
            if i < frames:
                self.after(20, lambda: step(i + 1))
            else:
                self.accent, self.accent_h, self.accent_d = c, ch, cd
                self.accent_choice.set(name)
                self._repaint_ui()
        step(0)

    def _repaint_ui(self, light=False):
        try:
            self.logo_label.configure(fg=self.accent)
            self.play_btn.configure(bg=self.accent,
                                    activebackground=self.accent_h)
            self.listbox.configure(selectbackground=self.accent)
            self.search_entry.configure(insertbackground=self.accent)
            self.status_label.configure(fg=self.accent)
            self.progress.set_accent(self.accent, self.accent_h)
            self.volume.set_accent(self.accent, self.accent_h)
            for b in (self.gear_btn, self.shuffle_btn, self.repeat_btn,
                      self.vol_icon, self.sort_btn):
                b.set_colors(COLOR_TEXT_DIM, self.accent)
            if not light:
                self._style_accent()
        except Exception:
            pass

    # ---------------- SLEEP TIMER ----------------
    def _start_sleep_timer(self, minutes):
        self._cancel_sleep_timer()
        end = time.time() + minutes * 60
        self._sleep_end_time = end
        try:
            self._sleep_lbl.configure(
                text=f"Sleeping at {datetime.fromtimestamp(end).strftime('%H:%M')}")
        except Exception:
            pass

        def check():
            if self._sleep_end_time is None:
                return
            left = self._sleep_end_time - time.time()
            if left <= 0:
                self._fade_out_and_pause()
                try: self._sleep_lbl.configure(text="Off")
                except Exception: pass
                self._sleep_end_time = None
                return
            m = int(left // 60)
            s = int(left % 60)
            try: self._sleep_lbl.configure(text=f"Sleep in {m:02d}:{s:02d}")
            except Exception: pass
            self._sleep_timer_id = self.after(1000, check)
        check()

    def _cancel_sleep_timer(self):
        if self._sleep_timer_id:
            try: self.after_cancel(self._sleep_timer_id)
            except Exception: pass
            self._sleep_timer_id = None
        self._sleep_end_time = None
        try: self._sleep_lbl.configure(text="Off")
        except Exception: pass

    def _fade_out_and_pause(self):
        def fade(step=0, total=30):
            if step >= total:
                try:
                    pygame.mixer.music.pause()
                    self.is_paused = True
                    self.play_btn.configure(text="▶")
                except Exception: pass
                return
            v = self._volume_value * (1 - step / total)
            try: pygame.mixer.music.set_volume(max(0, v) / 100)
            except Exception: pass
            self.after(50, lambda: fade(step + 1, total))
        fade()

    # ---------------- STATS ----------------
    def _stats_bump_play(self):
        today = datetime.now().strftime("%Y-%m-%d")
        self.stats[today] = self.stats.get(today, 0) + 1
        self._save_stats()

    def _load_stats(self):
        if os.path.exists(STATS_FILE):
            try:
                with open(STATS_FILE, "r", encoding="utf-8") as f:
                    self.stats = json.load(f)
            except Exception:
                self.stats = {}

    def _save_stats(self):
        try:
            with open(STATS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.stats, f, indent=2)
        except Exception:
            pass

    def _open_stats(self):
        win = tk.Toplevel(self)
        win.title("Statistics")
        win.configure(bg=COLOR_BG)
        win.geometry("640x600")
        win.transient(self)
        try: win.iconbitmap(ICO_FILE)
        except Exception: pass
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 640) // 2
        y = self.winfo_y() + (self.winfo_height() - 600) // 2
        win.geometry(f"+{x}+{y}")

        tk.Label(win, text="📊", bg=COLOR_BG, fg=self.accent,
                 font=("Segoe UI", 26, "bold")).pack(pady=(20, 2))
        tk.Label(win, text="Statistics", bg=COLOR_BG, fg=COLOR_TEXT,
                 font=("Segoe UI", 16, "bold")).pack()

        total_tracks = len(self.playlist)
        total_time = sum(t.get("length", 0) or 0 for t in self.playlist)
        total_plays = sum(self.play_counts.values())

        streak = 0
        d = datetime.now().date()
        while True:
            key = d.strftime("%Y-%m-%d")
            if self.stats.get(key, 0) > 0:
                streak += 1
                d -= timedelta(days=1)
            else:
                break

        cards = tk.Frame(win, bg=COLOR_BG)
        cards.pack(fill="x", padx=24, pady=(16, 8))

        def card(parent, label, value):
            c = tk.Frame(parent, bg=COLOR_CARD)
            c.pack(side="left", fill="both", expand=True, padx=4)
            tk.Label(c, text=value, bg=COLOR_CARD, fg=self.accent,
                     font=("Segoe UI", 15, "bold")).pack(pady=(10, 0))
            tk.Label(c, text=label, bg=COLOR_CARD, fg=COLOR_TEXT_DIM,
                     font=("Segoe UI", 8)).pack(pady=(2, 10))

        card(cards, "Tracks", str(total_tracks))
        card(cards, "Time", self._fmt_long(total_time))
        card(cards, "Plays", str(total_plays))
        card(cards, "Streak", f"{streak}d")

        # top artists
        tk.Label(win, text="Top artists", bg=COLOR_BG, fg=COLOR_TEXT_DIM,
                 font=("Segoe UI", 9, "bold")
                 ).pack(anchor="w", padx=28, pady=(14, 4))
        artist_frame = tk.Frame(win, bg=COLOR_CARD)
        artist_frame.pack(fill="x", padx=24, pady=(0, 10))
        lb1 = tk.Listbox(artist_frame, bg=COLOR_CARD, fg=COLOR_TEXT,
                         bd=0, highlightthickness=0, activestyle="none",
                         font=("Segoe UI", 10), height=5)
        lb1.pack(fill="x", padx=8, pady=6)
        counter = Counter()
        by_path = {t["path"]: t for t in self.playlist}
        for path, cnt in self.play_counts.items():
            t = by_path.get(path)
            if t:
                counter[t.get("artist") or "Unknown"] += cnt
        for i, (artist, cnt) in enumerate(counter.most_common(10), 1):
            lb1.insert("end", f"  {i:>2}.  {artist[:40]:<40}  ×  {cnt}")
        if not counter:
            lb1.insert("end", "  Nothing yet")

        # top tracks
        tk.Label(win, text="Top tracks", bg=COLOR_BG, fg=COLOR_TEXT_DIM,
                 font=("Segoe UI", 9, "bold")
                 ).pack(anchor="w", padx=28, pady=(6, 4))
        tf = tk.Frame(win, bg=COLOR_CARD)
        tf.pack(fill="both", expand=True, padx=24, pady=(0, 10))
        lb2 = tk.Listbox(tf, bg=COLOR_CARD, fg=COLOR_TEXT,
                         bd=0, highlightthickness=0, activestyle="none",
                         font=("Segoe UI", 10))
        lb2.pack(fill="both", expand=True, padx=8, pady=6)
        ranked = sorted(self.play_counts.items(), key=lambda x: -x[1])[:15]
        for i, (path, cnt) in enumerate(ranked, 1):
            t = by_path.get(path)
            name = t["title"] if t else os.path.basename(path)
            lb2.insert("end", f"  {i:>2}.  {name[:50]:<50}  ×  {cnt}")
        if not ranked:
            lb2.insert("end", "  Nothing played yet")

        ftr = tk.Frame(win, bg=COLOR_BG)
        ftr.pack(fill="x", padx=24, pady=(0, 16))
        ttk.Button(ftr, text="📤  Export CSV", style="Card.TButton",
                   command=self._export_stats_csv
                   ).pack(side="left", ipadx=6, ipady=4)
        ttk.Button(ftr, text="🗑  Clear stats", style="Danger.TButton",
                   command=self._clear_stats
                   ).pack(side="left", padx=(6, 0), ipadx=6, ipady=4)
        ttk.Button(ftr, text="Close", style="Accent.TButton",
                   command=win.destroy).pack(side="right", ipadx=20, ipady=4)

    def _export_stats_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="scarliplayer_stats.csv")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Date", "Plays"])
                for k in sorted(self.stats.keys()):
                    w.writerow([k, self.stats[k]])
                w.writerow([])
                w.writerow(["Track", "Plays"])
                by_path = {t["path"]: t for t in self.playlist}
                for p, c in sorted(self.play_counts.items(), key=lambda x: -x[1]):
                    name = by_path.get(p, {}).get("title", os.path.basename(p))
                    w.writerow([name, c])
            messagebox.showinfo("OK", "Stats exported.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _clear_stats(self):
        if messagebox.askyesno("Clear stats", "Reset all statistics?"):
            self.stats = {}
            self.play_counts = {}
            self._save_stats()
            self._save_library()

    def _fmt_long(self, sec):
        sec = int(sec)
        h = sec // 3600
        m = (sec % 3600) // 60
        return f"{h}h {m}m"

    # ---------------- FAVORITES / SORT ----------------
    def _toggle_favorite(self, i):
        if not (0 <= i < len(self.playlist)):
            return
        path = self.playlist[i]["path"]
        if path in self.favorites:
            self.favorites.discard(path)
        else:
            self.favorites.add(path)
        self._apply_filter()
        self._save_library()

    def _set_favorites_filter(self, on):
        self.show_favorites_only = on
        if on:
            self.playlist_tab.configure(fg=COLOR_TEXT_DIM)
            self.fav_tab.configure(fg=self.accent)
        else:
            self.playlist_tab.configure(fg=self.accent)
            self.fav_tab.configure(fg=COLOR_TEXT_DIM)
        self._apply_filter()

    def _cycle_sort(self):
        order = ["title", "artist", "length", "date"]
        i = order.index(self.sort_mode)
        self.sort_mode = order[(i + 1) % len(order)]
        self._apply_filter()

    def _toggle_compact(self):
        self.compact = not self.compact
        if self.compact:
            self.sidebar.grid_remove()
            self.minsize(600, 620)
        else:
            self.sidebar.grid()
            self.minsize(1000, 660)

    # ---------------- DND ----------------
    def _enable_dnd(self):
        if not DND_AVAILABLE:
            return
        try:
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_drop)
        except Exception:
            pass

    def _on_drop(self, event):
        paths = self.tk.splitlist(event.data)
        added = 0
        for p in paths:
            p = str(p)
            if os.path.isdir(p):
                for f in sorted(os.listdir(p)):
                    if f.lower().endswith((".mp3", ".wav", ".ogg")):
                        self._add_one(os.path.join(p, f))
                        added += 1
            elif p.lower().endswith((".mp3", ".wav", ".ogg")):
                self._add_one(p)
                added += 1
        if added:
            self._save_library()

    # ---------------- PLACEHOLDER ----------------
    def _show_placeholder(self, event=None):
        if not self.search_var.get():
            self._placeholder_active = True
            self.search_entry.configure(fg="#5a5a5a")
            self.search_var.set(self._search_placeholder)

    def _hide_placeholder(self, event=None):
        if self._placeholder_active:
            self._placeholder_active = False
            self.search_var.set("")
            self.search_entry.configure(fg=COLOR_TEXT)

    def _clear_search(self):
        self._placeholder_active = False
        self.search_var.set("")
        self.search_entry.configure(fg=COLOR_TEXT)

    # ---------------- HOTKEYS ----------------
    def _search_has_focus(self):
        try:
            return self.focus_get() is self.search_entry
        except Exception:
            return False

    def _hotkey(self, fn):
        def wrapped(event=None):
            if self._search_has_focus():
                return
            fn()
        return wrapped

    def _bind_hotkeys(self):
        self.bind("<space>", self._hotkey(self._toggle_play))
        self.bind("<Left>", self._hotkey(lambda: self._nudge(-5)))
        self.bind("<Right>", self._hotkey(lambda: self._nudge(5)))
        self.bind("<Up>", self._hotkey(lambda: self._nudge_volume(5)))
        self.bind("<Down>", self._hotkey(lambda: self._nudge_volume(-5)))
        self.bind("<Control-o>", lambda e: self._add_files())
        self.bind("<Control-O>", lambda e: self._add_files())
        self.bind("<Control-Shift-O>", lambda e: self._add_folder())
        self.bind("<Control-l>", lambda e: self._clear())
        self.bind("<Control-f>", lambda e: self._toggle_compact())
        self.bind("<Control-s>", lambda e: self._open_stats())
        self.bind("<s>", self._hotkey(self._toggle_shuffle))
        self.bind("<S>", self._hotkey(self._toggle_shuffle))
        self.bind("<r>", self._hotkey(self._toggle_repeat))
        self.bind("<R>", self._hotkey(self._toggle_repeat))
        self.bind("<m>", self._hotkey(self._toggle_mute))
        self.bind("<M>", self._hotkey(self._toggle_mute))
        self.bind("<F11>", lambda e: self._toggle_fullscreen())
        self.bind("<Escape>", lambda e: self._clear_search())

    def _toggle_fullscreen(self):
        self.attributes("-fullscreen", not self.attributes("-fullscreen"))

    def _nudge(self, seconds):
        if not self.is_playing or self.song_length <= 0:
            return
        cur = self.progress.get() / 100 * self.song_length
        target = max(0, min(self.song_length - 0.5, cur + seconds))
        pct = target / self.song_length * 100
        self.progress.set(pct)
        self._seek_release(pct)

    def _nudge_volume(self, delta):
        v = max(0, min(100, self._volume_value + delta))
        self._volume_value = v
        self._last_volume = v if v > 0 else self._last_volume
        self.volume.set(v)
        pygame.mixer.music.set_volume(v / 100)
        self._update_volume_icon()

    # ---------------- COVER ----------------
    def _make_default_cover(self, size):
        img = Image.new("RGB", (size, size), "#1a1a1a")
        d = ImageDraw.Draw(img)
        for r in range(size // 2 - 4, 20, -10):
            d.ellipse([size//2 - r, size//2 - r, size//2 + r, size//2 + r],
                      outline="#2b2140")
        r = size // 5
        d.ellipse([size//2 - r, size//2 - r, size//2 + r, size//2 + r],
                  fill=self.accent)
        d.rectangle([size//2 - 3, size//2 - 22, size//2 + 3, size//2 + 10],
                    fill="#1a1a1a")
        return ImageTk.PhotoImage(img)

    def _load_cover(self, path, size=None):
        size = size or self._cover_size
        try:
            mtime = os.path.getmtime(path)
        except Exception:
            return self._album_default
        key = (path, size, mtime)
        if key in self._cover_cache:
            self._cover_cache.move_to_end(key)
            return self._cover_cache[key]
        photo = self._album_default
        try:
            audio = MP3(path, ID3=ID3)
            if audio.tags:
                for tag in audio.tags.values():
                    if isinstance(tag, APIC):
                        img = Image.open(io.BytesIO(tag.data)).convert("RGB").resize((size, size), Image.LANCZOS)
                        mask = Image.new("L", (size, size), 0)
                        ImageDraw.Draw(mask).rounded_rectangle(
                            (0, 0, size, size), radius=14, fill=255)
                        img.putalpha(mask)
                        photo = ImageTk.PhotoImage(img)
                        break
        except Exception:
            pass
        self._cover_cache[key] = photo
        if len(self._cover_cache) > self._cover_cache_max:
            self._cover_cache.popitem(last=False)
        return photo

    # ---------------- META ----------------
    def _read_meta(self, path):
        title = os.path.splitext(os.path.basename(path))[0]
        artist = "Unknown Artist"
        album = ""
        length = 0
        try:
            audio = MP3(path, ID3=ID3)
            length = audio.info.length
            if audio.tags:
                if "TIT2" in audio.tags: title = str(audio.tags["TIT2"])
                if "TPE1" in audio.tags: artist = str(audio.tags["TPE1"])
                if "TALB" in audio.tags: album = str(audio.tags["TALB"])
        except Exception:
            pass
        return title, artist, album, length

    # ---------------- LIBRARY ----------------
    def _add_files(self):
        files = filedialog.askopenfilenames(
            title="Add Files",
            filetypes=[("Audio", "*.mp3 *.wav *.ogg")])
        for f in files:
            self._add_one(f)
        self._save_library()

    def _add_folder(self):
        folder = filedialog.askdirectory(title="Add Folder")
        if not folder:
            return
        for f in sorted(os.listdir(folder)):
            if f.lower().endswith((".mp3", ".wav", ".ogg")):
                self._add_one(os.path.join(folder, f))
        self._save_library()

    def _add_one(self, path):
        for t in self.playlist:
            if os.path.normpath(t["path"]) == os.path.normpath(path):
                return
        title, artist, album, length = self._read_meta(path)
        self.playlist.append({
            "path": path, "title": title, "artist": artist,
            "album": album, "length": length, "added": time.time()
        })
        self._apply_filter()

    def _clear(self):
        pygame.mixer.music.stop()
        self.is_playing = False
        self.is_paused = False
        self.playlist.clear()
        self.filtered.clear()
        self.current_index = -1
        self.listbox.delete(0, "end")
        self.title_label.configure(text="No track selected")
        self.artist_label.configure(text="")
        self.cover_label.configure(image=self._album_default)
        self.play_btn.configure(text="▶")
        self.progress.set(0)
        self.time_now.configure(text="00:00")
        self.time_end.configure(text="00:00")
        self._set_window_title(None)
        self._refresh_counter()
        self._update_taskbar_progress(0, 0)
        self._save_library()

    def _refresh_counter(self):
        n = len(self.filtered)
        total = sum(self.playlist[i].get("length", 0) or 0 for i in self.filtered)
        self.counter_lbl.configure(text=f"{n} tracks · {self._fmt_long(total)}")

    def _apply_filter(self):
        if not hasattr(self, "listbox"):
            return
        q = self.search_var.get().lower().strip()
        if self._placeholder_active or q == "search...":
            q = ""
        idxs = list(range(len(self.playlist)))
        if self.show_favorites_only:
            idxs = [i for i in idxs if self.playlist[i]["path"] in self.favorites]
        if q:
            idxs = [i for i in idxs
                    if fuzzy_match(q, self.playlist[i]["title"])
                    or fuzzy_match(q, self.playlist[i]["artist"])]
        key_map = {
            "title":  lambda i: self.playlist[i]["title"].lower(),
            "artist": lambda i: self.playlist[i]["artist"].lower(),
            "length": lambda i: self.playlist[i].get("length", 0) or 0,
            "date":   lambda i: self.playlist[i].get("added", 0),
        }
        idxs.sort(key=key_map.get(self.sort_mode, key_map["title"]))
        self.filtered = idxs
        self.listbox.delete(0, "end")

        now_playing_path = None
        if 0 <= self.current_index < len(self.playlist):
            now_playing_path = self.playlist[self.current_index]["path"]

        for i in self.filtered:
            t = self.playlist[i]
            heart = "♥ " if (self.opt_show_heart and t["path"] in self.favorites) else ("   " if self.opt_show_heart else "")
            dur = ""
            if self.opt_show_duration and t.get("length"):
                dur = f"  {self._fmt(t['length'])}"
            plays = ""
            if self.opt_show_playcount:
                plays = f"  ·  {self.play_counts.get(t['path'], 0)}×"
            marker = "▶ " if t["path"] == now_playing_path else ""
            line = f"  {heart}{marker}{t['title']}  ·  {t['artist']}{dur}{plays}"
            self.listbox.insert("end", line)
        self._refresh_counter()

    # ---------------- TITLE ----------------
    def _current_track(self):
        if 0 <= self.current_index < len(self.playlist):
            return self.playlist[self.current_index]
        return None

    def _set_window_title(self, track):
        if track:
            self.title(f"{self._base_title}  —  {track['title']} · {track['artist']}")
        else:
            self.title(self._base_title)

    # ---------------- PLAYBACK ----------------
    def _play_selected(self, event=None):
        sel = self.listbox.curselection()
        if not sel:
            return
        self.current_index = self.filtered[sel[0]]
        self._play_current()

    def _play_current(self):
        if not (0 <= self.current_index < len(self.playlist)):
            return
        t = self.playlist[self.current_index]
        self._show_loading(True)
        self.update_idletasks()
        try:
            pygame.mixer.music.load(t["path"])
            pygame.mixer.music.set_volume(self._volume_value / 100)
            pygame.mixer.music.play()
            self.is_playing = True
            self.is_paused = False
            self.start_time = time.time()
            self.paused_at = 0
            self.song_length = t["length"]

            self.title_label.configure(text=t["title"])
            self.artist_label.configure(text=t["artist"])
            self._set_window_title(t)

            cover = self._load_cover(t["path"])
            self._last_cover = cover
            self.cover_label.configure(image=cover)

            self.play_btn.configure(text="⏸")
            self.time_end.configure(text=self._fmt(self.song_length))

            self._played_seconds = 0
            self._counted_path = None

            self._apply_filter()
        except Exception as e:
            messagebox.showerror("Error", f"Could not play file:\n{e}")
        finally:
            self._show_loading(False)

    def _toggle_play(self):
        if not self.playlist:
            return
        if self.current_index < 0:
            self.current_index = self.filtered[0] if self.filtered else 0
            self._play_current()
            return
        if self.is_playing and not self.is_paused:
            pygame.mixer.music.pause()
            self.is_paused = True
            self.paused_at = time.time()
            self.play_btn.configure(text="▶")
        elif self.is_paused:
            pygame.mixer.music.unpause()
            self.is_paused = False
            self.start_time += time.time() - self.paused_at
            self.play_btn.configure(text="⏸")

    def _next(self):
        if not self.playlist:
            return
        if self.shuffle:
            self.current_index = random.randrange(len(self.playlist))
        else:
            self.current_index = (self.current_index + 1) % len(self.playlist)
        self._play_current()

    def _prev(self):
        if not self.playlist:
            return
        if self.shuffle:
            self.current_index = random.randrange(len(self.playlist))
        else:
            self.current_index = (self.current_index - 1) % len(self.playlist)
        self._play_current()

    def _seek_live(self, value):
        if self.song_length > 0:
            self.time_now.configure(text=self._fmt(float(value) / 100 * self.song_length))

    def _seek_release(self, value):
        if not self.is_playing or self.song_length <= 0:
            return
        self._seeking = True
        target = float(value) / 100 * self.song_length
        pygame.mixer.music.play(start=target)
        self.start_time = time.time() - target
        if self.is_paused:
            pygame.mixer.music.pause()
        self._seeking = False

    def _set_volume(self, value):
        v = float(value)
        self._volume_value = v
        if v > 0:
            self._muted = False
            self._last_volume = v
        pygame.mixer.music.set_volume(v / 100)
        self._update_volume_icon()

    def _toggle_mute(self):
        if self._muted:
            self._muted = False
            self._volume_value = self._last_volume
            self.volume.set(self._volume_value)
            pygame.mixer.music.set_volume(self._volume_value / 100)
        else:
            self._muted = True
            self._last_volume = self._volume_value
            self._volume_value = 0
            self.volume.set(0)
            pygame.mixer.music.set_volume(0)
        self._update_volume_icon()

    def _update_volume_icon(self):
        v = self._volume_value
        if self._muted or v <= 0: icon = "🔇"
        elif v < 30: icon = "🔈"
        elif v < 70: icon = "🔉"
        else: icon = "🔊"
        self.vol_icon.configure(text=icon)

    def _toggle_shuffle(self):
        self.shuffle = not self.shuffle
        self.shuffle_btn.set_state(self.shuffle)

    def _toggle_repeat(self):
        self.repeat = not self.repeat
        self.repeat_btn.set_state(self.repeat)

    # ---------------- TASKBAR ----------------
    def _update_taskbar_progress(self, pos, total):
        if not self._win32:
            return
        try:
            hwnd = self._win32.user32.GetParent(self.winfo_id())
            if total <= 0:
                try: self._win32.user32.SendMessageW(hwnd, 0x0400 + 91, 0, 0)
                except Exception: pass
                return
            self._win32.user32.SendMessageW(hwnd, 0x0400 + 90, 1, 0)
            self._win32.user32.SendMessageW(hwnd, 0x0400 + 90, 2, int(pos))
            self._win32.user32.SendMessageW(hwnd, 0x0400 + 90, 3, int(total))
        except Exception:
            pass

    # ---------------- LOADING ----------------
    def _show_loading(self, state):
        self._loading = state
        self.status_label.configure(text="Loading..." if state else "")

    def _loading_tick(self):
        if self._loading:
            self._loading_frame = (self._loading_frame + 1) % 4
            self.status_label.configure(text=f"Loading{'.' * self._loading_frame}")
        self.after(300, self._loading_tick)

    # ---------------- TICK ----------------
    def _fmt(self, sec):
        sec = int(sec)
        return f"{sec // 60:02d}:{sec % 60:02d}"

    def _tick(self):
        if self.is_playing and not self.is_paused and self.song_length > 0:
            elapsed = time.time() - self.start_time
            if elapsed >= self.song_length:
                if self.repeat:
                    self._play_current()
                else:
                    self._next()
            else:
                self._played_seconds += 0.4
                if (self._counted_path is None and
                        self._played_seconds >= min(30, self.song_length * 0.3)):
                    t = self._current_track()
                    if t:
                        p = t["path"]
                        self.play_counts[p] = self.play_counts.get(p, 0) + 1
                        self._counted_path = p
                        self._stats_bump_play()
                if not self.progress._dragging:
                    self._seeking = True
                    self.progress.set(elapsed / self.song_length * 100)
                    self._seeking = False
                    self.time_now.configure(text=self._fmt(elapsed))
                    self._update_taskbar_progress(elapsed * 1000,
                                                  self.song_length * 1000)
        else:
            self._update_taskbar_progress(0, 0)
        self.after(400, self._tick)

    # ---------------- CONTEXT MENU ----------------
    def _show_context_menu(self, event):
        try:
            idx = self.listbox.nearest(event.y)
            if idx < 0 or idx >= len(self.filtered):
                return
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(idx)
            i = self.filtered[idx]
        except Exception:
            return
        menu = tk.Menu(self, tearoff=0, bg=COLOR_CARD, fg=COLOR_TEXT,
                       activebackground=self.accent, activeforeground="white",
                       bd=0)
        menu.add_command(label="▶  Play", command=lambda: self._play_at(i))
        menu.add_command(label="♥  Toggle favorite",
                         command=lambda: self._toggle_favorite(i))
        menu.add_separator()
        if os.path.exists(self.playlist[i]["path"]):
            menu.add_command(label="✎  Edit tags",
                             command=lambda: self._open_tag_editor(i))
        menu.add_command(label="🗑  Remove from playlist",
                         command=lambda: self._remove_index(i))
        if os.path.exists(self.playlist[i]["path"]):
            menu.add_command(label="❌  Delete file from disk",
                             command=lambda: self._delete_file_from_disk(i))
            menu.add_separator()
            menu.add_command(label="📂  Show in folder",
                             command=lambda: self._show_in_folder(i))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _show_in_folder(self, i):
        try:
            path = self.playlist[i]["path"]
            folder = os.path.dirname(path)
            if os.name == "nt":
                os.startfile(folder)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", folder])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", folder])
        except Exception:
            pass

    def _play_at(self, i):
        self.current_index = i
        self._play_current()

    def _remove_index(self, i):
        if not (0 <= i < len(self.playlist)):
            return
        path = self.playlist[i]["path"]
        self.favorites.discard(path)
        self.play_counts.pop(path, None)
        del self.playlist[i]
        if self.current_index == i:
            self.current_index = -1
            pygame.mixer.music.stop()
            self.is_playing = False
            self.play_btn.configure(text="▶")
            self._update_taskbar_progress(0, 0)
        elif self.current_index > i:
            self.current_index -= 1
        self._apply_filter()
        self._save_library()

    def _delete_selected(self):
        sel = list(self.listbox.curselection())
        if not sel:
            return
        indices = sorted([self.filtered[s] for s in sel], reverse=True)
        if messagebox.askyesno("Delete",
                               f"Remove {len(indices)} track(s) from playlist?"):
            for i in indices:
                self._remove_index(i)

    def _delete_file_from_disk(self, i):
        if not (0 <= i < len(self.playlist)):
            return
        path = self.playlist[i]["path"]
        if not os.path.exists(path):
            return
        name = self.playlist[i]["title"]
        if messagebox.askyesno(
                "Delete file",
                f"Permanently delete this file from your computer?\n\n{name}\n\n{path}"):
            try:
                if self.current_index == i:
                    pygame.mixer.music.stop()
                    self.is_playing = False
                    self.is_paused = False
                    self.play_btn.configure(text="▶")
                    self._update_taskbar_progress(0, 0)
                os.remove(path)
            except Exception as e:
                messagebox.showerror("Error", str(e))
                return
            self._remove_index(i)

    # ---------------- TAG EDITOR ----------------
    def _open_tag_editor(self, i):
        if not (0 <= i < len(self.playlist)):
            return
        track = self.playlist[i]
        if not os.path.exists(track["path"]):
            messagebox.showerror("Error", "File not found.")
            return

        win = tk.Toplevel(self)
        win.title("Edit tags")
        win.configure(bg=COLOR_BG)
        win.geometry("460x440")
        win.transient(self)
        try: win.iconbitmap(ICO_FILE)
        except Exception: pass
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 460) // 2
        y = self.winfo_y() + (self.winfo_height() - 440) // 2
        win.geometry(f"+{x}+{y}")

        tk.Label(win, text="Edit tags", bg=COLOR_BG,
                 fg=self.accent, font=("Segoe UI", 14, "bold")
                 ).pack(pady=(16, 10))

        cover_holder = tk.Frame(win, bg=COLOR_BG)
        cover_holder.pack(pady=(0, 10))
        cover_preview = tk.Label(cover_holder, bg=COLOR_BG, bd=0)
        cover_preview.pack()

        current_pil = [self._cover_to_pil(track["path"])]
        new_cover_path = [None]

        def refresh_cover():
            img = current_pil[0]
            if img is None:
                img = self._cover_to_pil_default().resize((140, 140), Image.LANCZOS)
            else:
                img = img.copy().resize((140, 140), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            cover_preview.configure(image=photo)
            cover_preview.image = photo
        refresh_cover()

        tk.Label(win, text="Drag & drop image here to replace cover",
                 bg=COLOR_BG, fg=COLOR_TEXT_DIM,
                 font=("Segoe UI", 8)).pack()

        def load_new_cover(path):
            try:
                img = Image.open(path).convert("RGB")
                current_pil[0] = img
                new_cover_path[0] = path
                refresh_cover()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        def pick_cover():
            p = filedialog.askopenfilename(
                title="Choose cover",
                filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.bmp")])
            if p:
                load_new_cover(p)

        ttk.Button(win, text="📷  Choose image", style="Card.TButton",
                   command=pick_cover).pack(pady=(6, 12), ipadx=6, ipady=3)

        if DND_AVAILABLE:
            try:
                cover_preview.drop_target_register(DND_FILES)
                def on_drop(e):
                    files = self.tk.splitlist(e.data)
                    for f in files:
                        f = str(f).strip("{}")
                        if os.path.isfile(f):
                            load_new_cover(f)
                            break
                cover_preview.dnd_bind("<<Drop>>", on_drop)
            except Exception:
                pass

        def make_field(label, value):
            f = tk.Frame(win, bg=COLOR_BG)
            f.pack(fill="x", padx=30, pady=3)
            tk.Label(f, text=label, bg=COLOR_BG, fg=COLOR_TEXT_DIM,
                     font=("Segoe UI", 9), width=10, anchor="w"
                     ).pack(side="left")
            e = tk.Entry(f, bg=COLOR_CARD, fg=COLOR_TEXT,
                         insertbackground=self.accent, relief="flat", bd=0,
                         font=("Segoe UI", 10))
            e.insert(0, value)
            e.pack(side="left", fill="x", expand=True, ipady=6, padx=(6, 0))
            return e

        e_title = make_field("Title", track["title"])
        e_artist = make_field("Artist", track["artist"])
        e_album = make_field("Album", track.get("album", ""))

        def save():
            try:
                audio = MP3(track["path"], ID3=ID3)
                if audio.tags is None:
                    audio.add_tags()
                audio.tags["TIT2"] = TIT2(encoding=3, text=e_title.get())
                audio.tags["TPE1"] = TPE1(encoding=3, text=e_artist.get())
                if e_album.get():
                    audio.tags["TALB"] = TALB(encoding=3, text=e_album.get())
                if new_cover_path[0]:
                    with open(new_cover_path[0], "rb") as f:
                        data = f.read()
                    mime = "image/jpeg"
                    if new_cover_path[0].lower().endswith(".png"):
                        mime = "image/png"
                    audio.tags.delall("APIC")
                    audio.tags.add(APIC(encoding=3, mime=mime, type=3,
                                        desc="Cover", data=data))
                audio.save()
                track["title"] = e_title.get()
                track["artist"] = e_artist.get()
                track["album"] = e_album.get()
                try:
                    self._cover_cache.pop((track["path"], self._cover_size,
                                           os.path.getmtime(track["path"])), None)
                except Exception:
                    pass
                self._apply_filter()
                self._save_library()
                if self.current_index == i:
                    self.title_label.configure(text=track["title"])
                    self.artist_label.configure(text=track["artist"])
                    self._set_window_title(track)
                    cover = self._load_cover(track["path"])
                    self._last_cover = cover
                    self.cover_label.configure(image=cover)
            except Exception as e:
                messagebox.showerror("Error", str(e))
            win.destroy()

        footer = tk.Frame(win, bg=COLOR_BG)
        footer.pack(fill="x", padx=30, pady=(14, 14))
        ttk.Button(footer, text="Cancel",
                   style="Danger.TButton", command=win.destroy
                   ).pack(side="right", ipadx=6, ipady=3, padx=(6, 0))
        ttk.Button(footer, text="Save",
                   style="Accent.TButton", command=save
                   ).pack(side="right", ipadx=6, ipady=3)

    # ---------------- TRAY ----------------
    def _tray_play(self, icon=None, item=None):
        self.after(0, self._toggle_play)

    def _tray_next(self, icon=None, item=None):
        self.after(0, self._next)

    def _tray_prev(self, icon=None, item=None):
        self.after(0, self._prev)

    def _tray_show(self, icon=None, item=None):
        def show():
            try:
                self.deiconify()
                self.lift()
                self.focus_force()
            except Exception:
                pass
        self.after(0, show)

    def _tray_quit(self, icon=None, item=None):
        self._really_quit = True
        def q():
            try:
                if self._tray_icon:
                    self._tray_icon.stop()
            except Exception: pass
            try: self.destroy()
            except Exception: pass
        self.after(0, q)

    def _minimize_to_tray(self):
        if not TRAY_AVAILABLE:
            self.iconify()
            return
        try: self.withdraw()
        except Exception: pass
        if self._tray_icon:
            return

        def make_menu():
            return TrayMenu(
                TrayItem("Show", self._tray_show, default=True),
                TrayItem("Play / Pause", self._tray_play),
                TrayItem("Previous", self._tray_prev),
                TrayItem("Next", self._tray_next),
                TrayMenu.SEPARATOR,
                TrayItem("Quit", self._tray_quit),
            )

        def run_tray():
            try:
                img = self._build_icon_pil(64)
                self._tray_icon = pystray.Icon(
                    "ScarliPleer", img, "ScarliPleer", make_menu())
                self._tray_icon.run()
            except Exception as e:
                print("tray error:", e)
                self.after(0, self.deiconify)

        self._tray_thread = threading.Thread(target=run_tray, daemon=True)
        self._tray_thread.start()

    def _on_close_button(self):
        if TRAY_AVAILABLE and not self._really_quit:
            self._minimize_to_tray()
        else:
            self.destroy()

    # ---------------- PERSISTENCE ----------------
    def _save_library(self):
        data = {
            "playlist": self.playlist,
            "current_index": self.current_index,
            "volume": self._volume_value,
            "shuffle": self.shuffle,
            "repeat": self.repeat,
            "favorites": list(self.favorites),
            "play_counts": self.play_counts,
            "accent": self.accent,
            "accent_name": self.accent_choice.get(),
            "sort_mode": self.sort_mode,
            "opt_show_duration": self.opt_show_duration,
            "opt_show_heart": self.opt_show_heart,
            "opt_show_playcount": self.opt_show_playcount,
            "opt_autostart": self.opt_autostart,
        }
        try:
            with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_library(self):
        if not hasattr(self, "listbox"):
            return
        if not os.path.exists(LIBRARY_FILE):
            self._update_volume_icon()
            return
        try:
            with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            self._update_volume_icon()
            return

        accent = data.get("accent", COLOR_ACCENT)
        self.accent = accent
        self.accent_h = accent
        self.accent_d = accent
        self._repaint_ui()

        restored = [t for t in data.get("playlist", [])
                    if os.path.exists(t.get("path", ""))]
        self.playlist = restored
        self.favorites = set(data.get("favorites", []))
        self.play_counts = data.get("play_counts", {})
        self.sort_mode = data.get("sort_mode", "title")

        self.opt_show_duration = bool(data.get("opt_show_duration", True))
        self.opt_show_heart = bool(data.get("opt_show_heart", True))
        self.opt_show_playcount = bool(data.get("opt_show_playcount", False))
        self.opt_autostart = bool(data.get("opt_autostart", False))

        self._apply_filter()

        vol = float(data.get("volume", 70))
        self._volume_value = vol
        self._last_volume = vol if vol > 0 else 70
        self.volume.set(vol)
        pygame.mixer.music.set_volume(vol / 100)
        self._update_volume_icon()

        self.shuffle = bool(data.get("shuffle", False))
        self.repeat = bool(data.get("repeat", False))
        self.shuffle_btn.set_state(self.shuffle)
        self.repeat_btn.set_state(self.repeat)

        idx = data.get("current_index", -1)
        if 0 <= idx < len(self.playlist):
            self.current_index = idx
            t = self.playlist[idx]
            self.title_label.configure(text=t["title"])
            self.artist_label.configure(text=t["artist"])
            self.song_length = t.get("length", 0)
            self.time_end.configure(text=self._fmt(self.song_length))
            cover = self._load_cover(t["path"])
            self._last_cover = cover
            self.cover_label.configure(image=cover)
            self._set_window_title(t)
            try:
                pos = self.filtered.index(idx)
                self.listbox.selection_set(pos)
                self.listbox.see(pos)
            except ValueError:
                pass

    def destroy(self):
        self._really_quit = True
        try:
            if self._tray_icon:
                self._tray_icon.stop()
        except Exception:
            pass
        self._save_library()
        super().destroy()


# ---------------- RUN ----------------
if __name__ == "__main__":
    try:
        app = ScarliPleer()
        app.mainloop()
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            messagebox.showerror("Fatal error", str(e))
        except Exception:
            pass