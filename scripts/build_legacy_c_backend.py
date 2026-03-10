"""Build the vendored MP3Gain legacy C backend DLL."""

from __future__ import annotations

import argparse

from mp3gain_gui_py._c_backend.build import build_backend


def main() -> int:
    parser = argparse.ArgumentParser(description="Build mp3gain legacy C backend DLL.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force rebuild even if output DLL is newer than sources.",
    )
    args = parser.parse_args()

    dll_path = build_backend(force=args.force)
    print(f"Built C backend DLL: {dll_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

