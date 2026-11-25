"""Operações aritméticas entre duas imagens (A = imagem atual, B = segunda imagem).

A imagem B é redimensionada para o tamanho de A antes da operação (ver
``fit_cover``), então qualquer foto/textura pode ser combinada com a foto ou
com o vídeo da webcam. Todas as funções recebem ``uint8`` de 1 ou 3 canais
com o mesmo formato e devolvem ``uint8`` com saturação em [0, 255].
"""

from __future__ import annotations

import cv2
import numpy as np

from .params import EffectSpec, Param


def fit_cover(image: np.ndarray, height: int, width: int) -> np.ndarray:
    """Redimensiona ``image`` para cobrir (height x width) sem distorcer e recorta o centro."""
    h, w = image.shape[:2]
    if (h, w) == (height, width):
        return image
    scale = max(width / w, height / h)
    new_w, new_h = max(width, round(w * scale)), max(height, round(h * scale))
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    resized = cv2.resize(image, (new_w, new_h), interpolation=interp)
    x0, y0 = (new_w - width) // 2, (new_h - height) // 2
    return np.ascontiguousarray(resized[y0:y0 + height, x0:x0 + width])


def fit_image(image: np.ndarray, height: int, width: int, mode: str = "cover") -> np.ndarray:
    """Ajusta B ao tamanho de A: ``cover`` (preenche e recorta) ou ``stretch`` (estica)."""
    if mode == "stretch":
        if image.shape[:2] == (height, width):
            return image
        return cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
    return fit_cover(image, height, width)


FIT_MODES = (("cover", "Preencher e recortar"), ("stretch", "Esticar"))


def op_add(a, b, p):
    return cv2.addWeighted(a, p["peso_a"], b, p["peso_b"], 0)


def op_subtract(a, b, p):
    return cv2.addWeighted(a, p["peso_a"], b, -p["peso_b"], p["deslocamento"])


def op_absdiff(a, b, p):
    diff = cv2.absdiff(a, b)
    return cv2.convertScaleAbs(diff, alpha=p["ganho"])


def op_blend(a, b, p):
    alpha = p["alfa"]
    return cv2.addWeighted(a, 1.0 - alpha, b, alpha, 0)


def op_multiply(a, b, p):
    mult = cv2.multiply(a, b, scale=1.0 / 255.0)
    return cv2.addWeighted(mult, p["intensidade"], a, 1.0 - p["intensidade"], 0)


def op_max(a, b, p):
    return cv2.max(a, b)


def op_min(a, b, p):
    return cv2.min(a, b)


W_HELP = "multiplica a imagem antes de somar."

OPERATIONS: tuple[EffectSpec, ...] = (
    EffectSpec(
        "add", "Adição ponderada (A·wA + B·wB)", "Operação",
        "Soma pixel a pixel as duas imagens, com pesos, saturando em 255. Clareia a imagem; "
        "útil para sobrepor luzes, brilhos e texturas claras.",
        op_add,
        (Param("peso_a", "Peso de A", "float", 1.0, 0.0, 2.0, 0.05, short="wA", help=W_HELP),
         Param("peso_b", "Peso de B", "float", 0.6, 0.0, 2.0, 0.05, short="wB", help=W_HELP)),
        binary=True,
    ),
    EffectSpec(
        "subtract", "Subtração ponderada (A·wA − B·wB + d)", "Operação",
        "Subtrai B de A pixel a pixel, com pesos e deslocamento opcional, saturando em [0, 255]. "
        "Com deslocamento 128 as diferenças negativas também ficam visíveis.",
        op_subtract,
        (Param("peso_a", "Peso de A", "float", 1.0, 0.0, 2.0, 0.05, short="wA", help=W_HELP),
         Param("peso_b", "Peso de B", "float", 0.5, 0.0, 2.0, 0.05, short="wB", help=W_HELP),
         Param("deslocamento", "Deslocamento (d)", "int", 0, -128, 255, 1, short="d",
               help="valor somado ao resultado.")),
        binary=True,
    ),
    EffectSpec(
        "absdiff", "Diferença absoluta |A − B|", "Operação",
        "Mostra onde as imagens diferem. Com a webcam e um frame de fundo salvo como B "
        "(botão 'Usar imagem atual como B'), destaca o que se moveu na cena.",
        op_absdiff,
        (Param("ganho", "Ganho", "float", 1.0, 0.5, 8.0, 0.1, short="g",
               help="amplifica as diferenças pequenas."),),
        binary=True,
    ),
    EffectSpec(
        "blend", "Blending (mistura alfa)", "Operação",
        "Combinação convexa (1 − α)·A + α·B: transição suave entre as duas imagens, como uma "
        "dupla exposição.",
        op_blend,
        (Param("alfa", "Alfa (α)", "float", 0.5, 0.0, 1.0, 0.05, short="α",
               help="0 = só A, 1 = só B."),),
        binary=True,
    ),
    EffectSpec(
        "multiply", "Multiplicação (A·B/255)", "Operação",
        "Multiplica as imagens normalizadas: branco em B não altera A e preto escurece. "
        "Ótimo para aplicar texturas de papel, gradientes e molduras escuras.",
        op_multiply,
        (Param("intensidade", "Intensidade", "float", 1.0, 0.0, 1.0, 0.05, short="int",
               help="mistura entre A (0) e o resultado da multiplicação (1)."),),
        binary=True,
    ),
    EffectSpec(
        "max", "Máximo (clarear)", "Operação",
        "Escolhe, em cada pixel, o maior valor entre A e B. Com a textura 'moldura' cria uma "
        "borda branca estilo polaroid.",
        op_max,
        binary=True,
    ),
    EffectSpec(
        "min", "Mínimo (escurecer)", "Operação",
        "Escolhe, em cada pixel, o menor valor entre A e B.",
        op_min,
        binary=True,
    ),
)

OPERATIONS_BY_KEY: dict[str, EffectSpec] = {o.key: o for o in OPERATIONS}
