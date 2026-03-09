"""Compare codex output against mp3gain reference output.

Legacy Pointers:
- LEGACY_PTR:PARITY_COMPARE_STRICT
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import zip_longest
from pathlib import Path
from typing import TYPE_CHECKING

from parity_common import (
    CODEX_89DB_DIR,
    REFERENCE_89DB_DIR,
    SNAPSHOT_DIR,
    default_parity_jobs,
    has_id3v1_tag,
    list_mp3_files,
    read_raw_mp3gain_tags,
    run_mp3gain_table,
    sha256_file,
)

from mp3gain_gui_py._mp3.frame_parser import (
    find_next_frame,
    global_gain_offsets,
    has_xing_or_info_tag,
    parse_frame_header,
)

if TYPE_CHECKING:
    from argparse import Namespace
    from pathlib import Path

TRACK_GAIN_TOLERANCE_DB = 0.01
PEAK_TOLERANCE = 0.00002
MAX_AMPLITUDE_TOLERANCE = PEAK_TOLERANCE * 32768.0


def _peek8_bits(data: bytes, byte_off: int, bit_off: int) -> int:
    word = (data[byte_off] << 8) | data[byte_off + 1]
    word >>= 8 - bit_off
    return word & 0xFF


def _id3v2_end(data: bytes) -> int:
    if len(data) < 10 or data[:3] != b"ID3":
        return 0
    id3_size = (
        (data[9] & 0x7F)
        | ((data[8] & 0x7F) << 7)
        | ((data[7] & 0x7F) << 14)
        | ((data[6] & 0x7F) << 21)
    )
    return min(len(data), 10 + id3_size)


def _has_id3v1(data: bytes) -> bool:
    return len(data) >= 128 and data[-128:-125] == b"TAG"


def _find_trailer_start(data: bytes) -> int:
    pos = len(data)
    while True:
        old = pos
        if pos >= 128 and data[pos - 128 : pos - 125] == b"TAG":
            pos -= 128
            continue
        if pos >= 15:
            footer = data[pos - 15 : pos]
            if footer[6:15] == b"LYRICS200" and footer[:6].isdigit():
                lyrics_len = int(footer[:6])
                start = pos - 15 - lyrics_len
                if start >= 0 and data[start : start + 11] == b"LYRICSBEGIN":
                    pos = start
                    continue
        if pos == old:
            break
    return pos


def _ape_region_start(data: bytes) -> int | None:
    trailer_start = _find_trailer_start(data)
    if trailer_start < 32:
        return None
    footer = data[trailer_start - 32 : trailer_start]
    if footer[:8] != b"APETAGEX":
        return None
    tag_length = int.from_bytes(footer[12:16], "little")
    if tag_length < 32 or tag_length > trailer_start:
        return None
    return trailer_start - tag_length


def _semantic_bucket(data: bytes, offset: int) -> str:
    if offset < _id3v2_end(data):
        return "container.id3v2"
    if _has_id3v1(data) and offset >= len(data) - 128:
        return "container.id3v1"
    ape_start = _ape_region_start(data)
    trailer_start = _find_trailer_start(data)
    if ape_start is not None and ape_start <= offset < trailer_start:
        return "metadata.apev2"
    if offset >= trailer_start:
        return "container.trailing_tags"
    return "audio.mpeg_stream"


def first_byte_mismatch(reference: Path, codex: Path) -> dict[str, object] | None:
    ref = reference.read_bytes()
    cod = codex.read_bytes()
    shared = min(len(ref), len(cod))
    for i in range(shared):
        if ref[i] != cod[i]:
            return {
                "offset": i,
                "reference_byte": ref[i],
                "codex_byte": cod[i],
                "semantic_bucket": _semantic_bucket(ref, i),
            }
    if len(ref) != len(cod):
        longer = "reference" if len(ref) > len(cod) else "codex"
        return {
            "offset": shared,
            "reason": "length_mismatch",
            "longer_file": longer,
            "reference_size": len(ref),
            "codex_size": len(cod),
            "semantic_bucket": _semantic_bucket(ref if longer == "reference" else cod, shared),
        }
    return None


def _suite_name(filename: str) -> str:
    stem = Path(filename).stem
    if stem.isdigit():
        value = int(stem)
        if 1 <= value <= 7:
            return "numeric_1_7"
    upper = stem.upper()
    if upper.startswith("M") and upper[1:].isdigit():
        return "m_suite"
    return "external_or_other"


def _iter_frame_global_gain(data: bytes) -> list[tuple[int, list[int]]]:
    rows: list[tuple[int, list[int]]] = []
    pos = 0
    frame_index = 0
    first_audio_frame = True

    if data[:3] == b"ID3":
        id3_size = (
            (data[9] & 0x7F)
            | ((data[8] & 0x7F) << 7)
            | ((data[7] & 0x7F) << 14)
            | ((data[6] & 0x7F) << 21)
        )
        pos = 10 + id3_size

    while True:
        pos = find_next_frame(data, pos)
        if pos < 0:
            break

        header = parse_frame_header(data, pos)
        if header is None:
            pos += 1
            continue
        if pos + header.frame_size_bytes > len(data):
            break

        if first_audio_frame:
            first_audio_frame = False
            if has_xing_or_info_tag(data, pos, header):
                pos += header.frame_size_bytes
                continue

        gains: list[int] = []
        for byte_off, bit_off in global_gain_offsets(header):
            abs_byte = pos + byte_off
            if abs_byte + 1 >= len(data):
                continue
            gains.append(_peek8_bits(data, abs_byte, bit_off))
        rows.append((frame_index, gains))
        frame_index += 1
        pos += header.frame_size_bytes

    return rows


def first_global_gain_mismatch(reference: Path, codex: Path) -> dict[str, object] | None:
    """Return first frame-global_gain mismatch between oracle and codex outputs.

    Legacy pointer: LEGACY_PTR:PARITY_COMPARE_STRICT.
    """
    ref_rows = _iter_frame_global_gain(reference.read_bytes())
    codex_rows = _iter_frame_global_gain(codex.read_bytes())

    for ref_item, codex_item in zip_longest(ref_rows, codex_rows):
        if ref_item is None:
            return {"reason": "extra_frame_in_codex", "frame_index": codex_item[0]}  # type: ignore[index]
        if codex_item is None:
            return {"reason": "missing_frame_in_codex", "frame_index": ref_item[0]}

        ref_index, ref_gains = ref_item
        codex_index, codex_gains = codex_item
        if ref_index != codex_index:
            return {
                "reason": "frame_index_mismatch",
                "reference_frame_index": ref_index,
                "codex_frame_index": codex_index,
            }
        if ref_gains != codex_gains:
            for field_index, (ref_gain, codex_gain) in enumerate(
                zip_longest(ref_gains, codex_gains, fillvalue=-1)
            ):
                if ref_gain != codex_gain:
                    return {
                        "reason": "global_gain_field_mismatch",
                        "frame_index": ref_index,
                        "field_index": field_index,
                        "reference_gain": ref_gain,
                        "codex_gain": codex_gain,
                    }
    return None


def _parse_gain_db(text: str) -> float | None:
    value = text.strip()
    if value.endswith(" dB"):
        value = value[:-3].strip()
    try:
        return float(value)
    except ValueError:
        return None


def _parse_float(text: str) -> float | None:
    try:
        return float(text.strip())
    except ValueError:
        return None


def _is_tolerated_tag_diff(key: str, reference: str, codex: str, *, strict: bool) -> bool:
    if strict:
        return False
    upper = key.upper()
    if upper.startswith("REPLAYGAIN_") and upper.endswith("_GAIN"):
        ref_db = _parse_gain_db(reference)
        cod_db = _parse_gain_db(codex)
        return ref_db is not None and cod_db is not None and abs(ref_db - cod_db) <= TRACK_GAIN_TOLERANCE_DB
    if upper.startswith("REPLAYGAIN_") and upper.endswith("_PEAK"):
        ref_peak = _parse_float(reference)
        cod_peak = _parse_float(codex)
        return ref_peak is not None and cod_peak is not None and abs(ref_peak - cod_peak) <= PEAK_TOLERANCE
    return False


def _dict_diff(
    reference: dict[str, str],
    codex: dict[str, str],
    *,
    strict: bool,
) -> dict[str, object]:
    missing_in_codex = sorted(k for k in reference if k not in codex)
    missing_in_reference = sorted(k for k in codex if k not in reference)
    value_diffs: dict[str, dict[str, str]] = {}
    for key in sorted(set(reference) & set(codex)):
        if reference[key] != codex[key]:
            if _is_tolerated_tag_diff(key, reference[key], codex[key], strict=strict):
                continue
            value_diffs[key] = {"reference": reference[key], "codex": codex[key]}
    return {
        "missing_in_codex": missing_in_codex,
        "missing_in_reference": missing_in_reference,
        "value_diffs": value_diffs,
    }


def _is_tolerated_table_diff(key: str, reference: str, codex: str, *, strict: bool) -> bool:
    if strict:
        return False
    if key in {"db_gain", "album_db_gain"}:
        ref_db = _parse_float(reference)
        cod_db = _parse_float(codex)
        return ref_db is not None and cod_db is not None and abs(ref_db - cod_db) <= TRACK_GAIN_TOLERANCE_DB
    if key in {"max_amplitude", "album_max_amplitude"}:
        ref_amp = _parse_float(reference)
        cod_amp = _parse_float(codex)
        return (
            ref_amp is not None
            and cod_amp is not None
            and abs(ref_amp - cod_amp) <= MAX_AMPLITUDE_TOLERANCE
        )
    return False


def _table_row_diff(
    reference: dict[str, str],
    codex: dict[str, str],
    *,
    strict: bool,
) -> dict[str, object]:
    missing_in_codex = sorted(k for k in reference if k not in codex)
    missing_in_reference = sorted(k for k in codex if k not in reference)
    value_diffs: dict[str, dict[str, str]] = {}

    for key in sorted(set(reference) & set(codex)):
        ref_v = reference[key]
        cod_v = codex[key]
        if ref_v == cod_v:
            continue
        if _is_tolerated_table_diff(key, ref_v, cod_v, strict=strict):
            continue
        value_diffs[key] = {"reference": ref_v, "codex": cod_v}

    return {
        "missing_in_codex": missing_in_codex,
        "missing_in_reference": missing_in_reference,
        "value_diffs": value_diffs,
    }


def _compare_one_file(
    name: str,
    ref_path: Path,
    codex_path: Path,
    *,
    strict: bool,
) -> dict[str, object]:
    ref_size = ref_path.stat().st_size
    codex_size = codex_path.stat().st_size
    ref_hash = sha256_file(ref_path)
    codex_hash = sha256_file(codex_path)
    ref_id3v1 = has_id3v1_tag(ref_path)
    codex_id3v1 = has_id3v1_tag(codex_path)

    file_item: dict[str, object] = {
        "size_match": ref_size == codex_size,
        "hash_match": ref_hash == codex_hash,
        "reference_size": ref_size,
        "codex_size": codex_size,
        "reference_sha256": ref_hash,
        "codex_sha256": codex_hash,
        "reference_has_id3v1": ref_id3v1,
        "codex_has_id3v1": codex_id3v1,
        "id3v1_match": ref_id3v1 == codex_id3v1,
    }

    global_gain_mismatch = first_global_gain_mismatch(ref_path, codex_path)
    if global_gain_mismatch is not None:
        file_item["first_global_gain_mismatch"] = global_gain_mismatch
    if ref_hash != codex_hash:
        byte_mismatch = first_byte_mismatch(ref_path, codex_path)
        if byte_mismatch is not None:
            file_item["first_byte_mismatch"] = byte_mismatch

    ref_tags = read_raw_mp3gain_tags(ref_path)
    codex_tags = read_raw_mp3gain_tags(codex_path)
    tag_diff = _dict_diff(ref_tags, codex_tags, strict=strict)

    return {
        "file": name,
        "file_item": file_item,
        "global_gain_ok": global_gain_mismatch is None,
        "container_ok": ref_id3v1 == codex_id3v1,
        "tag_diff": tag_diff,
    }


def _parse_args() -> Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("quick", "full"),
        default="quick",
        help="quick=compare-only, full=oracle+build+compare.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Use zero-tolerance metadata checks.",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=default_parity_jobs(),
        help="Worker count for per-file compare/build operations.",
    )
    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="Only for --mode full: force parity build to ignore cache.",
    )
    return parser.parse_args()


def _run_step(command: list[str], *, cwd: Path) -> None:
    completed = subprocess.run(command, cwd=cwd, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(command)}")


def _run_full_pipeline(*, jobs: int, force_rebuild: bool) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    python_exe = sys.executable

    _run_step([python_exe, "scripts/parity_oracle_snapshot.py"], cwd=repo_root)

    build_cmd = [python_exe, "scripts/parity_build_codex_89db.py", "--jobs", str(jobs)]
    if force_rebuild:
        build_cmd.append("--force-rebuild")
    _run_step(build_cmd, cwd=repo_root)


def main() -> int:
    """Run parity compare workflow and emit consolidated report.

    Legacy pointer: LEGACY_PTR:PARITY_COMPARE_STRICT.
    """
    args = _parse_args()
    jobs = max(1, args.jobs)

    if args.mode == "full":
        _run_full_pipeline(jobs=jobs, force_rebuild=args.force_rebuild)

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = SNAPSHOT_DIR / "parity_compare_report.json"

    reference_files = list_mp3_files(REFERENCE_89DB_DIR)
    codex_files = list_mp3_files(CODEX_89DB_DIR)
    reference_map = {path.name: path for path in reference_files}
    codex_map = {path.name: path for path in codex_files}

    report: dict[str, object] = {
        "files": {},
        "table_mismatches": {},
        "tag_mismatches": {},
        "suite_rollups": {},
        "summary": {},
        "statuses": {},
    }
    file_report: dict[str, object] = report["files"]  # type: ignore[assignment]
    table_mismatches: dict[str, object] = report["table_mismatches"]  # type: ignore[assignment]
    tag_mismatches: dict[str, object] = report["tag_mismatches"]  # type: ignore[assignment]
    statuses: dict[str, str] = report["statuses"]  # type: ignore[assignment]
    suite_rollups: dict[str, dict[str, int]] = report["suite_rollups"]  # type: ignore[assignment]

    common_names = sorted(set(reference_map) & set(codex_map))
    file_set_mismatch = sorted(reference_map) != sorted(codex_map)

    if file_set_mismatch:
        report["file_set_mismatch"] = {
            "missing_in_codex": sorted(set(reference_map) - set(codex_map)),
            "extra_in_codex": sorted(set(codex_map) - set(reference_map)),
        }

    results: list[dict[str, object]] = []
    if common_names:
        with ThreadPoolExecutor(max_workers=min(jobs, len(common_names))) as executor:
            future_map = {
                executor.submit(
                    _compare_one_file,
                    name,
                    reference_map[name],
                    codex_map[name],
                    strict=args.strict,
                ): name
                for name in common_names
            }
            for future in as_completed(future_map):
                results.append(future.result())

    results_by_name = {str(item["file"]): item for item in results}
    global_gain_fail = False
    container_fail = False
    metadata_fail = False
    suite_tag_fail: dict[str, set[str]] = {"numeric_1_7": set(), "m_suite": set(), "external_or_other": set()}
    suite_table_fail: dict[str, set[str]] = {"numeric_1_7": set(), "m_suite": set(), "external_or_other": set()}
    suite_counts: dict[str, dict[str, int]] = {
        "numeric_1_7": {"files": 0, "global_gain_fail": 0, "container_fail": 0, "hash_fail": 0},
        "m_suite": {"files": 0, "global_gain_fail": 0, "container_fail": 0, "hash_fail": 0},
        "external_or_other": {"files": 0, "global_gain_fail": 0, "container_fail": 0, "hash_fail": 0},
    }

    for name in common_names:
        entry = results_by_name[name]
        file_item = entry["file_item"]
        file_report[name] = file_item
        suite = _suite_name(name)
        suite_counts[suite]["files"] += 1

        if entry["global_gain_ok"] is False:
            global_gain_fail = True
            suite_counts[suite]["global_gain_fail"] += 1
        if entry["container_ok"] is False:
            container_fail = True
            suite_counts[suite]["container_fail"] += 1
        if file_item["hash_match"] is False:
            suite_counts[suite]["hash_fail"] += 1

        tag_diff = entry["tag_diff"]
        if (
            tag_diff["missing_in_codex"]
            or tag_diff["missing_in_reference"]
            or tag_diff["value_diffs"]
        ):
            metadata_fail = True
            tag_mismatches[name] = tag_diff
            suite_tag_fail[suite].add(name)

    reference_table = run_mp3gain_table(reference_files, read_tag_only=True)
    codex_table = run_mp3gain_table(codex_files, read_tag_only=True)

    for key in sorted(set(reference_table) | set(codex_table)):
        if key not in reference_table:
            metadata_fail = True
            table_mismatches[key] = {"missing_in_reference": codex_table[key]}
            if key in reference_map or key in codex_map:
                suite_table_fail[_suite_name(key)].add(key)
            continue
        if key not in codex_table:
            metadata_fail = True
            table_mismatches[key] = {"missing_in_codex": reference_table[key]}
            if key in reference_map or key in codex_map:
                suite_table_fail[_suite_name(key)].add(key)
            continue
        row_diff = _table_row_diff(reference_table[key], codex_table[key], strict=args.strict)
        if (
            row_diff["missing_in_codex"]
            or row_diff["missing_in_reference"]
            or row_diff["value_diffs"]
        ):
            metadata_fail = True
            table_mismatches[key] = row_diff
            if key in reference_map or key in codex_map:
                suite_table_fail[_suite_name(key)].add(key)

    summary: dict[str, object] = report["summary"]  # type: ignore[assignment]
    byte_identical_files = sum(
        1 for v in file_report.values() if isinstance(v, dict) and v.get("hash_match") is True
    )
    summary["reference_files"] = len(reference_files)
    summary["codex_files"] = len(codex_files)
    summary["byte_identical_files"] = byte_identical_files
    summary["mode"] = args.mode
    summary["strict"] = args.strict
    summary["jobs_used"] = min(jobs, max(1, len(common_names)))
    summary["thresholds"] = {
        "track_gain_db": 0.0 if args.strict else TRACK_GAIN_TOLERANCE_DB,
        "peak": 0.0 if args.strict else PEAK_TOLERANCE,
        "max_amplitude": 0.0 if args.strict else MAX_AMPLITUDE_TOLERANCE,
    }

    audio_structure_ok = not file_set_mismatch and not global_gain_fail
    metadata_ok = not file_set_mismatch and not metadata_fail
    container_ok = not file_set_mismatch and not container_fail
    byte_identity_ok = byte_identical_files == len(common_names) and not file_set_mismatch
    byte_identity_blocking = args.strict
    overall_ok = (
        audio_structure_ok
        and metadata_ok
        and container_ok
        and ((not byte_identity_blocking) or byte_identity_ok)
    )

    statuses["audio_structure_parity"] = "PASS" if audio_structure_ok else "FAIL"
    statuses["metadata_parity"] = "PASS" if metadata_ok else "FAIL"
    statuses["container_parity"] = "PASS" if container_ok else "FAIL"
    statuses["byte_identity"] = (
        "PASS" if byte_identity_ok else "FAIL"
    )
    summary["byte_identity_blocking"] = byte_identity_blocking
    summary["status"] = "PASS" if overall_ok else "FAIL"
    summary["suite_gates"] = {
        "numeric_1_7": "PASS"
        if suite_counts["numeric_1_7"]["files"] > 0
        and suite_counts["numeric_1_7"]["global_gain_fail"] == 0
        and len(suite_tag_fail["numeric_1_7"]) == 0
        and len(suite_table_fail["numeric_1_7"]) == 0
        and suite_counts["numeric_1_7"]["hash_fail"] == 0
        else "FAIL",
        "m_suite": "PASS"
        if suite_counts["m_suite"]["files"] > 0
        and suite_counts["m_suite"]["global_gain_fail"] == 0
        and len(suite_tag_fail["m_suite"]) == 0
        and len(suite_table_fail["m_suite"]) == 0
        and suite_counts["m_suite"]["hash_fail"] == 0
        else "FAIL",
        "combined": "PASS" if overall_ok else "FAIL",
    }

    for suite_name, counts in suite_counts.items():
        suite_rollups[suite_name] = {
            "files": counts["files"],
            "global_gain_fail": counts["global_gain_fail"],
            "container_fail": counts["container_fail"],
            "hash_fail": counts["hash_fail"],
            "tag_fail": len(suite_tag_fail[suite_name]),
            "table_fail": len(suite_table_fail[suite_name]),
        }

    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    if not overall_ok:
        print(f"FAIL parity comparison: {report_path}")
        return 1

    print(f"PASS parity comparison: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
