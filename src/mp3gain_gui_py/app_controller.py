"""AppController — application lifecycle manager."""

from __future__ import annotations

import sys
from typing import cast

from PySide6.QtWidgets import QApplication
from threep_commons.logging import setup_logging_from_identity
from threep_commons.paths import configure_qsettings, resolve_app_data_dir

from ._settings.manager import SettingsManager
from ._workers.worker_bridge import WorkerBridge
from .constants import (
    APP_DISPLAY_NAME,
    APP_IDENTITY,
    SETTINGS_APP_NAME,
    SETTINGS_ORG_NAME,
)


class AppController:
    """Owns the QApplication, settings, worker bridge, and main window."""

    def __init__(self, argv: list[str] | None = None) -> None:
        argv_list = argv if argv is not None else sys.argv

        configure_qsettings(APP_IDENTITY)
        resolve_app_data_dir(APP_IDENTITY)
        setup_logging_from_identity(APP_IDENTITY)

        existing = cast("QApplication | None", QApplication.instance())
        self.app: QApplication = (
            existing if existing is not None else QApplication(argv_list)
        )
        self.app.setApplicationName(SETTINGS_APP_NAME)
        self.app.setOrganizationName(SETTINGS_ORG_NAME)
        self.app.setApplicationDisplayName(APP_DISPLAY_NAME)
        self.app.setQuitOnLastWindowClosed(True)

        self.settings = SettingsManager()
        self.bridge = WorkerBridge(parent=self.app)

        # Import late to avoid circular dependency (ui needs controller)
        from .ui.main_window import MainWindow

        self.window = MainWindow(
            controller=self, settings=self.settings, bridge=self.bridge
        )

    def run(self) -> int:
        self.window.show()
        self.window.restore_session()
        return self.app.exec()

    def save_session(self) -> None:
        self.window.save_session()
        self.settings.sync()
