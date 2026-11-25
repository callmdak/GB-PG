"""Gera as galerias de filtros e operações usadas no README (docs/*.png).

Uso (na raiz do projeto):
    python tools/gerar_galeria.py

Requer Pillow (requirements-dev.txt) só para escrever os rótulos com acentos.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pgstories.filters import FILTERS_BY_KEY, filters_by_category  # noqa: E402
from pgstories.io_utils import imread  # noqa: E402
from pgstories.operations import OPERATIONS  # noqa: E402
from pgstories.paths import EXAMPLES_DIR, TEXTURES_DIR  # noqa: E402
from pgstories.pipeline import CHANNEL_MODES, Step  # noqa: E402

DOCS = ROOT / "docs"
TILE_W = 300
LABEL_H = 34
COLS = 5
BG = (24, 18, 30)


def font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def tile(img_bgr: np.ndarray, label: str) -> Image.Image:
    h, w = img_bgr.shape[:2]
    th = round(h * TILE_W / w)
    small = cv2.resize(img_bgr, (TILE_W, th), interpolation=cv2.INTER_AREA)
    canvas = Image.new("RGB", (TILE_W, th + LABEL_H), BG)
    canvas.paste(Image.fromarray(cv2.cvtColor(small, cv2.COLOR_BGR2RGB)), (0, 0))
    draw = ImageDraw.Draw(canvas)
    f = font(13)
    text = label
    while draw.textlength(text, font=f) > TILE_W - 10 and len(text) > 4:
        text = text[:-2]
    if text != label:
        text = text.rstrip() + "…"
    draw.text((6, th + 9), text, fill=(240, 230, 245), font=f)
    return canvas


def grid(tiles: list[Image.Image], title: str) -> Image.Image:
    rows = (len(tiles) + COLS - 1) // COLS
    tw, th = tiles[0].size
    gap, head = 8, 50
    out = Image.new("RGB", (COLS * tw + (COLS + 1) * gap, head + rows * th + (rows + 1) * gap), BG)
    ImageDraw.Draw(out).text((gap + 4, 14), title, fill=(255, 255, 255), font=font(22))
    for i, t in enumerate(tiles):
        r, c = divmod(i, COLS)
        out.paste(t, (gap + c * (tw + gap), head + gap + r * (th + gap)))
    return out


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    photo = imread(EXAMPLES_DIR / "cafe.jpg")
    tiles = [tile(photo, "Original")]
    for _, specs in filters_by_category():
        for spec in specs:
            extra = {"fundo_branco": True} if spec.key == "canny" else {}
            tiles.append(tile(Step(spec, extra).apply(photo), spec.name))
    grid(tiles, "Filtros (parâmetros padrão) — foto: cafe.jpg").save(DOCS / "galeria_filtros.jpg", quality=88)

    textures = {name: imread(next(TEXTURES_DIR.glob(f"{name}.*")))
                for name in ("luz_quente", "moldura", "papel_antigo", "bokeh", "por_do_sol")}
    which = {"add": "bokeh", "multiply": "papel_antigo", "max": "moldura", "min": "por_do_sol",
             "blend": "por_do_sol"}
    tiles = [tile(photo, "A (foto)")]
    tiles += [tile(img, f"B: {name}") for name, img in textures.items()]
    for spec in OPERATIONS:
        name = which.get(spec.key, "luz_quente")
        fit = "stretch" if name == "moldura" else "cover"
        tiles.append(tile(Step(spec, operand=textures[name], operand_fit=fit).apply(photo),
                          f"{spec.name.split(' (')[0]} · B={name}"))
    grid(tiles, "Operações entre duas imagens").save(DOCS / "galeria_operacoes.jpg", quality=88)

    cat = imread(EXAMPLES_DIR / "gato.jpg")
    unsharp = FILTERS_BY_KEY["gaussian"]
    tiles = []
    for mode, label in CHANNEL_MODES:
        tiles.append(tile(Step(unsharp, {"k": 15}, mode, True).apply(cat), label))
    tiles.append(tile(Step(unsharp, {"k": 15}, "r", False).apply(cat), "Canal R exibido em cinza"))
    global COLS
    cols_backup, COLS = COLS, 3
    grid(tiles, "Seleção de canal — desfoque gaussiano k=15").save(DOCS / "galeria_canais.jpg", quality=88)
    COLS = cols_backup
    print("Galerias salvas em", DOCS)


if __name__ == "__main__":
    main()
