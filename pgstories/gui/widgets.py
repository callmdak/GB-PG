"""Widgets auxiliares: controles de parâmetros e seletor de canal."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout,
                               QLabel, QSlider, QSpinBox, QVBoxLayout, QWidget)

from ..params import Param
from ..pipeline import CHANNEL_MODES


def compact_combo(combo: QComboBox, chars: int = 12) -> QComboBox:
    """Evita que textos longos alarguem o painel lateral."""
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(chars)
    return combo


class SliderSpin(QWidget):
    """Slider + caixa numérica sincronizados (para parâmetros int/float)."""

    valueChanged = Signal()

    def __init__(self, param: Param, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.param = param
        self._steps = max(1, round((param.maximum - param.minimum) / param.step))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, self._steps)
        if param.kind == "int":
            self.spin = QSpinBox()
            self.spin.setRange(int(param.minimum), int(param.maximum))
            self.spin.setSingleStep(int(param.step))
        else:
            self.spin = QDoubleSpinBox()
            self.spin.setRange(param.minimum, param.maximum)
            self.spin.setSingleStep(param.step)
            self.spin.setDecimals(2)
        self.spin.setMinimumWidth(70)
        self.spin.setKeyboardTracking(False)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.spin)
        self.slider.valueChanged.connect(self._from_slider)
        self.spin.valueChanged.connect(self._from_spin)
        self.set_value(param.default)

    def _to_index(self, v: float) -> int:
        return round((v - self.param.minimum) / self.param.step)

    def _from_slider(self, idx: int) -> None:
        v = self.param.coerce(self.param.minimum + idx * self.param.step)
        self.spin.blockSignals(True)
        self.spin.setValue(v)
        self.spin.blockSignals(False)
        self.valueChanged.emit()

    def _from_spin(self, v: float) -> None:
        v = self.param.coerce(v)
        if v != self.spin.value():  # ajusta valores pares em kernels ímpares
            self.spin.blockSignals(True)
            self.spin.setValue(v)
            self.spin.blockSignals(False)
        self.slider.blockSignals(True)
        self.slider.setValue(self._to_index(v))
        self.slider.blockSignals(False)
        self.valueChanged.emit()

    def set_value(self, v: float) -> None:
        v = self.param.coerce(v)
        for w in (self.slider, self.spin):
            w.blockSignals(True)
        self.spin.setValue(v)
        self.slider.setValue(self._to_index(v))
        for w in (self.slider, self.spin):
            w.blockSignals(False)

    def value(self):
        return self.param.coerce(self.spin.value())


class ParamForm(QWidget):
    """Formulário montado dinamicamente a partir da lista de :class:`Param`."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QFormLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._widgets: dict[str, QWidget] = {}
        self._params: tuple[Param, ...] = ()

    def set_params(self, params: tuple[Param, ...]) -> None:
        while self._layout.rowCount():
            self._layout.removeRow(0)
        self._widgets.clear()
        self._params = params
        if not params:
            note = QLabel("Este efeito não tem parâmetros.")
            note.setStyleSheet("color:#9a90a4; font-style: italic;")
            self._layout.addRow(note)
            return
        for p in params:
            if p.kind == "bool":
                w = QCheckBox()
                w.setChecked(bool(p.default))
                w.toggled.connect(self.changed)
            elif p.kind == "choice":
                w = compact_combo(QComboBox())
                for value, label in p.choices:
                    w.addItem(label, value)
                w.setCurrentIndex(max(0, w.findData(p.default)))
                w.currentIndexChanged.connect(self.changed)
            else:
                w = SliderSpin(p)
                w.valueChanged.connect(self.changed)
            w.setToolTip(p.help)
            label = QLabel(p.label)
            label.setToolTip(p.help)
            self._layout.addRow(label, w)
            self._widgets[p.key] = w

    def values(self) -> dict:
        out = {}
        for p in self._params:
            w = self._widgets[p.key]
            if isinstance(w, QCheckBox):
                out[p.key] = w.isChecked()
            elif isinstance(w, QComboBox):
                out[p.key] = w.currentData()
            else:
                out[p.key] = w.value()
        return out


class ChannelSelector(QWidget):
    """Escolha de onde aplicar o efeito: imagem inteira (RGB/cinza) ou um canal."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.combo = compact_combo(QComboBox())
        for value, label in CHANNEL_MODES:
            self.combo.addItem(label, value)
        self.colored = QCheckBox("Canal isolado na cor do canal (senão, em cinza)")
        self.colored.setToolTip("Com um único canal escolhido, a imagem principal mostra só esse canal: "
                                "colorido (ex.: vermelho para R) ou em tons de cinza.")
        self.colored.setChecked(True)
        self.colored.setEnabled(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.combo)
        layout.addWidget(self.colored)
        self.combo.currentIndexChanged.connect(self._on_change)
        self.colored.toggled.connect(self.changed)

    def _on_change(self) -> None:
        self.colored.setEnabled(self.mode() in ("r", "g", "b"))
        self.changed.emit()

    def mode(self) -> str:
        return self.combo.currentData()

    def channel_color(self) -> bool:
        return self.colored.isChecked()

    def reset(self) -> None:
        self.combo.setCurrentIndex(0)
        self.colored.setChecked(True)
