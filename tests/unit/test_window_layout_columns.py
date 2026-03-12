from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QHeaderView, QMainWindow

from mp3gain_gui_py._model.file_list_model import FileListModel
from mp3gain_gui_py.ui.window.layout import WindowLayoutCoordinator

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def test_file_view_columns_are_interactive_resizable(qtbot: QtBot) -> None:
    window = QMainWindow()
    model = FileListModel(parent=window)
    layout = WindowLayoutCoordinator(window, model)
    qtbot.addWidget(window)

    header = layout.file_view.horizontalHeader()
    for column in range(header.count()):
        assert header.sectionResizeMode(column) == QHeaderView.ResizeMode.Interactive
