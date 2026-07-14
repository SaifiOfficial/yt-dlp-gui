from __future__ import annotations

import glob
import logging
import os
import re
import threading

from PySide6.QtCore import QThread

from yt_dlp import YoutubeDL

from app.models.download_item import DownloadItem, FormatType
from app.signals.signal_bus import signal_bus
from app.utils.paths import project_resource_path
from yt_dlp.networking.impersonate import ImpersonateTarget

log = logging.getLogger('app.workers.download')

_OUTPUT_RESERVATION_LOCK = threading.Lock()
_RESERVED_OUTPUT_STEMS: set[str] = set()
_MEDIA_EXTENSIONS = {
    '.3gp', '.aac', '.avi', '.flac', '.flv', '.m4a', '.m4v', '.mkv',
    '.mov', '.mp3', '.mp4', '.mpeg', '.mpg', '.oga', '.ogg', '.opus',
    '.ts', '.wav', '.webm', '.wmv',
}


def _get_deno_path() -> str:
    path = project_resource_path('bin', 'deno.exe')
    return path if os.path.isfile(path) else ''


def _get_ffmpeg_path() -> str:
    path = project_resource_path('bin', 'ffmpeg.exe')
    if os.path.isfile(path):
        log.info('ffmpeg found at: %s', path)
    else:
        log.warning('ffmpeg not found at: %s', path)
    return path if os.path.isfile(path) else ''


def _build_playlist_items(entries: list) -> str:
    selected_indices = [i + 1 for i, e in enumerate(entries) if e.selected]
    ranges = []
    start = selected_indices[0]
    end = start
    for idx in selected_indices[1:]:
        if idx == end + 1:
            end = idx
        else:
            ranges.append(f'{start}-{end}' if start != end else str(start))
            start = end = idx
    ranges.append(f'{start}-{end}' if start != end else str(start))
    return ','.join(ranges)


def _playlist_download_plan(item: DownloadItem) -> tuple[list[str], str | None, bool]:
    """Return URLs, selected playlist indices, and whether playlist mode is needed."""
    if not item.playlist_entries:
        return [item.url], None, False
    selected_entries = [entry for entry in item.playlist_entries if entry.selected]
    if not selected_entries:
        return [], None, False
    if len(selected_entries) == 1:
        return [selected_entries[0].url], None, False
    return [item.url], _build_playlist_items(item.playlist_entries), True


def _playlist_output_template(output_dir: str) -> str:
    return os.path.join(
        output_dir,
        '%(playlist_index)03d - %(title)s [%(id)s].%(ext)s',
    )


def _output_container(fmt_id: str, formats: list) -> str | None:
    if not fmt_id or '+' in fmt_id or '/' in fmt_id:
        return None
    if fmt_id in ('best', 'bestvideo', 'bestaudio', 'worst', 'worstvideo', 'worstaudio'):
        return None
    for f in formats:
        if f.format_id == fmt_id and f.ext in ('mp4', 'webm', 'mkv', 'm4a', 'mp3', 'flv', 'avi'):
            return f.ext
    return None


def _resolve_format(fmt_id: str, formats: list) -> str:
    if not fmt_id or '+' in fmt_id or '/' in fmt_id:
        return fmt_id
    if fmt_id in ('best', 'bestvideo', 'bestaudio', 'worst', 'worstvideo', 'worstaudio'):
        return fmt_id
    for f in formats:
        if f.format_id == fmt_id:
            if f.fmt_type == FormatType.VIDEO_ONLY:
                resolved = f'{fmt_id}+bestaudio/best'
                log.info('Video-only format %s -> %s', fmt_id, resolved)
                return resolved
            return fmt_id
    return fmt_id


def _reserve_output_stem(output_dir: str, clean_title: str) -> str:
    with _OUTPUT_RESERVATION_LOCK:
        counter = 0
        while True:
            suffix = f' ({counter})' if counter else ''
            stem = os.path.normcase(os.path.abspath(os.path.join(output_dir, clean_title + suffix)))
            if stem not in _RESERVED_OUTPUT_STEMS and not glob.glob(glob.escape(stem) + '.*'):
                _RESERVED_OUTPUT_STEMS.add(stem)
                return stem
            counter += 1


def _release_output_stem(stem: str | None):
    if not stem:
        return
    with _OUTPUT_RESERVATION_LOCK:
        _RESERVED_OUTPUT_STEMS.discard(os.path.normcase(os.path.abspath(stem)))


def _find_output_file(output_stem: str) -> str | None:
    candidates = []
    for f in glob.glob(glob.escape(output_stem) + '.*'):
        if not os.path.isfile(f):
            continue
        basename = os.path.basename(f)
        lower = basename.lower()
        if lower.endswith(('.part', '.ytdl', '.temp')) or re.search(r'\.f\d{1,5}\.', lower):
            continue
        if os.path.splitext(lower)[1] not in _MEDIA_EXTENSIONS:
            continue
        candidates.append((os.path.getmtime(f), f))
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]
    return None


