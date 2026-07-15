# yt-dlp GUI

Portable Qt-based GUI application for yt-dlp.

- Bundled ffmpeg and deno integration in portable builds
- Dark theme

## Screenshots


### Built-in browser

![Built-in browser](Screenshot/Screenshot%202026-07-14%20180105.png)

### Format selection

![Video format selection](Screenshot/Screenshot%202026-07-14%20180124.png)

### Download queue

![Download queue and progress](Screenshot/Screenshot%202026-07-14%20180144.png)


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

## On Windows

```bash
# 1. Create the virtual environment
python -m venv .venv

# 2. Activate it
.venv\Scripts\activate

# 3. Install the requirements
pip install -r requirements.txt

# 4. Run the application
python main.py

# Direct command
.venv\Scripts\python main.py


```
## Build On macOS / Linux:

```bash
# 1. Create the virtual environment
python3 -m venv .venv

# 2. Activate it
source .venv/bin/activate

# 3. Install the requirements
pip install -r requirements.txt

# 4. Run the application
python3 main.py

# Direct command
.venv/bin/python main.py

