import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import json
import os
import time
import threading
from .videoplayer import VideoPlayer
from .soundmanager import SoundManager

class GUI:
    def __init__(self, root):
        self.mute = None
        self.paused = None
        self.loading_screen = None
        self.progress = None

        self.root = root
        self.root.title("Half-Slice")
        self.root.geometry("600x450")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.iconbitmap(self.get_path("assets\\icon.ico"))
        self.window_width, self.window_height = 600, 450
        self.center_window(root, self.window_width, self.window_height)

        self.video_player = VideoPlayer(self)
        self.soundmanager = SoundManager()

        self.config_file = self.get_path("config.json")
        self.configuration = self.load_configuration()

        # Read mute state from config.json at startup
        if 'mute' in self.configuration:
            self.mute = self.configuration['mute']
            self.soundmanager.toggle_mute(self.mute)

        self.icons = self.load_icons()

        self.create_widgets()

    def get_path(self, relative_path):
        return os.path.join(os.path.abspath("."), relative_path)

    def load_icons(self):
        icons = {
            "mute": ImageTk.PhotoImage(Image.open(self.get_path("assets\\sound.png")).resize((24, 24), Image.LANCZOS)),
            "unmute": ImageTk.PhotoImage(Image.open(self.get_path("assets\\mute.png")).resize((24, 24), Image.LANCZOS)),
            "info": ImageTk.PhotoImage(Image.open(self.get_path("assets\\info.png")).resize((24, 24), Image.LANCZOS)),
            "settings": ImageTk.PhotoImage(Image.open(self.get_path("assets\\settings.png")).resize((24, 24), Image.LANCZOS))
        }
        return icons

    def load_configuration(self):
        """ JSON config load """
        if os.path.exists(self.config_file):
            with open(self.config_file, "r") as file:
                return json.load(file)
        return {}

    def save_configuration(self, config):
        with open(self.config_file, "w") as file:
            json.dump(config, file)

    def on_closing(self):
        self.root.destroy()

    def center_window(self, window, width, height):
        """Centers the given window on the screen based on its dimensions."""

        # Get the screen width and height
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()

        # Calculate the position to center the window
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)

        # Set the window's position and size
        window.geometry(f"{width}x{height}+{x}+{y}")

    def slice_video(self):
        self.soundmanager.play_sound("button")

        # Check if there is a loaded file
        file_path = self.entry_file_path.get()
        if not file_path:
            messagebox.showerror("Error", "Please select a video file first.")
            return

        # Process the slice thing in a separated thread
        threading.Thread(target=self.process_video_slice, daemon=True).start()

    def process_video_slice(self):
        try:
            self.video_player.trim_video()  # Call the function that do the process
        except Exception as e:
            messagebox.showwarning("Error", f"Error when slicing video: {e}")

        self.hide_loading_screen()

    def show_loading_screen(self):
        # Create a new top-level window for the loading screen
        self.loading_screen = tk.Toplevel(self.root)
        self.loading_screen.title("Processing clip...")  # Set the window title
        self.loading_screen.geometry("350x120")  # Set the window size
        self.loading_screen.resizable(False, False)  # Disable resizing
        self.loading_screen.iconbitmap(self.get_path("assets\\icon.ico"))  # Set the window icon

        # Create a frame to hold the icon, text, and progress bar
        frame = tk.Frame(self.loading_screen)
        frame.pack(pady=10, padx=10)

        # Load and display the processing icon
        icon_img = Image.open(self.get_path("assets\\processing.png")).resize((60, 60), Image.LANCZOS)
        icon = ImageTk.PhotoImage(icon_img)
        icon_label = tk.Label(frame, image=icon)
        icon_label.image = icon  # Keep a reference to avoid garbage collection
        icon_label.grid(row=0, column=0, rowspan=2, padx=(0, 20), sticky="w")  # Place icon on the left

        # Display the processing text
        text_label = tk.Label(frame, text="Processing clip...", font=("Arial", 12))
        text_label.grid(row=0, column=1, sticky="w")  # Place text next to the icon

        # Create and place the progress bar below the text
        if not hasattr(self, 'progress') or self.progress is None:
            self.progress = ttk.Progressbar(frame, orient="horizontal", length=200, mode="determinate")
        self.progress.grid(row=1, column=1, pady=(5, 0), sticky="we")  # Expand horizontally
        self.progress["value"] = 0  # Initialize progress at 0

        # Center the window on the screen
        self.center_window(self.loading_screen, 350, 120)
        self.loading_screen.wm_attributes("-toolwindow", True)  # Make it a tool window
        self.loading_screen.protocol("WM_DELETE_WINDOW", lambda: None)  # Disable close button
        self.loading_screen.grab_set()  # Make the window modal

    def hide_loading_screen(self):
        if self.loading_screen:
            self.loading_screen.destroy()
            self.loading_screen = None

    def select_file(self):
        """Opens a file dialog to select a video file and resets the start slider to 0."""
        self.soundmanager.play_sound("button")

        # Open a file selection dialog and allow only MP4 files
        file_path = filedialog.askopenfilename(filetypes=[("MP4 files", "*.mp4")])

        if file_path:
            self.entry_file_path.delete(0, tk.END)  # Clear the previous file path
            self.entry_file_path.insert(0, file_path)  # Insert the new file path
            self.video_player.load_video(file_path)  # Load the selected video into the player

            # Reset the start slider to 0
            self.slider_start.set(0)

    def process_video(self, file_path):
        time.sleep(2)
        self.video_player.load_video(file_path)
        self.hide_loading_screen()

    def toggle_mute(self):
        self.mute = not self.mute  # Change mute status
        self.configuration["mute"] = self.mute
        self.soundmanager.toggle_mute(self.mute)
        self.save_configuration(self.configuration)  # Save selection in JSON file

        # Change button appearance
        self.boton_mute.config(image=self.icons["unmute"] if self.mute else self.icons["mute"])

    def toggle_pause(self):
        self.paused = not self.paused  # Change pause status

        if self.paused:
            self.button_pause.config(text="Resume")
        else:
            self.button_pause.config(text="Pause")

    def info_box(self):
        self.soundmanager.play_loop("info")
        self.custom_warning("Created by Hiro. Version beta 0.5. Shoutout to the brownight gang.")

    def custom_warning(self, message):
        """Creates a custom warning dialog with an icon and a message."""

        # Create a new top-level window for the warning dialog
        warning_win = tk.Toplevel()
        warning_win.title("Info")
        warning_win.geometry("350x120")
        warning_win.resizable(False, False)
        warning_win.iconbitmap(self.get_path("assets\\icon.ico"))

        # Define window size and center it on the screen
        width, height = 350, 120
        self.center_window(warning_win, width, height)

        # Load a custom icon (must be in PNG or GIF format)
        icon = ImageTk.PhotoImage(Image.open(self.get_path("assets\\coomer.png")).resize((40, 40), Image.LANCZOS))

        # Keep a reference to the icon to prevent garbage collection
        warning_win.icon_image = icon

        # Function to handle closing the warning window
        def on_close():
            self.soundmanager.stop_sound()
            warning_win.destroy()

        # Override the default close button (X) behavior
        warning_win.protocol("WM_DELETE_WINDOW", on_close)

        # Create a frame to align elements
        frame = tk.Frame(warning_win)
        frame.pack(pady=10)

        # Add an icon label to the left side of the frame
        icon_label = tk.Label(frame, image=icon)
        icon_label.grid(row=0, column=0, padx=10)

        # Add a message label next to the icon
        message_label = tk.Label(frame, text=message, font=("Arial", 10), wraplength=250, justify="left")
        message_label.grid(row=0, column=1)

        # Create a close button to dismiss the warning
        close_button = tk.Button(warning_win, text="OK", command=on_close)
        close_button.pack(pady=10)

        # Start the Tkinter event loop for this window
        warning_win.mainloop()

    def select_quality(self):
        root = tk.Toplevel(self.root)
        root.title("Settings")
        root.iconbitmap(self.get_path("assets\\icon.ico"))
        self.soundmanager.play_sound("button")

        # Define window size and center it on the screen
        width, height = 280, 170
        self.center_window(root, width, height)

        # Load existing config or set defaults
        bitrate = self.configuration.get('bitrate', '2500k')
        resolution = self.configuration.get('resolution', '720p')
        preset = self.configuration.get('preset', 'medium')

        tk.Label(root, text="Bitrate:").grid(row=0, column=0, padx=10, pady=5)
        bitrate_combo = ttk.Combobox(root, values=["5000k", "2500k", "1000k", "500k"], state="readonly")
        bitrate_combo.set(bitrate)
        bitrate_combo.grid(row=0, column=1, padx=10, pady=5)

        tk.Label(root, text="Resolution:").grid(row=1, column=0, padx=10, pady=5)
        resolution_combo = ttk.Combobox(root, values=["1080p", "720p", "480p", "360p"], state="readonly")
        resolution_combo.set(resolution)
        resolution_combo.grid(row=1, column=1, padx=10, pady=5)

        tk.Label(root, text="FFmpeg Preset:").grid(row=2, column=0, padx=10, pady=5)
        preset_combo = ttk.Combobox(root,
                                    values=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow",
                                            "slower", "veryslow"], state="readonly")
        preset_combo.set(preset)
        preset_combo.grid(row=2, column=1, padx=10, pady=5)

        def on_ok():
            self.configuration['bitrate'] = bitrate_combo.get()
            self.configuration['resolution'] = resolution_combo.get()
            self.configuration['preset'] = preset_combo.get()
            self.save_configuration(self.configuration)
            root.bell = lambda *args, **kwargs: None
            self.soundmanager.play_sound("success")
            messagebox.showinfo("Quality Selected",
                                f"Bitrate: {bitrate_combo.get()}\nResolution: {resolution_combo.get()}\nPreset: {preset_combo.get()}")
            root.destroy()

        tk.Button(root, text="OK", command=on_ok).grid(row=3, column=0, columnspan=2, pady=10)

    def enable_buttons(self):
        """Enables UI controls (sliders and buttons) and binds necessary events."""

        # Bind events to the start time slider
        self.slider_start.bind("<ButtonPress-1>", self.soundmanager.on_slide_start)  # Play sound when clicked
        self.slider_start.bind("<ButtonRelease-1>", lambda e: self.video_player.update_start_time(self.slider_start.get()))  # Update start time on release
        self.slider_start.bind("<B1-Motion>")  # Allow dragging
        self.slider_start.bind("<KeyRelease>")  # Allow keyboard adjustments
        self.slider_start.config(state=tk.NORMAL)  # Enable the slider

        # Bind events to the end time slider
        self.slider_end.bind("<ButtonPress-1>", self.soundmanager.on_slide_start)  # Play sound once at the start
        self.slider_end.bind("<ButtonRelease-1>", lambda e: self.video_player.update_end_time(self.slider_end.get()))  # Update end time on release
        self.slider_end.bind("<B1-Motion>")  # Allow dragging
        self.slider_end.bind("<KeyRelease>")  # Allow keyboard adjustments
        self.slider_end.config(state=tk.NORMAL)  # Enable the slider

        # Enable control buttons
        self.button_cut.config(state=tk.NORMAL)  # Enable the "Slice" button
        self.button_play.config(state=tk.NORMAL)  # Enable the "Play Preview" button
        self.button_pause.config(state=tk.NORMAL)  # Enable the "Pause" button

    def create_widgets(self):
        """Creates and configures all GUI elements, including buttons, sliders, and video preview."""

        # Set up the main canvas and background image
        self.canvas = tk.Canvas(self.root, width=600, height=450, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        background_image = Image.open(self.get_path("assets/bckg.png")).resize((600, 450), Image.LANCZOS)
        self.background_photo = ImageTk.PhotoImage(background_image)
        self.canvas.create_image(0, 0, image=self.background_photo, anchor="nw")

        # File selection entry and button
        self.entry_file_path = tk.Entry(self.root, width=30)
        self.button_select = tk.Button(self.root, text="Select File", command=self.select_file)

        # Display file selection elements on the canvas
        self.canvas.create_text(130, 30, text="MP4 File", font=("Arial", 10, "bold"), fill="white")
        self.canvas.create_window(130, 60, window=self.entry_file_path)
        self.canvas.create_window(130, 90, window=self.button_select)

        # Video preview frame (black background)
        self.frame_preview = tk.Frame(self.root, bg="black", width=320, height=180)
        self.frame_preview.place(x=260, y=20)
        self.frame_preview.pack_propagate(False)  # Prevent frame from resizing with its content
        self.panel_video = tk.Label(self.frame_preview, bg="black")  # Video display area
        self.panel_video.pack(fill="both", expand=True)

        # Sliders for selecting start and end times
        self.slider_start = tk.Scale(self.root, from_=0, to=100, length=178, orient=tk.HORIZONTAL)
        self.slider_end = tk.Scale(self.root, from_=0, to=100, length=178, orient=tk.HORIZONTAL)
        self.entry_start_time = tk.Entry(self.root, width=30)
        self.entry_end_time = tk.Entry(self.root, width=30)

        # Disable slider events (mouse and keyboard) until a video is loaded
        self.slider_start.unbind("<ButtonPress-1>")  # Prevent clicking
        self.slider_start.unbind("<B1-Motion>")  # Prevent dragging
        self.slider_start.unbind("<KeyRelease>")  # Prevent keyboard adjustments
        self.slider_start.config(state=tk.DISABLED)  # Initially disabled

        self.slider_end.unbind("<ButtonPress-1>")  # Prevent clicking
        self.slider_end.unbind("<B1-Motion>")  # Prevent dragging
        self.slider_end.unbind("<KeyRelease>")  # Prevent keyboard adjustments
        self.slider_end.config(state=tk.DISABLED)  # Initially disabled

        # Place slider labels and elements on the canvas
        self.canvas.create_text(130, 120, text="Start time (sec)", font=("Arial", 10, "bold"), fill="white")
        self.canvas.create_window(130, 160, window=self.slider_start)
        self.canvas.create_window(130, 190, window=self.entry_start_time)

        self.canvas.create_text(130, 230, text="End time (sec)", font=("Arial", 10, "bold"), fill="white")
        self.canvas.create_window(130, 270, window=self.slider_end)
        self.canvas.create_window(130, 300, window=self.entry_end_time)

        # Control buttons
        self.button_play = tk.Button(self.root, text="Play Preview", command=self.video_player.start_video_preview,width=12)
        self.button_pause = tk.Button(self.root, text="Pause", command=self.video_player.toggle_pause, width=12)
        self.button_cut = tk.Button(self.root, text="Slice", command=self.slice_video, width=25)

        # Mute and Info buttons with icons
        self.boton_mute = tk.Button(self.root, image=self.icons["unmute"] if self.mute else self.icons["mute"],command=self.toggle_mute, borderwidth=0)
        # Set mute button state after widgets are created
        if self.mute is not None:
            self.boton_mute.config(image=self.icons["unmute"] if self.mute else self.icons["mute"])
        self.boton_info = tk.Button(self.root, image=self.icons["info"], command=self.info_box, borderwidth=0)
        self.boton_settings = tk.Button(self.root, image=self.icons["settings"], command=self.select_quality, borderwidth=0)

        # Initially disable key buttons until a video is loaded
        self.button_cut.config(state=tk.DISABLED)
        self.button_play.config(state=tk.DISABLED)
        self.button_pause.config(state=tk.DISABLED)

        # Position buttons in the window
        self.button_play.place(x=260, y=210)
        self.button_pause.place(x=370, y=210)
        self.button_cut.place(x=38, y=330)
        self.boton_mute.place(x=510, y=400)
        self.boton_info.place(x=550, y=400)
        self.boton_settings.place(x=470, y=400)

