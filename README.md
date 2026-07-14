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

## Screenshots

[Browse the screenshot gallery](https://github.com/SaifiOfficial/yt-dlp-gui/tree/main/Screenshot)

### Built-in browser

![Built-in browser](Screenshot/Screenshot%202026-07-14%20180105.png)

### Format selection

![Video format selection](Screenshot/Screenshot%202026-07-14%20180124.png)

### Download queue

![Download queue and progress](Screenshot/Screenshot%202026-07-14%20180144.png)

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
python main.py

```

