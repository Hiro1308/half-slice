import os
import cv2
import time
import threading
import subprocess
import sys
from moviepy import VideoFileClip
from PIL import Image, ImageTk, Image
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
                try:
                    fn()
                except Exception:
                    pass

    def _ui_safe(self, fn):
        """Si existe UIService.run_on_ui, lo usa; si no, fallback a _ui."""
        try:
            if hasattr(self.gui, "ui") and hasattr(self.gui.ui, "run_on_ui"):
                self.gui.ui.run_on_ui(fn)
                return
        except Exception:
            pass
        self._ui(fn)

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

    # -------------------- subprocess helpers (no-window, stable cwd, drain stderr) --------------------

    def _popen_no_window_kwargs(self):
        if os.name != "nt":
            return {}

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

        return {
            "creationflags": subprocess.CREATE_NO_WINDOW,
            "startupinfo": startupinfo,
        }

    def _ffmpeg_cwd(self):
        try:
            if self.ffmpeg_path and os.path.isabs(self.ffmpeg_path):
                return os.path.dirname(self.ffmpeg_path)
        except Exception:
            pass
        return None

    def _drain_stream(self, stream, tail_list=None, max_tail=120):
        """
        Drena un stream (stderr) para evitar deadlocks.
        Si tail_list es una lista, guarda las últimas líneas.
        """
        try:
            for line in stream:
                if not line:
                    break
                if tail_list is not None:
                    tail_list.append(line.rstrip("\n"))
                    if len(tail_list) > max_tail:
                        del tail_list[0:len(tail_list) - max_tail]
        except Exception:
            pass

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

        # validaciones de tiempos
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

        # habilitar play después de 1s
        try:
            self._ui(lambda: self.gui.root.after(1000, lambda: self.gui.button_play.config(state=tk.NORMAL)))
        except Exception:
            self._ui(lambda: self.gui.button_play.config(state=tk.NORMAL))

        # lanzar thread
        self._preview_thread = threading.Thread(
            target=self._play_video_preview_worker,
            args=(start_time, end_time),
            daemon=True
        )
        self._preview_thread.start()

    def _play_video_preview_worker(self, start_time: float, end_time: float):
        """Worker thread: NO toca tkinter; sólo lee frames y los manda por _ui."""
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

    # -------------------- trim / slice --------------------

    def trim_video(self):
        if self.clip is None:
            messagebox.showwarning("Error", "No video loaded.")
            return

        def _set_progress(p):
            p = float(max(0, min(100, p)))
            try:
                if hasattr(self.gui, "ui") and hasattr(self.gui.ui, "set_progress"):
                    self.gui.ui.set_progress(p)
                    return
            except Exception:
                pass

            def _u():
                try:
                    if hasattr(self.gui, "progress") and self.gui.progress is not None:
                        self.gui.progress["value"] = p
                except Exception:
                    pass
            self._ui_safe(_u)

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

            # mostrar loading UNA sola vez (acá)
            try:
                if hasattr(self.gui, "ui"):
                    self.gui.ui.show_loading("Processing clip...", "Processing clip...")
            except Exception:
                pass

            segment_duration = end_time - start_time
            discord_mode = bool(self.gui.configuration.get("discord_8mb", False))

            _set_progress(0)

            if discord_mode:
                v_kbps, a_kbps, _ = self._calc_discord_bitrates(segment_duration, target_mb=8.0)
                vf = "scale=1280:-2,fps=30"

                cmd = [
                    self.ffmpeg_path, "-y",
                    "-ss", str(start_time), "-to", str(end_time),
                    "-i", self.clip.filename,

                    "-vf", vf,
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-preset", "veryfast",
                    "-b:v", f"{v_kbps}k",
                    "-maxrate", f"{v_kbps}k",
                    "-bufsize", f"{max(v_kbps * 2, 200)}k",

                    "-c:a", "aac",
                    "-b:a", f"{a_kbps}k",
                    "-ac", "2",

                    "-movflags", "+faststart",
                    "-progress", "pipe:1",
                    "-nostats",
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
                    self.ffmpeg_path, "-y",
                    "-ss", str(start_time), "-to", str(end_time),
                    "-i", self.clip.filename,

                    "-c:v", "libx264",
                    "-preset", preset,
                    "-b:v", bitrate,
                    "-s", resolution,

                    "-c:a", "aac",
                    "-b:a", "128k",

                    "-movflags", "+faststart",
                    "-progress", "pipe:1",
                    "-nostats",
                    output_path
                ]

            # no window + cwd estable
            startupinfo = None
            creationflags = 0
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0
                creationflags = subprocess.CREATE_NO_WINDOW

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
                cwd=os.path.dirname(self.ffmpeg_path),
                startupinfo=startupinfo,
                creationflags=creationflags
            )

            # drenar stderr (evita deadlock)
            stderr_tail = []
            def drain_err():
                try:
                    for ln in process.stderr:
                        if not ln:
                            break
                        stderr_tail.append(ln.rstrip("\n"))
                        if len(stderr_tail) > 120:
                            stderr_tail.pop(0)
                except Exception:
                    pass

            threading.Thread(target=drain_err, daemon=True).start()

            # progreso por stdout (out_time_ms)
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                line = line.strip()

                if line.startswith("out_time_ms="):
                    try:
                        out_time = int(line.split("=", 1)[1]) / 1_000_000
                        pct = (out_time / max(segment_duration, 0.001)) * 100
                        _set_progress(pct)
                    except Exception:
                        pass
                elif line == "progress=end":
                    _set_progress(100)
                    break

            process.wait()

            self.gui.soundmanager.stop_sound()

            try:
                if hasattr(self.gui, "ui"):
                    self.gui.ui.hide_loading()
            except Exception:
                pass

            if process.returncode != 0:
                tail = "\n".join(stderr_tail)[-2000:].strip()
                raise RuntimeError(f"FFmpeg failed (code {process.returncode}).\n\n{tail}")

            self.gui.soundmanager.play_sound("success")
            messagebox.showinfo("Success", f"Video saved at: {output_path}")

        except Exception as e:
            try:
                self.gui.soundmanager.stop_sound()
            except Exception:
                pass
            try:
                if hasattr(self.gui, "ui"):
                    self.gui.ui.hide_loading()
            except Exception:
                pass
            messagebox.showwarning("Error", f"Error trimming the video: {e}")


    # -------------------- sliders --------------------

    def update_start_time(self, val):
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
