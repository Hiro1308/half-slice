import os
import re
import subprocess
import sys


class YouTubeService:
    def __init__(self, ytdlp_path=None):
        """
        Si ytdlp_path=None -> intenta usar yt-dlp.exe al lado del exe (instalado).
        Fallback: 'yt-dlp' en PATH.
        """
        self.ytdlp = ytdlp_path or self._resolve_ytdlp_path()

    # -------------------------
    # Paths robustos (dev + exe)
    # -------------------------
    @staticmethod
    def _app_dir() -> str:
        # En EXE: carpeta del ejecutable
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        # En dev: carpeta donde corrés el proceso
        return os.path.abspath(".")

    def _resolve_ytdlp_path(self) -> str:
        base = self._app_dir()

        # Caso instalador: {app}\yt-dlp.exe
        local = os.path.join(base, "yt-dlp.exe")
        if os.path.exists(local):
            return local

        # Fallback: si alguien lo tiene instalado en PATH
        return "yt-dlp"

    def _resolve_base_dir(self) -> str:
        """
        Base dir donde están los binarios.
        Si ytdlp es ruta absoluta existente -> su carpeta.
        Si no -> app_dir() (NO el CWD random).
        """
        if os.path.isabs(self.ytdlp) and os.path.exists(self.ytdlp):
            return os.path.dirname(self.ytdlp)
        return self._app_dir()

    def _resolve_ffmpeg_location(self) -> str | None:
        base = self._resolve_base_dir()

        # Tu instalador copia {app}\ffmpeg\bin\ffmpeg.exe
        candidates = [
            os.path.join(base, "ffmpeg", "bin"),                       # carpeta bin
            os.path.join(base, "ffmpeg", "bin", "ffmpeg.exe"),         # exe directo
            os.path.join(base, "ffmpeg.exe"),                          # fallback raro
        ]

        for c in candidates:
            if os.path.isdir(c) and os.path.exists(os.path.join(c, "ffmpeg.exe")):
                return c
            if os.path.isfile(c):
                return c  # yt-dlp acepta ruta al exe también

        return None

    # -------------------------
    # Run sin ventana (Windows)
    # -------------------------
    @staticmethod
    def _popen_no_window_kwargs():
        if os.name != "nt":
            return {}

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

        return {
            "creationflags": subprocess.CREATE_NO_WINDOW,
            "startupinfo": startupinfo,
        }

    def _height_from_quality(self, quality: str) -> int:
        q = (quality or "").strip().lower().replace("p", "")
        try:
            return int(q)
        except Exception:
            return 720

    # -------------------------
    # Download
    # -------------------------
    def download(
        self,
        url: str,
        out_dir: str,
        quality: str = "720p",
        output_type: str = "mp4",  # "mp4" | "mp3"
        progress_hook=None,
    ) -> bool:
        os.makedirs(out_dir, exist_ok=True)

        base = self._resolve_base_dir()
        ffmpeg_loc = self._resolve_ffmpeg_location()
        if ffmpeg_loc is None:
            raise FileNotFoundError(
                "No encontré ffmpeg.\n"
                "Esperaba: <app>\\ffmpeg\\bin\\ffmpeg.exe\n"
                "o ffmpeg en el PATH."
            )

        # ⚠️ clave: plantilla más segura (evita caracteres raros en Windows)
        out_tpl = os.path.join(out_dir, "%(title).200s.%(ext)s")

        height = self._height_from_quality(quality)

        if output_type == "mp3":
            cmd = [
                self.ytdlp,
                "--no-playlist",
                "--ffmpeg-location", ffmpeg_loc,
                "-x",
                "--audio-format", "mp3",
                "--audio-quality", "0",
                "-o", out_tpl,
                url,
            ]
        else:
            fmt = (
                f"bestvideo[ext=mp4][height<={height}]+bestaudio[ext=m4a]/"
                f"best[ext=mp4][height<={height}]/best"
            )
            cmd = [
                self.ytdlp,
                "--no-playlist",
                "--ffmpeg-location", ffmpeg_loc,
                "-f", fmt,
                "--merge-output-format", "mp4",
                "-o", out_tpl,
                url,
            ]

        # 🚨 clave: cwd fijo (evita que cambie por ocultar consola)
        process = subprocess.Popen(
            cmd,
            cwd=base,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            **self._popen_no_window_kwargs(),
        )

        # leer output (sirve para progreso y para debug si falla)
        last_lines = []
        for line in process.stdout:
            if progress_hook:
                progress_hook(line)

            # guardamos últimas líneas por si falla (muy útil)
            last_lines.append(line.rstrip("\n"))
            if len(last_lines) > 25:
                last_lines.pop(0)

        process.wait()

        if process.returncode != 0:
            # tiramos error detallado para que tu UI lo muestre si querés
            detalle = "\n".join(last_lines).strip() or "yt-dlp falló sin salida."
            raise RuntimeError(detalle)

        return True

    @staticmethod
    def parse_progress_percent(line: str):
        m = re.search(r"\[download\]\s+(\d{1,3}(?:\.\d+)?)%", line)
        if not m:
            return None
        try:
            return float(m.group(1))
        except Exception:
            return None
