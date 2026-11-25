"""Janela principal do PG Stories."""

from __future__ import annotations

import itertools
import time
import traceback
from datetime import datetime
from pathlib import Path

import numpy as np
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence, QPainter, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QFileDialog,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton,
                               QScrollArea, QSizePolicy, QSlider, QSpinBox, QSplitter, QStyle,
                               QTabWidget, QTextBrowser, QToolButton, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from ..filters import FILTERS_BY_KEY, filters_by_category
from ..io_utils import IMAGE_FILTER, VIDEO_FILTER, ensure_bgr, imread, imwrite, limit_size
from ..operations import FIT_MODES, OPERATIONS
from ..params import EffectSpec
from ..paths import EXAMPLES_DIR, OUTPUT_DIR, TEXTURES_DIR
from ..pipeline import Pipeline, Step
from ..stickers import Placement, StickerAsset, compose, load_stickers
from ..video import VideoSource
from .icons import badge, play_icon, stop_icon, undo_icon
from .image_view import ImageView, bgr_to_qimage, bgra_to_qimage
from .widgets import ChannelSelector, ParamForm, compact_combo

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}
RESOLUTIONS = (("1280 × 720", (1280, 720)), ("640 × 480", (640, 480)), ("1920 × 1080", (1920, 1080)))

_order = itertools.count()  # ordem de criação (para o "Desfazer")


def log(msg: str) -> None:
    """Mensagens no console (requisito: descrições também no console)."""
    print(msg, flush=True)


def _title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("step")
    return label


