from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QClipboard
from PySide6.QtWidgets import (
    QHBoxLayout, QLineEdit, QPushButton, QWidget, QApplication
)


class UrlBar(QWidget):
    fetch_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        from PySide6.QtGui import QIcon
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText('Paste a URL and press Enter, or click Fetch...')
        self.url_input.returnPressed.connect(self._on_fetch)
        
        link_icon = QIcon(os.path.join(base_dir, 'resources', 'icons', 'link.png'))
        self.url_input.addAction(link_icon, QLineEdit.LeadingPosition)

        self.fetch_btn = QPushButton('Fetch Info')
        self.fetch_btn.clicked.connect(self._on_fetch)
        self.fetch_btn.setObjectName("fetch_btn")
        
        search_icon = QIcon(os.path.join(base_dir, 'resources', 'icons', 'search.png'))
        self.fetch_btn.setIcon(search_icon)

        layout.addWidget(self.url_input, 1)
        layout.addWidget(self.fetch_btn)

    def _on_fetch(self):
        url = self.url_input.text().strip()
        if url:
            self.fetch_requested.emit(url)
