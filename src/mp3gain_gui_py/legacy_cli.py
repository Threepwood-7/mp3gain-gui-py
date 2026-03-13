"""Legacy-compatible command-line entrypoint.

Legacy Pointers:
- LEGACY_PTR:CLI_SWITCH_SURFACE
"""

from __future__ import annotations

import sys

from .legacy_cli_parser import parse_legacy_args
from .legacy_cli_runtime import (
    default_options,
    emit_album_summary,
    handle_check_only_path,
    handle_info_request,
    init_processor,
    prepare_album_summary,
    print_table_header,
    process_standard_path,
)

_parse_legacy_args = parse_legacy_args

__all__ = ["_parse_legacy_args", "main", "parse_legacy_args"]


def main(argv: list[str] | None = None) -> int:
    """Run legacy-compatible CLI argument handling and file operations.

    Legacy pointer: LEGACY_PTR:CLI_SWITCH_SURFACE.
    """
    try:
        args = parse_legacy_args(argv)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    info_result = handle_info_request(args)
    if info_result is not None:
        return info_result

    if not args.files:
        print("ERROR: no input files", file=sys.stderr)
        return 1

    print_table_header(args)
    try:
        processor = init_processor()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    options = default_options(args)
    existing_paths = [path for path in args.files if path.exists()]
    skip_tag_updates = args.stored_tag_policy == "skip" and not args.undo_requested
    album_summary = prepare_album_summary(
        args,
        processor=processor,
        existing_paths=existing_paths,
    )

    failures = 0
    for path in args.files:
        if not path.exists():
            failures += 1
            if not args.quiet:
                print(f"{path}\tERROR\tmissing file")
            continue
        if handle_check_only_path(args, processor=processor, path=path):
            continue
        failures += process_standard_path(
            args,
            processor=processor,
            path=path,
            options=options,
            skip_tag_updates=skip_tag_updates,
            existing_paths=existing_paths,
            album_summary=album_summary,
        )

    emit_album_summary(args, album_summary)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
