"""Legacy-compatible command-line entrypoint (subset).

Legacy Pointers:
- LEGACY_PTR:CLI_SWITCH_SURFACE
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ._legacy_exact import LegacyCompatOptions, LegacyExactProcessor, db_to_legacy_steps
from ._legacy_exact.math import legacy_steps_to_db_exact
from ._tags.reader import read_tags


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", help="Input MP3 files")
    parser.add_argument("-q", action="store_true", help="Quiet mode (supported)")
    parser.add_argument("-o", action="store_true", help="Print table output")
    parser.add_argument("-s", dest="scan_mode", default="", help="Use 'c' to read stored tags only")
    parser.add_argument("-r", action="store_true", help="Apply track gain")
    parser.add_argument("-u", action="store_true", help="Undo using MP3GAIN_UNDO")
    parser.add_argument("-k", action="store_true", help="Wrap gain values")
    parser.add_argument("-p", action="store_true", help="Preserve timestamps")
    parser.add_argument("-d", dest="db_mod", default=0.0, type=float, help="dB modifier")
    parser.add_argument("-g", dest="mp3_gain_mod", default=0, type=int, help="mp3 gain modifier")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run legacy-compatible CLI argument handling and file operations.

    Legacy pointer: LEGACY_PTR:CLI_SWITCH_SURFACE.
    """
    args = _parse_args(argv)
    processor = LegacyExactProcessor()
    options = LegacyCompatOptions(
        wrap_gain=args.k,
        preserve_timestamp=args.p,
        tag_format="apev2",
    )

    failures = 0
    for file_text in args.files:
        path = Path(file_text)
        if not path.exists():
            failures += 1
            if not args.q:
                print(f"{path}\tERROR\tmissing file")
            continue

        if args.u:
            result = processor.undo(path, options=options)
            if result.exit_code != 0:
                failures += 1
                if not args.q:
                    print(f"{path}\tERROR\t{result.message}")
            continue

        if args.scan_mode.lower() == "c":
            tags = read_tags(path)
            track_gain = tags.track_gain_db if tags.track_gain_db is not None else 0.0
            steps = db_to_legacy_steps(track_gain, mp3_gain_mod=args.mp3_gain_mod)
            db_gain = track_gain
            max_amp = (tags.track_peak or 0.0) * 32768.0
            min_gain = tags.min_gain if tags.min_gain is not None else 0
            max_gain = tags.max_gain if tags.max_gain is not None else 0
        else:
            raw_gain = processor.analyze_track_gain_db(path)
            db_gain = raw_gain + args.db_mod
            steps = db_to_legacy_steps(db_gain, mp3_gain_mod=args.mp3_gain_mod)
            max_amp = processor.analyze_max_amplitude(path)
            min_gain, max_gain = processor.analyze_minmax_gain(path)

        if args.r:
            result = processor.apply_steps(path, left_steps=steps, options=options)
            if result.exit_code != 0:
                failures += 1
                if not args.q:
                    print(f"{path}\tERROR\t{result.message}")
                continue

        if args.o and not args.q:
            print(
                f"{path}\t{steps}\t{db_gain:.6f}\t{max_amp:.6f}\t{max_gain}\t{min_gain}"
            )
        elif not args.q and not args.r and not args.u:
            print(
                f'Recommended "Track" dB change: {db_gain:.6f}\n'
                f'Recommended "Track" mp3 gain change: {steps}\n'
                f'Applied step dB (exact): {legacy_steps_to_db_exact(steps):.6f}'
            )

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
