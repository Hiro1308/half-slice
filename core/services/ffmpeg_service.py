import os
import subprocess
import json

class FFmpegService:
    def __init__(self, get_path_fn):
        self.get_path = get_path_fn

    def _get_ffmpeg_path(self):
        local = self.get_path("ffmpeg\\bin\\ffmpeg.exe")
        return local if os.path.exists(local) else "ffmpeg"

    def _get_ffprobe_path(self):
        local = self.get_path("ffmpeg\\bin\\ffprobe.exe")
        return local if os.path.exists(local) else "ffprobe"

    @staticmethod
    def _no_window_kwargs():
        """
        Evita que se abra la ventana de CMD en Windows
        """
        if os.name != "nt":
            return {}

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

        return {
            "creationflags": subprocess.CREATE_NO_WINDOW,
            "startupinfo": startupinfo,
        }

    def probe_duration_seconds(self, input_path):
        ffprobe = self._get_ffprobe_path()

        # cwd estable (si ffprobe es local, usamos su carpeta)
        cwd = os.path.dirname(ffprobe) if os.path.isabs(ffprobe) else None

        try:
            out = subprocess.check_output(
                [
                    ffprobe, "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    input_path
                ],
                stderr=subprocess.STDOUT,
                text=True,
                cwd=cwd,
                **self._no_window_kwargs()
            ).strip()
            return float(out)
        except Exception as e:
            raise RuntimeError(f"ffprobe failed: {e}")

    def _run_ffmpeg_with_progress(self, cmd, duration_sec, on_progress=None):
        """
        Usa -progress pipe:1 (stdout) y drena stderr en paralelo para evitar deadlocks.
        Corta al ver progress=end.
        """
        import threading, collections, time

        # cwd estable: si cmd[0] es ruta absoluta a ffmpeg.exe, usamos su carpeta
        ffmpeg_exe = cmd[0]
        cwd = os.path.dirname(ffmpeg_exe) if os.path.isabs(ffmpeg_exe) else None

        p = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,   # progress
            stderr=subprocess.PIPE,   # logs
            text=True,
            bufsize=1,
            universal_newlines=True,
            **self._no_window_kwargs()
        )

        def report(pct):
            if on_progress:
                try:
                    on_progress(int(pct))
                except:
                    pass

        report(0)

        err_tail = collections.deque(maxlen=80)

        def drain_stderr():
            try:
                for line in p.stderr:
                    if not line:
                        break
                    err_tail.append(line.rstrip("\n"))
            except:
                pass

        t = threading.Thread(target=drain_stderr, daemon=True)
        t.start()

        ended = False
        last_emit = -1
        last_time = 0.0

        try:
            for line in p.stdout:
                if not line:
                    break
                line = line.strip()

                if line.startswith("out_time_ms="):
                    try:
                        out_time = int(line.split("=", 1)[1]) / 1_000_000
                    except:
                        continue
                elif line.startswith("out_time_us="):
                    try:
                        out_time = int(line.split("=", 1)[1]) / 1_000_000
                    except:
                        continue
                elif line.startswith("out_time="):
                    try:
                        hh, mm, ss = line.split("=", 1)[1].split(":")
                        out_time = (int(hh) * 3600) + (int(mm) * 60) + float(ss)
                    except:
                        continue
                elif line == "progress=end":
                    report(100)
                    ended = True
                    break
                else:
                    continue

                pct = int(min(100, max(0, (out_time / max(duration_sec, 0.001)) * 100)))

                now = time.time()
                if pct != last_emit and (now - last_time) > 0.05:
                    report(pct)
                    last_emit = pct
                    last_time = now

            # Esperar fin (si se cuelga, kill)
            try:
                p.wait(timeout=10 if ended else 600)
            except subprocess.TimeoutExpired:
                try:
                    p.kill()
                except:
                    pass
                p.wait(timeout=5)

        finally:
            try:
                if p.stdout:
                    p.stdout.close()
            except:
                pass
            try:
                if p.stderr:
                    p.stderr.close()
            except:
                pass

        rc = p.returncode
        if rc != 0:
            tail = "\n".join(err_tail)[-2000:]
            raise RuntimeError(f"FFmpeg failed (code {rc}).\n\nFFmpeg stderr (tail):\n{tail}")

    def probe_resolution(self, input_path):
        ffprobe = self._get_ffprobe_path()

        cwd = os.path.dirname(ffprobe) if os.path.isabs(ffprobe) else None

        cmd = [
            ffprobe, "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "json",
            input_path
        ]
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, **self._no_window_kwargs())
        if p.returncode != 0:
            return None, None
        try:
            data = json.loads(p.stdout)
            s = (data.get("streams") or [{}])[0]
            return int(s.get("width") or 0), int(s.get("height") or 0)
        except:
            return None, None

    def compress_to_discord_10mb(self, input_path, out_dir=None, max_bytes=10 * 1024 * 1024, on_progress=None, on_status=None):
        """
        Compresión rápida y efectiva para Discord (<10MB).
        - Calcula bitrate por duración.
        - 1-pass (ultrafast) con fallbacks (res/audio/fps).
        Devuelve: (ok, output_path, size_mb)
        """
        import os

        ffmpeg = self._get_ffmpeg_path()
        duration = self.probe_duration_seconds(input_path)
        if duration <= 0:
            raise RuntimeError("Invalid duration")

        if not out_dir:
            out_dir = os.path.dirname(input_path)
        if not os.path.isdir(out_dir):
            raise RuntimeError("Invalid output directory")

        base = os.path.splitext(os.path.basename(input_path))[0]
        final_output = os.path.join(out_dir, f"{base}_discord10mb.mp4")

        # Protección: no pisar input
        if os.path.abspath(input_path) == os.path.abspath(final_output):
            raise RuntimeError("Output path matches input path (would overwrite input).")

        # margen seguro por overhead MP4
        target_bytes = int(max_bytes * 0.94)

        # bitrate total objetivo (bits/seg)
        total_bps = int((target_bytes * 8) / max(duration, 0.25))
        total_bps = max(min(total_bps, 6_000_000), 180_000)

        # Evitar upscaling
        in_w, in_h = self.probe_resolution(input_path)
        if not in_h or in_h <= 0:
            in_h = 2160

        # (target_height, audio_bps, extra_vf)
        attempts = [
            # normales
            (720,  64_000, None),
            (720,  48_000, None),
            (480,  48_000, None),
            (360,  32_000, None),

            # agresivos
            (360,  24_000, "fps=24"),
            (240,  24_000, "fps=24"),

            # nuclear (baja fuerte fps)
            (240,  24_000, "fps=10"),
            # último último: sin audio (si querés que “entre sí o sí”)
            (240,  0,       "fps=10"),
        ]

        total_attempts = len(attempts)

        for idx, (target_h, a_bps, extra_vf) in enumerate(attempts, start=1):
            if on_status:
                try:
                    on_status(f"Intento {idx} de {total_attempts} (10MB max)")
                except:
                    pass

            scale_h = min(in_h, target_h)

            # video bitrate = total - audio (con piso)
            v_bps = total_bps - a_bps
            v_bps = max(v_bps, 120_000)

            # si el total quedó muy bajo, no te mates con audio alto
            if a_bps > 0 and total_bps < (a_bps + 140_000):
                a_bps = min(a_bps, 32_000)
                v_bps = max(total_bps - a_bps, 100_000)

            vf_parts = [f"scale=-2:{scale_h}"]
            if extra_vf:
                vf_parts.append(extra_vf)
            vf = ",".join(vf_parts)

            tmp_output = os.path.join(out_dir, f"{base}_discord10mb_try{idx}.tmp.mp4")

            cmd = [
                ffmpeg, "-y",
                "-loglevel", "error",
                "-i", input_path,
                "-vf", vf,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-b:v", str(v_bps),
                "-maxrate", str(v_bps),
                "-bufsize", str(v_bps * 2),
                "-movflags", "+faststart",
                "-progress", "pipe:1",
                "-nostats",
            ]

            if a_bps and a_bps > 0:
                cmd += ["-c:a", "aac", "-b:a", str(a_bps), "-ac", "2"]
            else:
                cmd += ["-an"]

            cmd.append(tmp_output)

            self._run_ffmpeg_with_progress(cmd, duration, on_progress=on_progress)

            if os.path.exists(tmp_output):
                final_bytes = os.path.getsize(tmp_output)

                # si quedó “vacío/inválido”, descartalo
                if final_bytes < 50_000:
                    try:
                        os.remove(tmp_output)
                    except:
                        pass
                    continue

                if final_bytes <= max_bytes:
                    # mover a nombre final
                    try:
                        if os.path.exists(final_output):
                            os.remove(final_output)
                    except:
                        pass

                    os.replace(tmp_output, final_output)
                    size_mb = os.path.getsize(final_output) / (1024 * 1024)
                    return True, final_output, size_mb

                # si se pasa, borramos y probamos fallback
                try:
                    os.remove(tmp_output)
                except:
                    pass

        return False, final_output, 0.0
