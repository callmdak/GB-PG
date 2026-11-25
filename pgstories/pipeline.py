"""Pipeline de efeitos: lista ordenada de passos aplicados em sequência.

Cada :class:`Step` guarda o efeito (filtro ou operação), os parâmetros e o
modo de canal. O pipeline é *não destrutivo*: a imagem original nunca é
alterada, então "Resetar" é só esvaziar a lista, e o mesmo pipeline pode ser
aplicado a cada frame da webcam.

Modos de canal (requisito "Seleção de Canais"):

* ``rgb``  — imagem inteira colorida (padrão);
* ``gray`` — imagem inteira em tons de cinza;
* ``r``, ``g``, ``b`` — o efeito é aplicado só naquele canal e a imagem
  principal passa a exibir o resultado desse canal (colorizado na cor do canal
  ou em tons de cinza, conforme ``channel_color``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from .filters import to_bgr, to_gray
from .operations import fit_image
from .params import EffectSpec

CHANNEL_MODES: tuple[tuple[str, str], ...] = (
    ("rgb", "Imagem inteira (RGB)"),
    ("gray", "Imagem inteira (tons de cinza)"),
    ("r", "Somente canal R (vermelho)"),
    ("g", "Somente canal G (verde)"),
    ("b", "Somente canal B (azul)"),
)
CHANNEL_SHORT = {"rgb": "RGB", "gray": "Cinza", "r": "canal R", "g": "canal G", "b": "canal B"}
_CHANNEL_INDEX = {"b": 0, "g": 1, "r": 2}  # OpenCV usa a ordem BGR


def extract_channel(img_bgr: np.ndarray, mode: str) -> np.ndarray:
    """Devolve a imagem no formato de entrada do modo (1 ou 3 canais)."""
    if mode == "rgb":
        return img_bgr
    if mode == "gray":
        return to_gray(img_bgr)
    return np.ascontiguousarray(img_bgr[:, :, _CHANNEL_INDEX[mode]])


def channel_to_display(channel: np.ndarray, mode: str, colored: bool) -> np.ndarray:
    """Converte um canal isolado em imagem BGR para exibição."""
    if not colored or mode not in _CHANNEL_INDEX:
        return cv2.merge([channel, channel, channel])
    zeros = np.zeros_like(channel)
    planes = [zeros, zeros, zeros]
    planes[_CHANNEL_INDEX[mode]] = channel
    return cv2.merge(planes)


@dataclass(eq=False)
class Step:
    """Um passo do pipeline (filtro ou operação com segunda imagem)."""

    spec: EffectSpec
    params: dict = field(default_factory=dict)
    channel: str = "rgb"
    channel_color: bool = True
    operand: np.ndarray | None = None  # imagem B (somente operações)
    operand_name: str = ""
    operand_fit: str = "cover"  # "cover" (recorta) ou "stretch" (estica)
    _operand_cache: dict = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self.params = self.spec.resolve(self.params)

    @property
    def is_operation(self) -> bool:
        return self.spec.binary

    def label(self) -> str:
        text = self.spec.name
        summary = self.spec.summary(self.params)
        if summary:
            text += f"  ({summary})"
        if self.is_operation and self.operand_name:
            text += f"  com B = {self.operand_name}"
        return f"{text}  · {CHANNEL_SHORT.get(self.channel, self.channel)}"

    def _operand_for(self, h: int, w: int) -> np.ndarray:
        if self.operand is None:
            raise ValueError("Operação sem imagem B. Carregue uma segunda imagem.")
        key = (h, w, self.operand_fit)
        if key not in self._operand_cache:
            self._operand_cache.clear()
            self._operand_cache[key] = fit_image(self.operand, h, w, self.operand_fit)
        return self._operand_cache[key]

    def apply(self, img_bgr: np.ndarray) -> np.ndarray:
        """Aplica o passo e devolve sempre uma imagem BGR de 3 canais."""
        a = extract_channel(img_bgr, self.channel)
        if self.is_operation:
            b = extract_channel(self._operand_for(*img_bgr.shape[:2]), self.channel)
            out = self.spec.fn(a, b, self.params)
        else:
            out = self.spec.fn(a, self.params)

        if self.channel in _CHANNEL_INDEX:
            if out.ndim == 3:
                out = to_gray(out)
            return channel_to_display(out, self.channel, self.channel_color)
        return to_bgr(out)


class Pipeline:
    """Sequência de passos (combinação de filtros)."""

    def __init__(self) -> None:
        self.steps: list[Step] = []

    def __len__(self) -> int:
        return len(self.steps)

    def add(self, step: Step) -> None:
        self.steps.append(step)

    def remove(self, index: int) -> None:
        if 0 <= index < len(self.steps):
            del self.steps[index]

    def move(self, index: int, delta: int) -> int:
        new = index + delta
        if 0 <= index < len(self.steps) and 0 <= new < len(self.steps):
            self.steps[index], self.steps[new] = self.steps[new], self.steps[index]
            return new
        return index

    def undo(self) -> Step | None:
        return self.steps.pop() if self.steps else None

    def clear(self) -> None:
        self.steps.clear()

    def render(self, image: np.ndarray, preview: Step | None = None) -> np.ndarray:
        """Aplica todos os passos (e opcionalmente uma prévia) sobre uma cópia da imagem."""
        out = image
        for step in self.steps:
            out = step.apply(out)
        if preview is not None:
            out = preview.apply(out)
        return out if out is not image else image.copy()
