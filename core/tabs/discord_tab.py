import tkinter as tk
from tkinter import filedialog, messagebox

from .ui_helpers import build_tab_canvas, add_bottom_right_icons
from ..services.ffmpeg_service import FFmpegService


class DiscordTab:
    title = "Discord Compressor"

    def __init__(self, app, notebook):
        self.app = app
        self.frame = tk.Frame(notebook)
        self.ff = FFmpegService(app.get_path)
        self._build()

    def set_mute_icon(self, img):
        if getattr(self, "btn_mute", None):
            self.btn_mute.config(image=img)

    def _build(self):
        canvas = build_tab_canvas(self.app, self.frame)

        canvas.create_text(70, 30, text="MP4 Video", font=("Arial", 10, "bold"), fill="white")

        self.entry_in = tk.Entry(canvas, width=32)
        canvas.create_window(130, 60, window=self.entry_in)

        tk.Button(canvas, text="Browse", command=self.browse_mp4).place(x=250, y=48)

        canvas.create_text(145, 110, text="Save to folder (Default same folder)", font=("Arial", 10, "bold"), fill="white")

        self.entry_out = tk.Entry(canvas, width=32)
        canvas.create_window(130, 140, window=self.entry_out)

        tk.Button(canvas, text="Browse", command=self.browse_folder).place(x=250, y=128)

        tk.Button(canvas, text="Compress to 10MB", command=self.compress, width=25).place(x=35, y=195)

        self.btn_mute = add_bottom_right_icons(self.app, canvas, prefix="discord")

    def browse_mp4(self):
        self.app.soundmanager.play_sound("button")
        file_path = filedialog.askopenfilename(filetypes=[("MP4 files", "*.mp4")])
        if file_path:
            self.entry_in.delete(0, tk.END)
            self.entry_in.insert(0, file_path)

    def browse_folder(self):
        self.app.soundmanager.play_sound("button")
        folder = filedialog.askdirectory()
        if folder:
            self.entry_out.delete(0, tk.END)
            self.entry_out.insert(0, folder)

    def compress(self):
        self.app.soundmanager.play_sound("button")

        input_path = self.entry_in.get().strip()
        out_dir = self.entry_out.get().strip()

        if not input_path:
            messagebox.showerror("Error", "Elegí un MP4 válido primero.")
            return

        self.app.ui.show_loading("Compressing for Discord...", "Compressing for Discord...")
        self.app.ui.set_progress(0)

        def worker():
            try:
                ok, output_path, size_mb = self.ff.compress_to_discord_10mb(
                    input_path,
                    out_dir if out_dir else None,
                    on_progress=self.app.ui.set_progress,
                    on_status=self.app.ui.set_status_text
                )

                def done():
                    self.app.ui.hide_loading()
                    if ok:
                        self.app.soundmanager.play_sound("success")
                        messagebox.showinfo("Done", f"Listo \n{output_path}\nSize: {size_mb:.2f} MB")
                    else:
                        messagebox.showerror("Error", "No pude bajarlo a 10MB con los límites actuales.")

                self.app.ui.run_on_ui(done)

            except Exception as e:
                err = str(e)
                self.app.ui.run_on_ui(
                    lambda err=err: (
                        self.app.ui.hide_loading(),
                        messagebox.showerror("Error", f"Falló la compresión: {err}")
                    )
                )

        import threading
        threading.Thread(target=worker, daemon=True).start()
