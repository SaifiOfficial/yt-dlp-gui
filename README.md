# yt-dlp GUI

Portable Qt-based GUI application for yt-dlp.

## Features

- URL input with automatic metadata fetching
- Format selection table (video/audio codec, resolution, size)
- Playlist and channel support with item selection
- Download queue with parallel downloads (configurable)
- Real-time progress bars
- Persistent settings (output directory, proxy, cookies, etc.)
- Bundled ffmpeg and deno integration in portable builds
- Dark theme

## Usage

1. Paste a video/playlist URL and click **Fetch Info**
2. Browse available formats and select one
3. (Optional) Select individual playlist items
4. Click **Download Selected**
5. Monitor progress in the Queue tab

## Build from source

```bash
pip install -r requirements.txt
pip install pyinstaller

# Run directly
.venv\Scripts\python main.py

```

