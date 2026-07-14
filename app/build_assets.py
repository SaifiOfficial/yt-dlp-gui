import os
import sys
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPixmap, QColor, QPen, QBrush, QPainterPath

def draw_link(painter, size):
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor("#a78bfa"), 2, Qt.SolidLine, Qt.RoundCap))
    painter.setBrush(Qt.NoBrush)
    
    # interlock chain links
    painter.save()
    painter.translate(size / 2, size / 2)
    painter.rotate(45)
    
    # Link 1
    painter.drawRoundedRect(QRectF(-size*0.35, -size*0.12, size*0.45, size*0.24), size*0.12, size*0.12)
    # Link 2
    painter.drawRoundedRect(QRectF(-size*0.1, -size*0.12, size*0.45, size*0.24), size*0.12, size*0.12)
    painter.restore()

def draw_search(painter, size):
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor("#ffffff"), 2, Qt.SolidLine, Qt.RoundCap))
    painter.setBrush(Qt.NoBrush)
    
    r = size * 0.25
    cx, cy = size * 0.42, size * 0.42
    painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
    painter.drawLine(cx + r * 0.7, cy + r * 0.7, size * 0.8, size * 0.8)

def draw_download(painter, size):
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor("#ffffff"), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.setBrush(Qt.NoBrush)
    
    cx = size / 2
    painter.drawLine(cx, size * 0.15, cx, size * 0.65)
    painter.drawLine(cx - size * 0.22, size * 0.43, cx, size * 0.65)
    painter.drawLine(cx + size * 0.22, size * 0.43, cx, size * 0.65)
    painter.drawLine(size * 0.22, size * 0.8, size * 0.78, size * 0.8)

def draw_queue(painter, size):
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor("#ffffff"), 2, Qt.SolidLine, Qt.RoundCap))
    painter.setBrush(Qt.NoBrush)
    
    x1, x2 = size * 0.22, size * 0.78
    painter.drawLine(x1, size * 0.3, x2, size * 0.3)
    painter.drawLine(x1, size * 0.5, x2, size * 0.5)
    painter.drawLine(x1, size * 0.7, x2, size * 0.7)

def draw_settings(painter, size):
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor("#94a3b8"), 1.8, Qt.SolidLine, Qt.RoundCap))
    painter.setBrush(QBrush(QColor("#94a3b8")))
    
    # Slider 1
    painter.drawLine(size * 0.2, size * 0.35, size * 0.8, size * 0.35)
    painter.drawEllipse(QRectF(size * 0.35 - 2.5, size * 0.35 - 2.5, 5, 5))
    
    # Slider 2
    painter.drawLine(size * 0.2, size * 0.65, size * 0.8, size * 0.65)
    painter.drawEllipse(QRectF(size * 0.65 - 2.5, size * 0.65 - 2.5, 5, 5))

def draw_clapperboard(painter, size):
    painter.setRenderHint(QPainter.Antialiasing)
    
    bg_color = QColor("#475569")
    accent_color = QColor("#94a3b8")
    white = QColor("#ffffff")
    
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(bg_color))
    
    w, h = size * 0.65, size * 0.48
    x, y = size * 0.175, size * 0.32
    painter.drawRoundedRect(x, y, w, h, 8, 8)
    
    # stripes strip on top
    painter.setBrush(QBrush(accent_color))
    painter.drawRect(x, y, w, h * 0.2)
    
    painter.setPen(QPen(white, 2))
    painter.drawLine(x + w * 0.2, y, x + w * 0.3, y + h * 0.2)
    painter.drawLine(x + w * 0.5, y, x + w * 0.6, y + h * 0.2)
    painter.drawLine(x + w * 0.8, y, x + w * 0.9, y + h * 0.2)
    
    # small play triangle
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(white))
    path = QPainterPath()
    cx, cy = size / 2, y + h * 0.62
    ps = size * 0.08
    path.moveTo(cx - ps * 0.5, cy - ps)
    path.lineTo(cx + ps, cy)
    path.lineTo(cx - ps * 0.5, cy + ps)
    path.closeSubpath()
    painter.drawPath(path)

def draw_check(painter, size):
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor("#22c55e"), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.setBrush(Qt.NoBrush)
    
    painter.drawLine(size * 0.25, size * 0.5, size * 0.45, size * 0.7)
    painter.drawLine(size * 0.45, size * 0.7, size * 0.8, size * 0.35)

def draw_browser(painter, size):
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor("#ffffff"), 2, Qt.SolidLine, Qt.RoundCap))
    painter.setBrush(Qt.NoBrush)
    
    cx, cy = size / 2, size / 2
    r = size * 0.35
    painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
    painter.drawLine(cx - r, cy, cx + r, cy)
    painter.drawEllipse(QRectF(cx - r * 0.7, cy - r * 0.3, r * 1.4, r * 0.6))
    painter.drawLine(cx, cy - r, cx, cy + r)

def build_all():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
        
    icons_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "resources", "icons")
    os.makedirs(icons_dir, exist_ok=True)
    
    targets = [
        ("link.png", draw_link, 24),
        ("search.png", draw_search, 24),
        ("download.png", draw_download, 24),
        ("queue.png", draw_queue, 24),
        ("settings.png", draw_settings, 24),
        ("clapperboard.png", draw_clapperboard, 128),
        ("check.png", draw_check, 24),
        ("browser.png", draw_browser, 24),
    ]
    
    for filename, draw_func, size in targets:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        draw_func(painter, size)
        painter.end()
        
        path = os.path.join(icons_dir, filename)
        pixmap.save(path, "PNG")
        print(f"Saved {path}")

if __name__ == "__main__":
    build_all()
