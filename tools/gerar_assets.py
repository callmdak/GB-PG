"""Gera os stickers (PNG com canal alfa) e as texturas usadas no aplicativo.

Todos os desenhos são originais e feitos por código (Pillow + NumPy + OpenCV),
então não há problema de direitos autorais. Os arquivos gerados já estão no
repositório; este script só precisa ser executado para recriá-los.

Uso (na raiz do projeto):
    python tools/gerar_assets.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
STICKERS = ROOT / "assets" / "stickers"
TEXTURES = ROOT / "assets" / "texturas"
SS = 4  # supersampling: desenha 4x maior e reduz (bordas suaves)

# ---------------------------------------------------------------------------
# Utilitários de desenho
# ---------------------------------------------------------------------------


def blank(w: int, h: int) -> Image.Image:
    return Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))


def shape_mask(size: tuple[int, int], draw_fn) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw_fn(ImageDraw.Draw(mask))
    return mask


def gradient_layer(mask: Image.Image, top, bottom, angle_deg: float = 90) -> Image.Image:
    """Preenche a máscara com um gradiente linear entre duas cores."""
    w, h = mask.size
    bbox = mask.getbbox() or (0, 0, w, h)
    x0, y0, x1, y1 = bbox
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    a = math.radians(angle_deg)
    proj = (xx - x0) * math.cos(a) + (yy - y0) * math.sin(a)
    length = abs((x1 - x0) * math.cos(a)) + abs((y1 - y0) * math.sin(a)) or 1
    t = np.clip(proj / length, 0, 1)[..., None]
    rgb = np.array(top, np.float32) * (1 - t) + np.array(bottom, np.float32) * t
    rgba = np.dstack([rgb.astype(np.uint8), np.array(mask)])
    return Image.fromarray(rgba, "RGBA")


def clip_to(layer: Image.Image, mask: Image.Image) -> Image.Image:
    arr = np.array(layer)
    arr[..., 3] = (arr[..., 3].astype(np.uint16) * np.array(mask) // 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def outline_under(art: Image.Image, color, px: int) -> Image.Image:
    """Desenha um contorno da cor dada em volta da arte (por dilatação do alfa)."""
    alpha = np.array(art)[..., 3]
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * px + 1, 2 * px + 1))
    ring = cv2.dilate(alpha, k)
    base = Image.new("RGBA", art.size, tuple(color) + (0,))
    arr = np.array(base)
    arr[..., 3] = ring
    base = Image.fromarray(arr, "RGBA")
    base.alpha_composite(art)
    return base


def sticker_finish(art: Image.Image, size: tuple[int, int], border: int = 7,
                   shadow: bool = True, border_color=(255, 255, 255)) -> Image.Image:
    """Reduz a arte e aplica o visual de 'sticker': borda branca + sombra suave.

    Uma margem transparente é adicionada para a borda e a sombra não serem cortadas.
    """
    pad = border + 10
    small = art.resize(size, Image.LANCZOS)
    size = (size[0] + 2 * pad, size[1] + 2 * pad)
    art = Image.new("RGBA", size, (0, 0, 0, 0))
    art.paste(small, (pad, pad))
    alpha = np.array(art)[..., 3]
    layers = Image.new("RGBA", size, (0, 0, 0, 0))
    if border > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * border + 1, 2 * border + 1))
        ring = cv2.GaussianBlur(cv2.dilate(alpha, k), (3, 3), 0)
    else:
        ring = alpha
    if shadow:
        sh = cv2.GaussianBlur(ring, (0, 0), 4)
        sh = cv2.warpAffine(sh, np.float32([[1, 0, 3], [0, 1, 4]]), size)  # desloca sem "dar a volta"
        sh_img = np.zeros(size[::-1] + (4,), np.uint8)
        sh_img[..., 3] = (sh * 0.45).astype(np.uint8)
        layers.alpha_composite(Image.fromarray(sh_img, "RGBA"))
    if border > 0:
        b_img = np.zeros(size[::-1] + (4,), np.uint8)
        b_img[..., :3] = border_color
        b_img[..., 3] = ring
        layers.alpha_composite(Image.fromarray(b_img, "RGBA"))
    layers.alpha_composite(art)
    return layers


def highlight(art: Image.Image, mask: Image.Image, box, alpha: int = 110) -> Image.Image:
    layer = Image.new("RGBA", art.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse(box, fill=(255, 255, 255, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(SS * 5))
    out = art.copy()
    out.alpha_composite(clip_to(layer, mask))
    return out


def chaikin(points, iterations: int = 2, closed: bool = True):
    pts = list(points)
    for _ in range(iterations):
        new = []
        n = len(pts)
        rng = range(n) if closed else range(n - 1)
        for i in rng:
            p0, p1 = pts[i], pts[(i + 1) % n]
            new.append((0.75 * p0[0] + 0.25 * p1[0], 0.75 * p0[1] + 0.25 * p1[1]))
            new.append((0.25 * p0[0] + 0.75 * p1[0], 0.25 * p0[1] + 0.75 * p1[1]))
        pts = new if closed else [pts[0]] + new + [pts[-1]]
    return pts


def font(size: int) -> ImageFont.FreeTypeFont:
    for name in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf",
                 "arialbd.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


# ---------------------------------------------------------------------------
# Desenhos (em coordenadas já multiplicadas por SS)
# ---------------------------------------------------------------------------


def star_points(cx, cy, r_out, r_in, n=5, rot=-90.0):
    pts = []
    for i in range(2 * n):
        ang = math.radians(rot + i * 180.0 / n)
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return pts


def art_star(w=256, h=256, rot=-90.0) -> Image.Image:
    W, H = w * SS, h * SS
    pts = chaikin(star_points(W / 2, H / 2 + 6 * SS, W * 0.40, W * 0.18, rot=rot), 1)
    mask = shape_mask((W, H), lambda d: d.polygon(pts, fill=255))
    art = gradient_layer(mask, (255, 236, 110), (255, 150, 0))
    inner = chaikin(star_points(W / 2, H / 2 + 6 * SS, W * 0.24, W * 0.11, rot=rot), 1)
    glow = shape_mask((W, H), lambda d: d.polygon(inner, fill=255))
    art.alpha_composite(clip_to(gradient_layer(glow, (255, 250, 200), (255, 200, 40)), glow))
    return outline_under(art, (170, 80, 0), 3 * SS)


def heart_points(cx, cy, scale, n=240):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * scale, cy - y * scale))
    return pts


def art_heart(w=256, h=256) -> Image.Image:
    W, H = w * SS, h * SS
    pts = heart_points(W / 2, H / 2 + 4 * SS, W / 38)
    mask = shape_mask((W, H), lambda d: d.polygon(pts, fill=255))
    art = gradient_layer(mask, (255, 110, 140), (205, 0, 70))
    art = highlight(art, mask, (W * 0.22, H * 0.22, W * 0.44, H * 0.40), 150)
    return outline_under(art, (120, 0, 40), 3 * SS)


def art_sunglasses(w=512, h=190) -> Image.Image:
    W, H = w * SS, h * SS
    art = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    def lens(cx):
        x0, x1 = cx - W * 0.20, cx + W * 0.20
        y0, y1 = H * 0.22, H * 0.92
        pts = [(x0, y0), (x1, y0), (x1 - W * 0.015, y1 - H * 0.25),
               (cx + W * 0.06, y1), (cx - W * 0.06, y1), (x0 + W * 0.015, y1 - H * 0.25)]
        return chaikin(pts, 3)

    left, right = lens(W * 0.27), lens(W * 0.73)
    frame_mask = shape_mask((W, H), lambda d: (d.polygon(left, fill=255), d.polygon(right, fill=255)))
    frame_mask = Image.fromarray(cv2.dilate(np.array(frame_mask),
                                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13 * SS, 13 * SS))))
    d = ImageDraw.Draw(frame_mask)
    d.rounded_rectangle((W * 0.42, H * 0.20, W * 0.58, H * 0.36), radius=8 * SS, fill=255)  # ponte
    d.rectangle((0, H * 0.20, W * 0.08, H * 0.34), fill=255)  # hastes
    d.rectangle((W * 0.92, H * 0.20, W, H * 0.34), fill=255)
    art.alpha_composite(gradient_layer(frame_mask, (35, 30, 45), (10, 8, 15)))
    lens_mask = shape_mask((W, H), lambda d: (d.polygon(left, fill=255), d.polygon(right, fill=255)))
    art.alpha_composite(gradient_layer(lens_mask, (55, 40, 95), (230, 70, 140), 90))
    refl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(refl)
    for cx in (W * 0.27, W * 0.73):
        dr.polygon([(cx - W * 0.12, H * 0.30), (cx - W * 0.05, H * 0.30),
                    (cx - W * 0.13, H * 0.80), (cx - W * 0.20, H * 0.80)], fill=(255, 255, 255, 90))
        dr.polygon([(cx - W * 0.02, H * 0.30), (cx + W * 0.01, H * 0.30),
                    (cx - W * 0.07, H * 0.80), (cx - W * 0.10, H * 0.80)], fill=(255, 255, 255, 70))
    art.alpha_composite(clip_to(refl, lens_mask))
    return art


def art_crown(w=400, h=260) -> Image.Image:
    W, H = w * SS, h * SS
    base_y, top_y = H * 0.80, H * 0.18
    xs = np.linspace(W * 0.08, W * 0.92, 5)
    pts = [(W * 0.10, base_y)]
    for i, x in enumerate(xs):
        if i > 0:
            pts.append(((xs[i - 1] + x) / 2, H * 0.52))
        pts.append((x, top_y + (0 if i % 2 == 0 else H * 0.08)))
    pts.append((W * 0.90, base_y))
    mask = shape_mask((W, H), lambda d: (d.polygon(pts, fill=255),
                                         d.rounded_rectangle((W * 0.08, H * 0.70, W * 0.92, H * 0.93),
                                                             radius=10 * SS, fill=255)))
    art = gradient_layer(mask, (255, 230, 120), (220, 140, 10))
    d = ImageDraw.Draw(art)
    for i, x in enumerate(xs):
        y = top_y + (0 if i % 2 == 0 else H * 0.08)
        r = W * 0.035
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 245, 190, 255))
    band = shape_mask((W, H), lambda dd: dd.rounded_rectangle((W * 0.08, H * 0.70, W * 0.92, H * 0.93),
                                                              radius=10 * SS, fill=255))
    art.alpha_composite(clip_to(gradient_layer(band, (240, 170, 30), (190, 110, 0)), band))
    gems = [((W * 0.25), (230, 30, 80)), ((W * 0.50), (40, 120, 255)), ((W * 0.75), (30, 190, 110))]
    for x, color in gems:
        r = H * 0.075
        cy = H * 0.815
        d.ellipse((x - r, cy - r, x + r, cy + r), fill=color + (255,), outline=(120, 70, 0, 255), width=2 * SS)
        d.ellipse((x - r * 0.5, cy - r * 0.6, x - r * 0.05, cy - r * 0.15), fill=(255, 255, 255, 170))
    return outline_under(art, (140, 80, 0), 3 * SS)


def art_mustache(w=400, h=160) -> Image.Image:
    W, H = w * SS, h * SS
    half = [(0.00, 0.22), (0.10, 0.12), (0.24, 0.10), (0.40, 0.18), (0.56, 0.30), (0.70, 0.36),
            (0.82, 0.30), (0.90, 0.16), (0.95, 0.06), (0.99, 0.10), (0.98, 0.30), (0.90, 0.50),
            (0.76, 0.66), (0.58, 0.72), (0.40, 0.68), (0.22, 0.60), (0.08, 0.52), (0.00, 0.44)]
    right = [(W / 2 + x * W * 0.48, H * 0.12 + y * H * 0.8) for x, y in half]
    left = [(W - x, y) for x, y in reversed(right)]
    pts = chaikin(right[1:-1] + left[1:-1], 3)
    mask = shape_mask((W, H), lambda d: d.polygon(pts, fill=255))
    art = gradient_layer(mask, (110, 70, 40), (45, 25, 12))
    hair = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dh = ImageDraw.Draw(hair)
    rng = np.random.default_rng(3)
    for _ in range(90):
        x = rng.uniform(W * 0.1, W * 0.9)
        y = rng.uniform(H * 0.25, H * 0.75)
        dh.line((x, y, x + (x - W / 2) * 0.06, y + H * 0.12), fill=(160, 110, 70, 90), width=2 * SS)
    art.alpha_composite(clip_to(hair, mask))
    return outline_under(art, (30, 15, 5), 2 * SS)


def art_bubble(w=360, h=260, text="UAU!") -> Image.Image:
    W, H = w * SS, h * SS
    body = (W * 0.06, H * 0.06, W * 0.94, H * 0.74)
    tail = [(W * 0.22, H * 0.62), (W * 0.40, H * 0.70), (W * 0.12, H * 0.95)]
    mask = shape_mask((W, H), lambda d: (d.ellipse(body, fill=255), d.polygon(tail, fill=255)))
    art = gradient_layer(mask, (255, 255, 255), (235, 228, 245))
    art = outline_under(art, (25, 20, 35), 4 * SS)
    d = ImageDraw.Draw(art)
    f = font(int(H * 0.30))
    bbox = d.textbbox((0, 0), text, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx, ty = (W - tw) / 2 - bbox[0], H * 0.40 - th / 2 - bbox[1]
    txt_mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(txt_mask).text((tx, ty), text, font=f, fill=255)
    shadow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shadow).text((tx + 3 * SS, ty + 3 * SS), text, font=f, fill=255)
    art.alpha_composite(clip_to(Image.new("RGBA", (W, H), (60, 20, 90, 255)), shadow))
    art.alpha_composite(gradient_layer(txt_mask, (255, 80, 140), (150, 50, 230), 0))
    return art


def art_cat_ears(w=520, h=230) -> Image.Image:
    W, H = w * SS, h * SS
    art = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    band = shape_mask((W, H), lambda d: d.arc((W * 0.10, H * 0.55, W * 0.90, H * 1.6), 208, 332,
                                              fill=255, width=int(H * 0.09)))
    art.alpha_composite(gradient_layer(band, (90, 85, 100), (40, 38, 48)))
    for cx, tilt in ((W * 0.24, -1), (W * 0.76, 1)):
        outer = chaikin([(cx - W * 0.15, H * 0.92), (cx + tilt * W * 0.03, H * 0.04),
                         (cx + W * 0.15, H * 0.92)], 2)
        inner = chaikin([(cx - W * 0.085, H * 0.84), (cx + tilt * W * 0.022, H * 0.24),
                         (cx + W * 0.085, H * 0.84)], 2)
        om = shape_mask((W, H), lambda d, o=outer: d.polygon(o, fill=255))
        im = shape_mask((W, H), lambda d, i=inner: d.polygon(i, fill=255))
        ear = outline_under(gradient_layer(om, (110, 105, 120), (45, 42, 55)), (25, 22, 30), 2 * SS)
        art.alpha_composite(ear)
        art.alpha_composite(gradient_layer(im, (255, 175, 205), (240, 110, 160)))
    return art


def art_rainbow(w=420, h=250) -> Image.Image:
    W, H = w * SS, h * SS
    art = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    colors = [(235, 50, 60), (255, 140, 30), (255, 215, 40), (60, 190, 90), (50, 130, 235), (140, 70, 200)]
    d = ImageDraw.Draw(art)
    cx, cy = W / 2, H * 0.86
    r0, thick = W * 0.44, W * 0.045
    for i, c in enumerate(colors):
        r = r0 - i * thick
        d.arc((cx - r, cy - r, cx + r, cy + r), 180, 360, fill=c + (255,), width=int(thick) + SS)
    for ccx in (W * 0.16, W * 0.84):
        for dx, dy, rr in ((-0.07, 0.0, 0.07), (0.0, -0.04, 0.085), (0.075, 0.0, 0.065), (0.0, 0.03, 0.07)):
            x, y, r = ccx + dx * W, H * 0.78 + dy * W, rr * W
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 255))
    return outline_under(art, (60, 50, 80), 2 * SS)


def sparkle_points(cx, cy, r_out, r_in):
    return star_points(cx, cy, r_out, r_in, n=4, rot=-90)


def art_sparkles(phase_t: float, w=256, h=256) -> Image.Image:
    W, H = w * SS, h * SS
    art = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    spots = [(0.36, 0.40, 0.58, 0.0), (0.74, 0.26, 0.34, 0.33), (0.72, 0.72, 0.42, 0.66),
             (0.20, 0.80, 0.26, 0.5)]
    for x, y, size, ph in spots:
        s = 0.30 + 0.70 * (0.5 + 0.5 * math.cos(2 * math.pi * (phase_t + ph)))
        r = size * W * 0.5 * s
        pts = chaikin(sparkle_points(x * W, y * H, r, r * 0.24), 1)
        m = shape_mask((W, H), lambda d, p=pts: d.polygon(p, fill=255))
        glow = cv2.GaussianBlur(np.array(m), (0, 0), 5 * SS)
        glow = Image.fromarray(np.clip(glow.astype(np.float32) * 1.6, 0, 255).astype(np.uint8))
        art.alpha_composite(clip_to(Image.new("RGBA", (W, H), (255, 200, 60, 255)), glow))
        star = outline_under(gradient_layer(m, (255, 255, 235), (255, 210, 70)), (200, 120, 0), SS * 2)
        art.alpha_composite(star)
    return art


# ---------------------------------------------------------------------------
# Gravação
# ---------------------------------------------------------------------------


def save_sticker(name: str, img: Image.Image, meta: dict) -> None:
    STICKERS.mkdir(parents=True, exist_ok=True)
    img.save(STICKERS / f"{name}.png", optimize=True)
    (STICKERS / f"{name}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8")
    print("sticker:", name, img.size)


def save_sheet(name: str, frames: list[Image.Image], fps: float, meta: dict) -> None:
    fw, fh = frames[0].size
    sheet = Image.new("RGBA", (fw * len(frames), fh), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        sheet.paste(f, (i * fw, 0))
    meta = dict(meta, frames=len(frames), cols=len(frames), rows=1, fps=fps)
    save_sticker(name, sheet, meta)


def transformed(art: Image.Image, scale: float = 1.0, angle: float = 0.0) -> Image.Image:
    w, h = art.size
    img = art.rotate(angle, resample=Image.BICUBIC) if angle else art
    if scale != 1.0:
        sw, sh = max(1, int(w * scale)), max(1, int(h * scale))
        small = img.resize((sw, sh), Image.LANCZOS)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        img.paste(small, ((w - sw) // 2, (h - sh) // 2))
    return img


def make_stickers() -> None:
    save_sticker("estrela", sticker_finish(art_star(), (256, 256)),
                 {"nome": "Estrela", "descricao": "Estrela dourada."})
    save_sticker("coracao", sticker_finish(art_heart(), (256, 256)),
                 {"nome": "Coração", "descricao": "Coração vermelho com brilho."})
    save_sticker("oculos", sticker_finish(art_sunglasses(), (512, 190), border=5),
                 {"nome": "Óculos escuros", "descricao": "Óculos de sol com reflexo."})
    save_sticker("coroa", sticker_finish(art_crown(), (400, 260)),
                 {"nome": "Coroa", "descricao": "Coroa dourada com pedras."})
    save_sticker("bigode", sticker_finish(art_mustache(), (400, 160), border=5),
                 {"nome": "Bigode", "descricao": "Bigode estilo guidão."})
    save_sticker("balao_uau", sticker_finish(art_bubble(), (360, 260), border=4),
                 {"nome": "Balão \"UAU!\"", "descricao": "Balão de fala com o texto UAU!"})
    save_sticker("orelhas_gato", sticker_finish(art_cat_ears(), (520, 230), border=5),
                 {"nome": "Orelhas de gato", "descricao": "Tiara com orelhas de gatinho."})
    save_sticker("arco_iris", sticker_finish(art_rainbow(), (420, 250)),
                 {"nome": "Arco-íris", "descricao": "Arco-íris com nuvens."})

    # --- Animados (spritesheet horizontal) ---------------------------------
    heart = art_heart(220, 220)
    beat = [0.0, 0.55, 1.0, 0.45, 0.75, 0.35, 0.12, 0.0]
    frames = [sticker_finish(transformed(heart, 0.78 + 0.22 * b), (220, 220)) for b in beat]
    save_sheet("coracao_pulsando", frames, 10,
               {"nome": "Coração pulsante", "descricao": "Coração batendo (spritesheet com 8 quadros)."})

    frames = []
    for i in range(12):
        frames.append(sticker_finish(art_star(256, 256, rot=-90 + i * 6), (256, 256)))
    save_sheet("estrela_girando", frames, 15,
               {"nome": "Estrela girando", "descricao": "Estrela girando (spritesheet com 12 quadros)."})

    frames = [sticker_finish(art_sparkles(i / 12), (256, 256), border=0) for i in range(12)]
    save_sheet("brilhos", frames, 12,
               {"nome": "Brilhos", "descricao": "Brilhos que piscam (spritesheet com 12 quadros)."})


# ---------------------------------------------------------------------------
# Texturas para as operações com duas imagens
# ---------------------------------------------------------------------------


def blob(h, w, cx, cy, radius, color):
    y, x = np.ogrid[:h, :w]
    d2 = ((x - cx) ** 2 + (y - cy) ** 2) / (radius ** 2)
    return np.exp(-d2)[..., None] * np.array(color, np.float32)


def make_textures(w=1280, h=720) -> None:
    TEXTURES.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)

    # Light leak quente (para adição/blending)
    img = np.zeros((h, w, 3), np.float32)
    img += blob(h, w, -0.05 * w, 0.15 * h, 0.45 * w, (40, 120, 255))  # BGR: laranja
    img += blob(h, w, 0.10 * w, 0.95 * h, 0.35 * w, (130, 50, 255))   # rosa
    img += blob(h, w, 1.05 * w, 0.05 * h, 0.30 * w, (120, 220, 255))  # amarelo
    img += blob(h, w, 0.55 * w, -0.10 * h, 0.22 * w, (60, 160, 255))
    cv2.imwrite(str(TEXTURES / "luz_quente.png"), np.clip(img, 0, 255).astype(np.uint8))

    # Bokeh (para adição/máximo)
    img = np.zeros((h, w, 3), np.float32)
    palette = [(255, 200, 120), (120, 200, 255), (200, 140, 255), (140, 255, 220), (255, 255, 255)]
    for _ in range(80):
        layer = np.zeros((h, w, 3), np.float32)
        r = int(rng.uniform(12, 70))
        c = (int(rng.uniform(0, w)), int(rng.uniform(0, h)))
        color = np.array(palette[rng.integers(len(palette))], np.float32) * rng.uniform(0.25, 0.7)
        cv2.circle(layer, c, r, color.tolist(), -1, cv2.LINE_AA)
        cv2.circle(layer, c, r, (color * 1.4).tolist(), 2, cv2.LINE_AA)
        img += cv2.GaussianBlur(layer, (0, 0), 2.5)
    cv2.imwrite(str(TEXTURES / "bokeh.jpg"), np.clip(img, 0, 255).astype(np.uint8),
                [cv2.IMWRITE_JPEG_QUALITY, 92])

    # Pôr do sol (gradiente vertical, para multiplicação/blending)
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    top, mid, bottom = (np.array(c, np.float32) for c in ((140, 60, 70), (120, 130, 250), (170, 230, 255)))
    grad = np.where(t < 0.5, top * (1 - 2 * t) + mid * (2 * t), mid * (2 - 2 * t) + bottom * (2 * t - 1))
    cv2.imwrite(str(TEXTURES / "por_do_sol.png"), np.broadcast_to(grad, (h, w, 3)).astype(np.uint8))

    # Papel antigo (para multiplicação)
    base = np.full((h, w, 3), (190, 222, 240), np.float32)
    low = cv2.resize(rng.normal(0, 1, (9, 16)).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
    grain = rng.normal(0, 6, (h, w)).astype(np.float32)
    shade = (low * 10 + grain)[..., None]
    y, x = np.ogrid[:h, :w]
    edge = (((x - w / 2) / (w / 2)) ** 2 + ((y - h / 2) / (h / 2)) ** 2)[..., None]
    paper = base + shade - 45 * np.clip(edge - 0.4, 0, None)
    cv2.imwrite(str(TEXTURES / "papel_antigo.jpg"), np.clip(paper, 0, 255).astype(np.uint8),
                [cv2.IMWRITE_JPEG_QUALITY, 90])

    # Moldura estilo polaroid (para Máximo)
    frame = np.full((h, w, 3), 250, np.uint8)
    m = int(0.045 * w)
    cv2.rectangle(frame, (m, m), (w - m, h - int(m * 2.6)), (0, 0, 0), -1)
    cv2.imwrite(str(TEXTURES / "moldura.png"), frame)
    print("texturas salvas em", TEXTURES)


if __name__ == "__main__":
    make_stickers()
    make_textures()
