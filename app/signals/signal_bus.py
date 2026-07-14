from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

log = logging.getLogger('app.signals')


class SignalBus(QObject):
    metadata_fetched = Signal(object, str)
    metadata_error = Signal(str, str)
    format_selected = Signal(object)
    download_queued = Signal(object)
    progress_updated = Signal(str, float, str, str)
    download_completed = Signal(str)
    download_error = Signal(str, str)
    download_cancelled = Signal(str)
    download_paused = Signal(str)
    queue_changed = Signal()
    settings_changed = Signal()

    def __init__(self):
        super().__init__()
        self.metadata_fetched.connect(self._log_fetched)
        self.metadata_error.connect(self._log_error)
        self.progress_updated.connect(self._log_progress)
        self.download_completed.connect(lambda uid: log.info('Download completed: %s', uid))
        self.download_error.connect(lambda uid, err: log.error('Download error %s: %s', uid, err))
        self.download_paused.connect(lambda uid: log.info('Download paused: %s', uid))
        self.download_cancelled.connect(lambda uid: log.info('Download cancelled: %s', uid))

    def _log_fetched(self, item, url):
        log.info('Metadata fetched: %s (%d formats)', item.title[:50] if item.title else url, len(item.formats))

    def _log_error(self, error, url):
        log.error('Metadata error for %s: %s', url[:60], error)

    def _log_progress(self, uid, pct, speed, eta):
        if int(pct) % 25 == 0:
            log.debug('Progress %s: %.0f%% %s %s', uid, pct, speed, eta)


signal_bus = SignalBus()
