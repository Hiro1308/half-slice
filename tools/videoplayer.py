import os
import cv2
import time
import threading
import subprocess
import sys
from moviepy import VideoFileClip
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import filedialog, messagebox

class VideoPlayer:
    def __init__(self, gui):
        """Inicializa el reproductor de video."""
        self.gui = gui
        self.cap = None
        self.clip = None
        self.playing_preview = False
        self.paused = False
        self.video_fps = 30.0  # FPS predeterminado si no se puede obtener

        # Ruta al ejecutable de FFmpeg incluido en la aplicación
        self.ffmpeg_path = self.get_ffmpeg_path()
        print("Usando FFmpeg en:", self.ffmpeg_path)

    def get_ffmpeg_path(self):
        """Obtiene la ruta correcta de FFmpeg tanto en el código normal como en el standalone de PyInstaller."""
        if getattr(sys, 'frozen', False):
            # 🔥 Si el programa está empaquetado con PyInstaller
            base_path = os.path.dirname(sys.executable)  # Carpeta donde está el .exe
        else:
            # 🔥 Si se ejecuta normalmente (sin compilar)
            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # Subimos un nivel

        ffmpeg_exe = os.path.join(base_path, "ffmpeg", "bin", "ffmpeg.exe")

        if not os.path.exists(ffmpeg_exe):
            print(f"⚠️ ERROR: FFmpeg no encontrado en {ffmpeg_exe}")
        else:
            print(f"✅ FFmpeg encontrado en: {ffmpeg_exe}")

        return ffmpeg_exe

    def load_video(self, file_path):
        """Carga el video y configura los controles."""
        try:
            self.clip = VideoFileClip(file_path)
            self.cap = cv2.VideoCapture(file_path)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 10)  # Aumentar buffer para mejorar rendimiento
            self.video_fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0

            self.gui.enable_buttons()
            self.gui.slider_start.config(to=self.clip.duration, command=self.update_start_time)
            self.gui.slider_end.config(to=self.clip.duration, command=self.update_end_time)
            self.gui.slider_end.set(self.clip.duration)

            self.show_frame(0)  # Mostrar primer frame
        except Exception as e:
            self.gui.soundmanager.reproducir_sonido("denied")
            messagebox.showwarning("Error", f"No se pudo cargar el video: {e}")

    def play_video_preview(self):
        """Reproduce el fragmento del video sin audio en la interfaz."""
        if self.clip is None:
            messagebox.showwarning("Error", "No hay video cargado.")
            return

        # 🔥 Cerrar la captura anterior antes de abrir una nueva
        if self.cap is not None:
            self.cap.release()
            self.cap = None  # Evitar referencias a una captura cerrada

        # 🔥 REABRIR VideoCapture asegurándonos de que la anterior esté cerrada
        self.cap = cv2.VideoCapture(self.clip.filename)

        try:
            start_time = float(self.gui.entry_start_time.get())
            end_time = float(self.gui.entry_end_time.get())
        except ValueError:
            messagebox.showwarning("Error", "Tiempo de inicio o fin inválido.")
            return

        if start_time >= end_time:
            messagebox.showwarning("Error", "El tiempo de inicio debe ser menor que el final.")
            return

        self.cap.set(cv2.CAP_PROP_POS_FRAMES, int(start_time * self.video_fps))

        # ✅ Rehabilitar el botón en cuanto la preview comienza
        self.gui.root.after(1000, lambda: self.gui.button_play.config(state=tk.NORMAL))

        start_real_time = time.time()

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
        """Inicia o reinicia la previsualización en un hilo separado."""

        if self.playing_preview:
            print("♻️ Reiniciando la previsualización desde 0...")
            self.playing_preview = False
            time.sleep(0.1)

            # 🔥 Deshabilitar el botón por 2 segundos
        self.gui.button_play.config(state=tk.DISABLED)

        # ✅ Asegurar que usamos after() en la raíz de Tkinter
        if hasattr(self.gui, 'root'):
            self.gui.root.after(1000, lambda: self.gui.button_play.config(state=tk.NORMAL))
        else:
            self.gui.after(1000, lambda: self.gui.button_play.config(state=tk.NORMAL))

        self.playing_preview = True
        self.paused = False

        thread = threading.Thread(target=self.play_video_preview, daemon=True)
        thread.start()

    def toggle_pause(self):
        """Alterna entre pausar y reanudar la reproducción."""
        self.paused = not self.paused
        self.gui.button_pause.config(text="Resume" if self.paused else "Pause")

    def trim_video(self):
        """Recorta el video usando FFmpeg localmente para mayor velocidad."""
        if self.clip is None:
            messagebox.showwarning("Error", "No hay video cargado.")
            return

        try:
            start_time = float(self.gui.entry_start_time.get())
            end_time = float(self.gui.entry_end_time.get())

            if start_time >= end_time or end_time > self.clip.duration:
                messagebox.showwarning("Error", "Tiempos de recorte inválidos.")
                return

            output_path = filedialog.asksaveasfilename(defaultextension=".mp4", filetypes=[("MP4 files", "*.mp4")])
            if not output_path:
                return

            self.gui.soundmanager.play_loop("slice")
            self.gui.show_loading_screen()

            # Comando FFmpeg optimizado
            cmd = [
                self.ffmpeg_path, "-y", "-i", self.clip.filename,
                "-ss", str(start_time), "-to", str(end_time),
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                output_path
            ]

            try:
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if result.returncode != 0:
                    print(f"❌ Error ejecutando FFmpeg:\n{result.stderr}")
                else:
                    print("✅ FFmpeg ejecutado correctamente.")
            except Exception as e:
                print(f"⚠️ Error al ejecutar FFmpeg: {e}")

            self.gui.soundmanager.stop_sound()
            self.gui.soundmanager.reproducir_sonido("success")
            messagebox.showinfo("Éxito", f"Video guardado en: {output_path}")

        except Exception as e:
            messagebox.showwarning("Error", f"Error al recortar el video: {e}")

    def update_start_time(self, val):
        """Actualiza la entrada de tiempo de inicio."""
        self.gui.entry_start_time.delete(0, tk.END)
        self.gui.entry_start_time.insert(0, str(round(float(val), 2)))
        self.show_frame(float(val))

    def update_end_time(self, val):
        """Actualiza la entrada de tiempo de finalización."""
        self.gui.entry_end_time.delete(0, tk.END)
        self.gui.entry_end_time.insert(0, str(round(float(val), 2)))
        self.show_frame(float(val))

    def show_frame(self, time_pos):
        """Muestra un frame en la previsualización."""
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
