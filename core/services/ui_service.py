import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk


class UIService:
    def __init__(self, root, get_path_fn):
        self.root = root
        self.get_path = get_path_fn
        self.loading_screen = None
        self.progress = None

    def run_on_ui(self, fn):
        self.root.after(0, fn)

    def set_status_text(self, text: str):
        if hasattr(self, "status_label"):
            self.status_label.config(text=text)

    def show_loading(self, title="Processing...", text="Processing..."):
        def _show():
            if self.loading_screen:
                try:
                    self.loading_screen.destroy()
                except:
                    pass

            self.loading_screen = tk.Toplevel(self.root)
            self.loading_screen.title(title)
            self.loading_screen.geometry("350x120")
            self.loading_screen.resizable(False, False)
            self.loading_screen.iconbitmap(self.get_path("assets\\icon.ico"))

            frame = tk.Frame(self.loading_screen)
            frame.pack(pady=10, padx=10)

            icon_img = Image.open(self.get_path("assets\\processing.png")).resize((60, 60), Image.LANCZOS)
            icon = ImageTk.PhotoImage(icon_img)
            icon_label = tk.Label(frame, image=icon)
            icon_label.image = icon
            icon_label.grid(row=0, column=0, rowspan=2, padx=(0, 20), sticky="w")

            text_label = tk.Label(frame, text=text, font=("Arial", 12))
            text_label.grid(row=0, column=1, sticky="w")

            # 👇 NUEVO: texto de estado (Intento X de Y)
            self.status_label = tk.Label(
                frame,
                text="",
                font=("Arial", 9, "italic"),
                fg="#555555"
            )
            self.status_label.grid(row=1, column=1, sticky="w")

            self.progress = ttk.Progressbar(
                frame,
                orient="horizontal",
                length=200,
                mode="determinate"
            )
            self.progress.grid(row=2, column=1, pady=(5, 0), sticky="we")

            self.progress["value"] = 0

            # modal-ish
            self.loading_screen.wm_attributes("-toolwindow", True)
            self.loading_screen.protocol("WM_DELETE_WINDOW", lambda: None)
            self.loading_screen.grab_set()

            # center
            self._center(self.loading_screen, 350, 120)

        self.run_on_ui(_show)

    def set_progress(self, pct):
        def _set():
            if self.progress is not None:
                self.progress["value"] = int(pct)
                self.progress.update_idletasks()
        self.run_on_ui(_set)

    def hide_loading(self):
        def _hide():
            if self.loading_screen:
                try:
                    self.loading_screen.destroy()
                except:
                    pass
                self.loading_screen = None
                self.progress = None
                self.status_label = None

        self.run_on_ui(_hide)

    def _center(self, window, width, height):
        sw = window.winfo_screenwidth()
        sh = window.winfo_screenheight()
        x = (sw // 2) - (width // 2)
        y = (sh // 2) - (height // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")
