"""Área de exibição da imagem: mantém a proporção e converte cliques para
coordenadas relativas da imagem (0–1), usadas para posicionar os stickers."""

from __future__ import annotations

import cv2
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget


def bgr_to_qimage(img: np.ndarray) -> QImage:
    img = np.ascontiguousarray(img)
    h, w = img.shape[:2]
    return QImage(img.data, w, h, img.strides[0], QImage.Format.Format_BGR888).copy()


def bgra_to_qimage(img: np.ndarray) -> QImage:
    rgba = np.ascontiguousarray(cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA))
    h, w = rgba.shape[:2]
    return QImage(rgba.data, w, h, rgba.strides[0], QImage.Format.Format_RGBA8888).copy()


class ImageView(QWidget):
    pressed = Signal(float, float, int)  # rx, ry, botão (Qt.MouseButton como int)
    dragged = Signal(float, float)
    released = Signal(float, float)
    fileDropped = Signal(str)

    PLACEHOLDER = ("Abra uma foto (Ctrl+O), escolha uma foto de exemplo\n"
                   "ou inicie a webcam (Ctrl+K).\n\nVocê também pode arrastar uma imagem para cá.")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(480, 360)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self._image: QImage | None = None
        self._ghost: QImage | None = None
        self._ghost_rel_width = 0.25
        self._ghost_angle = 0.0
        self._mouse: QPointF | None = None
        self._dragging = False
        self.overlay_text = ""

    # --- imagem -----------------------------------------------------------
    def set_image(self, img_bgr: np.ndarray | None) -> None:
        self._image = None if img_bgr is None else bgr_to_qimage(img_bgr)
        self.update()

    def has_image(self) -> bool:
        return self._image is not None

    def set_ghost(self, sticker_bgra: np.ndarray | None, rel_width: float = 0.25, angle: float = 0.0) -> None:
        """Prévia semitransparente do sticker que acompanha o mouse."""
        self._ghost = None if sticker_bgra is None else bgra_to_qimage(sticker_bgra)
        self._ghost_rel_width = rel_width
        self._ghost_angle = angle
        self.setCursor(Qt.CursorShape.CrossCursor if self._ghost is not None else Qt.CursorShape.ArrowCursor)
        self.update()

    def image_rect(self) -> QRectF:
        if self._image is None:
            return QRectF()
        iw, ih = self._image.width(), self._image.height()
        scale = min(self.width() / iw, self.height() / ih)
        w, h = iw * scale, ih * scale
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def _relative(self, pos: QPointF) -> tuple[float, float] | None:
        r = self.image_rect()
        if r.isEmpty() or not r.contains(pos):
            return None
        return (pos.x() - r.x()) / r.width(), (pos.y() - r.y()) / r.height()

    # --- desenho ------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802 (nome do Qt)
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#120e16"))
        if self._image is None:
            p.setPen(QColor("#9a90a4"))
            f = QFont(self.font())
            f.setPointSizeF(f.pointSizeF() * 1.2)
            p.setFont(f)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.PLACEHOLDER)
            return
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        r = self.image_rect()
        p.drawImage(r, self._image)
        if self._ghost is not None and self._mouse is not None and r.contains(self._mouse) \
                and not self._dragging:
            gw = self._ghost_rel_width * r.width()
            gh = gw * self._ghost.height() / self._ghost.width()
            p.save()
            p.setOpacity(0.6)
            p.translate(self._mouse)
            p.rotate(-self._ghost_angle)
            p.drawImage(QRectF(-gw / 2, -gh / 2, gw, gh), self._ghost)
            p.restore()
        if self.overlay_text:
            p.setPen(QPen(QColor(255, 255, 255, 220)))
            p.fillRect(QRectF(r.x() + 8, r.y() + 8, 230, 26), QColor(0, 0, 0, 140))
            p.drawText(QRectF(r.x() + 14, r.y() + 8, 220, 26), Qt.AlignmentFlag.AlignVCenter,
                       self.overlay_text)

    # --- mouse --------------------------------------------------------------
    def mousePressEvent(self, event) -> None:  # noqa: N802
        rel = self._relative(event.position())
        if rel is not None:
            self._dragging = event.button() == Qt.MouseButton.LeftButton
            self.pressed.emit(rel[0], rel[1], event.button().value)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        self._mouse = event.position()
        if self._dragging:
            r = self.image_rect()
            if not r.isEmpty():
                rx = min(max((self._mouse.x() - r.x()) / r.width(), 0.0), 1.0)
                ry = min(max((self._mouse.y() - r.y()) / r.height(), 0.0), 1.0)
                self.dragged.emit(rx, ry)
        if self._ghost is not None:
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._dragging:
            self._dragging = False
            rel = self._relative(event.position()) or (0.0, 0.0)
            self.released.emit(rel[0], rel[1])

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._mouse = None
        self.update()

    # --- arrastar arquivo -----------------------------------------------------
    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.fileDropped.emit(url.toLocalFile())
                break
