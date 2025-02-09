import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import json
import os
import time
import threading
from .videoplayer import VideoPlayer
from .soundmanager import SoundManager

class GUI:
    def __init__(self, root):
        self.muteado = None
        self.paused = None
        self.loading_screen = None  # Variable para la pantalla de carga

        self.root = root
        self.root.title("Half-Slice")
        self.root.geometry("600x450")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.iconbitmap(self.get_path("assets\\icon.ico"))
        self.ancho_ventana, self.alto_ventana = 600, 450
        self.centrar_ventana(root, self.ancho_ventana, self.alto_ventana)

        self.video_player = VideoPlayer(self)
        self.soundmanager = SoundManager()

        self.config_file = self.get_path("config.json")
        self.configuracion = self.cargar_configuracion()

        self.iconos = self.cargar_iconos()

        self.create_widgets()

    def get_path(self, relative_path):
        """Devuelve la ruta absoluta de un archivo dentro del paquete."""
        return os.path.join(os.path.abspath("."), relative_path)

    def cargar_iconos(self):
        iconos = {
            "mute": ImageTk.PhotoImage(Image.open(self.get_path("assets\\sound.png")).resize((24, 24), Image.LANCZOS)),
            "unmute": ImageTk.PhotoImage(Image.open(self.get_path("assets\\mute.png")).resize((24, 24), Image.LANCZOS)),
            "info": ImageTk.PhotoImage(Image.open(self.get_path("assets\\info.png")).resize((24, 24), Image.LANCZOS))
        }
        return iconos

    def cargar_configuracion(self):
        """Carga la configuración desde un archivo JSON."""
        if os.path.exists(self.config_file):
            with open(self.config_file, "r") as file:
                return json.load(file)
        return {}

    def guardar_configuracion(self, config):
        with open(self.config_file, "w") as file:
            json.dump(config, file)

    def on_closing(self):
        """Cierra la aplicación correctamente."""
        self.root.destroy()

    def centrar_ventana(self, ventana, ancho, alto):
        pantalla_ancho = ventana.winfo_screenwidth()
        pantalla_alto = ventana.winfo_screenheight()

        x = (pantalla_ancho // 2) - (ancho // 2)
        y = (pantalla_alto // 2) - (alto // 2)

        ventana.geometry(f"{ancho}x{alto}+{x}+{y}")

    def slice_video(self):
        """Inicia el proceso de recorte del video con una pantalla de carga."""
        self.soundmanager.reproducir_sonido("button")

        # Verificar si hay un archivo cargado
        file_path = self.entry_file_path.get()
        if not file_path:
            messagebox.showerror("Error", "Please select a video file first.")
            return

        # Procesar el corte en un hilo separado
        threading.Thread(target=self.process_video_slice, daemon=True).start()

    def process_video_slice(self):
        """Procesa el corte del video en un hilo separado y cierra la pantalla de carga cuando termine."""
        try:
            self.video_player.trim_video()  # Llamar a la función de corte de video
        except Exception as e:
            messagebox.showwarning("Error", f"Error al recortar el video: {e}")

        self.hide_loading_screen()

    def show_loading_screen(self):
        """Muestra una pantalla de carga mientras se procesa el archivo."""
        self.loading_screen = tk.Toplevel(self.root)
        self.loading_screen.title("Processing clip...")
        self.loading_screen.geometry("300x100")
        self.loading_screen.resizable(False, False)
        self.loading_screen.iconbitmap(self.get_path("assets\\icon.ico"))
        self.centrar_ventana(self.loading_screen, 300, 100)

        # Convertir la ventana en una "ventana de herramienta" para ocultar minimizar y maximizar
        self.loading_screen.wm_attributes("-toolwindow", True)
        # Deshabilitar el botón de cerrar (X)
        self.loading_screen.protocol("WM_DELETE_WINDOW", lambda: None)

        # Evitar que se cierre la ventana
        self.loading_screen.protocol("WM_DELETE_WINDOW", lambda: None)

        # Bloquear interacción con la ventana principal
        self.loading_screen.grab_set()

        # Marco contenedor para organizar icono y texto horizontalmente
        frame = tk.Frame(self.loading_screen)
        frame.pack(pady=20, padx=10)

        # Cargar icono personalizado (debe ser PNG o GIF)
        icon_img = Image.open(self.get_path("assets\\processing.png")).resize((60, 60), Image.LANCZOS)
        icon = ImageTk.PhotoImage(icon_img)

        icon_label = tk.Label(frame, image=icon)
        icon_label.image = icon  # Guardar referencia para evitar que la imagen sea eliminada por el recolector de basura
        icon_label.pack(side=tk.LEFT, padx=(0, 30), anchor="w")

        # Texto al lado del icono
        text_label = tk.Label(frame, text="Processing clip...", font=("Arial", 12))
        text_label.pack(side=tk.LEFT)

    def hide_loading_screen(self):
        """Cierra la pantalla de carga cuando el proceso ha terminado."""
        if self.loading_screen:
            self.loading_screen.destroy()
            self.loading_screen = None

    def select_file(self):
        """Selecciona un archivo de video y restablece el slider de inicio a 0."""
        self.soundmanager.reproducir_sonido("button")
        file_path = filedialog.askopenfilename(filetypes=[("MP4 files", "*.mp4")])
        if file_path:
            self.entry_file_path.delete(0, tk.END)
            self.entry_file_path.insert(0, file_path)
            self.video_player.load_video(file_path)

            # ✅ Establecer el slider de inicio a 0
            self.slider_start.set(0)

    def process_video(self, file_path):
        """Procesa el video en un hilo separado y cierra la pantalla de carga cuando termine."""
        time.sleep(2)  # Simula un procesamiento largo (reemplázalo con el código real)
        self.video_player.load_video(file_path)
        self.hide_loading_screen()

    def toggle_mute(self):
        self.muteado = not self.muteado  # Cambia el estado
        self.configuracion["mute"] = self.muteado
        self.soundmanager.toggle_muteado(self.muteado)
        self.guardar_configuracion(self.configuracion)  # Guarda en archivo JSON

        # Cambiar la apariencia del botón
        self.boton_mute.config(image=self.iconos["unmute"] if self.muteado else self.iconos["mute"])

    def toggle_pause(self):
        self.paused = not self.paused  # Cambiar el estado de pausa

        if self.paused:
            self.button_pause.config(text="Resume")  # Cambiar el texto del botón a "Resume"
        else:
            self.button_pause.config(text="Pause")  # Cambiar el texto del botón a "Pause"

    def info_box(self):
        self.soundmanager.play_loop("info")
        self.custom_warning("Created by Hiro. Version 0.1. Shoutout to the usuales gang.")

    def custom_warning(self, message):
        warning_win = tk.Toplevel()
        warning_win.title("Info")
        warning_win.geometry("350x120")
        warning_win.resizable(False, False)
        warning_win.iconbitmap(self.get_path("assets\\icon.ico"))

        ancho, alto = 350, 120
        self.centrar_ventana(warning_win, ancho, alto)

        # Cargar icono personalizado (debe ser PNG o GIF)
        icon = ImageTk.PhotoImage(Image.open(self.get_path("assets\\coomer.png")).resize((40, 40), Image.LANCZOS))

        # Mantener referencia al icono
        warning_win.icon_image = icon

        def on_close():
            self.soundmanager.stop_sound()
            warning_win.destroy()

        warning_win.protocol("WM_DELETE_WINDOW", on_close)

        # Marco para alinear elementos
        frame = tk.Frame(warning_win)
        frame.pack(pady=10)

        # Etiqueta de icono
        icon_label = tk.Label(frame, image=icon)
        icon_label.grid(row=0, column=0, padx=10)

        # Mensaje de advertencia
        message_label = tk.Label(frame, text=message, font=("Arial", 10), wraplength=250, justify="left")
        message_label.grid(row=0, column=1)

        # Botón para cerrar la ventana
        close_button = tk.Button(warning_win, text="OK", command=on_close)
        close_button.pack(pady=10)

        warning_win.mainloop()

    def enable_buttons(self):
        self.slider_start.bind("<ButtonPress-1>", self.soundmanager.on_slide_start)
        self.slider_start.bind("<ButtonRelease-1>", lambda e: self.video_player.update_start_time(self.slider_start.get()))
        self.slider_start.bind("<B1-Motion>")  # Permite arrastrar
        self.slider_start.bind("<KeyRelease>")  # Permite usar teclas
        self.slider_start.config(state=tk.NORMAL)  # Habilita de nuevo el slider

        self.slider_end.bind("<ButtonPress-1>", self.soundmanager.on_slide_start)  # Solo suena una vez al empezar
        self.slider_end.bind("<ButtonRelease-1>", lambda e: self.video_player.update_end_time(self.slider_end.get()))
        self.slider_end.bind("<B1-Motion>")  # Permite arrastrar
        self.slider_end.bind("<KeyRelease>")  # Permite usar teclas
        self.slider_end.config(state=tk.NORMAL)  # Habilita de nuevo el slider

        self.button_cut.config(state=tk.NORMAL)
        self.button_play.config(state=tk.NORMAL)
        self.button_pause.config(state=tk.NORMAL)

    def create_widgets(self):
        # 🎨 Fondo
        self.canvas = tk.Canvas(self.root, width=600, height=450, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        background_image = Image.open(self.get_path("assets/bckg.png")).resize((600, 450), Image.LANCZOS)
        self.background_photo = ImageTk.PhotoImage(background_image)
        self.canvas.create_image(0, 0, image=self.background_photo, anchor="nw")

        # 📂 Entrada y botón de archivo
        self.entry_file_path = tk.Entry(self.root, width=30)
        self.button_select = tk.Button(self.root, text="Select File", command=self.select_file)

        self.canvas.create_text(130, 30, text="MP4 File", font=("Arial", 10, "bold"), fill="white")
        self.canvas.create_window(130, 60, window=self.entry_file_path)
        self.canvas.create_window(130, 90, window=self.button_select)

        # 🎬 Vista previa del video
        self.frame_preview = tk.Frame(self.root, bg="black", width=320, height=180)
        self.frame_preview.place(x=260, y=20)
        self.frame_preview.pack_propagate(False)
        self.panel_video = tk.Label(self.frame_preview, bg="black")
        self.panel_video.pack(fill="both", expand=True)

        # 🎛 Sliders
        self.slider_start = tk.Scale(self.root, from_=0, to=100, length=178, orient=tk.HORIZONTAL)
        self.slider_end = tk.Scale(self.root, from_=0, to=100, length=178, orient=tk.HORIZONTAL)
        self.entry_start_time = tk.Entry(self.root, width=30)
        self.entry_end_time = tk.Entry(self.root, width=30)

        # Bloquear eventos de teclado y mouse
        self.slider_start.unbind("<ButtonPress-1>")  # Evita clics
        self.slider_start.unbind("<B1-Motion>")  # Evita arrastrar con el mouse
        self.slider_start.unbind("<KeyRelease>")  # Evita cambios con el teclado
        self.slider_start.config(state=tk.DISABLED)

        self.slider_end.unbind("<ButtonPress-1>")  # Evita clics
        self.slider_end.unbind("<B1-Motion>")  # Evita arrastrar con el mouse
        self.slider_end.unbind("<KeyRelease>")  # Evita cambios con el teclado
        self.slider_end.config(state=tk.DISABLED)

        self.canvas.create_text(130, 120, text="Start time (sec)", font=("Arial", 10, "bold"), fill="white")
        self.canvas.create_window(130, 160, window=self.slider_start)
        self.canvas.create_window(130, 190, window=self.entry_start_time)

        self.canvas.create_text(130, 230, text="End time (sec)", font=("Arial", 10, "bold"), fill="white")
        self.canvas.create_window(130, 270, window=self.slider_end)
        self.canvas.create_window(130, 300, window=self.entry_end_time)

        # ▶ Botones
        self.button_play = tk.Button(self.root, text="Play Preview", command=self.video_player.start_video_preview, width=12)
        self.button_pause = tk.Button(self.root, text="Pause", command=self.video_player.toggle_pause, width=12)
        self.button_cut = tk.Button(self.root, text="Slice", command=self.slice_video, width=25)
        self.boton_mute = tk.Button(self.root, image=self.iconos["unmute"] if self.muteado else self.iconos["mute"], command=self.toggle_mute, borderwidth=0)
        self.boton_info = tk.Button(self.root, image=self.iconos["info"], command=self.info_box, borderwidth=0)

        self.button_cut.config(state=tk.DISABLED)
        self.button_play.config(state=tk.DISABLED)
        self.button_pause.config(state=tk.DISABLED)

        self.button_play.place(x=260, y=210)
        self.button_pause.place(x=370, y=210)
        self.button_cut.place(x=38, y=330)
        self.boton_mute.place(x=510, y=400)
        self.boton_info.place(x=550, y=400)
