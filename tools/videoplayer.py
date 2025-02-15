import os
import cv2
import time
import threading
import subprocess
import sys
from moviepy import VideoFileClip
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

class VideoPlayer:
    def __init__(self, gui):
        self.gui = gui
        self.cap = None
        self.clip = None
        self.playing_preview = False
        self.paused = False
        self.video_fps = 30.0

        self.ffmpeg_path = self.get_ffmpeg_path()
        print("Using FFMEPG in:", self.ffmpeg_path)

    def get_ffmpeg_path(self):
        # If the program is being executed on the standalone or without being compiled
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        ffmpeg_exe = os.path.join(base_path, "ffmpeg", "bin", "ffmpeg.exe")

        # Just for the logs :)
        if not os.path.exists(ffmpeg_exe):
            print(f"ERROR: FFmpeg not found in {ffmpeg_exe}")
        else:
            print(f"FFmpeg found in: {ffmpeg_exe}")

        return ffmpeg_exe

    def load_video(self, file_path):
        """ Loads the video and sets up the controllers """
        try:
            self.clip = VideoFileClip(file_path)
            self.cap = cv2.VideoCapture(file_path)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 10)  # Increas buffer to optimize performance
            self.video_fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0

            self.gui.enable_buttons()
            self.gui.slider_start.config(to=self.clip.duration, command=self.update_start_time)
            self.gui.slider_end.config(to=self.clip.duration, command=self.update_end_time)
            self.gui.slider_end.set(self.clip.duration)

            self.show_frame(0)
        except Exception as e:
            self.gui.soundmanager.play_sound("denied")
            messagebox.showwarning("Error", f"Video could not be loaded: {e}")

    def play_video_preview(self):
        """ Plays the fragment of the video without audio in the interface."""
        if self.clip is None:
            messagebox.showwarning("Error", "No video loaded.")
            return

        # Closing the previous capture before open a new one
        if self.cap is not None:
            self.cap.release()
            self.cap = None  # Avoid references to a close capture

        # Reopening VideoCapture ensuring the previous one is closed
        self.cap = cv2.VideoCapture(self.clip.filename)

        try:
            start_time = float(self.gui.entry_start_time.get())
            end_time = float(self.gui.entry_end_time.get())
        except ValueError:
            messagebox.showwarning("Error", "Invalid start or end time.")
            return

        if start_time >= end_time:
            messagebox.showwarning("Error", "Start time should be less than end time.")
            return

        self.cap.set(cv2.CAP_PROP_POS_FRAMES, int(start_time * self.video_fps))

        # Reactivate the button 1 sec after the preview starts
        self.gui.root.after(1000, lambda: self.gui.button_play.config(state=tk.NORMAL))

        while self.playing_preview:
            # If the video is paused, wait and continue looping
            if self.paused:
                time.sleep(0.1)
                continue

            # Read the next frame from the video
            ret, frame = self.cap.read()

            # If no frame is returned, stop the preview
            if not ret:
                break

            # Calculate the current playback time based on the frame position
            current_video_time = (self.cap.get(cv2.CAP_PROP_POS_FRAMES) / self.video_fps)

            # If the video has reached the end time, stop the preview
            if current_video_time >= end_time:
                break

            # Convert the frame from BGR (OpenCV format) to RGB (PIL format)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Convert the frame to a PIL image and resize it for display
            img = Image.fromarray(frame)
            img = img.resize((320, 180), Image.LANCZOS)
            img_tk = ImageTk.PhotoImage(image=img)

            # Update the GUI panel with the new frame
            self.gui.panel_video.config(image=img_tk)
            self.gui.panel_video.image = img_tk

            # Control the frame rate to match the original video FPS
            time.sleep(max(1 / self.video_fps, 0.005))

        self.playing_preview = False
        self.cap.release()
        self.cap = None

    def start_video_preview(self):
        """Starts or restarts the video preview in a separate thread."""

        # If a preview is already running, stop it and restart from the beginning
        if self.playing_preview:
            print("Reiniciando la previsualización desde 0")
            self.playing_preview = False
            time.sleep(0.1) # Short delay to ensure proper stopping before restarting

        # Disable the play button to prevent spamming while starting the preview
        self.gui.button_play.config(state=tk.DISABLED)

        # Re-enable the play button after 1 second
        if hasattr(self.gui, 'root'):
            self.gui.root.after(1000, lambda: self.gui.button_play.config(state=tk.NORMAL))
        else:
            self.gui.after(1000, lambda: self.gui.button_play.config(state=tk.NORMAL))

        # Set flags to indicate that the preview is running and not paused
        self.playing_preview = True
        self.paused = False

        # Start the video preview in a separate thread to avoid blocking the GUI
        thread = threading.Thread(target=self.play_video_preview, daemon=True)
        thread.start()

    def toggle_pause(self):
        self.paused = not self.paused
        self.gui.button_pause.config(text="Resume" if self.paused else "Pause")

    def trim_video(self):
        """Cuts the video using FFmpeg with quality settings from config.json."""

        if self.clip is None:
            messagebox.showwarning("Error", "No video loaded.")  # Warn if no video is loaded
            return

        try:
            # Get start and end times from GUI inputs
            start_time = float(self.gui.entry_start_time.get())
            end_time = float(self.gui.entry_end_time.get())

            # Validate trim times
            if start_time >= end_time or end_time > self.clip.duration:
                messagebox.showwarning("Error", "Invalid trim times.")  # Warn if times are invalid
                return

            # Ask for output file path
            output_path = filedialog.asksaveasfilename(defaultextension=".mp4", filetypes=[("MP4 files", "*.mp4")])
            if not output_path:
                return

            self.gui.soundmanager.play_loop("slice")  # Play slicing sound
            self.gui.show_loading_screen()  # Show loading screen with progress bar

            # Load quality settings from config.json or use defaults
            preset = self.gui.configuration.get('preset', 'medium')
            bitrate = self.gui.configuration.get('bitrate', '2500k')
            resolution_map = {
                '1080p': '1920x1080',
                '720p': '1280x720',
                '480p': '854x480',
                '360p': '640x360'
            }
            resolution = resolution_map.get(self.gui.configuration.get('resolution', '720p'), '1280x720')

            # Construct FFmpeg command with selected quality settings
            cmd = [
                self.ffmpeg_path, "-y", "-i", self.clip.filename,
                "-ss", str(start_time), "-to", str(end_time),
                "-c:v", "libx264", "-preset", preset,
                "-b:v", bitrate,
                "-s", resolution,
                "-c:a", "aac", "-b:a", "128k",
                output_path
            ]

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)  # Run FFmpeg

            # Parse FFmpeg output to update progress bar
            for line in iter(process.stderr.readline, ''):
                if "time=" in line:
                    try:
                        time_str = line.split("time=")[1].split(" ")[0]  # Extract time string
                        h, m, s = map(float, time_str.split(':'))  # Convert time to float
                        current_time = h * 3600 + m * 60 + s
                        progress_percent = (current_time / (end_time - start_time)) * 100  # Calculate progress
                        if hasattr(self.gui, 'progress') and self.gui.progress is not None:
                            self.gui.progress["value"] = progress_percent  # Update progress bar
                            self.gui.loading_screen.update_idletasks()  # Refresh UI
                    except ValueError:
                        continue  # Ignore invalid lines

            process.wait()  # Wait for FFmpeg to finish

            self.gui.soundmanager.stop_sound()  # Stop slicing sound
            self.gui.soundmanager.play_sound("success")  # Play success sound
            messagebox.showinfo("Success", f"Video saved at: {output_path}")  # Show success message

        except Exception as e:
            messagebox.showwarning("Error", f"Error trimming the video: {e}")  # Show error message if exception occurs

    def update_start_time(self, val):
        self.gui.entry_start_time.delete(0, tk.END)
        self.gui.entry_start_time.insert(0, str(round(float(val), 2)))
        self.show_frame(float(val))

    def update_end_time(self, val):
        self.gui.entry_end_time.delete(0, tk.END)
        self.gui.entry_end_time.insert(0, str(round(float(val), 2)))
        self.show_frame(float(val))

    def show_frame(self, time_pos):
        """Displays a specific frame from the video at a given timestamp."""

        # Check if the video capture is initialized and open
        if self.cap is None or not self.cap.isOpened():
            return

        # Set the video position to the specified time in milliseconds
        self.cap.set(cv2.CAP_PROP_POS_MSEC, time_pos * 1000)

        # Read the next frame from the video
        ret, frame = self.cap.read()

        # If no frame is retrieved, exit the function
        if not ret:
            return

        # Convert the frame from BGR (OpenCV format) to RGB (PIL format)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Convert the frame to a PIL image and resize it for display
        img = Image.fromarray(frame)
        img = img.resize((320, 180), Image.LANCZOS)
        img_tk = ImageTk.PhotoImage(image=img)

        # Update the GUI panel with the new frame
        self.gui.panel_video.config(image=img_tk)
        self.gui.panel_video.image = img_tk
