"""Ícones simples desenhados com QPainter (claros, para o tema escuro)."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

LIGHT = QColor("#f2e8f8")
PINK = QColor("#ff5c93")


def _canvas(size: int = 40) -> tuple[QPixmap, QPainter]:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    return pix, p


def play_icon() -> QIcon:
    pix, p = _canvas()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(PINK)
    p.drawEllipse(QRectF(3, 3, 34, 34))
    p.setBrush(LIGHT)
    p.drawPolygon(QPolygonF([QPointF(15, 11), QPointF(30, 20), QPointF(15, 29)]))
    p.end()
    return QIcon(pix)


def stop_icon() -> QIcon:
    pix, p = _canvas()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(PINK)
    p.drawEllipse(QRectF(3, 3, 34, 34))
    p.setBrush(LIGHT)
    p.drawRoundedRect(QRectF(13, 13, 14, 14), 2, 2)
    p.end()
    return QIcon(pix)


def undo_icon() -> QIcon:
    pix, p = _canvas()
    pen = QPen(LIGHT, 3.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    path = QPainterPath(QPointF(12, 17))
    path.cubicTo(QPointF(22, 9), QPointF(36, 14), QPointF(32, 26))
    path.cubicTo(QPointF(30, 31), QPointF(25, 33), QPointF(20, 33))
    p.drawPath(path)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(LIGHT)
    p.drawPolygon(QPolygonF([QPointF(5, 17), QPointF(15, 9), QPointF(16, 24)]))
    p.end()
    return QIcon(pix)


def badge(pixmap: QPixmap, text: str) -> QPixmap:
    """Desenha uma etiqueta pequena (ex.: "anim") no canto do ícone."""
    out = QPixmap(pixmap)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    f = p.font()
    f.setPixelSize(11)
    f.setBold(True)
    p.setFont(f)
    w = p.fontMetrics().horizontalAdvance(text) + 8
    rect = QRectF(out.width() - w - 1, out.height() - 16, w, 15)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(PINK)
    p.drawRoundedRect(rect, 7, 7)
    p.setPen(QColor("white"))
    p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
    p.end()
    return out
