# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('resources\\style.qss', 'resources'),
        ('resources\\icon.ico', 'resources'),
        ('resources\\icons', 'resources\\icons'),
        ('bin\\ffmpeg.exe', 'bin'),
        ('bin\\deno.exe', 'bin'),
    ],
    hiddenimports=[
        'yt_dlp',
        'yt_dlp.extractor.lazy_extractors',
        'yt_dlp.downloader',
        'yt_dlp.postprocessor',
        'yt_dlp.networking',
        'yt_dlp.utils',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'test',
        'unittest',
        'pydoc',
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='yt-dlp-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources\\icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='yt-dlp-gui',
)
