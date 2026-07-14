from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QHeaderView, QTreeWidget, QTreeWidgetItem, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
)

from app.models.download_item import DownloadItem, DownloadStatus


class PlaylistPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_item: DownloadItem | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header_row = QHBoxLayout()
        self.header = QLabel('Playlist / Channel')
        self.header.setStyleSheet('font-weight: bold; padding: 4px 0;')

        self.select_all_btn = QPushButton('Select All')
        self.select_all_btn.clicked.connect(self._select_all)
        self.select_none_btn = QPushButton('Select None')
        self.select_none_btn.clicked.connect(self._select_none)
        header_row.addWidget(self.header)
        header_row.addStretch()
        header_row.addWidget(self.select_all_btn)
        header_row.addWidget(self.select_none_btn)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['', 'Title', 'Duration'])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree.setRootIsDecorated(False)

        layout.addLayout(header_row)
        layout.addWidget(self.tree, 1)

    def display_playlist(self, item: DownloadItem):
        self._current_item = item
        self.tree.clear()
        if not item.playlist_entries:
            self.hide()
            return

        self.show()
        self.header.setText(f'{len(item.playlist_entries)} items')

        for entry in item.playlist_entries:
            widget_item = QTreeWidgetItem(self.tree)
            cb = QCheckBox()
            cb.setChecked(entry.selected)
            cb.stateChanged.connect(lambda state, e=entry: setattr(e, 'selected', bool(state)))
            self.tree.setItemWidget(widget_item, 0, cb)
            widget_item.setText(1, entry.title)
            if entry.duration:
                m, s = divmod(int(entry.duration), 60)
                widget_item.setText(2, f'{m}:{s:02d}')

    def clear(self):
        self._current_item = None
        self.tree.clear()
        self.hide()

    def _select_all(self):
        for i in range(self.tree.topLevelItemCount()):
            w = self.tree.topLevelItem(i)
            cb = self.tree.itemWidget(w, 0)
            if isinstance(cb, QCheckBox):
                cb.setChecked(True)

    def _select_none(self):
        for i in range(self.tree.topLevelItemCount()):
            w = self.tree.topLevelItem(i)
            cb = self.tree.itemWidget(w, 0)
            if isinstance(cb, QCheckBox):
                cb.setChecked(False)
