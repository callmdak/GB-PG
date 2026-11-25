"""PG Stories — protótipo de editor de imagens e vídeo (Processamento Gráfico, Grau B).

O pacote é dividido em duas partes:

* núcleo de processamento (sem interface): ``filters``, ``operations``,
  ``pipeline``, ``stickers``, ``video`` e ``io_utils``;
* interface gráfica em Qt (PySide6): subpacote ``gui``.

O núcleo pode ser usado e testado sem abrir nenhuma janela.
"""

__version__ = "1.0.0"
