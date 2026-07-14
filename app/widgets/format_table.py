from __future__ import annotations

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QFont
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QHeaderView, QLabel, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QWidget, QVBoxLayout
)

from app.models.download_item import DownloadItem, FormatInfo, FormatType


FILTER_ALL = 'All Formats'
FILTER_VIDEO_MP4 = 'Video: MP4'
FILTER_VIDEO_MKV = 'Video: MKV'
FILTER_VIDEO_MOV = 'Video: MOV'
FILTER_VIDEO_WEBM = 'Video: WEBM'
FILTER_AUDIO_MP3 = 'Audio: MP3'
FILTER_AUDIO_WAV = 'Audio: WAV'

FILTERS = [
    FILTER_ALL,
    FILTER_VIDEO_MP4,
    FILTER_VIDEO_MKV,
    FILTER_VIDEO_MOV,
    FILTER_VIDEO_WEBM,
    FILTER_AUDIO_MP3,
    FILTER_AUDIO_WAV,
]

VIDEO_CONTAINERS = {'mp4', 'mkv', 'mov', 'webm'}
AUDIO_CONTAINERS = {'mp3', 'wav', 'm4a', 'opus', 'aac', 'ogg'}


def _matches_filter(f: FormatInfo, filter_name: str) -> bool:
    if filter_name == FILTER_ALL:
        return True
    if filter_name == FILTER_VIDEO_MP4:
        return f.ext == 'mp4' and f.fmt_type in (FormatType.VIDEO_AUDIO, FormatType.VIDEO_ONLY)
    if filter_name == FILTER_VIDEO_MKV:
        return f.ext == 'mkv' and f.fmt_type in (FormatType.VIDEO_AUDIO, FormatType.VIDEO_ONLY)
    if filter_name == FILTER_VIDEO_MOV:
        return f.ext == 'mov' and f.fmt_type in (FormatType.VIDEO_AUDIO, FormatType.VIDEO_ONLY)
    if filter_name == FILTER_VIDEO_WEBM:
        return f.ext == 'webm' and f.fmt_type in (FormatType.VIDEO_AUDIO, FormatType.VIDEO_ONLY)
    if filter_name == FILTER_AUDIO_MP3:
        return f.fmt_type == FormatType.AUDIO_ONLY
    if filter_name == FILTER_AUDIO_WAV:
        return f.fmt_type == FormatType.AUDIO_ONLY
    return True


def _filter_and_sort_formats(formats: list[FormatInfo], filter_name: str = FILTER_ALL) -> list[FormatInfo]:
    seen = set()
    clean = []
    for f in formats:
        if f.format_id.startswith('sb') or f.format_id in ('none', ''):
            continue
        if f.format_id in seen:
            continue
        seen.add(f.format_id)
        if not _matches_filter(f, filter_name):
            continue
        clean.append(f)

    def sort_key(f: FormatInfo):
        container_rank = 0
        if f.ext == 'mp4':
            container_rank = 0
        elif f.ext == 'mkv':
            container_rank = 1
        elif f.ext == 'mov':
            container_rank = 2
        elif f.ext == 'webm':
            container_rank = 3
        elif f.ext == 'm4a':
            container_rank = 4
        elif f.ext == 'mp3':
            container_rank = 5
        elif f.ext == 'wav':
            container_rank = 6
        else:
            container_rank = 7

        if f.fmt_type == FormatType.VIDEO_AUDIO:
            type_rank = 0
        elif f.fmt_type == FormatType.VIDEO_ONLY:
            type_rank = 1
        else:
            type_rank = 2

        res = 0
        if f.resolution:
            m = re.search(r'(\d+)', f.resolution)
            if m:
                res = int(m.group(1))
        return (container_rank, type_rank, -res)

    clean.sort(key=sort_key)
    return clean


def _container_label(ext: str) -> str:
    return ext.upper()


def _section_bg(ext: str) -> QColor:
    if ext in ('mp4', 'm4a'):
        return QColor(45, 125, 70, 40)
    if ext == 'webm':
        return QColor(55, 100, 140, 40)
    if ext == 'mkv':
        return QColor(125, 90, 45, 40)
    if ext == 'mov':
        return QColor(140, 70, 55, 40)
    if ext in ('mp3', 'wav'):
        return QColor(100, 80, 140, 40)
    return QColor(60, 60, 60, 40)


