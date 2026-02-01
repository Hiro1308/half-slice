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
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 10)  # Increase buffer to optimize performance
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
            if self.paused:
                time.sleep(0.1)
                continue

            ret, frame = self.cap.read()
            if not ret:
                break

            current_video_time = (self.cap.get(cv2.CAP_PROP_POS_FRAMES) / self.video_fps)
            if current_video_time >= end_time:
                break

            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            img = Image.fromarray(frame)
            img = img.resize((320, 180), Image.LANCZOS)
            img_tk = ImageTk.PhotoImage(image=img)

            self.gui.panel_video.config(image=img_tk)
            self.gui.panel_video.image = img_tk

            time.sleep(max(1 / self.video_fps, 0.005))

        self.playing_preview = False
        self.cap.release()
        self.cap = None

    def start_video_preview(self):
        """Starts or restarts the video preview in a separate thread."""
        if self.playing_preview:
            print("Reiniciando la previsualización desde 0")
            self.playing_preview = False
            time.sleep(0.1)

        self.gui.button_play.config(state=tk.DISABLED)

        if hasattr(self.gui, 'root'):
            self.gui.root.after(1000, lambda: self.gui.button_play.config(state=tk.NORMAL))
        else:
            self.gui.after(1000, lambda: self.gui.button_play.config(state=tk.NORMAL))

        self.playing_preview = True
        self.paused = False

        thread = threading.Thread(target=self.play_video_preview, daemon=True)
        thread.start()

    def toggle_pause(self):
        self.paused = not self.paused
        self.gui.button_pause.config(text="Resume" if self.paused else "Pause")

    # ---------- NUEVO: helpers para Discord 8MB ----------

    def _format_hms(self, seconds: float) -> str:
        seconds = max(0.0, float(seconds))
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:06.3f}"

    def _calc_discord_bitrates(self, duration_sec: float, target_mb: float = 8.0):
        """
        Calcula bitrates (kbps) para que el output quede <= target_mb.
        Usamos margen (0.97) para overhead de contenedor/metadatos.
        """
        duration_sec = max(0.1, float(duration_sec))

        target_bytes = target_mb * 1024 * 1024 * 0.97
        total_kbps = int((target_bytes * 8) / duration_sec / 1000)

        # audio adaptativo
        # si el total es bajo, bajamos audio para no matar el video
        if total_kbps <= 160:
            audio_kbps = 32
        elif total_kbps <= 260:
            audio_kbps = 64
        else:
            audio_kbps = 96

        video_kbps = max(80, total_kbps - audio_kbps)  # piso mínimo para no romper del todo

        return video_kbps, audio_kbps, total_kbps

    def trim_video(self):
        """Cuts the video using FFmpeg with quality settings from config.json OR Discord 8MB mode."""

        if self.clip is None:
            messagebox.showwarning("Error", "No video loaded.")
            return

        try:
            start_time = float(self.gui.entry_start_time.get())
            end_time = float(self.gui.entry_end_time.get())

            if start_time >= end_time or end_time > self.clip.duration:
                messagebox.showwarning("Error", "Invalid trim times.")
                return

            output_path = filedialog.asksaveasfilename(
                defaultextension=".mp4",
                filetypes=[("MP4 files", "*.mp4")]
            )
            if not output_path:
                return

            self.gui.soundmanager.play_loop("slice")
            self.gui.show_loading_screen()

            segment_duration = end_time - start_time

            # NUEVO: modo discord
            discord_mode = bool(self.gui.configuration.get("discord_8mb", False))

            if discord_mode:
                v_kbps, a_kbps, total_kbps = self._calc_discord_bitrates(segment_duration, target_mb=8.0)

                # forzamos 720p y 30fps para ayudar (Discord friendly)
                vf = "scale=1280:-2,fps=30"

                # Usamos -ss / -to de forma consistente y calculamos progreso con duración
                cmd = [
                    self.ffmpeg_path, "-y",
                    "-i", self.clip.filename,
                    "-ss", str(start_time), "-to", str(end_time),

                    "-vf", vf,

                    "-c:v", "libx264",
                    "-profile:v", "baseline",
                    "-level", "3.0",
                    "-preset", "veryfast",

                    # bitrate calculado (kbps)
                    "-b:v", f"{v_kbps}k",
                    "-maxrate", f"{v_kbps}k",
                    "-bufsize", f"{max(v_kbps * 2, 200)}k",

                    "-c:a", "aac",
                    "-b:a", f"{a_kbps}k",

                    "-movflags", "+faststart",
                    output_path
                ]

            else:
                # modo normal (tu lógica actual)
                preset = self.gui.configuration.get('preset', 'medium')
                bitrate = self.gui.configuration.get('bitrate', '2500k')
                resolution_map = {
                    '1080p': '1920x1080',
                    '720p': '1280x720',
                    '480p': '854x480',
                    '360p': '640x360'
                }
                resolution = resolution_map.get(self.gui.configuration.get('resolution', '720p'), '1280x720')

                cmd = [
                    self.ffmpeg_path, "-y", "-i", self.clip.filename,
                    "-ss", str(start_time), "-to", str(end_time),
                    "-c:v", "libx264", "-preset", preset,
                    "-b:v", bitrate,
                    "-s", resolution,
                    "-c:a", "aac", "-b:a", "128k",
                    output_path
                ]

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            # Parse FFmpeg output to update progress bar
            for line in iter(process.stderr.readline, ''):
                if "time=" in line:
                    try:
                        time_str = line.split("time=")[1].split(" ")[0]
                        h, m, s = map(float, time_str.split(':'))
                        current_time = h * 3600 + m * 60 + s
                        progress_percent = (current_time / segment_duration) * 100
                        if hasattr(self.gui, 'progress') and self.gui.progress is not None:
                            self.gui.progress["value"] = min(100, max(0, progress_percent))
                            self.gui.loading_screen.update_idletasks()
                    except ValueError:
                        continue

            process.wait()

            self.gui.soundmanager.stop_sound()
            self.gui.soundmanager.play_sound("success")

            # Si discord mode, mostramos info útil
            if discord_mode:
                try:
                    final_size = os.path.getsize(output_path) / (1024 * 1024)
                    messagebox.showinfo(
                        "Success",
                        f"Video saved at:\n{output_path}\n\nDiscord mode: OK\nFinal size: {final_size:.2f} MB"
                    )
                except Exception:
                    messagebox.showinfo("Success", f"Video saved at: {output_path}")
            else:
                messagebox.showinfo("Success", f"Video saved at: {output_path}")

        except Exception as e:
            messagebox.showwarning("Error", f"Error trimming the video: {e}")

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
        if self.cap is None or not self.cap.isOpened():
            return

        self.cap.set(cv2.CAP_PROP_POS_MSEC, time_pos * 1000)
        ret, frame = self.cap.read()
        if not ret:
            return

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame)
        img = img.resize((320, 180), Image.LANCZOS)
        img_tk = ImageTk.PhotoImage(image=img)

        self.gui.panel_video.config(image=img_tk)
        self.gui.panel_video.image = img_tk
