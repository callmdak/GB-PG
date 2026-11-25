"""PG Stories — protótipo de editor de imagens e vídeo (Processamento Gráfico, Grau B).

Execução (na raiz do projeto):
    python main.py                 # abre a interface
    python main.py foto.jpg        # já abre uma foto
    python main.py --webcam        # já inicia a webcam
    python main.py --video v.mp4   # já abre um arquivo de vídeo
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PG Stories — editor de imagens e vídeo")
    parser.add_argument("foto", nargs="?", help="foto para abrir ao iniciar")
    parser.add_argument("--webcam", nargs="?", const=0, type=int, metavar="ÍNDICE",
                        help="inicia a webcam (índice opcional, padrão 0)")
    parser.add_argument("--video", metavar="ARQUIVO", help="abre um arquivo de vídeo")
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args(sys.argv[1:])
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("PySide6 não está instalado. Rode: pip install -r requirements.txt")
        return 1

    from pgstories.gui.main_window import MainWindow
    from pgstories.gui.theme import apply_theme

    app = QApplication(sys.argv[:1])
    app.setApplicationName("PG Stories")
    apply_theme(app)
    window = MainWindow()
    window.show()

    if args.foto:
        window.load_photo(Path(args.foto))
    elif args.video:
        window.start_video(args.video)
    elif args.webcam is not None:
        window.cam_index.setValue(args.webcam)
        window.start_video(args.webcam)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
