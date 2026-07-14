from __future__ import annotations

import logging
import os

from PySide6.QtCore import QThread

from yt_dlp import YoutubeDL

from app.models.download_item import DownloadItem, FormatInfo, FormatType, PlaylistEntry
from app.signals.signal_bus import signal_bus
from app.utils.paths import project_resource_path
from yt_dlp.networking.impersonate import ImpersonateTarget

log = logging.getLogger('app.workers.extract')


def _get_deno_path() -> str:
    path = project_resource_path('bin', 'deno.exe')
    return path if os.path.isfile(path) else ''


def _parse_formats(raw_formats: list[dict]) -> list[FormatInfo]:
    seen = set()
    result = []
    for f in raw_formats:
        fid = f.get('format_id', '')
        if not fid or fid in seen:
            continue
        
        # Skip AV1 video codec formats unless they are 1440p or 2160p (4K)
        vcodec = f.get('vcodec') or ''
        if 'av01' in vcodec.lower() or 'av1' in vcodec.lower():
            height = f.get('height') or 0
            if height < 1440:
                continue

        seen.add(fid)
        resolution = ''
        if f.get('height'):
            resolution = f'{f.get("height")}p'
            if f.get('fps') and f['fps'] > 30:
                resolution += f'{f["fps"]}'
        elif f.get('format_note'):
            resolution = f['format_note']

        filesize = ''
        for key in ('filesize', 'filesize_approx'):
            val = f.get(key)
            if val:
                if val >= 1073741824:
                    filesize = f'{val / 1073741824:.1f} GiB'
                elif val >= 1048576:
                    filesize = f'{val / 1048576:.1f} MiB'
                else:
                    filesize = f'{val / 1024:.0f} KiB'
                break

        vcodec = f.get('vcodec')
        acodec = f.get('acodec')
        has_video = vcodec not in ('none', None, '')
        has_audio = acodec not in ('none', None, '')
        codec = vcodec if has_video else acodec if has_audio else ''

        if has_video and has_audio:
            fmt_type = FormatType.VIDEO_AUDIO
        elif has_video:
            fmt_type = FormatType.VIDEO_ONLY
        elif has_audio:
            fmt_type = FormatType.AUDIO_ONLY
        else:
            fmt_type = FormatType.OTHER

        result.append(FormatInfo(
            format_id=fid,
            ext=f.get('ext', ''),
            resolution=resolution,
            filesize=filesize,
            tbr=str(round(f.get('tbr', 0))) if f.get('tbr') else '',
            codec=codec,
            note=f.get('format_note', ''),
            fmt_type=fmt_type,
        ))
    return result


class ExtractWorker(QThread):
    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        log.info('Starting metadata extraction for: %s', self.url)
        try:
            from app.widgets.settings_dialog import load_settings
            settings = load_settings()

            MAX_PLAYLIST = 100
            opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': 'in_playlist',
                'playlistend': MAX_PLAYLIST,
                'noplaylist': True,
                'socket_timeout': 30,
                'retries': 3,
                'file_access_retries': 3,
                'extractor_retries': 3,
            }

            proxy = settings.get('proxy', '').strip()
            if proxy:
                opts['proxy'] = proxy

            cookies_file = settings.get('cookies_file', '').strip()
            has_cookies_file = cookies_file and os.path.isfile(cookies_file)
            if has_cookies_file:
                opts['cookiefile'] = cookies_file
            else:
                from PySide6.QtCore import QStandardPaths
                base_app_dir = QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)
                if not base_app_dir:
                    base_app_dir = os.path.join(os.path.expanduser('~'), '.yt-dlp-gui')
                browser_cookies = os.path.join(base_app_dir, 'yt-dlp-gui', 'cookies.txt')
                if os.path.isfile(browser_cookies):
                    opts['cookiefile'] = browser_cookies
                    log.info("Using built-in browser cookies from: %s", browser_cookies)
                elif settings.get('cookies_from_browser', '').strip():
                    opts['cookiesfrombrowser'] = (settings['cookies_from_browser'].strip(),)

            if settings.get('impersonate', True):
                opts['impersonate'] = ImpersonateTarget()

            deno_path = _get_deno_path()
            if deno_path:
                opts['js_runtimes'] = {'deno': {'path': deno_path}}
                opts['remote_components'] = ['ejs:github']

            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=False)

            if self.isInterruptionRequested():
                log.info('Discarding interrupted extraction for: %s', self.url)
                return

            item = DownloadItem(url=self.url)
            item.title = info.get('title', self.url)
            item.thumbnail_url = info.get('thumbnail', '') or ''
            item.duration = info.get('duration')
            item.uploader = info.get('uploader', info.get('channel', ''))
            log.info('Extracted: %s (by %s)', item.title, item.uploader or 'unknown')

            entries = info.get('entries')
            if entries:
                total = info.get('playlist_count') or len(entries)
                capped = total > MAX_PLAYLIST
                for i, entry in enumerate(entries):
                    if entry is None:
                        continue
                    item.playlist_entries.append(PlaylistEntry(
                        url=entry.get('url') or entry.get('webpage_url') or entry.get('id', ''),
                        title=entry.get('title', 'Unknown'),
                        duration=entry.get('duration'),
                        selected=(i == 0),
                    ))
                msg = f'Playlist with {len(item.playlist_entries)} entries'
                if capped:
                    msg += f' (showing first {MAX_PLAYLIST} of {total})'
                msg += ', first selected by default'
                log.info(msg)

            raw_formats = info.get('formats', [])
            if raw_formats:
                item.formats = _parse_formats(raw_formats)
                log.info('Parsed %d formats', len(item.formats))
            elif entries:
                log.info('Playlist detected — fetching first video formats for reference')
                try:
                    first_url = item.playlist_entries[0].url if item.playlist_entries else self.url
                    single_opts = {
                        'quiet': True,
                        'no_warnings': True,
                        'extract_flat': False,
                        'socket_timeout': 30,
                        'retries': 3,
                        'file_access_retries': 3,
                        'extractor_retries': 3,
                    }
                    if proxy:
                        single_opts['proxy'] = proxy
                    if has_cookies_file:
                        single_opts['cookiefile'] = cookies_file
                    elif settings.get('cookies_from_browser', '').strip():
                        single_opts['cookiesfrombrowser'] = (settings['cookies_from_browser'].strip(),)
                    if settings.get('impersonate', True):
                        single_opts['impersonate'] = ImpersonateTarget()
                    if deno_path:
                        single_opts['js_runtimes'] = {'deno': {'path': deno_path}}
                        single_opts['remote_components'] = ['ejs:github']
                    with YoutubeDL(single_opts) as ydl2:
                        first_info = ydl2.extract_info(first_url, download=False)
                    first_formats = first_info.get('formats', [])
                    if first_formats:
                        item.formats = _parse_formats(first_formats)
                        log.info('Parsed %d formats from first playlist item', len(item.formats))
                except Exception as e:
                    log.warning('Could not fetch formats from first playlist item: %s', e)

            log.info('Emitting metadata_fetched signal')
            signal_bus.metadata_fetched.emit(item, self.url)
            log.info('Extraction complete')
        except Exception as e:
            if self.isInterruptionRequested():
                log.info('Extraction interrupted for: %s', self.url)
                return
            log.error('Extraction failed: %s', e, exc_info=True)
            signal_bus.metadata_error.emit(str(e), self.url)
