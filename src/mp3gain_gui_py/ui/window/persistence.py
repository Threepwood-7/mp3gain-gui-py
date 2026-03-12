"""WindowPersistenceCoordinator — geometry + column width save/restore."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QByteArray

if TYPE_CHECKING:
    from ..._settings.manager import SettingsManager
    from ..main_window import MainWindow
    from .layout import WindowLayoutCoordinator


class WindowPersistenceCoordinator:
    """Save and restore window geometry and column widths."""

    def __init__(
        self,
        window: MainWindow,
        settings: SettingsManager,
        layout: WindowLayoutCoordinator,
    ) -> None:
        self._window = window
        self._settings = settings
        self._layout = layout

    def save(self) -> None:
        self._settings.window_geometry = self._window.saveGeometry().data()
        self._settings.column_widths = self._layout.get_column_widths()
        self._settings.sync()

    def restore(self) -> None:
        geo = self._settings.window_geometry
        if geo:
            self._window.restoreGeometry(QByteArray(geo))

        widths = self._settings.column_widths
        if widths:
            self._layout.set_column_widths(widths)
