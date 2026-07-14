from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF


def _make_icon_pixmap(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    m = max(1, size // 20)
    painter.setBrush(QBrush(QColor(45, 125, 70)))
    painter.setPen(QPen(QColor(35, 100, 55), max(1, size // 40)))
    painter.drawRoundedRect(m, m, size - m * 2, size - m * 2, size // 5, size // 5)

    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(QColor(255, 255, 255)))

    cx = size // 2
    sw = max(2, size // 10)
    shaft_left = cx - sw // 2
    shaft_top = size * 7 // 24
    shaft_bot = size * 13 // 24
    painter.drawRect(shaft_left, shaft_top, sw, shaft_bot - shaft_top)

    head_top = size * 13 // 24
    head_bot = size * 11 // 16
    hw = size // 4
    painter.drawPolygon(QPolygonF([
        QPointF(cx - hw, head_top),
        QPointF(cx + hw, head_top),
        QPointF(cx, head_bot),
    ]))

    painter.end()
    return pixmap


def _find_ico() -> str:
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
        base = os.path.join(base, '..')
    path = os.path.join(base, 'resources', 'icon.ico')
    return path if os.path.isfile(path) else ''


_icon: QIcon | None = None


def get_app_icon() -> QIcon:
    global _icon
    if _icon is None:
        ico = _find_ico()
        if ico:
            _icon = QIcon(ico)
        else:
            icon = QIcon(_make_icon_pixmap(64))
            icon.addPixmap(_make_icon_pixmap(32))
            icon.addPixmap(_make_icon_pixmap(48))
            icon.addPixmap(_make_icon_pixmap(256))
            _icon = icon
    return _icon
