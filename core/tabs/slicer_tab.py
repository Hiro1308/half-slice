import tkinter as tk
from tkinter import filedialog, messagebox
import threading

from .ui_helpers import build_tab_canvas, add_bottom_right_icons


class SlicerTab:
    title = "Slicer"

    def __init__(self, app, notebook):
        self.app = app
        self.frame = tk.Frame(notebook)
        self._build()

    def set_mute_icon(self, img):
        if getattr(self, "btn_mute", None):
            self.btn_mute.config(image=img)

    def _build(self):
        canvas = build_tab_canvas(self.app, self.frame)

        self.entry_file_path = tk.Entry(canvas, width=30)
        self.button_select = tk.Button(canvas, text="Select File", command=self.select_file)

        canvas.create_text(130, 30, text="MP4 File", font=("Arial", 10, "bold"), fill="white")
        canvas.create_window(130, 60, window=self.entry_file_path)
        canvas.create_window(130, 90, window=self.button_select)

        self.frame_preview = tk.Frame(canvas, bg="black", width=320, height=180)
        self.frame_preview.pack_propagate(False)
        self.panel_video = tk.Label(self.frame_preview, bg="black")
        self.panel_video.pack(fill="both", expand=True)
        canvas.create_window(420, 110, window=self.frame_preview)

        self.slider_start = tk.Scale(canvas, from_=0, to=100, length=178, orient=tk.HORIZONTAL)
        self.slider_end = tk.Scale(canvas, from_=0, to=100, length=178, orient=tk.HORIZONTAL)
        self.entry_start_time = tk.Entry(canvas, width=30)
        self.entry_end_time = tk.Entry(canvas, width=30)

        # disabled inicial
        self.slider_start.config(state=tk.DISABLED)
        self.slider_end.config(state=tk.DISABLED)

        canvas.create_text(130, 120, text="Start time (sec)", font=("Arial", 10, "bold"), fill="white")
        canvas.create_window(130, 160, window=self.slider_start)
        canvas.create_window(130, 190, window=self.entry_start_time)

        canvas.create_text(130, 230, text="End time (sec)", font=("Arial", 10, "bold"), fill="white")
        canvas.create_window(130, 270, window=self.slider_end)
        canvas.create_window(130, 300, window=self.entry_end_time)

        self.button_play = tk.Button(
            canvas, text="Play Preview",
            command=self._on_play_preview,
            width=12
        )
        self.button_pause = tk.Button(
            canvas, text="Pause",
            command=self.app.video_player.toggle_pause,
            width=12
        )
        self.button_cut = tk.Button(
            canvas, text="Slice",
            command=self.slice_video,
            width=25
        )

        self.button_cut.config(state=tk.DISABLED)
        self.button_play.config(state=tk.DISABLED)
        self.button_pause.config(state=tk.DISABLED)

        canvas.create_window(320, 230, window=self.button_play)
        canvas.create_window(430, 230, window=self.button_pause)
        canvas.create_window(130, 345, window=self.button_cut)

        self.btn_mute = add_bottom_right_icons(self.app, canvas, prefix="")

        # 🔥 bindings: si el usuario toca/mueve sliders, cortamos preview para no crashear
        for w in (self.slider_start, self.slider_end):
            w.bind("<Button-1>", self._on_slider_interaction)
            w.bind("<B1-Motion>", self._on_slider_interaction)

        # guardar refs en app si tu VideoPlayer espera ciertas props
        self.app.entry_file_path = self.entry_file_path
        self.app.slider_start = self.slider_start
        self.app.slider_end = self.slider_end
        self.app.entry_start_time = self.entry_start_time
        self.app.entry_end_time = self.entry_end_time
        self.app.panel_video = self.panel_video
        self.app.button_cut = self.button_cut
        self.app.button_play = self.button_play
        self.app.button_pause = self.button_pause

    # -------------------- helpers UI --------------------

    def _on_slider_interaction(self, event=None):
        """Al tocar/mover sliders: stop preview para evitar race conditions."""
        try:
            self.app.video_player.stop_preview()
        except Exception:
            pass

    def _on_play_preview(self):
        """Antes de play: asegurar entries válidas."""
        try:
            # Si están vacíos, inicializamos con valores de sliders
            if not self.entry_start_time.get().strip():
                self.entry_start_time.insert(0, str(float(self.slider_start.get())))
            if not self.entry_end_time.get().strip():
                self.entry_end_time.insert(0, str(float(self.slider_end.get())))
        except Exception:
            pass

        self.app.video_player.start_video_preview()

    # -------------------- acciones --------------------

    def select_file(self):
        self.app.soundmanager.play_sound("button")

        # si había preview, lo cortamos antes de cambiar de archivo
        try:
            self.app.video_player.stop_preview()
        except Exception:
            pass

        file_path = filedialog.askopenfilename(filetypes=[("MP4 files", "*.mp4")])
        if not file_path:
            return

        self.entry_file_path.delete(0, tk.END)
        self.entry_file_path.insert(0, file_path)

        self.app.video_player.load_video(file_path)

        # habilitar controles
        self.enable_buttons()

        # inicializar start a 0 (y entry)
        self.slider_start.set(0)
        self.entry_start_time.delete(0, tk.END)
        self.entry_start_time.insert(0, "0")

        # end: si ya está seteado por load_video (duration), reflejarlo en entry
        try:
            end_val = float(self.slider_end.get())
            self.entry_end_time.delete(0, tk.END)
            self.entry_end_time.insert(0, str(round(end_val, 2)))
        except Exception:
            pass

    def enable_buttons(self):
        self.slider_start.config(state=tk.NORMAL)
        self.slider_end.config(state=tk.NORMAL)
        self.button_cut.config(state=tk.NORMAL)
        self.button_play.config(state=tk.NORMAL)
        self.button_pause.config(state=tk.NORMAL)

    def slice_video(self):
        self.app.soundmanager.play_sound("button")
        try:
            self.app.video_player.stop_preview()
        except Exception:
            pass

        file_path = self.entry_file_path.get().strip()
        if not file_path:
            messagebox.showerror("Error", "Please select a video file first.")
            return

        def worker():
            try:
                self.app.video_player.trim_video()
            except Exception as e:
                self.app.ui.run_on_ui(
                    lambda: messagebox.showwarning("Error", f"Error when slicing video: {e}")
                )

        threading.Thread(target=worker, daemon=True).start()

