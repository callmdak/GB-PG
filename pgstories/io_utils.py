"""Leitura e escrita de imagens com suporte a caminhos com acentos.

``cv2.imread``/``cv2.imwrite`` falham no Windows quando o caminho tem
caracteres fora do ASCII (ex.: "Área de Trabalho"). Por isso lemos os bytes
com NumPy e decodificamos/codificamos com ``cv2.imdecode``/``cv2.imencode``.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

IMAGE_FILTER = "Imagens (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)"
VIDEO_FILTER = "Vídeos (*.mp4 *.avi *.mov *.mkv *.webm *.m4v)"

# Fotos muito grandes deixam a prévia lenta; limitamos o maior lado.
MAX_WORKING_SIDE = 1920


def imread(path: str | Path, flags: int = cv2.IMREAD_COLOR) -> np.ndarray | None:
    """Lê uma imagem do disco. Retorna ``None`` se não for possível."""
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
    except OSError:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, flags)


def imwrite(path: str | Path, image: np.ndarray) -> bool:
    """Salva uma imagem; o formato vem da extensão (padrão: .png)."""
    path = Path(path)
    ext = path.suffix.lower() or ".png"
    if ext not in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}:
        path = path.with_suffix(".png")
        ext = ".png"
    params: list[int] = []
    if ext in {".jpg", ".jpeg"}:
        params = [cv2.IMWRITE_JPEG_QUALITY, 95]
    ok, buffer = cv2.imencode(ext, image, params)
    if not ok:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer.tofile(str(path))
    return True


def limit_size(image: np.ndarray, max_side: int = MAX_WORKING_SIDE) -> tuple[np.ndarray, bool]:
    """Reduz a imagem se o maior lado passar de ``max_side``."""
    h, w = image.shape[:2]
    side = max(h, w)
    if side <= max_side:
        return image, False
    scale = max_side / side
    new_size = (max(1, round(w * scale)), max(1, round(h * scale)))
    return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA), True


def ensure_bgr(image: np.ndarray) -> np.ndarray:
    """Garante imagem BGR de 3 canais e 8 bits."""
    if image.dtype != np.uint8:
        image = cv2.normalize(image, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    return image


def ensure_bgra(image: np.ndarray) -> np.ndarray:
    """Garante imagem BGRA (com canal alfa)."""
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 3:
        alpha = np.full(image.shape[:2] + (1,), 255, np.uint8)
        image = np.concatenate([image, alpha], axis=2)
    return image
