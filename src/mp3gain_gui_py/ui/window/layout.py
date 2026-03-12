"""WindowLayoutCoordinator — builds the central widget layout."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QTableView,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from ..._model.file_list_model import FileListModel
    from .._main_window import MainWindow


class WindowLayoutCoordinator:
    """Constructs and wires the central widget for *window*."""

    def __init__(self, window: MainWindow, model: FileListModel) -> None:
        self._window = window

        # ── File list view ────────────────────────────────────────────────────
        self.file_view = QTableView(window)
        self.file_view.setObjectName("file_list_view")
        self.file_view.setModel(model)
        self.file_view.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.file_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.file_view.setAlternatingRowColors(True)
        self.file_view.setSortingEnabled(False)
        hdr = self.file_view.horizontalHeader()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.file_view.setColumnWidth(0, 420)
        self.file_view.verticalHeader().setVisible(False)

        # ── Target volume spinbox ─────────────────────────────────────────────
        vol_label = QLabel("Target volume (dB):", window)
        self.target_volume_spin = QDoubleSpinBox(window)
        self.target_volume_spin.setObjectName("target_volume_spin")
        self.target_volume_spin.setRange(0.0, 150.0)
        self.target_volume_spin.setSingleStep(0.5)
        self.target_volume_spin.setDecimals(1)
        self.target_volume_spin.setValue(89.0)

        top_bar = QHBoxLayout()
        top_bar.addWidget(vol_label)
        top_bar.addWidget(self.target_volume_spin)
        top_bar.addStretch()

        # ── Progress bars ─────────────────────────────────────────────────────
        self.progress_file = QProgressBar(window)
        self.progress_file.setObjectName("progress_file")
        self.progress_file.setVisible(False)
        self.progress_file.setTextVisible(True)

        self.progress_total = QProgressBar(window)
        self.progress_total.setObjectName("progress_total")
        self.progress_total.setVisible(False)
        self.progress_total.setTextVisible(True)

        progress_row = QHBoxLayout()
        progress_row.addWidget(QLabel("File:", window))
        progress_row.addWidget(self.progress_file, 1)
        progress_row.addWidget(QLabel("Total:", window))
        progress_row.addWidget(self.progress_total, 1)

        # ── Assemble central widget ───────────────────────────────────────────
        central = QWidget(window)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addLayout(top_bar)
        layout.addWidget(self.file_view, 1)
        layout.addLayout(progress_row)

        window.setCentralWidget(central)

    def set_column_widths(self, widths: list[int]) -> None:
        hdr = self.file_view.horizontalHeader()
        for i, w in enumerate(widths):
            if i < hdr.count() and w > 0:
                hdr.resizeSection(i, w)

    def get_column_widths(self) -> list[int]:
        hdr = self.file_view.horizontalHeader()
        return [hdr.sectionSize(i) for i in range(hdr.count())]

    def show_progress(self, visible: bool) -> None:
        self.progress_file.setVisible(visible)
        self.progress_total.setVisible(visible)

    def set_progress(
        self, file_val: int, file_max: int, total_val: int, total_max: int
    ) -> None:
        self.progress_file.setMaximum(file_max)
        self.progress_file.setValue(file_val)
        self.progress_total.setMaximum(total_max)
        self.progress_total.setValue(total_val)

    def selected_rows(self) -> list[int]:
        sel = self.file_view.selectionModel()
        if sel is None:
            return []
        return sorted({idx.row() for idx in sel.selectedIndexes()})

    def accept_drops(self, enable: bool = True) -> None:
        self.file_view.setAcceptDrops(enable)
        self.file_view.setDragDropMode(
            QTableView.DragDropMode.DropOnly
            if enable
            else QTableView.DragDropMode.NoDragDrop
        )
