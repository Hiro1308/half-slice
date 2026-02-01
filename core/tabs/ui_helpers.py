import tkinter as tk
from PIL import Image, ImageTk


def build_tab_canvas(app, tab_frame):
    canvas = tk.Canvas(tab_frame, highlightthickness=0, bd=0)
    canvas.pack(fill="both", expand=True)

    bg_original = Image.open(app.get_path("assets/bckg.png"))
    bg_img_id = canvas.create_image(0, 0, anchor="nw")

    def _redraw_bg(event=None):
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w <= 1 or h <= 1:
            return
        resized = bg_original.resize((w, h), Image.LANCZOS)
        canvas._bg_photo = ImageTk.PhotoImage(resized)
        canvas.itemconfig(bg_img_id, image=canvas._bg_photo)

    canvas.bind("<Configure>", _redraw_bg)
    return canvas


def add_bottom_right_icons(app, canvas, prefix=""):
    btn_settings = tk.Button(canvas, image=app.icons["settings"], command=app.select_quality, borderwidth=0)
    btn_mute = tk.Button(
        canvas,
        image=app.icons["unmute"] if app.mute else app.icons["mute"],
        command=app.toggle_mute,
        borderwidth=0,
    )
    btn_info = tk.Button(canvas, image=app.icons["info"], command=app.info_box, borderwidth=0)

    canvas.create_window(470, 400, window=btn_settings)
    canvas.create_window(510, 400, window=btn_mute)
    canvas.create_window(550, 400, window=btn_info)

    # devolvemos mute button para que la tab lo actualice luego
    return btn_mute
