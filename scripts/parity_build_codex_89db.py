"""Build codex-normalized files for parity validation.

Legacy Pointers:
- LEGACY_PTR:PARITY_BUILD_89DB
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import stat
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING

from parity_common import (
    CODEX_89DB_DIR,
    LEGACY_ORACLE_EXE,
    LEGACY_SOURCE_DIR,
    ORIGINAL_DIR,
    SNAPSHOT_DIR,
    SRC_DIR,
    default_parity_jobs,
    list_mp3_files,
    preserve_id3v1_tail,
    read_id3v1_tail,
    sha256_file,
)

from mp3gain_gui_py._legacy_exact import (
    LegacyCompatOptions,
    LegacyExactProcessor,
    db_to_legacy_steps,
    legacy_steps_to_db_exact,
)
from mp3gain_gui_py._mp3.file_info import scan_file, scan_max_amplitude
from mp3gain_gui_py._tags.reader import TagData
from mp3gain_gui_py._tags.writer import delete_tags, write_tags

TARGET_DB = 89.0
BUILD_SCHEMA_VERSION = 2
CACHE_FILENAME = "parity_build_cache.json"
LEGACY_PROFILES = ("skip_tags", "write_apev2", "write_id3")
REPO_ROOT = Path(__file__).resolve().parents[1]
TRACKED_SIGNATURE_PATHS = [
    Path(__file__).resolve(),
    (Path(__file__).resolve().parent / "parity_common.py").resolve(),
    (SRC_DIR / "mp3gain_gui_py" / "_engine" / "pcm_reader.py").resolve(),
    (SRC_DIR / "mp3gain_gui_py" / "_engine" / "replaygain.py").resolve(),
    (SRC_DIR / "mp3gain_gui_py" / "_mp3" / "gain_writer.py").resolve(),
    (SRC_DIR / "mp3gain_gui_py" / "_tags" / "writer.py").resolve(),
]

if TYPE_CHECKING:
    from argparse import Namespace


def _analyze_track_gain_db(path: Path) -> tuple[float, bool]:
    return LegacyExactProcessor().analyze_track_gain_db_with_fallback(path)


def _build_one(src_path: Path, dst_path: Path, *, legacy_profile: str) -> dict[str, object]:
    """Build one codex output file from an original source input.

    Legacy pointer: LEGACY_PTR:PARITY_BUILD_89DB.
    """
    if legacy_profile not in LEGACY_PROFILES:
        raise ValueError(f"Unsupported legacy profile: {legacy_profile}")

    # copyfile avoids carrying over source read-only attributes on Windows.
    shutil.copyfile(src_path, dst_path)
    os.chmod(dst_path, stat.S_IREAD | stat.S_IWRITE)

    processor = LegacyExactProcessor()
    tag_format = "apev2" if legacy_profile != "write_id3" else "id3"
    stored_tag_policy = "skip" if legacy_profile == "skip_tags" else "auto"
    options = LegacyCompatOptions(
        wrap_gain=False,
        preserve_timestamp=False,
        tag_format=tag_format,
        stored_tag_policy=stored_tag_policy,
    )
    initial_gain_db, used_alias_before = _analyze_track_gain_db(dst_path)
    steps = db_to_legacy_steps(initial_gain_db)
    applied_db = legacy_steps_to_db_exact(steps)

    processor.apply_steps(dst_path, left_steps=steps, options=options)

    post_gain_db, used_alias_after = _analyze_track_gain_db(dst_path)
    used_ascii_alias = used_alias_before or used_alias_after

    min_gain: int | None = None
    max_gain: int | None = None
    max_amplitude: float | None = None
    track_peak: float | None = None

    if legacy_profile != "skip_tags":
        min_gain, max_gain = scan_file(dst_path)
        max_amplitude = scan_max_amplitude(dst_path)
        track_peak = max_amplitude / 32768.0 if max_amplitude else 0.0

        # Rebuild MP3Gain tags from computed post-apply state.
        delete_tags(dst_path)
        write_tags(
            dst_path,
            TagData(
                tag_format=tag_format,
                track_gain_db=post_gain_db,
                track_peak=track_peak,
                undo_left=-steps,
                undo_right=-steps,
                undo_mode="N",
                min_gain=min_gain,
                max_gain=max_gain,
            ),
            tag_format=tag_format,
        )

        legacy_id3v1_tail = read_id3v1_tail(src_path)
        preserve_id3v1_tail(dst_path, legacy_id3v1_tail)

    return {
        "file": dst_path.name,
        "legacy_profile": legacy_profile,
        "stored_tag_policy": stored_tag_policy,
        "tag_format": tag_format,
        "used_ascii_alias": used_ascii_alias,
        "initial_gain_db": round(initial_gain_db, 6),
        "steps": steps,
        "applied_db": round(applied_db, 6),
        "post_gain_db": round(post_gain_db, 6),
        "post_volume_db": round(TARGET_DB - post_gain_db, 6),
        "min_gain": min_gain,
        "max_gain": max_gain,
        "track_peak": round(track_peak, 6) if track_peak is not None else None,
    }


def _build_one_worker(src_text: str, dst_text: str, legacy_profile: str) -> dict[str, object]:
    return _build_one(Path(src_text), Path(dst_text), legacy_profile=legacy_profile)


def _tool_signature_payload(*, legacy_profile: str) -> dict[str, object]:
    file_hashes: dict[str, str] = {}
    for path in TRACKED_SIGNATURE_PATHS:
        rel = path.relative_to(REPO_ROOT).as_posix()
        file_hashes[rel] = sha256_file(path)
    return {
        "schema_version": BUILD_SCHEMA_VERSION,
        "python_version": platform.python_version(),
        "legacy_profile": legacy_profile,
        "tracked_files": file_hashes,
    }


def _signature_hash(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _cache_path(snapshot_dir: Path) -> Path:
    return snapshot_dir / CACHE_FILENAME


def _load_cache(
    *,
    expected_signature_hash: str,
    snapshot_dir: Path,
) -> dict[str, dict[str, object]]:
    path = _cache_path(snapshot_dir)
    if not path.exists():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if parsed.get("tool_signature_hash") != expected_signature_hash:
        return {}
    files_obj = parsed.get("files")
    if isinstance(files_obj, dict):
        return {
            str(name): value
            for name, value in files_obj.items()
            if isinstance(name, str) and isinstance(value, dict)
        }
    return {}


def _write_cache(
    *,
    signature_payload: dict[str, object],
    signature_hash: str,
    files: dict[str, dict[str, object]],
    snapshot_dir: Path,
) -> None:
    payload = {
        "tool_signature": signature_payload,
        "tool_signature_hash": signature_hash,
        "files": files,
    }
    _cache_path(snapshot_dir).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _parse_args() -> Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--original-dir",
        type=Path,
        default=ORIGINAL_DIR,
        help="Directory containing original MP3 files.",
    )
    parser.add_argument(
        "--codex-dir",
        type=Path,
        default=CODEX_89DB_DIR,
        help="Destination directory for codex-normalized MP3 files.",
    )
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        default=SNAPSHOT_DIR,
        help="Directory where cache and report JSON files are written.",
    )
    parser.add_argument(
        "--legacy-profile",
        choices=LEGACY_PROFILES,
        default="write_apev2",
        help="Tag/storage profile: skip_tags emulates legacy /s s behavior.",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=default_parity_jobs(),
        help="Parallel worker count for per-file parity build (default: 4 or MP3GAIN_PARITY_JOBS).",
    )
    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="Ignore cache and rebuild all source files.",
    )
    return parser.parse_args()


def main() -> int:
    """Run parallel codex 89 dB build for parity comparison.

    Legacy pointer: LEGACY_PTR:PARITY_BUILD_89DB.
    """
    args = _parse_args()
    snapshot_dir = args.snapshot_dir
    original_dir = args.original_dir
    codex_dir = args.codex_dir
    legacy_profile = args.legacy_profile

    snapshot_dir.mkdir(parents=True, exist_ok=True)
    codex_dir.mkdir(parents=True, exist_ok=True)

    signature_payload = _tool_signature_payload(legacy_profile=legacy_profile)
    signature_hash = _signature_hash(signature_payload)
    cache_files = _load_cache(expected_signature_hash=signature_hash, snapshot_dir=snapshot_dir)

    source_files = list_mp3_files(original_dir)
    source_names = {path.name for path in source_files}

    removed: list[str] = []
    for stale in list_mp3_files(codex_dir):
        if stale.name not in source_names:
            os.chmod(stale, stat.S_IREAD | stat.S_IWRITE)
            stale.unlink()
            removed.append(stale.name)
            cache_files.pop(stale.name, None)

    for cached_name in list(cache_files.keys()):
        if cached_name not in source_names:
            cache_files.pop(cached_name, None)

    jobs_requested = max(1, args.jobs)
    jobs_used = min(jobs_requested, max(1, len(source_files)))

    input_hashes: dict[str, str] = {}
    pending: list[tuple[Path, Path]] = []
    results_by_name: dict[str, dict[str, object]] = {}
    errors_by_name: dict[str, str] = {}

    for src in source_files:
        name = src.name
        dst = codex_dir / name
        input_sha = sha256_file(src)
        input_hashes[name] = input_sha
        entry = cache_files.get(name)

        can_skip = False
        if not args.force_rebuild and entry is not None and dst.exists():
            cached_in = str(entry.get("input_sha256", ""))
            cached_sig = str(entry.get("tool_signature_hash", ""))
            cached_out = str(entry.get("output_sha256", ""))
            if (
                cached_in == input_sha
                and cached_sig == signature_hash
                and cached_out
                and sha256_file(dst) == cached_out
            ):
                cached_result = entry.get("result")
                if isinstance(cached_result, dict):
                    result = dict(cached_result)
                    result["file"] = name
                    result["skipped"] = True
                    results_by_name[name] = result
                    can_skip = True

        if not can_skip:
            pending.append((src, dst))

    if pending:
        with ProcessPoolExecutor(max_workers=min(jobs_used, len(pending))) as executor:
            future_map = {
                executor.submit(_build_one_worker, str(src), str(dst), legacy_profile): src.name
                for src, dst in pending
            }
            for future in as_completed(future_map):
                name = future_map[future]
                try:
                    result = future.result()
                    result["file"] = name
                    result["skipped"] = False
                    results_by_name[name] = result
                except Exception as exc:
                    errors_by_name[name] = f"{exc.__class__.__name__}: {exc}"

    results: list[dict[str, object]] = []
    for src in source_files:
        result = results_by_name.get(src.name)
        if result is not None:
            results.append(result)
            print(
                f"{src.name}: steps={result['steps']} post_gain_db={result['post_gain_db']} "
                f"skipped={result['skipped']}"
            )
            continue

        error_result: dict[str, object] = {
            "file": src.name,
            "error": errors_by_name.get(src.name, "unknown build error"),
            "skipped": False,
        }
        results.append(error_result)
        print(f"{src.name}: ERROR {error_result['error']}")

    for src in source_files:
        name = src.name
        if name not in results_by_name:
            continue
        dst = codex_dir / name
        cached_result = dict(results_by_name[name])
        cached_result.pop("skipped", None)
        cache_files[name] = {
            "input_sha256": input_hashes[name],
            "output_sha256": sha256_file(dst),
            "tool_signature_hash": signature_hash,
            "result": cached_result,
        }

    _write_cache(
        signature_payload=signature_payload,
        signature_hash=signature_hash,
        files=cache_files,
        snapshot_dir=snapshot_dir,
    )

    report_path = snapshot_dir / "parity_build_codex_89db.json"
    report = {
        "target_db": TARGET_DB,
        "legacy_oracle_exe": str(LEGACY_ORACLE_EXE),
        "legacy_source_dir": str(LEGACY_SOURCE_DIR),
        "original_dir": str(original_dir),
        "codex_dir": str(codex_dir),
        "snapshot_dir": str(snapshot_dir),
        "legacy_profile": legacy_profile,
        "jobs_requested": jobs_requested,
        "jobs_used": jobs_used,
        "tool_signature_hash": signature_hash,
        "removed_stale_files": removed,
        "failed_files": sorted(errors_by_name),
        "rebuilt_files": sum(
            1 for item in results if item.get("skipped") is False and "error" not in item
        ),
        "skipped_files": sum(1 for item in results if item.get("skipped") is True),
        "results": results,
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Build report written: {report_path}")
    return 0 if not errors_by_name else 1


if __name__ == "__main__":
    raise SystemExit(main())
