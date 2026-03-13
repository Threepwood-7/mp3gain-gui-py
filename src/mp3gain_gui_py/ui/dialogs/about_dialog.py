"""AboutDialog — credits and version information."""

from __future__ import annotations

from typing import final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ...constants import APP_DISPLAY_NAME, APP_VERSION


@final
class AboutDialog(QDialog):
    """Displays application version and author credits."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("about_dialog")
        self.setWindowTitle(f"About {APP_DISPLAY_NAME}")
        self.setMinimumWidth(380)

        text = (
            f"<h2>{APP_DISPLAY_NAME} {APP_VERSION}</h2>"
            "<p>Python/PySide6 port of the original MP3Gain application.</p>"
            "<p><b>Original MP3Gain authors:</b><br>"
            "Glen Sawyer — Windows GUI<br>"
            "David Robinson — ReplayGain algorithm</p>"
            "<p><b>Python port:</b> ThreepSoftwz</p>"
            "<p>Released under LGPL 2.1</p>"
        )
        label = QLabel(text, self)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        label.setOpenExternalLinks(True)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, self)
        _ = buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(label)
        layout.addWidget(buttons)
