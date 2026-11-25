"""Descrição de parâmetros e de efeitos (filtros e operações).

Cada efeito do aplicativo é descrito por um :class:`EffectSpec`, que reúne
nome, categoria, descrição textual, lista de parâmetros configuráveis e a
função que faz o processamento. A interface usa essas informações para
montar os controles e para mostrar a descrição do filtro *antes* de aplicá-lo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np


@dataclass(frozen=True)
class Param:
    """Um parâmetro configurável de um efeito."""

    key: str
    label: str
    kind: str = "int"  # "int" | "float" | "choice" | "bool"
    default: Any = 0
    minimum: float = 0
    maximum: float = 100
    step: float = 1
    choices: tuple[tuple[str, str], ...] = ()  # (valor, rótulo)
    odd: bool = False  # tamanhos de kernel precisam ser ímpares
    help: str = ""
    short: str = ""  # nome curto usado no histórico (ex.: "k", "σ")

    def coerce(self, value: Any) -> Any:
        """Converte e limita um valor para o tipo/intervalo do parâmetro."""
        if value is None:
            value = self.default
        if self.kind == "bool":
            return bool(value)
        if self.kind == "choice":
            valid = [c[0] for c in self.choices]
            return value if value in valid else self.default
        if self.kind == "int":
            v = int(round(float(value)))
            v = int(min(max(v, self.minimum), self.maximum))
            if self.odd and v % 2 == 0:
                v = v + 1 if v + 1 <= self.maximum else v - 1
            return v
        v = float(value)
        return float(min(max(v, self.minimum), self.maximum))

    def format_value(self, value: Any) -> str:
        if self.kind == "bool":
            return "sim" if value else "não"
        if self.kind == "choice":
            return dict(self.choices).get(value, str(value))
        if self.kind == "float":
            return f"{value:.2f}".rstrip("0").rstrip(".") if value != 0 else "0"
        return str(value)

    def short_value(self, value: Any) -> str:
        """Versão curta do valor (para o histórico do pipeline)."""
        text = self.format_value(value)
        return text.split(" (")[0] if self.kind == "choice" else text

    def range_text(self) -> str:
        if self.kind == "bool":
            return f"sim/não; padrão: {self.format_value(self.default)}"
        if self.kind == "choice":
            opts = ", ".join(label for _, label in self.choices)
            return f"opções: {opts}; padrão: {self.format_value(self.default)}"
        extra = ", ímpar" if self.odd else ""
        return (f"{self.format_value(self.minimum)} a {self.format_value(self.maximum)}{extra}; "
                f"padrão: {self.format_value(self.default)}")


@dataclass(frozen=True)
class EffectSpec:
    """Descrição completa de um filtro ou operação."""

    key: str
    name: str
    category: str
    description: str
    fn: Callable[..., np.ndarray]
    params: tuple[Param, ...] = ()
    binary: bool = False  # True para operações com duas imagens
    tags: tuple[str, ...] = field(default=())

    def resolve(self, values: dict | None = None) -> dict:
        """Completa os valores com os padrões e garante tipos/intervalos válidos."""
        values = values or {}
        return {p.key: p.coerce(values.get(p.key, p.default)) for p in self.params}

    def defaults(self) -> dict:
        return self.resolve({})

    def summary(self, values: dict | None = None) -> str:
        """Texto curto com os valores atuais, ex.: ``k=9, sigma=0``."""
        values = self.resolve(values)
        return ", ".join(f"{p.short or p.key}={p.short_value(values[p.key])}"
                         for p in self.params)

    def describe_text(self) -> str:
        """Descrição em texto puro (usada no console)."""
        lines = [f"[{self.category}] {self.name}", f"  {self.description}"]
        if self.params:
            lines.append("  Parâmetros configuráveis:")
            for p in self.params:
                lines.append(f"   - {p.label} ({p.range_text()}): {p.help}")
        else:
            lines.append("  Não possui parâmetros configuráveis.")
        return "\n".join(lines)

    def describe_html(self) -> str:
        """Descrição em HTML (usada no painel da interface)."""
        html = [f"<h3 style='margin:0'>{self.name}</h3>",
                f"<p style='color:#b9a3c9;margin:2px 0 8px 0'>{self.category}</p>",
                f"<p>{self.description}</p>"]
        if self.params:
            html.append("<p><b>Parâmetros configuráveis:</b></p><ul style='margin-left:-20px'>")
            for p in self.params:
                html.append(f"<li><b>{p.label}</b> <i>({p.range_text()})</i>: {p.help}</li>")
            html.append("</ul>")
        else:
            html.append("<p><i>Não possui parâmetros configuráveis.</i></p>")
        return "".join(html)
