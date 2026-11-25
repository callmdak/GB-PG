"""Stickers: imagens PNG com canal alfa sobrepostas à foto/vídeo.

* Cada sticker fica em ``assets/stickers/<nome>.png`` e pode ter um arquivo
  ``<nome>.json`` com metadados (nome, descrição e, para os animados,
  quantos quadros a spritesheet tem e a velocidade em fps).
* Stickers animados usam uma *spritesheet*: todos os quadros lado a lado
  numa única imagem; o quadro exibido depende do tempo.
* A composição usa a equação de "alpha blending":
  ``resultado = alfa · sticker + (1 − alfa) · fundo``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from .io_utils import ensure_bgra, imread
from .paths import STICKERS_DIR

@dataclass(eq=False)
class StickerAsset:
    key: str
    name: str
    frames: list[np.ndarray]  # imagens BGRA
    fps: float = 0.0
    description: str = ""

    @property
    def animated(self) -> bool:
        return len(self.frames) > 1 and self.fps > 0

    @property
    def aspect(self) -> float:
        h, w = self.frames[0].shape[:2]
        return h / w

    def frame_at(self, t: float) -> np.ndarray:
        if not self.animated:
            return self.frames[0]
        return self.frames[int(t * self.fps) % len(self.frames)]

    def describe_text(self) -> str:
        kind = f"animado ({len(self.frames)} quadros a {self.fps:g} fps)" if self.animated else "estático"
        return f"Sticker '{self.name}' — {kind}. {self.description}"


def split_sheet(sheet: np.ndarray, frames: int, cols: int, rows: int) -> list[np.ndarray]:
    """Recorta uma spritesheet em quadros (ordem: linha a linha)."""
    h, w = sheet.shape[:2]
    fw, fh = w // cols, h // rows
    out = []
    for i in range(frames):
        r, c = divmod(i, cols)
        out.append(np.ascontiguousarray(sheet[r * fh:(r + 1) * fh, c * fw:(c + 1) * fw]))
    return out


def load_sticker(png: Path) -> StickerAsset | None:
    image = imread(png, cv2.IMREAD_UNCHANGED)
    if image is None:
        return None
    image = ensure_bgra(image)
    meta: dict = {}
    meta_path = png.with_suffix(".json")
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}
    n = int(meta.get("frames", 1))
    frames = split_sheet(image, n, int(meta.get("cols", n)), int(meta.get("rows", 1))) if n > 1 else [image]
    return StickerAsset(
        key=png.stem,
        name=meta.get("nome", png.stem.replace("_", " ").capitalize()),
        frames=frames,
        fps=float(meta.get("fps", 0)) if n > 1 else 0.0,
        description=meta.get("descricao", ""),
    )


def load_stickers(folder: Path = STICKERS_DIR) -> list[StickerAsset]:
    """Carrega todos os PNG da pasta (estáticos primeiro, depois os animados)."""
    assets = [a for a in (load_sticker(p) for p in sorted(Path(folder).glob("*.png"))) if a]
    return sorted(assets, key=lambda a: (a.animated, a.name.lower()))


# ---------------------------------------------------------------------------
# Transformação e composição
# ---------------------------------------------------------------------------

_cache: dict = {}


def prepare(frame: np.ndarray, width: int, angle: float = 0.0) -> np.ndarray:
    """Redimensiona (e gira) um quadro BGRA. Resultados ficam em cache."""
    width = max(4, int(width))
    key = (id(frame), width, round(angle, 1))
    hit = _cache.get(key)
    if hit is not None:
        return hit
    h, w = frame.shape[:2]
    height = max(4, round(h * width / w))
    interp = cv2.INTER_AREA if width < w else cv2.INTER_LINEAR
    img = cv2.resize(frame, (width, height), interpolation=interp)
    if abs(angle) > 0.05:
        # Gira em torno do centro, aumentando a tela para não cortar os cantos.
        m = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
        cos, sin = abs(m[0, 0]), abs(m[0, 1])
        nw, nh = int(height * sin + width * cos), int(height * cos + width * sin)
        m[0, 2] += nw / 2 - width / 2
        m[1, 2] += nh / 2 - height / 2
        img = cv2.warpAffine(img, m, (nw, nh), flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    if len(_cache) > 256:
        _cache.clear()
    _cache[key] = img
    return img


def overlay(dst_bgr: np.ndarray, src_bgra: np.ndarray, cx: float, cy: float) -> None:
    """Sobrepõe ``src_bgra`` centralizado em (cx, cy), recortando nas bordas (in-place)."""
    H, W = dst_bgr.shape[:2]
    h, w = src_bgra.shape[:2]
    x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
    dx0, dy0 = max(0, x0), max(0, y0)
    dx1, dy1 = min(W, x0 + w), min(H, y0 + h)
    if dx0 >= dx1 or dy0 >= dy1:
        return  # completamente fora da imagem
    src = src_bgra[dy0 - y0:dy1 - y0, dx0 - x0:dx1 - x0]
    roi = dst_bgr[dy0:dy1, dx0:dx1]
    alpha = src[:, :, 3:4].astype(np.float32) / 255.0
    blended = src[:, :, :3].astype(np.float32) * alpha + roi.astype(np.float32) * (1.0 - alpha)
    roi[:] = np.clip(blended + 0.5, 0, 255).astype(np.uint8)


@dataclass(eq=False)
class Placement:
    """Um sticker posicionado. Coordenadas relativas (0–1) para valer em qualquer resolução."""

    asset: StickerAsset
    rx: float
    ry: float
    rel_width: float = 0.25  # largura do sticker / largura da imagem
    angle: float = 0.0
    t0: float = field(default=0.0)  # início da animação deste sticker

    def draw(self, img: np.ndarray, t: float) -> None:
        h, w = img.shape[:2]
        frame = self.asset.frame_at(max(0.0, t - self.t0))
        overlay(img, prepare(frame, self.rel_width * w, self.angle), self.rx * w, self.ry * h)


def compose(img_bgr: np.ndarray, placements: list[Placement], t: float) -> np.ndarray:
    """Devolve uma cópia da imagem com todos os stickers desenhados."""
    if not placements:
        return img_bgr
    out = img_bgr.copy()
    for p in placements:
        p.draw(out, t)
    return out
