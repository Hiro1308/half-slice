import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
from pathlib import Path

from .ui_helpers import build_tab_canvas, add_bottom_right_icons


class YouTubeTab:
    title = "YouTube Downloader"

    def __init__(self, app, notebook):
        self.app = app
        self.frame = tk.Frame(notebook)
        self._downloading = False
        self._build()

    def _default_downloads_path(self) -> str:
        return str(Path.home() / "Downloads")

    def _downloads_display_name(self) -> str:
        lang = (os.environ.get("LANG", "") or "").lower()
        if "es" in lang:
            return "Descargas"
        return "Downloads"

    def set_mute_icon(self, img):
        if getattr(self, "btn_mute", None):
            self.btn_mute.config(image=img)

    def _build(self):
        canvas = build_tab_canvas(self.app, self.frame)

        canvas.create_text(80, 30, text="YouTube URL", font=("Arial", 10, "bold"), fill="white")
        self.entry_url = tk.Entry(canvas, width=42)
        canvas.create_window(160, 50, window=self.entry_url)
        
        canvas.create_text(70, 90, text=f"Save folder", font=("Arial", 10, "bold"), fill="white")
        self.entry_out = tk.Entry(canvas, width=32)
        canvas.create_window(130, 120, window=self.entry_out)
        tk.Button(canvas, text="Browse", command=self.browse_folder).place(x=240, y=108)
 
        # setear default desde config o Downloads
        saved_dir = self.app.configuration.get("youtube_download_dir")
        default_dir = saved_dir if saved_dir else self._default_downloads_path()
        self.entry_out.insert(0, default_dir)

        # guardar si el usuario escribe a mano y sale del input
        self.entry_out.bind("<FocusOut>", self._save_out_dir_from_entry)

        # Quality
        canvas.create_text(60, 160, text="Quality", font=("Arial", 10, "bold"), fill="white")
        self.quality_combo = ttk.Combobox(
            canvas,
            values=["1080p", "720p", "480p", "360p"],
            state="readonly",
            width=10
        )
        self.quality_combo.set("720p")
        canvas.create_window(75, 190, window=self.quality_combo)

        # Output type
        canvas.create_text(180, 160, text="Format", font=("Arial", 10, "bold"), fill="white")
        self.format_combo = ttk.Combobox(
            canvas,
            values=["MP4", "MP3"],
            state="readonly",
            width=10
        )
        self.format_combo.set("MP4")
        canvas.create_window(195, 190, window=self.format_combo)

        # Progress
        canvas.create_text(160, 225, text="Progress", font=("Arial", 9, "bold"), fill="white")
        self.progress = ttk.Progressbar(canvas, orient="horizontal", length=260, mode="determinate", maximum=100)
        canvas.create_window(160, 245, window=self.progress)

        self.lbl_status = tk.Label(canvas, text="", bg="#000000", fg="white", font=("Arial", 9))
        canvas.create_window(160, 270, window=self.lbl_status)

        self.btn_download = tk.Button(canvas, text="Download", command=self.download, width=25)
        self.btn_download.place(x=65, y=295)

        self.btn_mute = add_bottom_right_icons(self.app, canvas, prefix="yt")

    # -------------------------
    # Persistencia de carpeta
    # -------------------------
    def _save_download_dir(self, folder: str):
        if not folder:
            return
        self.app.configuration["youtube_download_dir"] = folder
        self.app.save_configuration()

    def _save_out_dir_from_entry(self, _event=None):
        folder = self.entry_out.get().strip()
        if folder:
            self._save_download_dir(folder)

    def browse_folder(self):
        self.app.soundmanager.play_sound("button")

        initial_dir = self.entry_out.get().strip() or self._default_downloads_path()
        folder = filedialog.askdirectory(initialdir=initial_dir)

        if folder:
            self.entry_out.delete(0, tk.END)
            self.entry_out.insert(0, folder)
            self._save_download_dir(folder)

    # ---------- Thread-safe UI helpers ----------
    def _set_status(self, text):
        self.app.root.after(0, lambda: self.lbl_status.config(text=text))

    def _set_progress(self, value):
        def _u():
            self.progress["value"] = max(0, min(100, float(value)))
        self.app.root.after(0, _u)

    def _set_downloading(self, downloading: bool):
        def _u():
            self._downloading = downloading
            self.btn_download.config(state=("disabled" if downloading else "normal"))
            if not downloading:
                self._set_status("")
        self.app.root.after(0, _u)

    # ---------- yt-dlp progress hook ----------
    def _ytdlp_hook(self, line: str):
        pct = self.app.youtube_service.parse_progress_percent(line)
        if pct is not None:
            self._set_progress(pct)
            self._set_status(f"Downloading... {pct:.1f}%")
        else:
            if "[ExtractAudio]" in line:
                self._set_status("Converting to MP3...")
            elif "Merging formats" in line:
                self._set_status("Merging video+audio...")
            elif "Destination" in line:
                self._set_status("Starting...")

    def download(self):
        self.app.soundmanager.play_sound("button")

        if self._downloading:
            return

        url = self.entry_url.get().strip()
        out_dir = self.entry_out.get().strip()
        quality = self.quality_combo.get().strip()
        fmt_ui = self.format_combo.get().strip().upper()  # "MP4" | "MP3"
        output_type = "mp3" if fmt_ui == "MP3" else "mp4"

        # normalizar url mínima (por si pega "tps://")
        if url.startswith("tps://"):
            url = "ht" + url
            self.entry_url.delete(0, tk.END)
            self.entry_url.insert(0, url)

        if not url:
            messagebox.showerror("Error", "Pegá una URL de YouTube.")
            return
        if not out_dir:
            messagebox.showerror("Error", "Elegí una carpeta válida para guardar.")
            return
        if quality not in ("1080p", "720p", "480p", "360p"):
            messagebox.showerror("Error", "Elegí una calidad: 1080p, 720p, 480p o 360p.")
            return
        if not os.path.isdir(out_dir):
            messagebox.showerror("Error", "La carpeta seleccionada no existe.")
            return

        # Persistir carpeta por si cambió y no salió del focus
        self._save_download_dir(out_dir)

        self._set_progress(0)
        self._set_status("Preparing...")
        self._set_downloading(True)

        def worker():
            ok = False
            try:
                ok = self.app.youtube_service.download(
                    url=url,
                    out_dir=out_dir,
                    quality=quality,
                    output_type=output_type,
                    progress_hook=self._ytdlp_hook,
                )
            except FileNotFoundError as e:
                ok = False
                self.app.root.after(0, lambda: messagebox.showerror("Missing dependency", str(e)))
            except Exception as e:
                self.app.root.after(0, lambda: messagebox.showerror("Error", str(e)))

            def finish():
                self._set_downloading(False)
                if ok:
                    self._set_progress(100)
                    self._set_status("Done ✅")
                    self.app.soundmanager.play_sound("success")
                    messagebox.showinfo("YouTube Downloader", f"Listo!\nFormato: {fmt_ui}\nCalidad: {quality}")
                else:
                    self._set_status("Failed")
                    messagebox.showerror("YouTube Downloader", "Falló la descarga. Revisá la URL o yt-dlp/ffmpeg.")

            self.app.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()
