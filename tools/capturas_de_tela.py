"""Gera as capturas de tela do README rodando a interface sem janela (offscreen).

Também serve como teste de fumaça da interface: abre foto, aplica filtros,
operações e stickers, usa o modo vídeo com um arquivo gerado na hora e salva.

Uso (na raiz do projeto):
    python tools/capturas_de_tela.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QTreeWidgetItemIterator  # noqa: E402

from pgstories.gui.main_window import MainWindow  # noqa: E402
from pgstories.gui.theme import apply_theme  # noqa: E402
from pgstories.io_utils import imread  # noqa: E402
from pgstories.paths import EXAMPLES_DIR  # noqa: E402

DOCS = ROOT / "docs"


def wait(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def select_filter(win: MainWindow, key: str) -> None:
    it = QTreeWidgetItemIterator(win.filter_tree)
    while it.value():
        item = it.value()
        if item.data(0, 256) == key:  # Qt.UserRole
            win.filter_tree.setCurrentItem(item)
            return
        it += 1
    raise KeyError(key)


def select_operation(win: MainWindow, key: str) -> None:
    for i in range(win.op_list.count()):
        if win.op_list.item(i).data(256) == key:
            win.op_list.setCurrentRow(i)
            return
    raise KeyError(key)


def select_sticker(win: MainWindow, key: str) -> None:
    for i in range(win.sticker_list.count()):
        if win.stickers[win.sticker_list.item(i).data(256)].key == key:
            win.sticker_list.setCurrentRow(i)
            return
    raise KeyError(key)


def snap(win: MainWindow, name: str) -> None:
    wait(120)
    win.grab().save(str(DOCS / name), quality=90)
    print("captura:", name)


def make_test_video(path: Path) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 20, (640, 360))
    cat = cv2.resize(imread(EXAMPLES_DIR / "gato.jpg"), (640, 426))[33:393]
    for i in range(40):
        frame = np.roll(cat, i * 6, axis=1)
        writer.write(frame)
    writer.release()


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    app = QApplication([])
    apply_theme(app)
    win = MainWindow()
    win.resize(1500, 920)
    win.show()
    snap(win, "tela_inicial.jpg")

    # --- Modo foto + filtros ------------------------------------------------------
    win.load_photo(EXAMPLES_DIR / "gato.jpg")
    select_filter(win, "temperature")
    win.apply_filter()
    select_filter(win, "vignette")
    win.apply_filter()
    select_filter(win, "unsharp")  # selecionado, com descrição visível, mas ainda não aplicado
    win.filter_preview.setChecked(True)
    snap(win, "tela_filtros.jpg")
    win.filter_preview.setChecked(False)
    assert len(win.pipeline) == 2

    # --- Seleção de canal -----------------------------------------------------------
    win.reset()
    select_filter(win, "equalize")
    win.filter_channels.combo.setCurrentIndex(2)  # canal R
    win.apply_filter()
    snap(win, "tela_canal_r.jpg")
    win.reset()

    # --- Operações ----------------------------------------------------------------
    win.load_photo(EXAMPLES_DIR / "cafe.jpg")
    win.tabs.setCurrentIndex(1)
    select_operation(win, "add")
    idx = next(i for i in range(win.operand_combo.count()) if "bokeh" in win.operand_combo.itemText(i))
    win.operand_combo.setCurrentIndex(idx)
    win._on_operand_combo(idx)
    win.apply_operation()
    snap(win, "tela_operacoes.jpg")
    win.reset()

    # --- Stickers -----------------------------------------------------------------
    win.load_photo(EXAMPLES_DIR / "gato.jpg")
    select_filter(win, "saturation")
    win.apply_filter()
    win.tabs.setCurrentIndex(2)
    for key, rx, ry, size, angle in (("coroa", 0.55, 0.12, 30, -8), ("balao_uau", 0.18, 0.25, 30, 0),
                                     ("coracao_pulsando", 0.85, 0.78, 18, 0), ("brilhos", 0.3, 0.75, 25, 0),
                                     ("oculos", 0.53, 0.44, 42, -4)):
        select_sticker(win, key)
        win.sticker_size.setValue(size)
        win.sticker_angle.setValue(angle)
        win._on_view_pressed(rx, ry, 1)  # clique esquerdo
    win.sticker_angle.setValue(0)
    select_sticker(win, "estrela")
    assert len(win.placements) == 5
    snap(win, "tela_stickers.jpg")

    # arrastar um sticker e remover com o botão direito
    win._on_view_pressed(0.85, 0.78, 1)
    win._on_view_dragged(0.80, 0.70)
    win._on_view_released(0.80, 0.70)
    win._on_view_pressed(0.30, 0.75, 2)  # botão direito remove os brilhos
    assert len(win.placements) == 4

    # salvar (sem diálogo)
    out = Path(tempfile.gettempdir()) / "pgstories_teste_salvar.png"
    from pgstories.io_utils import imwrite
    assert imwrite(out, win.output) and imread(out).shape == win.output.shape

    # desfazer: o último item criado foi um sticker
    n = len(win.placements)
    win.undo()
    assert len(win.placements) == n - 1 and len(win.pipeline) == 1
    win.reset()
    assert not win.placements and not win.pipeline.steps

    # --- Modo vídeo (arquivo, já que aqui não há webcam) ---------------------------
    video = Path(tempfile.gettempdir()) / "pgstories_teste.avi"
    make_test_video(video)
    win.start_video(str(video))
    assert win.mode == "video"
    select_filter(win, "cartoon")
    win.apply_filter()
    win.tabs.setCurrentIndex(2)
    select_sticker(win, "estrela_girando")
    win.sticker_size.setValue(20)
    win._on_view_pressed(0.85, 0.2, 1)
    wait(800)
    assert win.raw_frame is not None and win.output is not None
    snap(win, "tela_video.jpg")
    win.stop_video()
    assert win.mode == "photo"  # último quadro vira foto
    win.close()
    print("Interface OK — capturas salvas em", DOCS)


if __name__ == "__main__":
    main()