class FormatTable(QWidget):
    format_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_item: DownloadItem | None = None
        self._all_formats: list[FormatInfo] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.header = QLabel('Enter a URL above and press Enter to see available formats')
        self.header.setStyleSheet('font-weight: bold; padding: 4px 0;')
        layout.addWidget(self.header)

        # Custom Placeholder Card
        self.placeholder_widget = QWidget()
        placeholder_layout = QVBoxLayout(self.placeholder_widget)
        placeholder_layout.setAlignment(Qt.AlignCenter)
        placeholder_layout.setSpacing(12)
        placeholder_layout.setContentsMargins(20, 40, 20, 40)
        
        self.placeholder_icon = QLabel()
        from PySide6.QtGui import QPixmap
        import os
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'resources', 'icons', 'clapperboard.png')
        self.placeholder_icon.setPixmap(QPixmap(icon_path))
        self.placeholder_icon.setAlignment(Qt.AlignCenter)
        placeholder_layout.addWidget(self.placeholder_icon)
        
        self.placeholder_title = QLabel("No formats to display")
        self.placeholder_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #f8fafc;")
        self.placeholder_title.setAlignment(Qt.AlignCenter)
        placeholder_layout.addWidget(self.placeholder_title)
        
        self.placeholder_subtext = QLabel("Fetch information from a URL to see available formats.")
        self.placeholder_subtext.setStyleSheet("font-size: 13px; color: #64748b;")
        self.placeholder_subtext.setAlignment(Qt.AlignCenter)
        placeholder_layout.addWidget(self.placeholder_subtext)
        
        layout.addWidget(self.placeholder_widget, 1)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(['Type', 'Resolution', 'Format', 'Size'])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(self.table, 1)
        self.table.hide()

    def display_formats(self, item: DownloadItem):
        self._current_item = item
        self._all_formats = item.formats
        self._apply_filter(FILTER_ALL)

    def set_filter(self, filter_name: str):
        self._apply_filter(filter_name)

    def _apply_filter(self, filter_name: str = FILTER_ALL):
        self.table.setRowCount(0)
        if not self._all_formats:
            self.header.setText(f'{self._current_item.title}  \u2014  no formats available' if self._current_item else 'No formats')
            self.placeholder_widget.show()
            self.table.hide()
            return
        self.placeholder_widget.hide()
        self.table.show()
        filtered = _filter_and_sort_formats(self._all_formats, filter_name)

        groups: dict[str, list[FormatInfo]] = {}
        for f in filtered:
            groups.setdefault(f.ext, []).append(f)

        total = len(filtered)
        detail = ', '.join(f'{len(v)} {_container_label(k)}' for k, v in groups.items())
        self.header.setText(
            f'{self._current_item.title}  \u2014  {total} format{"s" if total != 1 else ""} ({detail})'
        )

        for ext in ('mp4', 'mkv', 'mov', 'webm', 'm4a', 'mp3', 'wav', 'opus', 'aac', 'ogg'):
            entries = groups.pop(ext, None)
            if not entries:
                continue
            self._add_container_section(ext, entries)

        for ext, entries in groups.items():
            self._add_container_section(ext, entries)

        if self.table.rowCount() > 0:
            self.table.selectRow(0)

    def _add_container_section(self, ext: str, entries: list[FormatInfo]):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setSpan(row, 0, 1, 4)
        label = _container_label(ext)
        section_item = QTableWidgetItem(f'  {label}')
        section_font = QFont()
        section_font.setBold(True)
        section_item.setFont(section_font)
        section_item.setFlags(Qt.ItemIsEnabled)
        section_item.setBackground(QBrush(QColor(60, 60, 60)))
        self.table.setItem(row, 0, section_item)

        for f in entries:
            row = self.table.rowCount()
            self.table.insertRow(row)
            type_str = {
                FormatType.VIDEO_AUDIO: 'V+A',
                FormatType.VIDEO_ONLY: 'V',
                FormatType.AUDIO_ONLY: 'A',
                FormatType.OTHER: '?',
            }.get(f.fmt_type, '?')

            fmt_item = QTableWidgetItem(type_str)
            fmt_item.setData(Qt.UserRole, f.format_id)
            codec = (f.codec or '').lower()
            aliases = []
            if 'avc' in codec or 'h264' in codec:
                aliases.extend(('h264', 'vcodec:h264'))
            if 'hevc' in codec or 'h265' in codec:
                aliases.extend(('h265', 'hevc', 'vcodec:h265'))
            if 'av01' in codec or 'av1' in codec:
                aliases.extend(('av1', 'vcodec:av1'))
            if 'vp9' in codec or 'vp09' in codec:
                aliases.extend(('vp9', 'vcodec:vp9'))
            search_terms = ' '.join((
                f.format_id, f.ext, f.resolution, f.filesize, f.tbr,
                f.codec or '', f.note or '', *aliases,
            )).lower()
            fmt_item.setData(Qt.UserRole + 1, search_terms)
            self.table.setItem(row, 0, fmt_item)
            self.table.setItem(row, 1, QTableWidgetItem(f.resolution))
            self.table.setItem(row, 2, QTableWidgetItem(f.ext.upper()))
            size_str = f.filesize or (f.tbr + ' (tbr)' if f.tbr else '')
            self.table.setItem(row, 3, QTableWidgetItem(size_str))

            bg = _section_bg(ext)
            brush = QBrush(bg)
            for col in range(4):
                self.table.item(row, col).setBackground(brush)

    def clear(self):
        self._current_item = None
        self._all_formats = []
        self.table.setRowCount(0)
        self.header.setText('Enter a URL above and press Enter to see available formats')
        self.placeholder_widget.show()
        self.table.hide()

    def set_search_filter(self, text: str):
        text = text.strip().lower()
        if not text:
            for row in range(self.table.rowCount()):
                self.table.setRowHidden(row, False)
            return

        last_section_row = -1
        section_has_matches = False
        
        for row in range(self.table.rowCount()):
            is_section = self.table.columnSpan(row, 0) > 1
            if is_section:
                if last_section_row != -1:
                    self.table.setRowHidden(last_section_row, not section_has_matches)
                last_section_row = row
                section_has_matches = False
                self.table.setRowHidden(row, False)
            else:
                match = False
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    searchable = item.data(Qt.UserRole + 1) if item else ''
                    if item and (text in item.text().lower() or text in (searchable or '')):
                        match = True
                        break
                self.table.setRowHidden(row, not match)
                if match:
                    section_has_matches = True
                    
        if last_section_row != -1:
            self.table.setRowHidden(last_section_row, not section_has_matches)

    def _on_selection_changed(self):
        rows = self.table.selectedItems()
        if not rows:
            return
        row = rows[0].row()
        item = self.table.item(row, 0)
        if item:
            fmt_id = item.data(Qt.UserRole) or item.text()
            self.format_selected.emit(fmt_id)
