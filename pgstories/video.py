"""Fontes de vídeo: webcam (tempo real) ou arquivo de vídeo."""

from __future__ import annotations

import sys
import time

import cv2
import numpy as np


def _camera_backends() -> list[int]:
    if sys.platform.startswith("win"):
        # DirectShow abre a câmera bem mais rápido que o Media Foundation no Windows.
        return [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
    if sys.platform.startswith("linux"):
        return [cv2.CAP_V4L2, cv2.CAP_ANY]
    if sys.platform == "darwin":
        return [cv2.CAP_AVFOUNDATION, cv2.CAP_ANY]
    return [cv2.CAP_ANY]


class VideoSource:
    """Lê quadros da webcam (``source`` = índice) ou de um arquivo (``source`` = caminho).

    Arquivos são reproduzidos em loop. Na webcam o quadro é espelhado por
    padrão (efeito "selfie", como nos stories).
    """

    def __init__(self, source: int | str, mirror: bool | None = None,
                 size: tuple[int, int] | None = (1280, 720)) -> None:
        self.source = source
        self.is_camera = isinstance(source, int)
        self.mirror = self.is_camera if mirror is None else mirror
        self.size = size
        self.cap: cv2.VideoCapture | None = None
        self.fps = 30.0
        self.last_frame: np.ndarray | None = None
        self._frame_times: list[float] = []

    def open(self) -> bool:
        if self.is_camera:
            for backend in _camera_backends():
                cap = cv2.VideoCapture(self.source, backend)
                if cap.isOpened():
                    if self.size:
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.size[0])
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.size[1])
                    ok, frame = cap.read()
                    if ok and frame is not None:
                        self.cap = cap
                        self.last_frame = frame
                        return True
                cap.release()
            return False
        cap = cv2.VideoCapture(str(self.source))
        if not cap.isOpened():
            return False
        fps = cap.get(cv2.CAP_PROP_FPS)
        self.fps = fps if 1 <= fps <= 240 else 30.0
        self.cap = cap
        return True

    @property
    def is_open(self) -> bool:
        return self.cap is not None and self.cap.isOpened()

    def read(self) -> np.ndarray | None:
        if not self.is_open:
            return None
        ok, frame = self.cap.read()
        if (not ok or frame is None) and not self.is_camera:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # volta ao início (loop)
            ok, frame = self.cap.read()
        if not ok or frame is None:
            return None
        if frame.ndim == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        elif frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        if self.mirror:
            frame = cv2.flip(frame, 1)
        self.last_frame = frame
        now = time.perf_counter()
        self._frame_times = [t for t in self._frame_times if now - t < 1.0] + [now]
        return frame

    @property
    def measured_fps(self) -> float:
        return float(len(self._frame_times))

    def frame_interval_ms(self) -> int:
        return 15 if self.is_camera else max(5, int(1000 / self.fps))

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()
        self.cap = None
