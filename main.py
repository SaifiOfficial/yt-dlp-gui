from __future__ import annotations

import logging
import sys
import traceback

from PySide6.QtCore import QFile, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from app.icon import get_app_icon
from app.main_window import MainWindow
from app.widgets.settings_dialog import load_settings


def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S',
        stream=sys.stderr,
        force=True,
    )
    logging.getLogger('app').info('Logging initialized')


def global_exception_handler(exc_type, exc_value, exc_tb):
    logging.critical('Unhandled exception', exc_info=(exc_type, exc_value, exc_tb))
    print(f'\nFATAL: {exc_type.__name__}: {exc_value}', file=sys.stderr)
    traceback.print_exception(exc_type, exc_value, exc_tb)


def qt_message_handler(mode, context, message):
    if mode == Qt.WarningMsg or mode == Qt.CriticalMsg or mode == Qt.FatalMsg:
        logging.warning('Qt: %s', message)
        print(f'  [Qt] {message}', file=sys.stderr)


def _load_stylesheet(app: QApplication, path: str):
    f = QFile(path)
    if f.open(QFile.ReadOnly | QFile.Text):
        style = f.readAll().data().decode('utf-8')
        app.setStyleSheet(style)
        f.close()
        logging.getLogger('app').info('Stylesheet loaded from %s', path)


def main():
    setup_logging()
    sys.excepthook = global_exception_handler

    log = logging.getLogger('app')

    log.info('Starting yt-dlp GUI')
    app = QApplication(sys.argv)

    try:
        import yt_dlp
        log.info('yt-dlp version: %s', yt_dlp.version.__version__)
    except Exception as e:
        log.error('Failed to import yt_dlp: %s', e)

    try:
        import PySide6
        log.info('PySide6 version: %s', PySide6.__version__)
    except Exception:
        pass

    app.setApplicationName('yt-dlp GUI')
    app.setOrganizationName('yt-dlp-gui')
    app.setWindowIcon(get_app_icon())
    font = QFont('Segoe UI', 9)
    app.setFont(font)

    settings = load_settings()
    
    # Initialize global application proxy configuration
    try:
        from app.utils.proxy import set_proxy_ip
        set_proxy_ip(settings.get('proxy', ''))
    except Exception as e:
        log.error("Failed to initialize proxy: %s", e)

    if settings.get('dark_theme', True):
        import os
        qss_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'style.qss')
        if os.path.isfile(qss_path):
            _load_stylesheet(app, qss_path)
        else:
            log.warning('Stylesheet not found at %s', qss_path)

    log.info('Creating main window')
    window = MainWindow()
    window.show()
    log.info('Application running')
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
