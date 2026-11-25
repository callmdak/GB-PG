"""Caminhos das pastas do projeto (assets, saídas)."""

from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_DIR / "assets"
STICKERS_DIR = ASSETS_DIR / "stickers"
TEXTURES_DIR = ASSETS_DIR / "texturas"
EXAMPLES_DIR = ASSETS_DIR / "exemplos"
OUTPUT_DIR = PROJECT_DIR / "saidas"
