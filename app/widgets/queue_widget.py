from __future__ import annotations

import logging
import os

import subprocess

from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QAction, QColor, QBrush
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QMenu, QPushButton,
    QTableWidget, QTableWidgetItem, QWidget, QVBoxLayout,
    QProgressBar, QStyledItemDelegate, QFileDialog, QMessageBox
)

from app.models.download_item import DownloadItem, DownloadStatus
from app.signals.signal_bus import signal_bus

log = logging.getLogger('app.queue')


class ProgressDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        if index.column() == 2:
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(int(index.data(Qt.UserRole)))
            bar.setTextVisible(True)
            bar.setFormat(f'{int(index.data(Qt.UserRole))}%')
            bar.resize(option.rect.size())
            painter.save()
            painter.translate(option.rect.topLeft())
            bar.render(painter, QPoint(0, 0))
            painter.restore()
        else:
            super().paint(painter, option, index)


STATUS_COLORS = {
    'Downloading': QColor(45, 125, 70, 40),
    'Paused': QColor(200, 180, 50, 40),
    'Completed': QColor(45, 125, 70, 20),
    'Error': QColor(200, 50, 50, 40),
    'Cancelled': QColor(120, 120, 120, 30),
}


class QueueWidget(QWidget):
    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.items: dict[str, DownloadItem] = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header_row = QHBoxLayout()
        title = QLabel('Download Queue & History')
        title.setStyleSheet('font-weight: bold; padding: 4px 0;')

        self.clear_btn = QPushButton('Clear Completed')
        self.clear_btn.clicked.connect(self._clear_completed)
        self.clear_all_btn = QPushButton('Clear All')
        self.clear_all_btn.clicked.connect(self._clear_all)

        header_row.addWidget(title)
        header_row.addStretch()
        header_row.addWidget(self.clear_btn)
        header_row.addWidget(self.clear_all_btn)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['Title', 'Status', 'Progress', 'Speed/ETA', 'Format', 'Output'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        self.table.setItemDelegateForColumn(2, ProgressDelegate())

        layout.addLayout(header_row)
        layout.addWidget(self.table, 1)

        signal_bus.progress_updated.connect(self._on_progress)
        signal_bus.download_completed.connect(self._on_completed)
        signal_bus.download_error.connect(self._on_error)
        signal_bus.download_cancelled.connect(self._on_cancelled)
        signal_bus.download_paused.connect(self._on_paused)

    def add_item(self, item: DownloadItem):
        self.items[item.uid] = item
        self._insert_row(item)
        signal_bus.queue_changed.emit()

    def _insert_row(self, item: DownloadItem):
        row = self.table.rowCount()
        self.table.insertRow(row)

        title_item = QTableWidgetItem(item.title or item.url[:60])
        title_item.setData(Qt.UserRole, item.uid)
        self.table.setItem(row, 0, title_item)
        self.table.setItem(row, 1, QTableWidgetItem(self._status_text(item.status)))
        pct_item = QTableWidgetItem()
        pct_item.setData(Qt.UserRole, int(item.progress))
        self.table.setItem(row, 2, pct_item)
        self.table.setItem(row, 3, QTableWidgetItem(''))
        self.table.setItem(row, 4, QTableWidgetItem(item.selected_format or 'best'))
        self._apply_row_color(row, item.status)
        self._set_output_cell(row, item)

    def _set_output_cell(self, row: int, item: DownloadItem, file_path: str = ''):
        output_widget = QWidget()
        output_layout = QHBoxLayout(output_widget)
        output_layout.setContentsMargins(2, 0, 2, 0)
        output_layout.setSpacing(2)

        display = file_path or item.output_path or item.output_dir or 'Downloads'
        path_label = QLabel(self._short_path(display))
        path_label.setStyleSheet('background: transparent;')

        folder_btn = QPushButton('...')
        folder_btn.setFixedWidth(28)
        folder_btn.setFixedHeight(22)
        folder_btn.setToolTip('Open file location')
        folder_btn.clicked.connect(lambda checked, u=item.uid: self._open_file_location(u))

        output_layout.addWidget(path_label, 1)
        output_layout.addWidget(folder_btn)
        self.table.setCellWidget(row, 5, output_widget)

    def _short_path(self, path: str) -> str:
        if not path:
            return 'Downloads'
        if len(path) > 30:
            return '...' + path[-27:]
        return path

    def _status_text(self, status: DownloadStatus) -> str:
        return {
            DownloadStatus.PENDING: 'Pending',
            DownloadStatus.EXTRACTING: 'Extracting',
            DownloadStatus.QUEUED: 'Queued',
            DownloadStatus.DOWNLOADING: 'Downloading',
            DownloadStatus.PAUSED: 'Paused',
            DownloadStatus.PROCESSING: 'Processing',
            DownloadStatus.COMPLETED: 'Completed',
            DownloadStatus.ERROR: 'Error',
            DownloadStatus.CANCELLED: 'Cancelled',
        }.get(status, 'Unknown')

    def _find_row(self, uid: str) -> int:
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).data(Qt.UserRole) == uid:
                return row
        return -1

    def _apply_row_color(self, row: int, status: DownloadStatus):
        text = self._status_text(status)
        for key in ('Downloading', 'Paused', 'Completed', 'Error', 'Cancelled'):
            if key in text:
                color = STATUS_COLORS.get(key)
                if color:
                    for col in range(self.table.columnCount()):
                        it = self.table.item(row, col)
                        if it:
                            it.setBackground(QBrush(color))
                break

    def _on_progress(self, uid: str, pct: float, speed: str, eta: str):
        row = self._find_row(uid)
        if row < 0:
            return
        self.table.item(row, 1).setText('Downloading' if pct < 100 else 'Processing')
        self.table.item(row, 3).setText(f'{speed}  {eta}')
        self.table.item(row, 2).setData(Qt.UserRole, int(pct))
        self.table.update(self.table.visualItemRect(self.table.item(row, 2)))
        if uid in self.items:
            self.items[uid].progress = pct
            self.items[uid].speed = speed
            self.items[uid].eta = eta
            if pct < 100:
                self.items[uid].status = DownloadStatus.DOWNLOADING

    def _on_completed(self, uid: str):
        row = self._find_row(uid)
        if row >= 0:
            self.table.item(row, 1).setText('Completed')
            self.table.item(row, 3).setText('')
            self.table.item(row, 2).setData(Qt.UserRole, 100)
            self._apply_row_color(row, DownloadStatus.COMPLETED)
            self._set_output_cell(row, self.items.get(uid))
        if uid in self.items:
            self.items[uid].status = DownloadStatus.COMPLETED
            self.items[uid].progress = 100

    def _on_error(self, uid: str, error: str):
        row = self._find_row(uid)
        if row >= 0:
            self.table.item(row, 1).setText('Error')
            self.table.item(row, 3).setText(error[:40])
            self._apply_row_color(row, DownloadStatus.ERROR)
        if uid in self.items:
            self.items[uid].status = DownloadStatus.ERROR
            self.items[uid].error_message = error

    def _on_cancelled(self, uid: str):
        row = self._find_row(uid)
        if row >= 0:
            self.table.item(row, 1).setText('Cancelled')
            self.table.item(row, 3).setText('')
            self._apply_row_color(row, DownloadStatus.CANCELLED)
        if uid in self.items:
            self.items[uid].status = DownloadStatus.CANCELLED

    def _on_paused(self, uid: str):
        row = self._find_row(uid)
        if row >= 0:
            self.table.item(row, 1).setText('Paused')
            self.table.item(row, 3).setText('')
            self._apply_row_color(row, DownloadStatus.PAUSED)
        if uid in self.items:
            self.items[uid].status = DownloadStatus.PAUSED

    def _open_file_location(self, uid: str):
        item = self.items.get(uid)
        if not item:
            return
        target = item.output_path or item.output_dir or os.path.expanduser('~')
        log.info('Opening file location: %s', target)
        try:
            if os.path.isfile(target):
                subprocess.Popen(['explorer', '/select,', os.path.normpath(target)])
            elif os.path.isdir(target):
                subprocess.Popen(['explorer', os.path.normpath(target)])
            else:
                parent = os.path.dirname(target) if target else ''
                if parent and os.path.isdir(parent):
                    subprocess.Popen(['explorer', os.path.normpath(parent)])
                elif item.output_dir and os.path.isdir(item.output_dir):
                    subprocess.Popen(['explorer', os.path.normpath(item.output_dir)])
                else:
                    fallback_dir = os.path.expanduser('~')
                    subprocess.Popen(['explorer', os.path.normpath(fallback_dir)])
        except Exception as e:
            log.error('Failed to open file location: %s', e)

    def _show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return
        row = item.row()
        uid = self.table.item(row, 0).data(Qt.UserRole)
        if not uid or uid not in self.items:
            return
        dl_item = self.items[uid]
        status = dl_item.status

        menu = QMenu(self)

        if status == DownloadStatus.DOWNLOADING:
            pause_act = QAction('Pause', self)
            pause_act.triggered.connect(lambda: self._pause(uid))
            menu.addAction(pause_act)

            cancel_act = QAction('Cancel', self)
            cancel_act.triggered.connect(lambda: self._cancel(uid))
            menu.addAction(cancel_act)

            menu.addSeparator()

        elif status == DownloadStatus.PAUSED:
            resume_act = QAction('Resume', self)
            resume_act.triggered.connect(lambda: self._resume(uid))
            menu.addAction(resume_act)

            cancel_act = QAction('Cancel', self)
            cancel_act.triggered.connect(lambda: self._cancel(uid))
            menu.addAction(cancel_act)

            menu.addSeparator()

        elif status in (DownloadStatus.QUEUED, DownloadStatus.PENDING):
            cancel_act = QAction('Cancel', self)
            cancel_act.triggered.connect(lambda: self._cancel(uid))
            menu.addAction(cancel_act)

            menu.addSeparator()

        elif status == DownloadStatus.ERROR:
            retry_act = QAction('Retry', self)
            retry_act.triggered.connect(lambda: self._retry(uid))
            menu.addAction(retry_act)

            menu.addSeparator()

        elif status == DownloadStatus.COMPLETED:
            open_act = QAction('Open File Location', self)
            open_act.triggered.connect(lambda: self._open_file_location(uid))
            menu.addAction(open_act)
            menu.addSeparator()

        elif status == DownloadStatus.CANCELLED:
            retry_act = QAction('Retry', self)
            retry_act.triggered.connect(lambda: self._retry(uid))
            menu.addAction(retry_act)

            menu.addSeparator()

        change_dir_act = QAction('Change Output Folder...', self)
        change_dir_act.triggered.connect(lambda: self._change_output_dir(uid))
        menu.addAction(change_dir_act)

        delete_act = QAction('Delete from List', self)
        delete_act.triggered.connect(lambda: self._delete(uid))
        menu.addAction(delete_act)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _pause(self, uid: str):
        log.info('Pause requested: %s', uid)
        if self.main_window:
            self.main_window.pause_download(uid)

    def _resume(self, uid: str):
        log.info('Resume requested: %s', uid)
        if self.main_window:
            self.main_window.resume_download(uid)

    def _cancel(self, uid: str):
        log.info('Cancel requested: %s', uid)
        if self.main_window:
            self.main_window.cancel_download(uid)

    def _retry(self, uid: str):
        log.info('Retry requested: %s', uid)
        item = self.items.get(uid)
        if item:
            item.status = DownloadStatus.QUEUED
            item.progress = 0
            item.error_message = ''
            row = self._find_row(uid)
            if row >= 0:
                self.table.item(row, 1).setText('Queued')
                self.table.item(row, 2).setData(Qt.UserRole, 0)
                self.table.item(row, 3).setText('')
                self._apply_row_color(row, DownloadStatus.QUEUED)
            if self.main_window:
                self.main_window._pending_items.append(item)
                self.main_window._process_queue()

    def _delete(self, uid: str):
        log.info('Delete from list: %s', uid)
        if self.main_window:
            self.main_window.cancel_download(uid)
        self.items.pop(uid, None)
        row = self._find_row(uid)
        if row >= 0:
            self.table.removeRow(row)

    def _change_output_dir(self, uid: str):
        item = self.items.get(uid)
        if not item:
            return
        start_dir = item.output_dir or os.path.expanduser('~')
        new_dir = QFileDialog.getExistingDirectory(self, 'Select Output Folder', start_dir)
        if new_dir:
            item.output_dir = new_dir
            if self.main_window:
                self.main_window.change_output_dir(uid, new_dir)
            row = self._find_row(uid)
            if row >= 0:
                self._set_output_cell(row, item)
            log.info('Output dir changed to: %s', new_dir)

    def _clear_completed(self):
        to_remove = []
        for row in range(self.table.rowCount()):
            status = self.table.item(row, 1).text()
            if status in ('Completed', 'Cancelled', 'Error'):
                uid = self.table.item(row, 0).data(Qt.UserRole)
                to_remove.append((row, uid))
        for row, uid in reversed(to_remove):
            self.table.removeRow(row)
            self.items.pop(uid, None)

    def _clear_all(self):
        reply = QMessageBox.question(
            self, 'Clear All',
            'Remove all items from the queue list?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self.main_window:
                self.main_window.cancel_all_downloads()
            self.table.setRowCount(0)
            self.items.clear()
            signal_bus.queue_changed.emit()
