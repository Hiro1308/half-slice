import os
import re
import subprocess


class YouTubeService:
    def __init__(self, ytdlp_path="yt-dlp"):
        self.ytdlp = ytdlp_path

    def _height_from_quality(self, quality: str) -> int:
        q = (quality or "").strip().lower().replace("p", "")
        try:
            return int(q)
        except Exception:
            return 720

    def _resolve_base_dir(self) -> str:
        # Si ytdlp_path es un exe local, usamos su carpeta.
        # Si es "yt-dlp" (PATH), usamos cwd del proyecto.
        if os.path.isabs(self.ytdlp) and os.path.exists(self.ytdlp):
            return os.path.dirname(self.ytdlp)
        # fallback: carpeta desde donde corre el proceso
        return os.path.abspath(".")

    def _resolve_ffmpeg_location(self) -> str | None:
        base = self._resolve_base_dir()

        candidates = [
            os.path.join(base, "ffmpeg", "bin"),              # tu caso
            os.path.join(base, "ffmpeg", "bin", "ffmpeg.exe"),
            os.path.join(base, "ffmpeg.exe"),
        ]

        for c in candidates:
            if os.path.isdir(c):
                # si hay ffmpeg.exe adentro, sirve
                if os.path.exists(os.path.join(c, "ffmpeg.exe")):
                    return c
            elif os.path.isfile(c):
                return c  # yt-dlp acepta path al exe también

        return None

    def download(
        self,
        url: str,
        out_dir: str,
        quality: str = "720p",
        output_type: str = "mp4",  # "mp4" | "mp3"
        progress_hook=None,
    ) -> bool:
        os.makedirs(out_dir, exist_ok=True)
        height = self._height_from_quality(quality)
        out_tpl = os.path.join(out_dir, "%(title)s.%(ext)s")

        ffmpeg_loc = self._resolve_ffmpeg_location()
        if ffmpeg_loc is None:
            raise FileNotFoundError(
                "No encontré ffmpeg. Colocalo en ./ffmpeg/bin/ffmpeg.exe "
                "o en el PATH del sistema."
            )

        if output_type == "mp3":
            cmd = [
                self.ytdlp,
                "--ffmpeg-location", ffmpeg_loc,
                "-x",
                "--audio-format", "mp3",
                "--audio-quality", "0",
                "-o", out_tpl,
                url,
            ]
        else:
            # Forzar contenedores compatibles para MP4:
            # - video mp4
            # - audio m4a
            fmt = (
                f"bestvideo[ext=mp4][height<={height}]+bestaudio[ext=m4a]/"
                f"best[ext=mp4][height<={height}]/best"
            )
            cmd = [
                self.ytdlp,
                "--ffmpeg-location", ffmpeg_loc,
                "-f", fmt,
                "--merge-output-format", "mp4",
                "-o", out_tpl,
                url,
            ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        for line in process.stdout:
            if progress_hook:
                progress_hook(line)

        process.wait()
        return process.returncode == 0

    @staticmethod
    def parse_progress_percent(line: str):
        m = re.search(r"\[download\]\s+(\d{1,3}(?:\.\d+)?)%", line)
        if not m:
            return None
        try:
            return float(m.group(1))
        except Exception:
            return None
