import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk
from PIL import Image, ImageTk
import os

from .videoplayer import VideoPlayer
from .soundmanager import SoundManager

from .services.config_service import ConfigService
from .services.ui_service import UIService
from .services.youtube_service import YouTubeService

from .tabs.slicer_tab import SlicerTab
from .tabs.discord_tab import DiscordTab
from .tabs.youtube_tab import YouTubeTab


class GUI:
    def __init__(self, root):
        self.root = root

        self.root.title("Half-Slice")
        self.root.geometry("600x450")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.window_width, self.window_height = 600, 450
        self.center_window(self.root, self.window_width, self.window_height)

        self.root.iconbitmap(self.get_path("assets\\icon.ico"))

        # Services / managers
        self.soundmanager = SoundManager()
        self.video_player = VideoPlayer(self)  # mantiene compat con tu VideoPlayer actual

        self.config_service = ConfigService(self.get_path("config.json"))
        self.configuration = self.config_service.load()
        self.youtube_service = YouTubeService(
            ytdlp_path=self.get_path("yt-dlp.exe")
        )

        # defaults
        if "discord_8mb" not in self.configuration:
            self.configuration["discord_8mb"] = False

        self.mute = bool(self.configuration.get("mute", False))
        self.soundmanager.toggle_mute(self.mute)

        self.icons = self.load_icons()

        # UI service (loading modal + thread-safe updates)
        self.ui = UIService(self.root, self.get_path)

        # Build app UI
        self.create_widgets()

    # -------------------------
    # PATH / CONFIG
    # -------------------------
    def get_path(self, relative_path):
        return os.path.join(os.path.abspath("."), relative_path)

    def load_icons(self):
        icons = {
            "mute": ImageTk.PhotoImage(Image.open(self.get_path("assets\\sound.png")).resize((24, 24), Image.LANCZOS)),
            "unmute": ImageTk.PhotoImage(Image.open(self.get_path("assets\\mute.png")).resize((24, 24), Image.LANCZOS)),
            "info": ImageTk.PhotoImage(Image.open(self.get_path("assets\\info.png")).resize((24, 24), Image.LANCZOS)),
            "settings": ImageTk.PhotoImage(Image.open(self.get_path("assets\\settings.png")).resize((24, 24), Image.LANCZOS)),
        }
        return icons

    def save_configuration(self):
        self.config_service.save(self.configuration)

    # -------------------------
    # WINDOW HELPERS
    # -------------------------
    def on_closing(self):
        self.root.destroy()

    def center_window(self, window, width, height):
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")

    # -------------------------
    # GLOBAL ACTIONS (shared)
    # -------------------------
    def toggle_mute(self):
        self.mute = not self.mute
        self.configuration["mute"] = self.mute
        self.save_configuration()

        self.soundmanager.toggle_mute(self.mute)

        img = self.icons["unmute"] if self.mute else self.icons["mute"]

        # actualizar botones de mute en todas las tabs
        for tab in getattr(self, "_tabs", []):
            if hasattr(tab, "set_mute_icon"):
                tab.set_mute_icon(img)

    def info_box(self):
        self.soundmanager.play_loop("info")
        self.custom_warning("Created by Hiro. Version beta 0.9. Shoutout to the brownight gang.")

    def custom_warning(self, message):
        warning_win = tk.Toplevel(self.root)
        warning_win.title("Info")
        warning_win.geometry("350x120")
        warning_win.resizable(False, False)
        warning_win.iconbitmap(self.get_path("assets\\icon.ico"))
        self.center_window(warning_win, 350, 120)

        icon = ImageTk.PhotoImage(Image.open(self.get_path("assets\\coomer.png")).resize((40, 40), Image.LANCZOS))
        warning_win.icon_image = icon

        def on_close():
            self.soundmanager.stop_sound()
            warning_win.destroy()

        warning_win.protocol("WM_DELETE_WINDOW", on_close)

        frame = tk.Frame(warning_win)
        frame.pack(pady=10)

        tk.Label(frame, image=icon).grid(row=0, column=0, padx=10)
        tk.Label(frame, text=message, font=("Arial", 10), wraplength=250, justify="left").grid(row=0, column=1)

        def donate():
            webbrowser.open("https://www.paypal.com/paypalme/hiro1891")

        paypal_img = Image.open(self.get_path("assets/paypal.png")).resize((12, 12))
        paypal_icon = ImageTk.PhotoImage(paypal_img)

        button_frame = tk.Frame(warning_win)
        button_frame.pack(pady=10)

        tk.Button(button_frame, text="OK", command=on_close, width=8).pack(side="left", padx=5)

        donate_button = tk.Button(
            button_frame,
            text="Donate",
            image=paypal_icon,
            compound="left",
            width=60,
            command=donate,
            padx=10,
            pady=3,
            font=("Arial", 9),
        )
        donate_button.image = paypal_icon
        donate_button.pack(side="left", padx=5)

    # -------------------------
    # SETTINGS MODAL (shared)
    # -------------------------
    def select_quality(self):
        root = tk.Toplevel(self.root)
        root.title("Settings")
        root.iconbitmap(self.get_path("assets\\icon.ico"))
        self.soundmanager.play_sound("button")

        width, height = 280, 200
        self.center_window(root, width, height)

        bitrate = self.configuration.get("bitrate", "2500k")
        resolution = self.configuration.get("resolution", "720p")
        preset = self.configuration.get("preset", "medium")
        discord_8mb = bool(self.configuration.get("discord_8mb", False))

        tk.Label(root, text="Bitrate:").grid(row=0, column=0, padx=10, pady=5)
        bitrate_combo = ttk.Combobox(root, values=["5000k", "2500k", "1000k", "500k"], state="readonly")
        bitrate_combo.set(bitrate)
        bitrate_combo.grid(row=0, column=1, padx=10, pady=5)

        tk.Label(root, text="Resolution:").grid(row=1, column=0, padx=10, pady=5)
        resolution_combo = ttk.Combobox(root, values=["1080p", "720p", "480p", "360p"], state="readonly")
        resolution_combo.set(resolution)
        resolution_combo.grid(row=1, column=1, padx=10, pady=5)

        tk.Label(root, text="FFmpeg Preset:").grid(row=2, column=0, padx=10, pady=5)
        preset_combo = ttk.Combobox(
            root,
            values=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"],
            state="readonly",
        )
        preset_combo.set(preset)
        preset_combo.grid(row=2, column=1, padx=10, pady=5)

        discord_var = tk.BooleanVar(value=discord_8mb)
        tk.Checkbutton(root, text="Compress for Discord (8MB)", variable=discord_var).grid(
            row=3, column=0, columnspan=2, pady=(6, 0)
        )

        def on_ok():
            self.configuration["bitrate"] = bitrate_combo.get()
            self.configuration["resolution"] = resolution_combo.get()
            self.configuration["preset"] = preset_combo.get()
            self.configuration["discord_8mb"] = bool(discord_var.get())
            self.save_configuration()
            self.soundmanager.play_sound("success")

            extra = "\nDiscord: ON (8MB max)" if self.configuration["discord_8mb"] else "\nDiscord: OFF"
            messagebox.showinfo(
                "Quality Selected",
                f"Bitrate: {bitrate_combo.get()}\nResolution: {resolution_combo.get()}\nPreset: {preset_combo.get()}{extra}",
            )
            root.destroy()

        tk.Button(root, text="OK", command=on_ok).grid(row=4, column=0, columnspan=2, pady=10)

    # -------------------------
    # MAIN UI
    # -------------------------
    def create_widgets(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)

        self._tabs = [
            SlicerTab(self, self.notebook),
            DiscordTab(self, self.notebook),
            YouTubeTab(self, self.notebook),
        ]

        for tab in self._tabs:
            self.notebook.add(tab.frame, text=tab.title)
