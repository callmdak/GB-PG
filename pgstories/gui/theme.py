"""Tema escuro da interface (estilo Fusion + folha de estilos)."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

ACCENT = "#E1306C"

STYLESHEET = f"""
QMainWindow, QWidget {{ font-size: 10pt; }}
QToolBar {{ spacing: 4px; padding: 4px; border: none; background: #1d1724; }}
QToolButton {{ padding: 5px 8px; border-radius: 6px; }}
QToolButton:hover {{ background: #3a2d47; }}
QToolButton:checked {{ background: #5a2a48; }}
QTabWidget::pane {{ border: 1px solid #3a2d47; border-radius: 6px; top: -1px; }}
QTabBar::tab {{ padding: 7px 12px; background: #241c2d; border: 1px solid #3a2d47;
               border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px; }}
QTabBar::tab:selected {{ background: #3a2d47; color: white; }}
QPushButton {{ padding: 6px 10px; border-radius: 6px; background: #2e2438; border: 1px solid #45375a; }}
QPushButton:hover {{ background: #3d3049; }}
QPushButton:disabled {{ color: #7d7288; }}
QPushButton#primary {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7b3fe4, stop:0.55 {ACCENT}, stop:1 #f7894a);
    color: white; font-weight: bold; padding: 9px; border: none; }}
QPushButton#primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8d55f0, stop:0.55 #ec4c80, stop:1 #ff9b60); }}
QPushButton#primary:disabled {{ background: #4a4052; color: #9a90a4; }}
QTreeWidget, QListWidget, QTextBrowser {{ background: #17121d; border: 1px solid #3a2d47; border-radius: 6px; }}
QTreeWidget::item, QListWidget::item {{ padding: 3px; }}
QTreeWidget::item:selected, QListWidget::item:selected {{ background: #5a2a48; color: white; }}
QGroupBox {{ border: 1px solid #3a2d47; border-radius: 6px; margin-top: 12px; padding-top: 8px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #e9b3cc; }}
QLabel#step {{ color: #e9b3cc; font-weight: bold; margin-top: 4px; }}
QLabel#chip {{ background: #5a2a48; color: white; border-radius: 9px; padding: 3px 10px; font-weight: bold; }}
QStatusBar {{ background: #1d1724; }}
QScrollArea {{ border: none; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid #9a8aab; border-radius: 3px;
                        background: #17121d; }}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: #f59ac0; }}
QCheckBox::indicator:disabled {{ border-color: #4a4052; background: #2a2231; }}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor("#201a27"))
    pal.setColor(QPalette.ColorRole.WindowText, QColor("#ece6f2"))
    pal.setColor(QPalette.ColorRole.Base, QColor("#17121d"))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#241c2d"))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#2e2438"))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.Text, QColor("#ece6f2"))
    pal.setColor(QPalette.ColorRole.Button, QColor("#2e2438"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor("#ece6f2"))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.Link, QColor("#f59ac0"))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#7d7288"))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#7d7288"))
    app.setPalette(pal)
    app.setStyleSheet(STYLESHEET)
