"""Testes do núcleo de processamento (rodar com: python -m pytest)."""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pgstories.filters import FILTERS, FILTERS_BY_KEY, filters_by_category  # noqa: E402
from pgstories.io_utils import imread, imwrite  # noqa: E402
from pgstories.operations import OPERATIONS, OPERATIONS_BY_KEY, fit_cover  # noqa: E402
from pgstories.paths import EXAMPLES_DIR, TEXTURES_DIR  # noqa: E402
from pgstories.pipeline import CHANNEL_MODES, Pipeline, Step  # noqa: E402
from pgstories.stickers import Placement, compose, load_stickers, overlay  # noqa: E402
from pgstories.video import VideoSource  # noqa: E402


@pytest.fixture(scope="module")
def photo() -> np.ndarray:
    img = imread(EXAMPLES_DIR / "cafe.jpg")
    assert img is not None
    return img


@pytest.fixture(scope="module")
def texture() -> np.ndarray:
    img = imread(TEXTURES_DIR / "luz_quente.png")
    assert img is not None
    return img


def test_requisitos_minimos_de_filtros():
    assert len(FILTERS) >= 10
    categories = {f.category for f in FILTERS}
    assert "Suavização" in categories and "Realce" in categories
    assert len(OPERATIONS) >= 3
    assert all(f.description for f in FILTERS + OPERATIONS)
    assert sum(len(specs) for _, specs in filters_by_category()) == len(FILTERS)


@pytest.mark.parametrize("spec", FILTERS + OPERATIONS, ids=lambda s: s.key)
@pytest.mark.parametrize("mode", [m for m, _ in CHANNEL_MODES])
def test_todos_os_efeitos_em_todos_os_canais(spec, mode, photo, texture):
    step = Step(spec, {}, mode, operand=texture if spec.binary else None)
    out = step.apply(photo)
    assert out.shape == photo.shape and out.dtype == np.uint8


@pytest.mark.parametrize("spec", FILTERS + OPERATIONS, ids=lambda s: s.key)
def test_parametros_extremos(spec, photo, texture):
    for p in spec.params:
        if p.kind in ("int", "float"):
            values = [p.minimum, p.maximum]
        elif p.kind == "choice":
            values = [c[0] for c in p.choices]
        else:
            values = [True, False]
        for v in values:
            out = Step(spec, {p.key: v}, operand=texture if spec.binary else None).apply(photo)
            assert out.shape == photo.shape


def test_descricao_lista_parametros():
    text = FILTERS_BY_KEY["gaussian"].describe_text()
    assert "Parâmetros configuráveis" in text and "Sigma" in text
    assert "Não possui parâmetros" in FILTERS_BY_KEY["negative"].describe_text()


def test_canal_isolado_mostra_somente_o_canal(photo):
    out = Step(FILTERS_BY_KEY["box"], {"k": 3}, "r", channel_color=True).apply(photo)
    assert out[:, :, 0].max() == 0 and out[:, :, 1].max() == 0 and out[:, :, 2].max() > 0
    gray = Step(FILTERS_BY_KEY["box"], {"k": 3}, "g", channel_color=False).apply(photo)
    assert np.array_equal(gray[:, :, 0], gray[:, :, 2])


def test_kernel_impar_e_limites():
    spec = FILTERS_BY_KEY["box"]
    assert spec.resolve({"k": 8})["k"] % 2 == 1
    assert spec.resolve({"k": 999})["k"] == 51


def test_operacoes_valores_conhecidos():
    a = np.full((4, 4, 3), 200, np.uint8)
    b = np.full((4, 4, 3), 100, np.uint8)
    add = OPERATIONS_BY_KEY["add"]
    assert Step(add, {"peso_a": 1, "peso_b": 1}, operand=b).apply(a)[0, 0, 0] == 255  # satura
    sub = OPERATIONS_BY_KEY["subtract"]
    assert Step(sub, {"peso_a": 1, "peso_b": 1, "deslocamento": 0}, operand=b).apply(a)[0, 0, 0] == 100
    blend = OPERATIONS_BY_KEY["blend"]
    assert Step(blend, {"alfa": 0.5}, operand=b).apply(a)[0, 0, 0] == 150
    assert Step(OPERATIONS_BY_KEY["absdiff"], operand=a).apply(b)[0, 0, 0] == 100


def test_fit_cover_mantem_tamanho(texture):
    out = fit_cover(texture, 300, 451)
    assert out.shape[:2] == (300, 451)


def test_pipeline_encadeia_desfaz_e_reseta(photo):
    pipe = Pipeline()
    pipe.add(Step(FILTERS_BY_KEY["grayscale"]))
    pipe.add(Step(FILTERS_BY_KEY["negative"]))
    out = pipe.render(photo)
    expected = 255 - cv2.cvtColor(photo, cv2.COLOR_BGR2GRAY)
    assert np.array_equal(out[:, :, 0], expected)
    pipe.move(1, -1)
    assert pipe.steps[0].spec.key == "negative"
    pipe.undo()
    assert len(pipe) == 1
    pipe.clear()
    assert np.array_equal(pipe.render(photo), photo)
    assert pipe.render(photo) is not photo  # sempre devolve cópia


def test_stickers_carregam_e_tem_alfa():
    stickers = load_stickers()
    assert len(stickers) >= 5
    assert any(s.animated for s in stickers)
    for s in stickers:
        assert s.frames[0].shape[2] == 4
        assert s.frames[0][:, :, 3].min() == 0  # tem transparência


def test_overlay_respeita_alfa_e_bordas():
    dst = np.zeros((50, 50, 3), np.uint8)
    src = np.zeros((20, 20, 4), np.uint8)
    src[:, :, 2] = 255
    src[:10, :, 3] = 255  # metade de cima opaca, metade de baixo transparente
    overlay(dst, src, 10, 10)
    assert dst[5, 5, 2] == 255 and dst[15, 5, 2] == 0
    cut = np.zeros((50, 50, 3), np.uint8)
    overlay(cut, src, 0, 10)  # metade esquerda do sticker fica fora da imagem
    assert cut[5, 5, 2] == 255 and cut[5, 15, 2] == 0
    overlay(dst, src, 500, 500)  # fora da imagem: não deve quebrar


def test_compose_com_animacao(photo):
    animated = next(s for s in load_stickers() if s.animated)
    p = Placement(animated, 0.5, 0.5, 0.3)
    a = compose(photo, [p], 0.0)
    b = compose(photo, [p], 0.5 / animated.fps * 3)
    assert a.shape == photo.shape
    assert not np.array_equal(a, b)  # quadros diferentes
    assert not np.array_equal(a, photo)


def test_io_com_acentos(tmp_path, photo):
    path = tmp_path / "pasta com acentuação" / "saída_ção.png"
    assert imwrite(path, photo)
    assert np.array_equal(imread(path), photo)


def test_video_de_arquivo(tmp_path):
    path = tmp_path / "teste.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
    for i in range(5):
        writer.write(np.full((48, 64, 3), i * 40, np.uint8))
    writer.release()
    src = VideoSource(str(path))
    assert src.open()
    frames = [src.read() for _ in range(8)]  # mais quadros que o vídeo: deve fazer loop
    assert all(f is not None and f.shape == (48, 64, 3) for f in frames)
    src.release()