def _scroll(widget: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(widget)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    return area


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PG Stories — editor de imagens e vídeo (Processamento Gráfico · Grau B)")
        self.resize(1440, 900)

        # Estado ----------------------------------------------------------------
        self.pipeline = Pipeline()
        self.placements: list[Placement] = []
        self.source: np.ndarray | None = None  # foto original (modo foto)
        self.source_name = ""
        self.mode = "none"  # "none" | "photo" | "video"
        self.video: VideoSource | None = None
        self.raw_frame: np.ndarray | None = None  # último quadro sem efeitos
        self.filtered: np.ndarray | None = None  # imagem com o pipeline aplicado
        self.output: np.ndarray | None = None  # imagem exibida (com stickers) = o que é salvo
        self.show_original = False
        self.operand: np.ndarray | None = None
        self.operand_name = ""
        self._drag: Placement | None = None
        self._drag_offset = (0.0, 0.0)
        self._t0 = time.perf_counter()
        self._fail_count = 0

        self.stickers: list[StickerAsset] = load_stickers()

        # Timers ----------------------------------------------------------------
        self.video_timer = QTimer(self)
        self.video_timer.timeout.connect(self._on_video_tick)
        self.anim_timer = QTimer(self)  # anima stickers no modo foto
        self.anim_timer.setInterval(40)
        self.anim_timer.timeout.connect(self._show_output)
        self.debounce = QTimer(self)  # evita reprocessar a cada passo do slider
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(70)
        self.debounce.timeout.connect(lambda: self._refresh(rerender=True))

        self._build_ui()
        self._load_default_operand()
        self._update_actions()
        self._print_banner()

    # =========================================================================
    # Construção da interface
    # =========================================================================
    def _icon(self, sp: QStyle.StandardPixmap) -> QIcon:
        return self.style().standardIcon(sp)

    def _build_ui(self) -> None:
        self._build_toolbar()
        self.view = ImageView()
        self.view.pressed.connect(self._on_view_pressed)
        self.view.dragged.connect(self._on_view_dragged)
        self.view.released.connect(self._on_view_released)
        self.view.fileDropped.connect(self._open_path)

        self.tabs = QTabWidget()
        self.tabs.addTab(_scroll(self._build_filters_tab()), "Filtros")
        self.tabs.addTab(_scroll(self._build_operations_tab()), "Operações")
        self.tabs.addTab(_scroll(self._build_stickers_tab()), "Stickers")
        self.tabs.addTab(self._build_pipeline_tab(), "Pipeline (0)")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.tabs.setMinimumWidth(400)

        splitter = QSplitter()
        splitter.addWidget(self.view)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([1000, 430])
        self.setCentralWidget(splitter)

        self.status_mode = QLabel()
        self.status_size = QLabel()
        self.status_fps = QLabel()
        for w in (self.status_mode, self.status_size, self.status_fps):
            self.statusBar().addPermanentWidget(w)

    def _build_toolbar(self) -> None:
        tb = self.addToolBar("Principal")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        self.act_open = QAction(self._icon(QStyle.StandardPixmap.SP_DialogOpenButton), "Abrir foto", self)
        self.act_open.setShortcut(QKeySequence.StandardKey.Open)
        self.act_open.setToolTip("Modo Foto: carregar uma imagem do disco (Ctrl+O)")
        self.act_open.triggered.connect(self.open_photo_dialog)
        tb.addAction(self.act_open)

        examples = QToolButton()
        examples.setText("Exemplos")
        examples.setIcon(self._icon(QStyle.StandardPixmap.SP_DirIcon))
        examples.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        examples.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(examples)
        for path in sorted(EXAMPLES_DIR.glob("*")):
            if path.suffix.lower() in IMAGE_EXTS:
                menu.addAction(path.stem.capitalize(), lambda p=path: self.load_photo(p))
        examples.setMenu(menu)
        examples.setToolTip("Abrir uma das fotos de exemplo do projeto")
        tb.addWidget(examples)
        tb.addSeparator()

        self.act_webcam = QAction(play_icon(), "Iniciar webcam", self)
        self.act_webcam.setShortcut(QKeySequence("Ctrl+K"))
        self.act_webcam.setToolTip("Modo Vídeo: iniciar/parar a captura da webcam (Ctrl+K)")
        self.act_webcam.triggered.connect(self.toggle_webcam)
        tb.addAction(self.act_webcam)

        tb.addWidget(QLabel(" Câmera "))
        self.cam_index = QSpinBox()
        self.cam_index.setRange(0, 9)
        self.cam_index.setToolTip("Índice da câmera (0 = padrão)")
        tb.addWidget(self.cam_index)
        self.cam_res = QComboBox()
        for label, size in RESOLUTIONS:
            self.cam_res.addItem(label, size)
        self.cam_res.setToolTip("Resolução pedida à webcam (resoluções menores deixam o vídeo mais fluido)")
        tb.addWidget(self.cam_res)

        self.act_video = QAction(self._icon(QStyle.StandardPixmap.SP_FileDialogDetailedView),
                                 "Abrir vídeo", self)
        self.act_video.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.act_video.setToolTip("Modo Vídeo a partir de um arquivo (útil sem webcam) (Ctrl+Shift+O)")
        self.act_video.triggered.connect(self.open_video_dialog)
        tb.addAction(self.act_video)
        tb.addSeparator()

        self.act_save = QAction(self._icon(QStyle.StandardPixmap.SP_DialogSaveButton), "Salvar", self)
        self.act_save.setShortcut(QKeySequence.StandardKey.Save)
        self.act_save.setToolTip("Salvar a imagem resultante (no vídeo: o quadro atual) (Ctrl+S)")
        self.act_save.triggered.connect(self.save)
        tb.addAction(self.act_save)

        self.act_undo = QAction(undo_icon(), "Desfazer", self)
        self.act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.act_undo.setToolTip("Desfaz o último filtro/operação/sticker (Ctrl+Z)")
        self.act_undo.triggered.connect(self.undo)
        tb.addAction(self.act_undo)

        self.act_reset = QAction(self._icon(QStyle.StandardPixmap.SP_BrowserReload), "Resetar", self)
        self.act_reset.setShortcut(QKeySequence("Ctrl+R"))
        self.act_reset.setToolTip("Remove todos os filtros, operações e stickers (Ctrl+R)")
        self.act_reset.triggered.connect(self.reset)
        tb.addAction(self.act_reset)

        self.btn_original = QToolButton()
        self.btn_original.setText("Ver original (segure)")
        self.btn_original.setIcon(self._icon(QStyle.StandardPixmap.SP_FileDialogContentsView))
        self.btn_original.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_original.setToolTip("Enquanto pressionado, mostra a imagem sem nenhum efeito")
        self.btn_original.pressed.connect(lambda: self._set_show_original(True))
        self.btn_original.released.connect(lambda: self._set_show_original(False))
        tb.addWidget(self.btn_original)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        self.mode_chip = QLabel()
        self.mode_chip.setObjectName("chip")
        tb.addWidget(self.mode_chip)

    # --- aba Filtros ----------------------------------------------------------
    def _build_filters_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.addWidget(_title("1. Escolha um filtro"))
        self.filter_tree = QTreeWidget()
        self.filter_tree.setHeaderHidden(True)
        self.filter_tree.setMinimumHeight(250)
        for category, specs in filters_by_category():
            parent = QTreeWidgetItem([f"{category} ({len(specs)})"])
            parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.filter_tree.addTopLevelItem(parent)
            for spec in specs:
                child = QTreeWidgetItem([spec.name])
                child.setData(0, Qt.ItemDataRole.UserRole, spec.key)
                child.setToolTip(0, spec.description)
                parent.addChild(child)
            parent.setExpanded(True)
        self.filter_tree.currentItemChanged.connect(self._on_filter_selected)
        lay.addWidget(self.filter_tree, 2)

        lay.addWidget(_title("2. Leia a descrição e ajuste os parâmetros"))
        self.filter_desc = QTextBrowser()
        self.filter_desc.setMinimumHeight(150)
        self.filter_desc.setHtml("<p style='color:#9a90a4'>Selecione um filtro na lista para ver "
                                 "o que ele faz e quais parâmetros podem ser configurados.</p>")
        lay.addWidget(self.filter_desc, 1)
        self.filter_form = ParamForm()
        self.filter_form.changed.connect(self._on_preview_input_changed)
        lay.addWidget(self.filter_form)

        lay.addWidget(_title("3. Onde aplicar"))
        self.filter_channels = ChannelSelector()
        self.filter_channels.changed.connect(self._on_preview_input_changed)
        lay.addWidget(self.filter_channels)

        self.filter_preview = QCheckBox("Prévia ao vivo (ver o resultado antes de aplicar)")
        self.filter_preview.toggled.connect(lambda: self._refresh(rerender=True))
        lay.addWidget(self.filter_preview)
        self.btn_apply_filter = QPushButton("Aplicar filtro")
        self.btn_apply_filter.setObjectName("primary")
        self.btn_apply_filter.setEnabled(False)
        self.btn_apply_filter.clicked.connect(self.apply_filter)
        lay.addWidget(self.btn_apply_filter)
        note = QLabel("Os filtros se acumulam: cada novo filtro é aplicado sobre o resultado do "
                      "anterior (veja a aba Pipeline).")
        note.setWordWrap(True)
        note.setStyleSheet("color:#9a90a4")
        lay.addWidget(note)
        return page

    # --- aba Operações --------------------------------------------------------
    def _build_operations_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        box = QGroupBox("Imagem B (segunda imagem)")
        bl = QGridLayout(box)
        self.operand_thumb = QLabel()
        self.operand_thumb.setFixedSize(150, 96)
        self.operand_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.operand_thumb.setStyleSheet("background:#120e16; border-radius:4px;")
        bl.addWidget(self.operand_thumb, 0, 0, 3, 1)
        self.operand_combo = compact_combo(QComboBox())
        self.operand_combo.addItem("— texturas e fotos prontas —", None)
        for folder in (TEXTURES_DIR, EXAMPLES_DIR):
            for path in sorted(folder.glob("*")):
                if path.suffix.lower() in IMAGE_EXTS:
                    self.operand_combo.addItem(f"{folder.name}/{path.name}", str(path))
        self.operand_combo.activated.connect(self._on_operand_combo)
        bl.addWidget(self.operand_combo, 0, 1)
        btn_load = QPushButton("Carregar imagem B do disco…")
        btn_load.clicked.connect(self._load_operand_dialog)
        bl.addWidget(btn_load, 1, 1)
        self.btn_operand_current = QPushButton("Usar imagem atual como B")
        self.btn_operand_current.setToolTip("Copia a foto/quadro atual (sem efeitos). Na webcam, use "
                                            "com 'Diferença absoluta' para ver o que se mexeu.")
        self.btn_operand_current.clicked.connect(self._operand_from_current)
        bl.addWidget(self.btn_operand_current, 2, 1)
        self.operand_label = QLabel()
        self.operand_label.setWordWrap(True)
        self.operand_label.setStyleSheet("color:#9a90a4")
        bl.addWidget(self.operand_label, 3, 0, 1, 2)
        self.operand_fit = compact_combo(QComboBox())
        for value, label in FIT_MODES:
            self.operand_fit.addItem(label, value)
        self.operand_fit.currentIndexChanged.connect(self._on_preview_input_changed)
        bl.addWidget(QLabel("Ajuste de B:"), 4, 0)
        bl.addWidget(self.operand_fit, 4, 1)
        lay.addWidget(box)

        lay.addWidget(_title("1. Escolha a operação (A = imagem atual)"))
        self.op_list = QListWidget()
        self.op_list.setMinimumHeight(190)
        for spec in OPERATIONS:
            item = QListWidgetItem(spec.name)
            item.setData(Qt.ItemDataRole.UserRole, spec.key)
            item.setToolTip(spec.description)
            self.op_list.addItem(item)
        self.op_list.currentItemChanged.connect(self._on_operation_selected)
        lay.addWidget(self.op_list)
        lay.addWidget(_title("2. Descrição e parâmetros"))
        self.op_desc = QTextBrowser()
        self.op_desc.setMinimumHeight(120)
        self.op_desc.setHtml("<p style='color:#9a90a4'>Selecione uma operação para ver a descrição.</p>")
        lay.addWidget(self.op_desc)
        self.op_form = ParamForm()
        self.op_form.changed.connect(self._on_preview_input_changed)
        lay.addWidget(self.op_form)
        lay.addWidget(_title("3. Onde aplicar"))
        self.op_channels = ChannelSelector()
        self.op_channels.changed.connect(self._on_preview_input_changed)
        lay.addWidget(self.op_channels)
        self.op_preview = QCheckBox("Prévia ao vivo (ver o resultado antes de aplicar)")
        self.op_preview.toggled.connect(lambda: self._refresh(rerender=True))
        lay.addWidget(self.op_preview)
        self.btn_apply_op = QPushButton("Aplicar operação")
        self.btn_apply_op.setObjectName("primary")
        self.btn_apply_op.setEnabled(False)
        self.btn_apply_op.clicked.connect(self.apply_operation)
        lay.addWidget(self.btn_apply_op)
        lay.addStretch()
        return page

    # --- aba Stickers ---------------------------------------------------------
    def _build_stickers_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.addWidget(_title("Escolha um sticker e clique na imagem"))
        tip = QLabel("Clique com o botão esquerdo para colar. Arraste um sticker já colado para "
                     "movê-lo e use o botão direito sobre ele para removê-lo.")
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#9a90a4")
        lay.addWidget(tip)
        self.sticker_list = QListWidget()
        self.sticker_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.sticker_list.setIconSize(QSize(76, 76))
        self.sticker_list.setGridSize(QSize(124, 112))
        self.sticker_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.sticker_list.setMovement(QListWidget.Movement.Static)
        self.sticker_list.setWordWrap(True)
        self.sticker_list.setMinimumHeight(250)
        for i, asset in enumerate(self.stickers):
            thumb = bgra_to_qimage(asset.frames[0]).scaled(
                76, 76, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            square = QPixmap(76, 76)  # centraliza num quadrado para alinhar os nomes
            square.fill(Qt.GlobalColor.transparent)
            painter = QPainter(square)
            painter.drawImage((76 - thumb.width()) // 2, (76 - thumb.height()) // 2, thumb)
            painter.end()
            if asset.animated:
                square = badge(square, "anim")
            item = QListWidgetItem(QIcon(square), asset.name)
            item.setData(Qt.ItemDataRole.UserRole, i)
            item.setToolTip(asset.describe_text())
            self.sticker_list.addItem(item)
        self.sticker_list.currentItemChanged.connect(self._on_sticker_selected)
        lay.addWidget(self.sticker_list, 1)
        self.sticker_desc = QLabel("Nenhum sticker selecionado.")
        self.sticker_desc.setWordWrap(True)
        lay.addWidget(self.sticker_desc)

        form = QGridLayout()
        self.sticker_size = QSlider(Qt.Orientation.Horizontal)
        self.sticker_size.setRange(5, 90)
        self.sticker_size.setValue(25)
        self.sticker_size_label = QLabel("25%")
        self.sticker_angle = QSlider(Qt.Orientation.Horizontal)
        self.sticker_angle.setRange(-180, 180)
        self.sticker_angle.setValue(0)
        self.sticker_angle_label = QLabel("0°")
        form.addWidget(QLabel("Tamanho (% da largura):"), 0, 0)
        form.addWidget(self.sticker_size, 0, 1)
        form.addWidget(self.sticker_size_label, 0, 2)
        form.addWidget(QLabel("Rotação:"), 1, 0)
        form.addWidget(self.sticker_angle, 1, 1)
        form.addWidget(self.sticker_angle_label, 1, 2)
        lay.addLayout(form)
        self.sticker_size.valueChanged.connect(self._on_sticker_settings)
        self.sticker_angle.valueChanged.connect(self._on_sticker_settings)

        row = QHBoxLayout()
        b1 = QPushButton("Remover último")
        b1.clicked.connect(self.remove_last_sticker)
        b2 = QPushButton("Remover todos")
        b2.clicked.connect(self.clear_stickers)
        row.addWidget(b1)
        row.addWidget(b2)
        lay.addLayout(row)

        return page

    # --- aba Pipeline ---------------------------------------------------------
    def _build_pipeline_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        info = QLabel("Efeitos aplicados em sequência (combinação de filtros): o resultado de cada "
                      "passo é a entrada do próximo. Selecione um passo para reordenar ou remover.")
        info.setWordWrap(True)
        lay.addWidget(info)
        self.step_list = QListWidget()
        self.step_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.step_list.setWordWrap(True)
        lay.addWidget(self.step_list, 1)
        grid = QGridLayout()
        buttons = (("Subir", lambda: self._move_step(-1)), ("Descer", lambda: self._move_step(1)),
                   ("Remover passo", self._remove_step), ("Desfazer último", self.undo))
        for i, (text, slot) in enumerate(buttons):
            b = QPushButton(text)
            b.clicked.connect(slot)
            grid.addWidget(b, i // 2, i % 2)
        lay.addLayout(grid)
        btn_reset = QPushButton("Resetar tudo (voltar à imagem original)")
        btn_reset.clicked.connect(self.reset)
        lay.addWidget(btn_reset)
        self.pipeline_stickers = QLabel()
        lay.addWidget(self.pipeline_stickers)
        return page

    # =========================================================================
    # Abrir foto / vídeo
    # =========================================================================
    def open_photo_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Abrir foto", str(EXAMPLES_DIR), IMAGE_FILTER)
        if path:
            self.load_photo(Path(path))

    def open_video_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Abrir vídeo", str(Path.home()), VIDEO_FILTER)
        if path:
            self.start_video(path)

    def _open_path(self, path: str) -> None:
        ext = Path(path).suffix.lower()
        if ext in IMAGE_EXTS:
            self.load_photo(Path(path))
        elif ext in VIDEO_EXTS:
            self.start_video(path)
        else:
            self._message(f"Formato não suportado: {Path(path).name}")

    def load_photo(self, path: Path) -> None:
        img = imread(path)
        if img is None:
            QMessageBox.warning(self, "Abrir foto", f"Não foi possível ler a imagem:\n{path}")
            return
        img, reduced = limit_size(ensure_bgr(img))
        self.stop_video(keep_frame=False)
        self._set_photo(img, Path(path).name)
        extra = " (reduzida para edição interativa)" if reduced else ""
        if self.pipeline.steps:
            extra += f" Os {len(self.pipeline)} efeitos do pipeline continuam aplicados (Ctrl+R para resetar)."
        self._message(f"Modo Foto: '{Path(path).name}' carregada — {img.shape[1]}×{img.shape[0]}.{extra}")

    def _set_photo(self, img: np.ndarray, name: str) -> None:
        self.source = img
        self.source_name = name
        self.mode = "photo"
        self.placements.clear()  # stickers são de cada foto; os filtros continuam valendo
        self._update_stickers_info()
        self._refresh(rerender=True)
        self._update_actions()

    def toggle_webcam(self) -> None:
        if self.mode == "video" and self.video is not None and self.video.is_camera:
            self.stop_video()
        else:
            self.start_video(self.cam_index.value())

    def start_video(self, source: int | str) -> None:
        self.stop_video(keep_frame=False)
        src = VideoSource(source, size=self.cam_res.currentData())
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            ok = src.open()
        finally:
            QApplication.restoreOverrideCursor()
        if not ok:
            what = f"a câmera {source}" if isinstance(source, int) else f"o vídeo:\n{source}"
            QMessageBox.warning(self, "Modo Vídeo",
                                f"Não foi possível abrir {what}.\n\nVerifique se outra aplicação está "
                                "usando a câmera, tente outro índice ou abra um arquivo de vídeo.")
            self._update_actions()
            return
        self.video = src
        self.mode = "video"
        self.source = None
        self.placements.clear()
        self._fail_count = 0
        self._update_stickers_info()
        self.video_timer.start(src.frame_interval_ms())
        name = f"webcam {source}" if src.is_camera else Path(str(source)).name
        self.source_name = name
        self._message(f"Modo Vídeo: capturando de {name}.")
        self._update_actions()

    def stop_video(self, keep_frame: bool = True) -> None:
        if self.video is None:
            return
        self.video_timer.stop()
        last = self.raw_frame
        self.video.release()
        self.video = None
        self.view.overlay_text = ""
        self.mode = "none"
        if keep_frame and last is not None:
            # O último quadro vira uma foto editável (dá para colar stickers com calma).
            self._set_photo(last.copy(), "quadro do vídeo")
            self._message("Vídeo parado. O último quadro virou uma foto editável (Modo Foto).")
        self._update_actions()

    # =========================================================================
    # Renderização
    # =========================================================================
    def _preview_step(self) -> Step | None:
        tab = self.tabs.currentIndex()
        try:
            if tab == 0 and self.filter_preview.isChecked():
                return self._make_filter_step()
            if tab == 1 and self.op_preview.isChecked():
                return self._make_operation_step()
        except ValueError:
            return None
        return None

    def _render(self, base: np.ndarray) -> np.ndarray:
        try:
            return self.pipeline.render(base, self._preview_step())
        except Exception as exc:  # um efeito com problema não derruba o app
            traceback.print_exc()
            self._message(f"Erro ao aplicar efeito: {exc}")
            try:
                return self.pipeline.render(base)
            except Exception:
                return base.copy()

    def _refresh(self, rerender: bool = True) -> None:
        """Atualiza a imagem exibida (no vídeo isso acontece a cada quadro)."""
        if self.mode == "photo" and self.source is not None:
            if rerender or self.filtered is None:
                self.filtered = self._render(self.source)
            self._show_output()
        elif self.mode == "none":
            self.view.set_image(None)
        self._update_anim_timer()

    def _now(self) -> float:
        return time.perf_counter() - self._t0

    def _show_output(self) -> None:
        base = self.source if self.mode == "photo" else self.raw_frame
        if base is None or self.filtered is None:
            return
        if self.show_original:
            out = base
        else:
            out = compose(self.filtered, self.placements, self._now())
        self.output = out
        self.view.set_image(out)
        self.status_size.setText(f"{base.shape[1]}×{base.shape[0]} px  ")

    def _on_video_tick(self) -> None:
        if self.video is None:
            return
        frame = self.video.read()
        if frame is None:
            self._fail_count += 1
            if self._fail_count > 60:
                self.stop_video()
                QMessageBox.warning(self, "Modo Vídeo", "A câmera parou de enviar imagens.")
            return
        self._fail_count = 0
        self.raw_frame = frame
        self.filtered = self._render(frame)
        self._show_output()
        fps = self.video.measured_fps
        self.status_fps.setText(f"{fps:.0f} fps  ")
        self.view.overlay_text = f"● AO VIVO  {fps:.0f} fps" if self.video.is_camera else f"▶ vídeo  {fps:.0f} fps"

    def _update_anim_timer(self) -> None:
        animated = self.mode == "photo" and any(p.asset.animated for p in self.placements)
        if animated and not self.anim_timer.isActive():
            self.anim_timer.start()
        elif not animated and self.anim_timer.isActive():
            self.anim_timer.stop()

    def _set_show_original(self, on: bool) -> None:
        self.show_original = on
        self._refresh(rerender=False)

    # =========================================================================
    # Filtros e operações
    # =========================================================================
    def _current_filter(self) -> EffectSpec | None:
        item = self.filter_tree.currentItem()
        key = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        return FILTERS_BY_KEY.get(key) if key else None

    def _current_operation(self) -> EffectSpec | None:
        item = self.op_list.currentItem()
        if item is None:
            return None
        key = item.data(Qt.ItemDataRole.UserRole)
        return next((o for o in OPERATIONS if o.key == key), None)

    def _make_filter_step(self) -> Step:
        spec = self._current_filter()
        if spec is None:
            raise ValueError("nenhum filtro selecionado")
        return Step(spec, self.filter_form.values(), self.filter_channels.mode(),
                    self.filter_channels.channel_color())

    def _make_operation_step(self) -> Step:
        spec = self._current_operation()
        if spec is None:
            raise ValueError("nenhuma operação selecionada")
        if self.operand is None:
            raise ValueError("carregue a imagem B")
        return Step(spec, self.op_form.values(), self.op_channels.mode(), self.op_channels.channel_color(),
                    operand=self.operand, operand_name=self.operand_name,
                    operand_fit=self.operand_fit.currentData())

    def _on_filter_selected(self, item: QTreeWidgetItem | None, _prev=None) -> None:
        spec = self._current_filter()
        self.btn_apply_filter.setEnabled(spec is not None)
        if spec is None:
            return
        # Requisito: mostrar a descrição ANTES de aplicar (na interface e no console).
        self.filter_desc.setHtml(spec.describe_html())
        self.filter_form.set_params(spec.params)
        log("\n" + "=" * 70 + "\nFiltro selecionado (ainda não aplicado):\n" + spec.describe_text())
        self._refresh(rerender=True)

    def _on_operation_selected(self, item: QListWidgetItem | None, _prev=None) -> None:
        spec = self._current_operation()
        self.btn_apply_op.setEnabled(spec is not None)
        if spec is None:
            return
        self.op_desc.setHtml(spec.describe_html())
        self.op_form.set_params(spec.params)
        log("\n" + "=" * 70 + "\nOperação selecionada (ainda não aplicada):\n" + spec.describe_text())
        self._refresh(rerender=True)

    def _on_preview_input_changed(self) -> None:
        if self._preview_step() is not None:
            self.debounce.start()

    def _on_tab_changed(self, _index: int) -> None:
        self._update_ghost()
        self._refresh(rerender=True)

    def _add_step(self, step: Step) -> None:
        step.order = next(_order)
        self.pipeline.add(step)
        log(f"[pipeline] + {step.label()}")
        self._update_pipeline_list()
        self._message(f"Aplicado: {step.label()}")
        self._refresh(rerender=True)

    def apply_filter(self) -> None:
        try:
            step = self._make_filter_step()
        except ValueError as exc:
            self._message(str(exc))
            return
        self.filter_preview.blockSignals(True)
        self.filter_preview.setChecked(False)  # senão a prévia aplicaria o filtro duas vezes
        self.filter_preview.blockSignals(False)
        self._add_step(step)

    def apply_operation(self) -> None:
        try:
            step = self._make_operation_step()
        except ValueError as exc:
            QMessageBox.information(self, "Operação", f"Não foi possível aplicar: {exc}.")
            return
        self.op_preview.blockSignals(True)
        self.op_preview.setChecked(False)
        self.op_preview.blockSignals(False)
        self._add_step(step)

    # --- imagem B ---------------------------------------------------------------
    def _set_operand(self, img: np.ndarray, name: str) -> None:
        self.operand = ensure_bgr(img)
        self.operand_name = name
        thumb = bgr_to_qimage(self.operand).scaled(
            self.operand_thumb.width(), self.operand_thumb.height(),
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.operand_thumb.setPixmap(QPixmap.fromImage(thumb))
        h, w = self.operand.shape[:2]
        self.operand_label.setText(f"B = {name} ({w}×{h}). Ela é ajustada ao tamanho de A automaticamente.")
        log(f"[operações] imagem B = {name} ({w}x{h})")
        self._on_preview_input_changed()

    def _load_default_operand(self) -> None:
        for i in range(1, self.operand_combo.count()):
            if "luz_quente" in self.operand_combo.itemText(i):
                self.operand_combo.setCurrentIndex(i)
                self._on_operand_combo(i)
                return

    def _on_operand_combo(self, index: int) -> None:
        path = self.operand_combo.itemData(index)
        if path:
            img = imread(path)
            if img is not None:
                self._set_operand(img, Path(path).name)

    def _load_operand_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Carregar imagem B", str(TEXTURES_DIR), IMAGE_FILTER)
        if path:
            img = imread(path)
            if img is None:
                QMessageBox.warning(self, "Imagem B", "Não foi possível ler a imagem.")
                return
            self._set_operand(limit_size(ensure_bgr(img))[0], Path(path).name)

    def _operand_from_current(self) -> None:
        base = self.source if self.mode == "photo" else self.raw_frame
        if base is None:
            self._message("Não há imagem atual para usar como B.")
            return
        self._set_operand(base.copy(), "quadro capturado" if self.mode == "video" else self.source_name)

    # =========================================================================
    # Stickers
    # =========================================================================
    def _selected_sticker(self) -> StickerAsset | None:
        item = self.sticker_list.currentItem()
        return self.stickers[item.data(Qt.ItemDataRole.UserRole)] if item else None

    def _on_sticker_selected(self, *_args) -> None:
        asset = self._selected_sticker()
        if asset is not None:
            self.sticker_desc.setText(asset.describe_text())
            log(f"[stickers] {asset.describe_text()}")
        self._update_ghost()
        self._refresh(rerender=False)

    def _on_sticker_settings(self) -> None:
        self.sticker_size_label.setText(f"{self.sticker_size.value()}%")
        self.sticker_angle_label.setText(f"{self.sticker_angle.value()}°")
        self._update_ghost()
        if self.mode == "photo":
            self._refresh(rerender=False)

    def _update_ghost(self) -> None:
        asset = self._selected_sticker()
        on_tab = self.tabs.currentIndex() == 2
        self.view.set_ghost(asset.frames[0] if (asset and on_tab) else None,
                            self.sticker_size.value() / 100.0, self.sticker_angle.value())

    def _placement_at(self, rx: float, ry: float) -> Placement | None:
        base = self.source if self.mode == "photo" else self.raw_frame
        if base is None:
            return None
        h, w = base.shape[:2]
        for p in reversed(self.placements):
            half_w = p.rel_width / 2
            half_h = p.rel_width * p.asset.aspect * w / h / 2
            if abs(rx - p.rx) <= half_w and abs(ry - p.ry) <= half_h:
                return p
        return None

    def _on_view_pressed(self, rx: float, ry: float, button: int) -> None:
        if self.mode == "none":
            return
        hit = self._placement_at(rx, ry)
        if button == Qt.MouseButton.RightButton.value:
            if hit is not None:
                self.placements.remove(hit)
                self._message(f"Sticker '{hit.asset.name}' removido.")
                self._update_stickers_info()
                self._refresh(rerender=False)
            return
        if button != Qt.MouseButton.LeftButton.value:
            return
        if hit is not None:  # arrastar sticker existente
            self._drag = hit
            self._drag_offset = (hit.rx - rx, hit.ry - ry)
            return
        asset = self._selected_sticker()
        if asset is None:
            if self.tabs.currentIndex() == 2:
                self._message("Selecione um sticker na lista antes de clicar na imagem.")
            return
        p = Placement(asset, rx, ry, self.sticker_size.value() / 100.0, self.sticker_angle.value(),
                      t0=self._now())
        p.order = next(_order)
        self.placements.append(p)
        log(f"[stickers] + {asset.name} em ({rx:.2f}, {ry:.2f}), largura {p.rel_width:.0%}")
        self._update_stickers_info()
        self._refresh(rerender=False)

    def _on_view_dragged(self, rx: float, ry: float) -> None:
        if self._drag is not None:
            self._drag.rx = rx + self._drag_offset[0]
            self._drag.ry = ry + self._drag_offset[1]
            self._refresh(rerender=False)

    def _on_view_released(self, _rx: float, _ry: float) -> None:
        self._drag = None

    def remove_last_sticker(self) -> None:
        if self.placements:
            p = self.placements.pop()
            self._message(f"Sticker '{p.asset.name}' removido.")
            self._update_stickers_info()
            self._refresh(rerender=False)

    def clear_stickers(self) -> None:
        self.placements.clear()
        self._update_stickers_info()
        self._refresh(rerender=False)

    # =========================================================================
    # Pipeline, desfazer, resetar, salvar
    # =========================================================================
    def _update_pipeline_list(self) -> None:
        current = self.step_list.currentRow()
        self.step_list.clear()
        for i, step in enumerate(self.pipeline.steps, 1):
            self.step_list.addItem(f"{i}. {step.label()}")
        if 0 <= current < self.step_list.count():
            self.step_list.setCurrentRow(current)
        self.tabs.setTabText(3, f"Pipeline ({len(self.pipeline)})")
        self._update_actions()

    def _update_stickers_info(self) -> None:
        n = len(self.placements)
        self.pipeline_stickers.setText(f"Stickers colados: {n}")
        self._update_actions()
        self._update_anim_timer()

    def _move_step(self, delta: int) -> None:
        row = self.step_list.currentRow()
        if row < 0:
            return
        new = self.pipeline.move(row, delta)
        self._update_pipeline_list()
        self.step_list.setCurrentRow(new)
        self._refresh(rerender=True)

    def _remove_step(self) -> None:
        row = self.step_list.currentRow()
        if row < 0:
            self._message("Selecione um passo na lista.")
            return
        step = self.pipeline.steps[row]
        self.pipeline.remove(row)
        log(f"[pipeline] - {step.label()}")
        self._update_pipeline_list()
        self._refresh(rerender=True)

    def undo(self) -> None:
        last_step = max(self.pipeline.steps, key=lambda s: getattr(s, "order", -1), default=None)
        last_sticker = max(self.placements, key=lambda p: getattr(p, "order", -1), default=None)
        step_order = getattr(last_step, "order", -1) if last_step else -1
        sticker_order = getattr(last_sticker, "order", -1) if last_sticker else -1
        if last_step is None and last_sticker is None:
            self._message("Nada para desfazer.")
            return
        if step_order >= sticker_order:
            self.pipeline.steps.remove(last_step)
            log(f"[pipeline] desfeito: {last_step.label()}")
            self._message(f"Desfeito: {last_step.spec.name}")
            self._update_pipeline_list()
            self._refresh(rerender=True)
        else:
            self.placements.remove(last_sticker)
            self._message(f"Desfeito: sticker '{last_sticker.asset.name}'")
            self._update_stickers_info()
            self._refresh(rerender=False)

    def reset(self) -> None:
        self.pipeline.clear()
        self.placements.clear()
        for chk in (self.filter_preview, self.op_preview):
            chk.blockSignals(True)
            chk.setChecked(False)
            chk.blockSignals(False)
        self.filter_channels.reset()
        self.op_channels.reset()
        log("[pipeline] RESET: todos os efeitos e stickers removidos.")
        self._message("Resetado: imagem original restaurada.")
        self._update_pipeline_list()
        self._update_stickers_info()
        self._refresh(rerender=True)

    def save(self) -> None:
        if self.output is None or self.mode == "none":
            QMessageBox.information(self, "Salvar", "Não há imagem para salvar.")
            return
        snapshot = self.output.copy()  # no vídeo, congela o quadro do momento do clique
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        default = OUTPUT_DIR / f"pgstories_{datetime.now():%Y%m%d_%H%M%S}.png"
        path, _ = QFileDialog.getSaveFileName(self, "Salvar imagem", str(default),
                                              "PNG (*.png);;JPEG (*.jpg *.jpeg);;BMP (*.bmp)")
        if not path:
            return
        if imwrite(path, snapshot):
            log(f"[salvar] imagem salva em {path}")
            self._message(f"Imagem salva em {path}")
        else:
            QMessageBox.warning(self, "Salvar", f"Não foi possível salvar em:\n{path}")

    # =========================================================================
    # Utilidades
    # =========================================================================
    def _message(self, text: str) -> None:
        self.statusBar().showMessage(text, 8000)

    def _update_actions(self) -> None:
        has_image = self.mode != "none"
        self.act_save.setEnabled(has_image)
        self.act_reset.setEnabled(bool(self.pipeline.steps or self.placements))
        self.act_undo.setEnabled(bool(self.pipeline.steps or self.placements))
        is_cam = self.mode == "video" and self.video is not None and self.video.is_camera
        self.act_webcam.setText("Parar webcam" if is_cam else "Iniciar webcam")
        self.act_webcam.setIcon(stop_icon() if is_cam else play_icon())
        if self.mode == "video":
            chip, label = "MODO VÍDEO", f"Modo Vídeo · {self.source_name}  "
        elif self.mode == "photo":
            chip, label = "MODO FOTO", f"Modo Foto · {self.source_name}  "
        else:
            chip, label = "SEM IMAGEM", "Nenhuma imagem carregada  "
            self.status_size.setText("")
            self.status_fps.setText("")
        if self.mode != "video":
            self.status_fps.setText("")
        self.mode_chip.setText(chip)
        self.status_mode.setText(label)

    def _print_banner(self) -> None:
        log("=" * 70)
        log("PG Stories — editor de imagens e vídeo (Processamento Gráfico, Grau B)")
        log("Ctrl+O abrir foto | Ctrl+K webcam | Ctrl+Shift+O abrir vídeo | Ctrl+S salvar")
        log("Ctrl+Z desfazer | Ctrl+R resetar | clique na imagem = colar sticker")
        log(f"Filtros: {sum(len(s) for _, s in filters_by_category())} | Operações: {len(OPERATIONS)} | "
            f"Stickers: {len(self.stickers)}")
        log("=" * 70)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.video_timer.stop()
        if self.video is not None:
            self.video.release()
        super().closeEvent(event)
