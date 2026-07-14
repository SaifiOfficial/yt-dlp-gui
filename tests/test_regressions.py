import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication

from app import main_window
from app.models.download_item import DownloadItem, DownloadStatus, FormatInfo, FormatType, PlaylistEntry
from app.utils.paths import project_resource_path
from app.widgets import browser_widget, queue_widget
from app.widgets.format_table import FormatTable
from app.widgets.playlist_panel import PlaylistPanel
from app.widgets.queue_widget import QueueWidget
from app.workers import download_worker
from app.workers.download_worker import (
    DownloadWorker,
    _find_output_file,
    _playlist_download_plan,
    _playlist_output_template,
    _release_output_stem,
    _reserve_output_stem,
    _resolve_output_candidates,
)
from yt_dlp import YoutubeDL


class RegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_change_output_folder_updates_cell_widget(self):
        widget = QueueWidget()
        item = DownloadItem('https://example.test/video', title='Video')
        widget.add_item(item)
        with patch.object(queue_widget.QFileDialog, 'getExistingDirectory', return_value='C:/Temp'):
            widget._change_output_dir(item.uid)
        self.assertEqual(item.output_dir, 'C:/Temp')
        self.assertIsNotNone(widget.table.cellWidget(0, 5))

    def test_download_complete_popup_contains_title_and_location(self):
        item = DownloadItem(
            'url', title='Finished video', output_path='C:/Downloads/video.mp4',
            output_paths=['C:/Downloads/video.mp4'],
        )
        popup = main_window._create_download_complete_popup(None, item)
        try:
            self.assertEqual(popup.windowTitle(), 'Download Complete')
            self.assertIn('Finished video', popup.text())
            self.assertIn('C:/Downloads/video.mp4', popup.text())
            self.assertFalse(popup.isModal())
        finally:
            popup.deleteLater()

    def test_playlist_complete_popup_contains_file_count(self):
        item = DownloadItem(
            'url', title='Playlist', output_dir='C:/Downloads',
            output_paths=['one.mp4', 'two.mp4', 'three.mp4'],
        )
        popup = main_window._create_download_complete_popup(None, item)
        try:
            self.assertIn('3 files downloaded', popup.text())
            self.assertIn('C:/Downloads', popup.text())
        finally:
            popup.deleteLater()

    def test_pending_item_uses_its_selected_output_directory(self):
        class FakeSignal:
            def connect(self, callback):
                self.callback = callback

        class FakeWorker:
            created = []

            def __init__(self, item, output_dir, parent=None):
                self.item = item
                self.output_dir = output_dir
                self.finished = FakeSignal()
                self.created.append(self)

            def start(self):
                pass

        item = DownloadItem('url', title='Video', output_dir='C:/Chosen')
        window = SimpleNamespace(
            settings={'max_parallel': 1, 'output_dir': 'C:/Default'},
            _active_workers={}, _pending_items=[item], _closing=False,
            _on_worker_finished=lambda *args: None,
        )
        with patch.object(main_window, 'DownloadWorker', FakeWorker):
            main_window.MainWindow._process_queue(window)
        self.assertEqual(FakeWorker.created[0].output_dir, 'C:/Chosen')
        self.assertEqual(item.status, DownloadStatus.DOWNLOADING)

    def test_clear_all_cancels_background_work(self):
        owner = SimpleNamespace(cancelled=False)
        owner.cancel_all_downloads = lambda: setattr(owner, 'cancelled', True)
        widget = QueueWidget(main_window=owner)
        widget.add_item(DownloadItem('url', title='Video'))
        with patch.object(
            queue_widget.QMessageBox,
            'question',
            return_value=queue_widget.QMessageBox.StandardButton.Yes,
        ):
            widget._clear_all()
        self.assertTrue(owner.cancelled)
        self.assertEqual(widget.table.rowCount(), 0)

    def test_fractional_playlist_duration_is_rendered(self):
        panel = PlaylistPanel()
        item = DownloadItem(
            'https://example.test/list',
            playlist_entries=[PlaylistEntry('entry', 'Entry', duration=12.5)],
        )
        panel.display_playlist(item)
        self.assertEqual(panel.tree.topLevelItem(0).text(2), '0:12')

    def test_output_reservations_are_unique_and_ignore_sidecars(self):
        with tempfile.TemporaryDirectory() as directory:
            first = _reserve_output_stem(directory, 'Video')
            second = _reserve_output_stem(directory, 'Video')
            try:
                self.assertNotEqual(first, second)
                with open(first + '.jpg', 'wb') as sidecar:
                    sidecar.write(b'image')
                self.assertIsNone(_find_output_file(first))
                with open(first + '.mp4', 'wb') as media:
                    media.write(b'media')
                self.assertEqual(_find_output_file(first), first + '.mp4')
            finally:
                _release_output_stem(first)
                _release_output_stem(second)

    def test_partial_playlist_selection_enables_playlist_mode(self):
        item = DownloadItem(
            'https://example.test/playlist',
            playlist_entries=[
                PlaylistEntry('entry-1', 'One', selected=True),
                PlaylistEntry('entry-2', 'Two', selected=False),
                PlaylistEntry('entry-3', 'Three', selected=True),
                PlaylistEntry('entry-4', 'Four', selected=True),
            ],
        )
        urls, playlist_items, is_playlist = _playlist_download_plan(item)
        self.assertEqual(urls, [item.url])
        self.assertEqual(playlist_items, '1,3-4')
        self.assertTrue(is_playlist)

    def test_single_playlist_selection_stays_single_video_mode(self):
        item = DownloadItem(
            'https://example.test/playlist',
            playlist_entries=[
                PlaylistEntry('entry-1', 'One', selected=False),
                PlaylistEntry('entry-2', 'Two', selected=True),
            ],
        )
        urls, playlist_items, is_playlist = _playlist_download_plan(item)
        self.assertEqual(urls, ['entry-2'])
        self.assertIsNone(playlist_items)
        self.assertFalse(is_playlist)

    def test_playlist_template_is_unique_for_duplicate_titles(self):
        with tempfile.TemporaryDirectory() as directory:
            template = _playlist_output_template(directory)
            with YoutubeDL({'outtmpl': {'default': template}, 'quiet': True}) as ydl:
                first = ydl.prepare_filename({
                    'id': 'same-title-a', 'title': 'Same title', 'ext': 'mp4',
                    'playlist_index': 1,
                })
                second = ydl.prepare_filename({
                    'id': 'same-title-b', 'title': 'Same title', 'ext': 'mp4',
                    'playlist_index': 2,
                })
            self.assertNotEqual(first, second)
            self.assertIn('001 - Same title [same-title-a].mp4', first)
            self.assertIn('002 - Same title [same-title-b].mp4', second)

    def test_playlist_output_tracking_resolves_postprocessed_file(self):
        with tempfile.TemporaryDirectory() as directory:
            fragment = os.path.join(directory, '001 - Video [id].f137.mp4')
            final = os.path.join(directory, '001 - Video [id].mp4')
            with open(final, 'wb') as media:
                media.write(b'media')
            self.assertEqual(_resolve_output_candidates({fragment}), [final])

    def test_multi_playlist_worker_enables_playlist_mode_and_tracks_files(self):
        class FakeYoutubeDL:
            options = None

            def __init__(self, options):
                self.options = options
                FakeYoutubeDL.options = options

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def download(self, urls):
                self.urls = urls
                output_dir = os.path.dirname(self.options['outtmpl']['default'])
                for index, video_id in enumerate(('id-a', 'id-b'), start=1):
                    path = os.path.join(output_dir, f'{index:03d} - Same title [{video_id}].mp4')
                    with open(path, 'wb') as media:
                        media.write(b'media')
                    for hook in self.options['progress_hooks']:
                        hook({'status': 'finished', 'filename': path})
                return 0

        item = DownloadItem(
            'https://example.test/playlist', title='Playlist',
            playlist_entries=[
                PlaylistEntry('entry-a', 'Same title', selected=True),
                PlaylistEntry('entry-b', 'Same title', selected=True),
            ],
        )
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(download_worker, 'YoutubeDL', FakeYoutubeDL), \
                patch.object(download_worker, '_get_ffmpeg_path', return_value=''), \
                patch.object(download_worker, '_get_deno_path', return_value=''), \
                patch('app.widgets.settings_dialog.load_settings', return_value={
                    'proxy': '', 'cookies_file': '', 'cookies_from_browser': '',
                    'impersonate': False, 'custom_args': '',
                }):
            worker = DownloadWorker(item, directory)
            worker.run()

        self.assertFalse(FakeYoutubeDL.options['noplaylist'])
        self.assertEqual(FakeYoutubeDL.options['playlist_items'], '1-2')
        self.assertIn('%(playlist_index)03d', FakeYoutubeDL.options['outtmpl']['default'])
        self.assertEqual(len(item.output_paths), 2)
        self.assertEqual(item.output_path, directory)

    def test_frozen_resource_lookup_uses_bundle_root(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = os.path.join(directory, 'bin', 'ffmpeg.exe')
            os.makedirs(os.path.dirname(binary))
            with open(binary, 'wb') as executable:
                executable.write(b'ffmpeg')
            with patch('sys.frozen', True, create=True), patch('sys._MEIPASS', directory, create=True):
                self.assertEqual(project_resource_path('bin', 'ffmpeg.exe'), binary)

    def test_generated_adblock_extension_is_manifest_v3(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
            browser_widget, 'get_app_dir', return_value=directory
        ):
            extension_dir = browser_widget.create_built_in_adblocker()
            with open(os.path.join(extension_dir, 'manifest.json'), encoding='utf-8') as manifest_file:
                manifest = json.load(manifest_file)
            self.assertEqual(manifest['manifest_version'], 3)
            self.assertIn('declarative_net_request', manifest)
            self.assertTrue(os.path.isfile(os.path.join(extension_dir, 'rules.json')))

    def test_codec_alias_is_searchable(self):
        table = FormatTable()
        item = DownloadItem('url', title='Video', formats=[FormatInfo(
            format_id='137', ext='mp4', resolution='1080p', filesize='',
            tbr='1000', codec='avc1.640028', note='', fmt_type=FormatType.VIDEO_ONLY,
        )])
        table.display_formats(item)
        table.set_search_filter('vcodec:h264')
        self.assertFalse(table.table.isRowHidden(1))


if __name__ == '__main__':
    unittest.main()
