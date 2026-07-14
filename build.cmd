@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
pyinstaller build.spec
echo.
echo Build complete. Output in dist/yt-dlp-gui/
pause
