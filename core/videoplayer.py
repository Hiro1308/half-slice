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

        # sincronización
        self._cap_lock = threading.Lock()
        self._preview_thread = None

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

    # -------------------- helpers internos (thread-safe UI) --------------------

    def _ui(self, fn):
        """Ejecuta fn() en el hilo de UI."""
        try:
            self.gui.root.after(0, fn)
        except Exception:
            try:
                self.gui.after(0, fn)
            except Exception:
                # último recurso: ejecutar directo (no ideal, pero evita crash si no hay root)
                try:
                    fn()
                except Exception:
                    pass

    def _set_panel_image(self, img_rgb):
        """Convierte numpy RGB -> PhotoImage y lo setea en el label (SIEMPRE en UI thread)."""
        def apply():
            try:
                img = Image.fromarray(img_rgb)
                img = img.resize((320, 180), Image.LANCZOS)
                img_tk = ImageTk.PhotoImage(image=img)
                self.gui.panel_video.config(image=img_tk)
                self.gui.panel_video.image = img_tk
            except Exception:
                pass

        self._ui(apply)

    def _safe_release_cap(self):
        with self._cap_lock:
            try:
                if self.cap is not None:
                    self.cap.release()
            except Exception:
                pass
            self.cap = None

    # -------------------- carga --------------------

    def load_video(self, file_path):
        """Loads the video and sets up the controllers."""
        try:
            self.stop_preview()

            self.clip = VideoFileClip(file_path)

            # abrir cap para scrubbing (show_frame)
            self._safe_release_cap()
            with self._cap_lock:
                self.cap = cv2.VideoCapture(file_path)
                try:
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 10)
                except Exception:
                    pass
                fps = self.cap.get(cv2.CAP_PROP_FPS)
                self.video_fps = fps or 30.0

            self.gui.enable_buttons()
            self.gui.slider_start.config(to=self.clip.duration, command=self.update_start_time)
            self.gui.slider_end.config(to=self.clip.duration, command=self.update_end_time)
            self.gui.slider_end.set(self.clip.duration)

            self.show_frame(0)

        except Exception as e:
            try:
                self.gui.soundmanager.play_sound("denied")
            except Exception:
                pass
            messagebox.showwarning("Error", f"Video could not be loaded: {e}")

    # -------------------- preview --------------------

    def stop_preview(self):
        """Stop preview safely (can be called from UI thread)."""
        self.playing_preview = False
        self.paused = False

        def reset_pause_text():
            try:
                self.gui.button_pause.config(text="Pause")
            except Exception:
                pass

        self._ui(reset_pause_text)

    def start_video_preview(self):
        """Starts or restarts the video preview in a separate thread."""
        if self.clip is None:
            messagebox.showwarning("Error", "No video loaded.")
            return

        # reinicia
        if self.playing_preview:
            self.stop_preview()
            time.sleep(0.05)

        # deshabilitar play instantáneo
        self._ui(lambda: self.gui.button_play.config(state=tk.DISABLED))

        # validaciones de tiempos (en UI thread se leen entries, ok)
        try:
            start_time = float(self.gui.entry_start_time.get())
            end_time = float(self.gui.entry_end_time.get())
        except ValueError:
            self._ui(lambda: self.gui.button_play.config(state=tk.NORMAL))
            messagebox.showwarning("Error", "Invalid start or end time.")
            return

        if start_time >= end_time:
            self._ui(lambda: self.gui.button_play.config(state=tk.NORMAL))
            messagebox.showwarning("Error", "Start time should be less than end time.")
            return

        self.playing_preview = True
        self.paused = False

        # habilitar play después de 1s (como tenías)
        self._ui(lambda: self.gui.root.after(1000, lambda: self.gui.button_play.config(state=tk.NORMAL)))

        # lanzar thread
        self._preview_thread = threading.Thread(
            target=self._play_video_preview_worker,
            args=(start_time, end_time),
            daemon=True
        )
        self._preview_thread.start()

    def _play_video_preview_worker(self, start_time: float, end_time: float):
        """Worker thread: NO toca tkinter; sólo lee frames y los manda por _ui."""
        # reabrir cap dedicada al preview
        self._safe_release_cap()
        with self._cap_lock:
            self.cap = cv2.VideoCapture(self.clip.filename)
            if self.cap is None or not self.cap.isOpened():
                self.playing_preview = False
                self._ui(lambda: messagebox.showwarning("Error", "Could not open video capture."))
                return

            self.cap.set(cv2.CAP_PROP_POS_FRAMES, int(start_time * self.video_fps))

        last_emit = 0.0
        min_emit_interval = 1.0 / max(self.video_fps, 1.0)

        while self.playing_preview:
            if self.paused:
                time.sleep(0.05)
                continue

            with self._cap_lock:
                if self.cap is None:
                    break

                ret, frame = self.cap.read()
                if not ret:
                    break

                current_video_time = (self.cap.get(cv2.CAP_PROP_POS_FRAMES) / self.video_fps)

            if current_video_time >= end_time:
                break

            # throttle mínimo
            now = time.time()
            if now - last_emit >= min_emit_interval:
                try:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                except Exception:
                    continue
                self._set_panel_image(frame_rgb)
                last_emit = now

            time.sleep(0.001)

        self.playing_preview = False
        self._safe_release_cap()

    def toggle_pause(self):
        self.paused = not self.paused

        def set_text():
            try:
                self.gui.button_pause.config(text="Resume" if self.paused else "Pause")
            except Exception:
                pass

        self._ui(set_text)

    # ---------- helpers para Discord 8MB ----------

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

        if total_kbps <= 160:
            audio_kbps = 32
        elif total_kbps <= 260:
            audio_kbps = 64
        else:
            audio_kbps = 96

        video_kbps = max(80, total_kbps - audio_kbps)
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

            discord_mode = bool(self.gui.configuration.get("discord_8mb", False))

            if discord_mode:
                v_kbps, a_kbps, total_kbps = self._calc_discord_bitrates(segment_duration, target_mb=8.0)

                # Compresión tipo "Discord compressor":
                # - fps fijo
                # - escala (720p) friendly
                # - yuv420p (compatibilidad)
                # - faststart
                # - límites de bitrate
                vf = "scale=1280:-2,fps=30"

                cmd = [
                    self.ffmpeg_path, "-y",
                    "-ss", str(start_time), "-to", str(end_time),
                    "-i", self.clip.filename,

                    "-vf", vf,

                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-preset", "veryfast",

                    # bitrate calculado (kbps)
                    "-b:v", f"{v_kbps}k",
                    "-maxrate", f"{v_kbps}k",
                    "-bufsize", f"{max(v_kbps * 2, 200)}k",

                    # audio también ajustado
                    "-c:a", "aac",
                    "-b:a", f"{a_kbps}k",
                    "-ac", "2",

                    "-movflags", "+faststart",
                    output_path
                ]
            else:
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

    # -------------------- sliders --------------------

    def update_start_time(self, val):
        # si el usuario cambia el slider mientras preview corre, cortamos preview
        if self.playing_preview:
            self.stop_preview()

        self.gui.entry_start_time.delete(0, tk.END)
        self.gui.entry_start_time.insert(0, str(round(float(val), 2)))
        self.show_frame(float(val))

    def update_end_time(self, val):
        if self.playing_preview:
            self.stop_preview()

        self.gui.entry_end_time.delete(0, tk.END)
        self.gui.entry_end_time.insert(0, str(round(float(val), 2)))
        self.show_frame(float(val))

    def show_frame(self, time_pos):
        """Displays a specific frame from the video at a given timestamp."""
        # si preview corre, lo cortamos para que no compitan por cap
        if self.playing_preview:
            self.stop_preview()
            time.sleep(0.01)

        with self._cap_lock:
            if self.cap is None or not self.cap.isOpened():
                return

            self.cap.set(cv2.CAP_PROP_POS_MSEC, time_pos * 1000)
            ret, frame = self.cap.read()

        if not ret:
            return

        try:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        except Exception:
            return

        self._set_panel_image(frame_rgb)