def _resolve_output_candidates(paths: set[str]) -> list[str]:
    """Resolve hook paths to final media files after merging/transcoding."""
    results: set[str] = set()
    stems: set[str] = set()
    for path in paths:
        if not path:
            continue
        absolute = os.path.abspath(path)
        root, _ = os.path.splitext(absolute)
        stems.add(re.sub(r'\.f\d{1,5}$', '', root))
        if os.path.isfile(absolute):
            lower = absolute.lower()
            if (os.path.splitext(lower)[1] in _MEDIA_EXTENSIONS
                    and not re.search(r'\.f\d{1,5}\.', lower)):
                results.add(absolute)

    for stem in stems:
        for candidate in glob.glob(glob.escape(stem) + '.*'):
            lower = candidate.lower()
            if (os.path.isfile(candidate)
                    and os.path.splitext(lower)[1] in _MEDIA_EXTENSIONS
                    and not re.search(r'\.f\d{1,5}\.', lower)):
                results.add(os.path.abspath(candidate))
    return sorted(results)


class _StopDownload(KeyboardInterrupt):
    pass


class DownloadWorker(QThread):
    def __init__(self, item: DownloadItem, output_dir: str, parent=None):
        super().__init__(parent)
        self.item = item
        self.output_dir = output_dir
        self._cancelled = False
        self._paused = False
        self._expected_output_path = None
        self._reserved_output_stem: str | None = None

    def cancel(self):
        log.info('Cancelling download: %s', self.item.uid)
        self._cancelled = True

    def pause(self):
        log.info('Pausing download: %s', self.item.uid)
        self._paused = True

    def release_output_reservation(self):
        _release_output_stem(self._reserved_output_stem)
        self._reserved_output_stem = None

    def run(self):
        uid = self.item.uid
        log.info('Starting download [%s]: %s', uid, self.item.title or self.item.url[:60])

        last_filename = None
        output_candidates: set[str] = set()
        self.item.output_paths = []

        urls, playlist_items, is_multi_playlist = _playlist_download_plan(self.item)
        if not urls:
            log.info('No playlist items selected, cancelling download')
            signal_bus.download_cancelled.emit(uid)
            return

        def progress_hook(d):
            nonlocal last_filename
            if self._paused or self._cancelled:
                raise _StopDownload()
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                pct = (downloaded / total * 100) if total else 0
                speed = d.get('_speed_str', '').strip() or ''
                eta = d.get('_eta_str', '').strip() or ''
                signal_bus.progress_updated.emit(uid, pct, speed, eta)
                self.item.progress = pct
            elif d['status'] == 'finished':
                log.info('Download finished [%s], processing...', uid)
                last_filename = d.get('filename', '')
                if last_filename:
                    output_candidates.add(last_filename)
                log.info('Hook output: %s', last_filename)
                signal_bus.progress_updated.emit(uid, 100.0, '', 'Processing...')

        def postprocessor_hook(d):
            if self._paused or self._cancelled:
                raise _StopDownload()
            if d['status'] == 'started':
                signal_bus.progress_updated.emit(uid, 100.0, '', f'Running {d.get("postprocessor", "postprocessor")}...')
            info = d.get('info_dict') or {}
            for key in ('filepath', '_filename'):
                candidate = info.get(key) or d.get(key)
                if candidate:
                    output_candidates.add(candidate)
            for requested in info.get('requested_downloads') or []:
                candidate = requested.get('filepath')
                if candidate:
                    output_candidates.add(candidate)

        from app.widgets.settings_dialog import load_settings
        settings = load_settings()

        ffmpeg = _get_ffmpeg_path()
        self.item.output_dir = self.output_dir
        fmt = _resolve_format(self.item.selected_format or 'bestvideo+bestaudio/best', self.item.formats)
        
        # Auto-increment filename if it already exists on disk
        ext = 'mp4'
        out_fmt = (self.item.output_format or '').lower()
        if out_fmt:
            ext = out_fmt
        else:
            resolved_ext = _output_container(self.item.selected_format, self.item.formats)
            if resolved_ext:
                ext = resolved_ext

        # Resolve selected format resolution to include in filename
        res_str = ''
        if self.item.formats:
            for f in self.item.formats:
                if f.format_id == self.item.selected_format:
                    res_str = f.resolution
                    break

        from yt_dlp.utils import sanitize_filename
        base_title = self.item.title or 'video'
        if res_str:
            base_title = f"{base_title} ({res_str})"
        clean_title = sanitize_filename(base_title)
        
        if is_multi_playlist:
            outtmpl_val = _playlist_output_template(self.output_dir)
            self._expected_output_path = None
        else:
            self._reserved_output_stem = _reserve_output_stem(self.output_dir, clean_title)
            outtmpl_val = self._reserved_output_stem + '.%(ext)s'
            self._expected_output_path = self._reserved_output_stem + f'.{ext}'

        opts = {
            'format': fmt,
            'outtmpl': {'default': outtmpl_val},
            'progress_hooks': [progress_hook],
            'postprocessor_hooks': [postprocessor_hook],
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'noplaylist': not is_multi_playlist,
            'socket_timeout': 30,
            'retries': 3,
            'file_access_retries': 3,
            'extractor_retries': 3,
        }
        if playlist_items:
            opts['playlist_items'] = playlist_items
            log.info('Downloading selected playlist items: %s', playlist_items)

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

        if settings.get('embed_thumbnail', False):
            opts['writethumbnail'] = True
            opts.setdefault('postprocessors', []).append({
                'key': 'EmbedThumbnail',
                'already_have_thumbnail': False,
            })

        if settings.get('embed_metadata', False):
            opts['addmetadata'] = True
            opts.setdefault('postprocessors', []).append({
                'key': 'FFmpegMetadata',
                'add_chapters': True,
                'add_metadata': True,
            })

        if settings.get('write_subs', False):
            opts['writesubtitles'] = True
            opts['allsubtitles'] = True

        out_fmt = (self.item.output_format or '').lower()
        if not out_fmt and settings.get('convert_mp3', False):
            out_fmt = 'mp3'

        if out_fmt in ('mp4', 'mkv', 'mov', 'webm'):
            opts['merge_output_format'] = out_fmt
            log.info('Output container: %s', out_fmt)
        elif out_fmt in ('mp3', 'wav'):
            opts.setdefault('postprocessors', []).append({
                'key': 'FFmpegExtractAudio',
                'preferredcodec': out_fmt,
                'preferredquality': '0' if out_fmt == 'mp3' else None,
            })
            log.info('Audio output: %s', out_fmt)

        import shlex
        import yt_dlp
        custom_args_str = settings.get('custom_args', '').strip()
        if custom_args_str:
            try:
                _, _, _, def_opts = yt_dlp.parse_options([])
                _, _, _, custom_opts = yt_dlp.parse_options(shlex.split(custom_args_str))
                diff_opts = {k: v for k, v in custom_opts.items() if def_opts.get(k) != v}
                
                custom_pps = diff_opts.pop('postprocessors', None)
                if custom_pps:
                    existing_pps = opts.setdefault('postprocessors', [])
                    for pp in custom_pps:
                        if pp not in existing_pps:
                            existing_pps.append(pp)
                
                opts.update(diff_opts)
            except Exception as e:
                log.error('Failed to parse custom_args: %s', e)

        log.debug('Download opts: format=%s, outtmpl=%s',
                  opts['format'], opts['outtmpl'])
        if ffmpeg:
            opts['ffmpeg_location'] = ffmpeg

        try:
            with YoutubeDL(opts) as ydl:
                result = ydl.download(urls)

            if is_multi_playlist:
                self.item.output_paths = _resolve_output_candidates(output_candidates)
                if not self.item.output_paths:
                    message = (f'yt-dlp exited with status {result}'
                               if result not in (None, 0)
                               else 'Playlist download produced no output files')
                    log.warning('%s [%s]', message, uid)
                    signal_bus.download_error.emit(uid, message)
                    return
                self.item.output_path = self.output_dir
                log.info('Playlist produced %d files in %s',
                         len(self.item.output_paths), self.output_dir)
            elif self._expected_output_path and os.path.isfile(self._expected_output_path):
                self.item.output_path = self._expected_output_path
                self.item.output_paths = [self.item.output_path]
                log.info('Using expected output file: %s', self.item.output_path)
            elif last_filename and os.path.isfile(last_filename):
                self.item.output_path = last_filename
                self.item.output_paths = [self.item.output_path]
                log.info('Using hook output: %s', last_filename)
            else:
                found = _find_output_file(self._reserved_output_stem)
                if found:
                    self.item.output_path = found
                    self.item.output_paths = [found]
                    log.info('Found output file: %s', found)
                else:
                    log.warning('Download produced no output (format %s may not be available)', fmt)
                    signal_bus.download_error.emit(uid, f'No output produced for format {fmt}')
                    return

            if result not in (None, 0) and not self.item.output_path:
                signal_bus.download_error.emit(uid, f'yt-dlp exited with status {result}')
                return

            if self._paused:
                log.info('Download paused [%s]', uid)
                signal_bus.download_paused.emit(uid)
            elif self._cancelled:
                log.info('Download cancelled [%s]', uid)
                signal_bus.download_cancelled.emit(uid)
            else:
                log.info('Download completed [%s]', uid)
                signal_bus.download_completed.emit(uid)
        except (Exception, KeyboardInterrupt) as e:
            if not self.item.output_path:
                if last_filename and os.path.isfile(last_filename):
                    self.item.output_path = last_filename
                    self.item.output_paths = [last_filename]
            if self._paused:
                log.info('Download paused [%s]', uid)
                signal_bus.download_paused.emit(uid)
            elif self._cancelled:
                log.info('Download cancelled [%s]', uid)
                signal_bus.download_cancelled.emit(uid)
            else:
                log.error('Download failed [%s]: %s', uid, e, exc_info=True)
                signal_bus.download_error.emit(uid, str(e))
        finally:
            self.release_output_reservation()
