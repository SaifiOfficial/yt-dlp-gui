from __future__ import annotations

import logging
import os
from copy import deepcopy

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QStatusBar, QTabWidget, QVBoxLayout, QWidget,
    QLineEdit, QApplication, QSplitter
)

from app.icon import get_app_icon
from app.models.download_item import DownloadItem, DownloadStatus
from app.signals.signal_bus import signal_bus
from app.widgets.format_table import FormatTable
from app.widgets.playlist_panel import PlaylistPanel
from app.widgets.queue_widget import QueueWidget
from app.widgets.settings_dialog import SettingsDialog, load_settings
from app.widgets.url_bar import UrlBar
from app.workers.download_worker import DownloadWorker, _get_ffmpeg_path
from app.workers.extract_worker import ExtractWorker
from app.widgets.browser_widget import BrowserWidget
from app.utils.paths import project_resource_path

log = logging.getLogger('app.main_window')


FORMAT_PRESETS = [
    ('Best Video + Audio (Recommended)', 'bestvideo+bestaudio/best'),
    ('Best MP4 Video + Audio', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]'),
    ('Best WebM Video + Audio', 'bestvideo[ext=webm]+bestaudio[ext=webm]/best[ext=webm]'),
    ('Best MKV Video + Audio', 'bestvideo[ext=mkv]+bestaudio/best[ext=mkv]'),
    ('Best MOV Video + Audio', 'bestvideo[ext=mov]+bestaudio/best[ext=mov]'),
    ('Best MP3 Audio', 'bestaudio[ext=mp3]/bestaudio'),
    ('Best M4A Audio', 'bestaudio[ext=m4a]/bestaudio'),
    ('Best Video Only', 'bestvideo'),
    ('Best Audio Only', 'bestaudio'),
]


