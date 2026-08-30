"""Localização centralizada dos recursos visuais da aplicação."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGO_PATH = PROJECT_ROOT / "resources" / "images" / "adega_do_bruninho_logo_transparent.png"


def logo_pixmap(width: int, height: int) -> QPixmap:
    """Carrega a marca em alta qualidade, mantendo proporção e transparência."""
    return QPixmap(str(LOGO_PATH)).scaled(
        width,
        height,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
