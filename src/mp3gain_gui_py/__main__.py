"""Module entry point for ``python -m mp3gain_gui_py``."""

from __future__ import annotations

import sys


def main() -> int:
    from .app_controller import AppController

    ctrl = AppController(sys.argv)
    return ctrl.run()


if __name__ == "__main__":
    raise SystemExit(main())