def _create_download_complete_popup(parent, item: DownloadItem | None) -> QMessageBox:
    popup = QMessageBox(parent)
    popup.setIcon(QMessageBox.Icon.Information)
    popup.setWindowTitle('Download Complete')
    popup.setTextFormat(Qt.PlainText)
    popup.setStandardButtons(QMessageBox.StandardButton.Ok)
    popup.setWindowModality(Qt.NonModal)
    popup.setModal(False)
    popup.setAttribute(Qt.WA_DeleteOnClose)

    if item and len(item.output_paths) > 1:
        location = item.output_dir or item.output_path or 'Downloads'
        popup.setText(
            f'Playlist download finished.\n\n'
            f'{len(item.output_paths)} files downloaded.\n\n'
            f'Saved to:\n{location}'
        )
    elif item:
        location = item.output_path or item.output_dir or 'Downloads'
        popup.setText(
            f'Download finished:\n{item.title or item.url}\n\n'
            f'Saved to:\n{location}'
        )
    else:
        popup.setText('Download finished successfully.')
    return popup


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        log.info('Initializing MainWindow')
        self.settings = load_settings()
        self._current_item: DownloadItem | None = None
        self._active_workers: dict[str, DownloadWorker] = {}
        self._extract_worker: ExtractWorker | None = None
        self._extract_workers: set[ExtractWorker] = set()
        self._requested_url = ''
        self._pending_items: list[DownloadItem] = []
        self._closing = False
        self._shutdown_ready = False
        self._shutdown_timer = QTimer(self)
        self._shutdown_timer.setInterval(100)
        self._shutdown_timer.timeout.connect(self._poll_shutdown)
        self._completion_notifications: list[QMessageBox] = []

        self.setWindowTitle('yt-dlp GUI')
        self.setWindowIcon(get_app_icon())
        self.setMinimumSize(960, 680)
        self._build_ui()
        self._connect_signals()

        QTimer.singleShot(500, self._init_ffmpeg_status)

    def _build_ui(self):
        log.debug('Building UI')
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        from PySide6.QtGui import QIcon
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.url_bar = UrlBar()
        main_layout.addWidget(self.url_bar)

        format_bar = QHBoxLayout()
        format_bar.addWidget(QLabel('Format:'))
        self.format_filter = QComboBox()
        self.format_filter.setMinimumWidth(140)
        from app.widgets.format_table import FILTERS
        self.format_filter.addItems(FILTERS)
        format_bar.addWidget(self.format_filter)
        
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText('Filter formats (e.g. 1080p, mp4, vcodec:h264)')
        settings_icon = QIcon(os.path.join(base_dir, 'resources', 'icons', 'settings.png'))
        self.filter_edit.addAction(settings_icon, QLineEdit.TrailingPosition)
        format_bar.addWidget(self.filter_edit, 1)

        self.format_combo = QComboBox()
        self.format_combo.hide()

        self.download_btn = QPushButton('Download')
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._on_download)
        
        dl_icon = QIcon(os.path.join(base_dir, 'resources', 'icons', 'download.png'))
        self.download_btn.setIcon(dl_icon)
        
        format_bar.addWidget(self.download_btn)
        main_layout.addLayout(format_bar)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs, 1)

        fetch_tab = QWidget()
        fetch_layout = QVBoxLayout(fetch_tab)
        self.format_table = FormatTable()
        self.playlist_panel = PlaylistPanel()
        self.playlist_panel.hide()

        fetch_layout.addWidget(self.format_table, 2)
        fetch_layout.addWidget(self.playlist_panel, 1)

        self.tabs.addTab(fetch_tab, 'Fetch')

        self.queue_widget = QueueWidget(self)
        self.tabs.addTab(self.queue_widget, 'Queue')

        from app.widgets.browser_widget import BrowserWidget
        self.browser_panel = BrowserWidget(self)
        self.tabs.addTab(self.browser_panel, 'Browser')

        self.tabs.setTabIcon(0, QIcon(os.path.join(base_dir, 'resources', 'icons', 'search.png')))
        self.tabs.setTabIcon(1, QIcon(os.path.join(base_dir, 'resources', 'icons', 'queue.png')))
        self.tabs.setTabIcon(2, QIcon(os.path.join(base_dir, 'resources', 'icons', 'browser.png')))

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel('<span style="color: #22c55e; font-size: 14px;">●</span> Ready')
        self.ffmpeg_status = QLabel()
        self.ffmpeg_ok_badge = QLabel("")
        self.ffmpeg_ok_badge.setObjectName("ffmpeg_ok_badge")
        self.ffmpeg_ok_badge.hide()

        self.status_bar.addWidget(self.status_label, 1)
        self.status_bar.addPermanentWidget(self.ffmpeg_status)
        self.status_bar.addPermanentWidget(self.ffmpeg_ok_badge)

        menubar = self.menuBar()
        settings_action = QAction('Settings...', self)
        settings_action.triggered.connect(self._open_settings)
        file_menu = menubar.addMenu('File')
        file_menu.addAction(settings_action)

        browser_action = QAction('Browser', self)
        browser_action.triggered.connect(self._open_browser)
        menubar.addAction(browser_action)

        about_action = QAction('About', self)
        about_action.triggered.connect(self._show_about)
        help_menu = menubar.addMenu('Help')
        help_menu.addAction(about_action)

    def _connect_signals(self):
        log.debug('Connecting signals')
        self.url_bar.fetch_requested.connect(self._on_fetch_url)
        self.format_filter.currentTextChanged.connect(
            lambda name: self.format_table.set_filter(name)
        )
        self.filter_edit.textChanged.connect(self.format_table.set_search_filter)
        self.format_table.format_selected.connect(self._on_format_selected)
        signal_bus.metadata_fetched.connect(self._on_metadata_fetched)
        signal_bus.metadata_error.connect(self._on_metadata_error)
        signal_bus.download_completed.connect(self._on_download_done)
        signal_bus.download_error.connect(self._on_download_error)
        signal_bus.settings_changed.connect(self._on_settings_changed)
        self.browser_panel.web_view.urlChanged.connect(self._on_browser_url_changed)
        log.debug('Signals connected')

    def _on_fetch_url(self, url: str):
        log.info('Fetch requested for URL: %s', url[:80])
        if (self._extract_worker and self._extract_worker.isRunning()
                and self._extract_worker.url == url):
            self.status_label.setText('Already fetching this URL...')
            return
        self.status_label.setText('Fetching metadata...')
        self.download_btn.setEnabled(False)
        self.filter_edit.clear()
        self.format_combo.clear()
        self.format_filter.setCurrentIndex(0)
        self.format_table.clear()
        self.playlist_panel.clear()
        self._current_item = None

        self._requested_url = url
        if self._extract_worker and self._extract_worker.isRunning():
            self._extract_worker.requestInterruption()

        worker = ExtractWorker(url, self)
        self._extract_worker = worker
        self._extract_workers.add(worker)
        worker.finished.connect(lambda w=worker: self._on_extract_worker_finished(w))
        worker.start()

    def _on_extract_worker_finished(self, worker: ExtractWorker):
        self._extract_workers.discard(worker)
        if self._extract_worker is worker:
            self._extract_worker = None
        worker.deleteLater()

    def _on_metadata_fetched(self, item: DownloadItem, url: str):
        if url != self._requested_url or self._closing:
            log.info('Ignoring stale metadata result for: %s', url[:80])
            return
        log.info('Metadata received: %s', item.title[:60])
        self._current_item = item
        self.status_label.setText(f'Fetched: {item.title}')
        log.debug('Displaying %d formats', len(item.formats))
        self.format_table.display_formats(item)
        self.playlist_panel.display_playlist(item)

        self.format_combo.clear()
        if item.formats:
            for label, fmt in FORMAT_PRESETS:
                self.format_combo.addItem(label, fmt)
            self.format_combo.setCurrentIndex(0)
            self.download_btn.setEnabled(True)
            log.info('Download button enabled')
        else:
            self.download_btn.setEnabled(False)
            self.status_label.setText('No downloadable formats found (playlist only)')

    def _on_metadata_error(self, error: str, url: str):
        if url != self._requested_url or self._closing:
            log.info('Ignoring stale metadata error for: %s', url[:80])
            return
        log.error('Metadata fetch failed: %s', error)
        self.status_label.setText('Error fetching metadata')
        QMessageBox.warning(self, 'Fetch Error', f'Could not fetch metadata:\n{error}')

    def _on_format_selected(self, format_id: str):
        log.debug('Format selected from table: %s', format_id)
        label = format_id
        if self._current_item:
            for f in self._current_item.formats:
                if f.format_id == format_id:
                    parts = [f.ext.upper(), f.resolution] if f.resolution else [f.ext.upper()]
                    parts.append(f'({format_id})')
                    label = ' '.join(parts)
                    break
        for i in range(self.format_combo.count()):
            if self.format_combo.itemData(i) == format_id:
                self.format_combo.setCurrentIndex(i)
                return
        self.format_combo.insertItem(0, label, format_id)
        self.format_combo.setCurrentIndex(0)

    def _on_download(self):
        if not self._current_item:
            log.warning('Download clicked but no current item')
            return

        from dataclasses import replace
        import uuid

        # Clone the item so that each queued item is an independent entry in the queue
        item = replace(
            self._current_item,
            status=DownloadStatus.PENDING,
            progress=0.0,
            speed='',
            eta='',
            error_message='',
            output_path='',
            output_paths=[],
            formats=list(self._current_item.formats),
            playlist_entries=deepcopy(self._current_item.playlist_entries),
            uid=uuid.uuid4().hex[:8]
        )
        
        fmt = self.format_combo.currentData()
        item.selected_format = fmt
        log.info('Download queued: %s (format: %s)', item.title[:50], fmt)

        out_ext = ''
        if item.formats:
            for f in item.formats:
                if f.format_id == fmt:
                    out_ext = f.ext
                    break
        if not out_ext and fmt:
            if 'mp4' in fmt:
                out_ext = 'mp4'
            elif 'webm' in fmt:
                out_ext = 'webm'
            elif 'mkv' in fmt:
                out_ext = 'mkv'
            elif 'mov' in fmt:
                out_ext = 'mov'
            elif 'mp3' in fmt:
                out_ext = 'mp3'
            elif 'm4a' in fmt:
                out_ext = 'm4a'
            elif 'wav' in fmt:
                out_ext = 'wav'

        # Force transcoding to MP3 or WAV if selected in the dropdown filter
        filter_text = self.format_filter.currentText()
        if filter_text == 'Audio: MP3':
            out_ext = 'mp3'
        elif filter_text == 'Audio: WAV':
            out_ext = 'wav'

        item.output_format = out_ext

        if item.playlist_entries:
            name = f'{item.title} ({len([e for e in item.playlist_entries if e.selected])} items)'
        else:
            name = item.title

        self.queue_widget.add_item(item)
        self._pending_items.append(item)
        self.tabs.setCurrentIndex(1)
        self.status_label.setText(f'Queued: {name}')
        self._process_queue()

    def _process_queue(self):
        max_parallel = self.settings.get('max_parallel', 3)
        running = len(self._active_workers)
        available = max_parallel - running
        log.debug('Queue: %d pending, %d running, %d available',
                  len(self._pending_items), running, available)

        while available > 0 and self._pending_items:
            item = self._pending_items.pop(0)
            if item.status in (DownloadStatus.CANCELLED, DownloadStatus.COMPLETED, DownloadStatus.PAUSED):
                continue
            item.status = DownloadStatus.DOWNLOADING
            output_dir = item.output_dir or self.settings.get('output_dir') or os.path.join(
                os.path.expanduser('~'), 'Downloads'
            )
            log.info('Starting worker for %s -> %s', item.uid, output_dir)
            worker = DownloadWorker(item, output_dir, self)
            self._active_workers[item.uid] = worker
            worker.finished.connect(lambda uid=item.uid, w=worker: self._on_worker_finished(uid, w))
            worker.start()
            available -= 1

    def _on_worker_finished(self, uid: str, worker: DownloadWorker):
        worker.release_output_reservation()
        self._active_workers.pop(uid, None)
        log.debug('Worker finished: %s (%d remaining)', uid, len(self._active_workers))
        worker.deleteLater()
        if not self._closing:
            QTimer.singleShot(100, self._process_queue)

    def pause_download(self, uid: str):
        worker = self._active_workers.get(uid)
        if worker:
            worker.pause()

    def resume_download(self, uid: str):
        item = self.queue_widget.items.get(uid)
        if item and item.status == DownloadStatus.PAUSED:
            item.status = DownloadStatus.QUEUED
            self._pending_items.append(item)
            self._process_queue()

    def cancel_download(self, uid: str):
        worker = self._active_workers.get(uid)
        if worker:
            worker.cancel()
        else:
            item = self.queue_widget.items.get(uid)
            if item:
                item.status = DownloadStatus.CANCELLED
                signal_bus.download_cancelled.emit(uid)

    def cancel_all_downloads(self):
        for worker in list(self._active_workers.values()):
            worker.cancel()
        for item in self._pending_items:
            item.status = DownloadStatus.CANCELLED
            signal_bus.download_cancelled.emit(item.uid)
        self._pending_items.clear()

    def change_output_dir(self, uid: str, new_dir: str):
        item = self.queue_widget.items.get(uid)
        if item:
            item.output_dir = new_dir
            log.info('Output dir changed for %s: %s', uid, new_dir)

    def _on_download_done(self, uid: str):
        log.info('Download completed: %s', uid)
        self.status_label.setText('Download completed')
        if self._closing:
            return
        item = self.queue_widget.items.get(uid)
        popup = _create_download_complete_popup(self, item)
        self._completion_notifications.append(popup)
        popup.finished.connect(
            lambda _result, notification=popup: self._forget_completion_popup(notification)
        )
        popup.show()
        popup.raise_()
        popup.activateWindow()
        QApplication.alert(self, 3000)

    def _forget_completion_popup(self, popup: QMessageBox):
        try:
            self._completion_notifications.remove(popup)
        except ValueError:
            pass

    def _on_download_error(self, uid: str, error: str):
        log.error('Download error %s: %s', uid, error)
        self.status_label.setText(f'Download error')

    def _init_ffmpeg_status(self):
        path = _get_ffmpeg_path()
        if path:
            folder = os.path.basename(os.path.dirname(path))
            self.ffmpeg_status.setText(f'ffmpeg: bundled ({folder})')
            self.ffmpeg_ok_badge.setText("OK")
            self.ffmpeg_ok_badge.show()
            log.info('ffmpeg bundled: %s', path)
        else:
            self.ffmpeg_status.setText('ffmpeg: not bundled')
            self.ffmpeg_ok_badge.hide()
            log.warning('ffmpeg not found')

    def _open_settings(self):
        log.info('Opening settings dialog')
        dlg = SettingsDialog(self)
        dlg.exec()

    def _open_browser(self):
        log.info('Switching to browser tab')
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == 'Browser':
                self.tabs.setCurrentIndex(i)
                break

    def _on_settings_changed(self):
        log.info('Settings changed, reloading')
        self.settings = load_settings()
        try:
            from app.utils.proxy import set_proxy_ip
            set_proxy_ip(self.settings.get('proxy', ''))
        except Exception as e:
            log.error("Failed to apply proxy settings dynamically: %s", e)

        if hasattr(self, 'browser_panel') and self.browser_panel:
            self.browser_panel.apply_settings()

        app = QApplication.instance()
        if app:
            if self.settings.get('dark_theme', True):
                qss_path = project_resource_path('resources', 'style.qss')
                try:
                    with open(qss_path, encoding='utf-8') as stylesheet:
                        app.setStyleSheet(stylesheet.read())
                except OSError as e:
                    log.error('Failed to apply stylesheet: %s', e)
            else:
                app.setStyleSheet('')

    def _on_browser_url_changed(self, url):
        url_str = url.toString()
        video_patterns = [
            "youtube.com/watch", "youtu.be/", "youtube.com/shorts",
            "youtube.com/live", "vimeo.com/", "dailymotion.com/video/"
        ]
        if any(pattern in url_str for pattern in video_patterns):
            log.info("Detected video URL from browser: %s", url_str)
            self.url_bar.url_input.setText(url_str)

    def _show_about(self):
        QMessageBox.about(
            self, 'About yt-dlp GUI',
            'yt-dlp GUI v1.0\n\n'
            'A graphical interface for yt-dlp.\n'
            'Powered by yt-dlp and PySide6.'
        )

    def closeEvent(self, event):
        if not self._shutdown_ready:
            event.ignore()
            if not self._closing:
                log.info('Shutting down...')
                self._closing = True
                self.setEnabled(False)
                self.status_label.setText('Waiting for background operations to stop...')
                for worker in list(self._extract_workers):
                    worker.requestInterruption()
                self.cancel_all_downloads()
                self._shutdown_timer.start()
            self._poll_shutdown()
            return

        if hasattr(self, 'browser_panel') and self.browser_panel:
            # Explicitly detach and delete the page before closing so
            # QWebEngineProfile can be released cleanly (avoids the
            # "WebEnginePage still not deleted" Qt warning).
            try:
                page = self.browser_panel.web_view.page()
                self.browser_panel.web_view.setPage(None)
                if page is not None:
                    page.deleteLater()
                QApplication.processEvents()
            except Exception:
                pass

        log.info('Shutdown complete')
        super().closeEvent(event)

    def _poll_shutdown(self):
        extract_running = any(worker.isRunning() for worker in self._extract_workers)
        downloads_running = any(worker.isRunning() for worker in self._active_workers.values())
        if extract_running or downloads_running:
            return
        self._shutdown_timer.stop()
        self._shutdown_ready = True
        QTimer.singleShot(0, self.close)
