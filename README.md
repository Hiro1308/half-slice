# Half-Slice

A local FFMPEG based MP4 video slicer and video downloader with a Half-Life theme

<img src="https://i.imgur.com/BPmlM7T.png" width="400">
<img src="https://i.imgur.com/dSwMKFQ.png" width="400">
<img src="https://i.imgur.com/Tp3nK1b.png" width="400">

### Instalation:

To fully run this program locally, we have to install FFMPEG in this directory. You can find FFMPEG here:
https://www.ffmpeg.org/download.html. You just have to drop the .exe files in ffmpeg/bin in the root path of the project.

You will also need to download yt-dlp as an executable file and drop it in the root path as well. You can find it here:
https://github.com/yt-dlp/yt-dlp/releases

For the moment, this program only works with MP4 files.

### Libraries and tools used:

- Tkinter: Used for the graphical user interface (GUI)
- MoviePy: Used for video preview and frame extraction (internally relies on FFmpeg)
- FFmpeg: External binary used to encode, slice and process video clips
- YT-DLP: External binary used to download videos and audio from YouTube
- Pillow: Used for image handling and UI rendering
- Pygame: Used to handle sound effects
- OS, sys, json, time, threading and subprocess: Used for user interaction, process handling and general application logic

This is an alpha version, there are a lot of things that need to be fixed and code to be optimized :)
