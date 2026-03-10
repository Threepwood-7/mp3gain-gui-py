# mp3gain-gui-py

PySide6 port of MP3Gain GUI - ReplayGain analysis and gain adjustment

## Table of Contents

- [Features](#features)
- [Why?](#why)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Normalize Helper](#normalize-helper)
- [What Is ReplayGain?](#what-is-replaygain)
- [GUI Usage](#gui-usage)
- [Legacy CLI](#legacy-cli)
- [Legacy C Source Comparison (1.5.2 vs 1.6.2)](#legacy-c-source-comparison-152-vs-162)
- [Legacy VB6 Source Comparison (1.2.5 vs 1.3.4)](#legacy-vb6-source-comparison-125-vs-134)
- [C-Backend Performance Report (Migrated From PERF.md)](#c-backend-performance-report-migrated-from-perfmd)
- [Parity Harness](#parity-harness)
- [rgain3 Notes](#rgain3-notes)
- [Configuration](#configuration)
- [Logging](#logging)
- [Project Structure](#project-structure)
- [Architecture Patterns](#architecture-patterns)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Legal Disclaimer](#legal-disclaimer)

## Features

<!-- TODO: List key capabilities as bullet points. -->

## Why?

Not because the old code could not be replaced, nor because the new machines demanded this exact labor, but because some tools are bound to the hours in which we first learned to trust them, and in this loud and hurried age there is a quiet pleasure in taking what was built then, with its plain windows and stubborn switches, and carrying it forward so it may keep doing its work in the present tense.

So this port is as much affection as engineering: a way to keep a useful thing alive, to keep faith with the craft that made it, and to let software from the good old days stand up again in a new and crazier world without asking it to forget where it came from.

## Requirements

- **Python 3.13+**

- **Windows** (10 or later)

- **MinGW GCC** (required to build the vendored C runtime DLL)


## Installation

```bat
python scripts\windows\setup_env.py
```

Creates the local `.venv` by running `uv sync --locked` and falls back to `uv sync` when no lockfile is available yet.

Manual development alternative:

```bat
uv sync --group dev
```


## Usage

### Recommended

```bat
pyw scripts\windows\run_app_gui.pyw
```

### Direct

```bat
python -m mp3gain_gui_py
```

### Legacy CLI Entrypoint

```bat
python -m mp3gain_gui_py.legacy_cli /q /o /s r "song.mp3"
```

### Build C Backend (required runtime component)

```bat
python scripts\build_legacy_c_backend.py
```

`legacy_cli` and runtime processing call the vendored C backend DLL (via `ctypes`) as the canonical execution path.
The pure-Python runtime code is retained only as reference and is not maintained or tested.

### Normalize Helper

Normalize every MP3 in a directory using the legacy two-step flow, per file:

1. Analyze with `/q /o /s r`
2. Apply with `/q /g <steps> /t` when the computed final steps are non-zero

Final steps are computed with legacy step math:

`final_steps = analyzed_steps + db_to_legacy_steps(target_db - 89.0)`

Target dB is configurable via `--db` (default `89`), and parallelism is configurable via `--jobs` (default: CPU count).

#### `run_normalize.py` Arguments (What They Actually Do)

| Argument | What it controls | Practical effect |
|---|---|---|
| `src_dir` | Source MP3 discovery root | The script scans this directory for `.mp3` files and normalizes those files (or copies of them if `--dst-dir` is used). |
| `--db <float>` | Target loudness relative to 89 dB baseline | Converted to integer step offset with legacy math: `db_to_legacy_steps(db - 89.0)`. This offset is added to analyzed `MP3 gain` before apply. |
| `--recurse` | Discovery depth | If set, includes MP3 files in all subdirectories; otherwise only top-level files in `src_dir`. |
| `--dst-dir <path>` | Output location mode | If set, source files are copied (preserving relative layout) and normalization is applied to copies only. If omitted, files are normalized in place. |
| `--jobs <int>` | Parallel worker count | Number of concurrent file workers. Each worker still runs analyze then apply sequentially per file. Default is logical CPU count. |

#### Under-the-Hood `legacy_cli` Commands

For each file, `run_normalize.py` executes:

1. Analysis command

```bat
python -m mp3gain_gui_py.legacy_cli /q /o /s r "<file>"
```

2. Apply command (only if final steps is non-zero)

```bat
python -m mp3gain_gui_py.legacy_cli /q /g <final_steps> /t "<file>"
```

Switch semantics used by the helper:

| Switch | Meaning in this helper flow |
|---|---|
| `/q` | Quiet mode: suppresses non-essential chatter while preserving machine-parseable output. |
| `/o` | Tabular output mode used by the helper parser to extract `MP3 gain` integer steps from the file row. |
| `/s r` | Force recalculation from audio data and ignore existing gain tags during analysis. |
| `/g <steps>` | Directly apply an explicit integer MP3 gain step value (no recompute in apply phase). |
| `/t` | Apply using legacy temp-file write mode. |

#### Step Computation Details

`final_steps` is computed as:

```text
final_steps = analyzed_steps + db_to_legacy_steps(target_db - 89.0)
```

Examples:

| `--db` | Offset term `db_to_legacy_steps(db - 89.0)` | Meaning |
|---:|---:|---|
| `89` | `0` | Use analyzed steps as-is. |
| `87` | `-1` | Apply one step less than analyzed recommendation. |
| `81` | `-5` | Apply five steps less than analyzed recommendation. |
| `90.5` | `+1` | Apply one step more than analyzed recommendation. |

In place (default):

```bat
python scripts\run_normalize.py "C:\music\album"
```

Recurse through subdirectories:

```bat
python scripts\run_normalize.py "C:\music" --recurse
```

Copy to destination then normalize there (source files unchanged):

```bat
python scripts\run_normalize.py "C:\music" --dst-dir "C:\tmp\music-89db"
```

Recurse + preserve source-relative folder structure under destination:

```bat
python scripts\run_normalize.py "C:\music" --recurse --dst-dir "C:\tmp\music-89db"
```

Normalize to a different target dB:

```bat
python scripts\run_normalize.py "C:\music" --db 87
```

Set explicit parallelism:

```bat
python scripts\run_normalize.py "C:\music" --jobs 4
```

## What Is ReplayGain?

ReplayGain is a loudness normalization method. It measures perceived loudness and stores (or applies) gain so playback volume is consistent.

Key concepts:
- `Track Gain`: normalize each track independently to a reference loudness.
- `Album Gain`: normalize a whole album with one shared gain so relative song-to-song dynamics stay intact.
- `Peak`: max sample level; used to estimate clipping risk when gain is increased.
- `Clipping prevention`: lower recommended gain when needed to avoid overflow distortion.

ReplayGain can be applied in two broad ways:
- Metadata-only: write gain tags and let the player apply them at playback.
- Audio-data modification: directly change codec gain fields in the file.

`mp3gain` uses audio-data modification for MP3 global gain fields (with optional tags for undo/state). For MP3, effective changes are quantized to ~1.5 dB steps.

Important distinctions from the original MP3Gain FAQ:
- ReplayGain is not peak normalization. Two files can have similar peaks but very different perceived loudness.
- MP3Gain-style volume changes do not decode and re-encode MP3 audio. Volume is adjusted via MP3 gain fields, so repeated adjustments do not add transcoding loss.

## GUI Usage

The GUI is the primary workflow for day-to-day processing. It is designed to be fast on large file sets:

- runtime operations are DLL-backed (vendored legacy C backend),
- file work is parallelized through a process pool,
- worker count is auto-sized to logical CPU count (`min(cpu_count, file_count)`).

In practice, that means analysis/apply/delete actions process many files concurrently and usually complete much faster than single-threaded legacy flows.

### Typical Workflow

1. Launch the app:

```bat
pyw scripts\windows\run_app_gui.pyw
```

2. Add files or a folder:
- `Add Files...` for explicit file selection.
- `Add Folder...` for bulk import (`Include subfolders` is controlled in Options).

3. Set target loudness:
- Use `Target volume (dB)` in the main window (default `89.0`).

4. Analyze:
- `Track Analysis`: per-file gain/peak metrics.
- `Album Analysis`: computes album-group metrics and merges them into each file row.

5. Apply changes:
- `Apply Track Gain`
- `Apply Album Gain`
- `Apply Constant Gain...`
- `Undo Gain Change`
- `Delete Tags`

6. Watch progress/status:
- Per-file completion updates table rows.
- Progress bar and status text are updated while workers run.
- `Cancel` stops new submissions and cancels pending work.

### Parallel Execution Model (Why It Is Fast)

- `Track Analysis`, `Album Analysis`, `Apply`, and `Delete Tags` use `ProcessPoolExecutor`.
- Each file is processed in its own task; multiple tasks run at once up to CPU capacity.
- Album analysis/apply uses a two-phase model:
  1. per-group album metric computation,
  2. per-file execution with merged group result.
- C-backend calls happen inside worker processes, which avoids a single global Python thread bottleneck.

### Forced Normalize-on-Apply (Track + Album)

The GUI has two options in `Options -> Gain Writing`:

- `Force analyze+normalize on apply (track+album)` (default: enabled)
- `Apply even when computed step is 0` (default: disabled)

With forced mode enabled, apply actions do not trust stored tags for gain derivation. They recalculate from audio and then apply explicit legacy steps:

- Track apply per file:
  - analyze track gain from audio,
  - `analyzed_steps = db_to_legacy_steps(analyzed_track_gain_db)`,
  - `final_steps = analyzed_steps + db_to_legacy_steps(target_volume_db - 89.0)`,
  - if `final_steps == 0`, apply is skipped unless `Apply even when computed step is 0` is enabled.

- Album apply per group:
  - compute one album gain from audio for each folder group,
  - convert that to steps using the same offset formula,
  - apply that group step result to each file in the group.

With forced mode disabled, GUI apply falls back to tag-driven behavior (`track_gain_db` / `album_gain_db`) for compatibility.

## Legacy CLI

The project exposes a legacy-compatible CLI surface through:

```bat
python -m mp3gain_gui_py.legacy_cli [switches] <file1.mp3> [file2.mp3 ...]
```

Switches accept either `/` or `-` prefixes. Attached and separated values are supported (`/d1.5` and `/d 1.5`).

### Switch Reference

| Switch | Exact behavior in this repo | Interactions / caveats | Example |
|---|---|---|---|
| `/v` | Prints version-style banner text. | If no files are passed, command exits successfully after printing info. | `/v` |
| `/h` | Prints help usage/switch list. | Optional help topic may be attached (`/hwrap`) but is informational only. | `/h` |
| `/?` | Help mode matching legacy style. | With no files and no topic (`/?`), exit code is `1` (legacy parity). With topic (`/? wrap`), exits `0`. | `/? wrap` |
| `/q` | Quiet mode. Suppresses normal recommendation/apply chatter. | Errors still go to stderr and still fail command when applicable. | `/q /o /s r file.mp3` |
| `/o` | Tabular output mode (tab-separated). | Header shape depends on mode: regular analysis, check-only (`/s c`), or undo (`/u`). | `/o /s r file.mp3` |
| `/s c` | Check-only mode: read stored MP3Gain data, do not analyze audio or apply gain. | Best for inspecting existing tags quickly; combines well with `/o`. | `/q /o /s c file.mp3` |
| `/s d` | Delete MP3Gain tag data from files. | Tag deletion path; does not perform gain analysis/apply. | `/s d file.mp3` |
| `/s s` | Skip tag update mode during runtime processing. | Treats processing as "do not rely on/write runtime tag state" for non-undo paths. Useful when you want computation without MP3Gain tag mutation. | `/q /o /s s file.mp3` |
| `/s r` | Recalculate from audio data and clear/rebuild recalculated fields. | This is the forced analysis mode used by parity/perf harnesses and `run_normalize.py`. | `/q /o /s r file.mp3` |
| `/s i` | Select ID3 tag backend for MP3Gain tag read/write/delete operations. | Does not change analyze/apply math; controls which tag family is used for MP3Gain metadata operations in this invocation. | `/s i /s d file.mp3` |
| `/s a` | Select APEv2 tag backend for MP3Gain tag read/write/delete operations. | This is the default backend if neither `/s i` nor `/s a` is provided. | `/s a /s d file.mp3` |
| `/r` | Auto-apply Track gain path (per file). | If both `/r` and `/a` are present, last one wins. Subject to clipping rules unless `/c` or `/k` is used. | `/r /c /s r file.mp3` |
| `/a` | Auto-apply Album gain path (shared album step outcome). | If both `/r` and `/a` are present, last one wins. Album summary row appears in table mode where applicable. | `/a /c /s r file1.mp3 file2.mp3` |
| `/e` | Accepted for compatibility, but treated as unrecognized option text. | Emits `"I don't recognize option /e"` and does not alter execution behavior. | `/e file.mp3` |
| `/g <i>` | Directly apply explicit integer MP3 gain steps. | Bypasses recommend/analyze decision flow for apply. Often paired with `/t` in deterministic workflows. | `/q /g 3 /t file.mp3` |
| `/l <ch> <i>` | Single-channel direct step apply (`ch=0` left, `ch=1` right). | Accepts separated form (`/l 0 2`) and attached form (`/l0,2`, `/l0:2`, `/l0;2`). | `/l 1 -2 file.mp3` |
| `/m <i>` | Integer step modifier added to computed recommendation path. | Changes step math directly; can be combined with `/r` or `/a`. | `/r /m 1 /s r file.mp3` |
| `/d <n>` | Floating-point dB modifier added before step quantization. | Converted to legacy steps via quantized math, so final result may round to nearest step. | `/r /d -2 /s r file.mp3` |
| `/k` | Auto-clipping prevention. | If requested steps would clip, steps are reduced to the max non-clipping value. | `/r /k /s r file.mp3` |
| `/c` | Clipping override/confirmation. | Allows apply even when clipping risk exists (without auto-lowering). | `/r /c /s r file.mp3` |
| `/w` | Wrap gain arithmetic mode for legacy behavior. | Affects gain-byte boundary behavior and undo metadata mode (`W` vs `N`). | `/r /w /c /s r file.mp3` |
| `/p` | Preserve original file timestamps when writing tags. | Applies on tag write/delete operations that mutate metadata. | `/r /p /c /s r file.mp3` |
| `/t` | Enable legacy temp-file mutation mode during apply. | Frequently used in deterministic apply flows (`/g ... /t`). | `/q /g -1 /t file.mp3` |
| `/x` | Max-amplitude-focused analysis mode. | Gain recommendation fields are de-emphasized; primarily useful for legacy parity lanes. | `/o /x /s r file.mp3` |
| `/f` | Compatibility placeholder switch. | Parsed for compatibility; currently no distinct runtime behavior change in this port. | `/f /r /s r file.mp3` |
| `/u` | Undo prior change using stored MP3Gain undo metadata. | In table mode prints left/right undo step columns; no effect if no undo info exists. | `/u file.mp3` |

Behavior notes:
- `/r` and `/a`: last one wins.
- `/g` and `/l` are direct-apply paths and bypass regular recommendation flow.
- `/m` and `/d` modify recommendation math; `/g` and `/l` override with explicit apply steps.
- `/k` (auto-lower) and `/c` (allow clipping) are clipping-policy controls for apply paths.
- Legacy MP3 global gain math is step-based, so exact dB targets quantize to nearest step.
- `legacy_cli` runtime execution is DLL-backed from vendored C sources (`src/c/legacy/mp3gain-1_5_2-src` + `src/mp3gain_gui_py/_c_backend`).
- Pure-Python runtime code is reference-only and is not maintained or tested.
- There is no supported Python runtime fallback path; if DLL backend initialization fails, runtime commands fail.
- Local `mp3gain.exe` remains oracle-only for parity/benchmark scripts and must not be used as runtime backend.

### Tag Behavior and Player Compatibility

MP3Gain analysis/undo state is stored in MP3 tags by runtime operations that write metadata.

Practical guidance:
- Use `/s r` when you want forced recalculation from audio data.
- Use `/s s` when you want to avoid runtime MP3Gain tag mutation in normal processing paths.
- Use `/s d` to remove MP3Gain analysis/undo tags already written.
- Use `/s i` to target ID3-based MP3Gain metadata operations.
- Use `/s a` to target APEv2-based MP3Gain metadata operations (default).

Compatibility note (from MP3Gain FAQ experience):
- Some players with non-standard tag handling can display garbage metadata after MP3Gain-style tag writes. If that happens, prefer skip/delete-tag flows (`/s s`, `/s d`).

### Common Command Recipes

Analyze with recalculation (ignore tags):

```bat
python -m mp3gain_gui_py.legacy_cli /q /o /s r "song.mp3"
```

Track normalize near 89 dB baseline:

```bat
python -m mp3gain_gui_py.legacy_cli /q /r /c /s r /g 0 "song.mp3"
```

Track normalize lane equivalent to 87 dB and 81 dB:

```bat
python -m mp3gain_gui_py.legacy_cli /q /r /c /s r /g 0 /d -2 "song.mp3"
python -m mp3gain_gui_py.legacy_cli /q /r /c /s r /g 0 /d -8 "song.mp3"
```

Modifier lanes:

```bat
python -m mp3gain_gui_py.legacy_cli /q /r /c /s r /m 1 "song.mp3"
python -m mp3gain_gui_py.legacy_cli /q /r /c /s r /d 1.5 "song.mp3"
```

## Legacy C Source Comparison (1.5.2 vs 1.6.2)

This section records the current in-repo comparison between:

- `src/c/legacy/mp3gain-1_5_2-src`
- `src/c/legacy/mp3gain-1_6_2-src`

### Snapshot Inventory

| Metric | `1_5_2` | `1_6_2` |
|---|---:|---:|
| Total files | 54 | 21 |
| Common-path files | 21 | 21 |
| Identical common files | 14 | 14 |
| Changed common files | 7 | 7 |
| Files only in tree | 33 | 0 |

### Files Present Only In `1_5_2`

`1_6_2` does not include these paths:

```text
c_api_shim.c
c_api_shim.h
mpglibDBL/CVS/Entries
mpglibDBL/CVS/Repository
mpglibDBL/CVS/Root
mpglibDBL/README
mpglibDBL/VbrTag.h
mpglibDBL/bitstream.h
mpglibDBL/common.c
mpglibDBL/common.h
mpglibDBL/config.h
mpglibDBL/dct64_i386.c
mpglibDBL/dct64_i386.h
mpglibDBL/decode_i386.c
mpglibDBL/decode_i386.h
mpglibDBL/encoder.h
mpglibDBL/huffman.h
mpglibDBL/interface.c
mpglibDBL/interface.h
mpglibDBL/l2tables.h
mpglibDBL/lame-analysis.h
mpglibDBL/lame.h
mpglibDBL/layer1.c
mpglibDBL/layer1.h
mpglibDBL/layer2.c
mpglibDBL/layer2.h
mpglibDBL/layer3.c
mpglibDBL/layer3.h
mpglibDBL/machine.h
mpglibDBL/mpg123.h
mpglibDBL/mpglib.h
mpglibDBL/tabinit.c
mpglibDBL/tabinit.h
```

### Changed Common Files

Approximate line churn (`+added/-removed`) across changed common files:

| File | Churn | Note |
|---|---:|---|
| `mp3gain.c` | `+173/-310` | decode backend and runtime flow changes |
| `id3tag.c` | `+116/-3` | ReplayGain `TXXX` decode/write support and safety updates |
| `Makefile` | `+34/-18` | links `-lmpg123`, removes `mpglibDBL` object list |
| `apetag.c` | `+18/-4` | stronger tag bounds/offset validation |
| `lgpl.txt` | `+9/-13` | license text revision |
| `mp3gain.h` | `+2/-12` | version bump and reduced DLL prototype surface |
| `gain_analysis.c` | `+6/-6` | mostly macro naming/unit-expression cleanup |

`git diff --no-index --stat` on the two trees reports 40 changed paths with net large removals due to `mpglibDBL` absence in `1_6_2`.

### Key Behavioral/Build Differences

| Area | `1_5_2` | `1_6_2` |
|---|---|---|
| Decoder backend | bundled `mpglibDBL` decode path | external `libmpg123` decode path |
| Temp-write mode | historical temp-file switch behavior | temp-file mode is default; `-T` switches to direct modify |
| ReplayGain ID3 handling | RVA2 and mp3gain-private frame focus | adds case-insensitive `TXXX` ReplayGain parse/write (`replaygain_track_*`, `replaygain_album_*`, `replaygain_reference_loudness`) |
| APE/tag safety checks | fewer offset/length guards | extra validation for malformed offsets/lengths |
| `asWIN32DLL` header surface | includes `scanFile`, `beginAlbumScan`, `finishAlbumScan`, `changeGain` | only declares `changeGain` |
| Makefile linkage model | compiles local decoder objects (`mpglibDBL/*.c`) | links `-lmpg123`; no local `mpglibDBL` object list |
| Project shim presence | includes project `c_api_shim.c/.h` in vendored tree | imported upstream tree has no project shim files |

### Impact On This Repository

1. Current Python runtime and ctypes backend are wired to `src/c/legacy/mp3gain-1_5_2-src` plus project shim exports.
2. Switching runtime to `1_6_2` is not drop-in and requires shim port/adaptation to the `1_6_2` codebase.
3. Build pipeline would need `libmpg123` dependency handling and updated compile/link inputs.
4. CLI parity and byte-level output parity must be revalidated due to decode and tag behavior changes.
5. Canonical runtime remains `1_5_2`-based unless an explicit migration is completed.

## Legacy VB6 Source Comparison (1.2.5 vs 1.3.4)

This section records the current in-repo comparison between:

- `src/vbs/legacy/mp3gain-win-gui-1_2_5-src`
- `src/vbs/legacy/mp3gain-win-gui-1_3_4-src`

### Snapshot Inventory

| Metric | `1_2_5` | `1_3_4` |
|---|---:|---:|
| Total files | 39 | 41 |
| Common-path files | 39 | 39 |
| Identical common files | 33 | 33 |
| Changed common files | 6 | 6 |
| Files only in tree | 0 | 2 |

`git diff --no-index --stat` across both trees reports 8 changed paths and overall churn of `452 insertions(+), 84 deletions(-)`.

### Files Present Only In `1_3_4`

```text
basFixUnicodeFileName.bas
basUnicodeFileFind.bas
```

### Changed File Churn (Top Files)

Approximate line churn (`+added/-removed`) across changed common files:

| File | Churn | Note |
|---|---:|---|
| `frmMain.frm` | `+197/-39` | Unicode-aware file handling, command paths, and lookup logic |
| `basCommandOutput.bas` | `+58/-25` | process launch/pipe handling hardening and API declaration fixes |
| `basCommDialog.bas` | `+39/-14` | ANSI/Unicode open-save dialog branching |
| `Get Directory Dialog.bas` | `+14/-6` | Unicode-related directory dialog handling adjustments |
| `MP3Gain.vbp` | `+4/-2` | version bump + added Unicode helper modules |
| `Mp3Info.cls` | `+1/-0` | `mLongPathName` field for long-path restoration checks |

### Key Behavioral Differences

| Area | `1_2_5` | `1_3_4` |
|---|---|---|
| Unicode file discovery | no dedicated wide-char scanner module | adds `basUnicodeFileFind.bas` (`FindFirstFileW`/`FindNextFileW` path scanning) |
| Unicode filename repair | none | adds `basFixUnicodeFileName.bas` (`GetLongPathNameW`, `MoveFileW`) |
| Dialog API usage | `GetOpenFileNameA` / `GetSaveFileNameA` only | runtime branch to `GetOpenFileNameW` / `GetSaveFileNameW` when Unicode-capable OS detected |
| Main form file-key strategy | list item operations mostly keyed by display text | list item key path handling branches to short-path keys with long-path reconciliation |
| Command execution plumbing | older `STARTUPINFO`/pipe handling and less defensive handle setup | stricter structure declarations, startup init, duplicate-handle checks, output buffer resets |
| Project metadata | `MP3Gain.vbp` version 1.2.5 | `MP3Gain.vbp` version 1.3.4 with Unicode modules added |

### Semantics Relevant To Current Python Port

1. The largest VB delta (`frmMain.frm`) is primarily about Windows Unicode path robustness and command invocation path normalization.
2. `basUnicodeFileFind.bas` and `basFixUnicodeFileName.bas` encode behavior worth retaining as reference for non-ASCII/long-path edge cases in parity tooling.
3. `1_3_4` appears to be a compatibility/stability iteration over `1_2_5`, not a total workflow redesign.
4. VB6 legacy tree diffs are now documented in-repo to support traceability when deciding which GUI reference behavior should drive Python parity.

## C-Backend Performance Report (Migrated From PERF.md)

This section preserves the latest oracle-vs-Python performance/parity execution for `legacy_cli` after the C-DLL runtime migration.

### Purpose

This dataset supersedes the earlier python-only baseline run and reflects DLL-backed runtime behavior.

### Latest Execution (C-backed Python CLI)

| Field | Value |
|---|---|
| Date | `2026-03-10` |
| Source pool | `mp3-albums` |
| Random sample size | `6` files |
| Total sampled bytes | `46,178,377` (`~46.18 MB`) |
| Command log | `c:\tmp\mp3\89dbcodex\exec.log` |
| Machine report | `c:\tmp\mp3\89dbcodex\parity_perf_report.json` |
| Scenario outputs | `c:\tmp\mp3\89dbcodex\runs\` |

### Selected Files

Track titles are intentionally anonymized in documentation output.

1. `sample_01.mp3`
2. `sample_02.mp3`
3. `sample_03.mp3`
4. `sample_04.mp3`
5. `sample_05.mp3`
6. `sample_06.mp3`

### Scenario Matrix

| Scenario | Switches |
|---|---|
| `analysis_o_sr` | `/q /o /s r` |
| `g_89` | `/q /r /c /s r /g 0` |
| `g_87` | `/q /r /c /s r /g 0 /d -2` |
| `g_81` | `/q /r /c /s r /g 0 /d -8` |
| `m_plus_1` | `/q /r /c /s r /m 1` |
| `d_plus_1_5` | `/q /r /c /s r /d 1.5` |

### Parity Results

All scenarios passed:

1. `output_parity = True`
2. `byte_parity_all_files = True`
3. `oracle_returncode = 0`
4. `python_returncode = 0`

No byte mismatches were reported for any file in any scenario.

### Detailed Timing (Oracle vs Python DLL)

`ratio = python_elapsed / oracle_elapsed`

| Scenario | Oracle | Python DLL | Ratio | Delta |
|---|---:|---:|---:|---:|
| `analysis_o_sr` | `7.428429s` | `9.650772s` | `1.299x` | `+2.222343s` |
| `g_89` | `0.030019s` | `0.120492s` | `4.014x` | `+0.090473s` |
| `g_87` | `0.029601s` | `0.118373s` | `3.999x` | `+0.088772s` |
| `g_81` | `0.028959s` | `0.127494s` | `4.403x` | `+0.098535s` |
| `m_plus_1` | `7.888899s` | `5.210642s` | `0.661x` | `-2.678256s` |
| `d_plus_1_5` | `7.797092s` | `5.274918s` | `0.677x` | `-2.522175s` |

### Aggregate Timing

| Metric | Value |
|---|---:|
| Oracle total | `23.202999s` |
| Python DLL total | `20.502690s` |
| Aggregate ratio (`python/oracle`) | `0.8836x` |

Interpretation:

1. Python DLL path is slower for very short direct-gain lanes (`/g` family), where process/CLI overhead dominates.
2. Python DLL path is faster for longer apply lanes (`/m`, `/d`) in this sample.
3. Combined run time is better on Python DLL by about `11.64%`.

### Exact Commands

All commands executed in this run are stored verbatim in:

- `c:\tmp\mp3\89dbcodex\exec.log`

This includes:

1. Oracle commands (`C:\bin\mp3gain-win-1_2_5\mp3gain.exe ...`) for each scenario.
2. Python commands (`python -m mp3gain_gui_py.legacy_cli ...`) for each scenario.

## Parity Harness

Use the parity matrix harness to compare oracle CLI behavior vs Python CLI behavior across case catalogs.

```bat
hatch run python scripts/parity_cli_matrix.py --sample 2 --jobs 2
```

Default artifact output:
- `c:\tmp\pycompa\parity_cli_full_run_<ts>.json`
- `c:\tmp\pycompa\parity_cli_full_results_<ts>.json`
- `c:\tmp\pycompa\parity_cli_full_progress_<ts>.jsonl`
- `c:\tmp\pycompa\parity_cli_full_report_<ts>.xlsx`

## rgain3 Notes

[`rgain3`](https://github.com/chaudum/rgain3) is a Python ReplayGain toolkit focused on metadata-driven multi-format workflows (for example MP3/FLAC/MP4 via its scanner/writer toolchain).

Why this matters here:
- `mp3gain` parity is MP3 global-gain mutation focused.
- `rgain3` is a strong reference for metadata-centric ReplayGain flows and collection-wide album grouping.
- Future integration candidates include:
  - metadata-only scan/write modes,
  - collection/album-ID style workflows,
  - MP3 tag-format policy options aligned with broader ReplayGain ecosystems.

## References

- MP3Gain FAQ: https://mp3gain.sourceforge.net/faq.php
- ReplayGain overview: https://wiki.hydrogenaudio.org/index.php?title=ReplayGain
- rgain3 project: https://github.com/chaudum/rgain3

## Configuration

Application identity is defined in `src/mp3gain_gui_py/constants.py` and passed directly to `threep_commons`.

- configure QSettings with `threep_commons.paths.configure_qsettings(APP_IDENTITY, config_dir_override=...)`
- resolve runtime storage with `threep_commons.paths.resolve_app_data_dir(APP_IDENTITY, override_dir=...)`
- use `CONFIG_DIR` and `DATA_DIR` for environment overrides

### Forced Normalize-on-Apply (GUI + INI)

GUI `Apply Track Gain` and `Apply Album Gain` now support a persisted forced-normalization mode aligned with `scripts/run_normalize.py`.

INI keys:

| Key | Default | Effect |
|---|---:|---|
| `ops/force_apply_normalization` | `true` | Re-analyzes audio during apply and computes steps from fresh analysis, instead of using stored tag gain values. |
| `ops/apply_zero_step` | `false` | Controls whether files with computed final step `0` are still sent to apply (`true`) or treated as successful no-op (`false`). |

Options dialog checkboxes:

- `Force analyze+normalize on apply (track+album)`
- `Apply even when computed step is 0`

When forced mode is enabled:

- Track apply computes `analyzed_steps = db_to_legacy_steps(analyzed_track_gain_db)`.
- Album apply computes one album gain per folder group first, then maps that step result to each file in the group.
- Both use:
  - `final_steps = analyzed_steps + db_to_legacy_steps(target_volume_db - 89.0)`
- If `final_steps == 0`, behavior is controlled by `ops/apply_zero_step`.

When forced mode is disabled, GUI apply falls back to tag-driven gain selection (`track_gain_db` / `album_gain_db`) as before.

## Logging

Initialize runtime logging directly through `threep_commons.logging`.

```python
from mp3gain_gui_py.constants import APP_IDENTITY
from threep_commons.logging import setup_logging_from_identity

setup_logging_from_identity(APP_IDENTITY)
```


## Project Structure

```text
mp3gain-gui-py/
|-- pyproject.toml
|-- uv.lock
|-- src/
|   `-- mp3gain_gui_py/
|       |-- __init__.py
|       |-- __main__.py

|       |-- constants.py

|       `-- py.typed
|-- scripts/
|   |-- policy/
|   |   `-- check_standard.py
|   `-- windows/

|       |-- run_app.py
|       |-- run_app_gui.pyw

|       |-- run_tests.py
|       `-- setup_env.py
|-- tests/
|   |-- __init__.py

|   |-- conftest.py

|   |-- unit/
|   |   `-- __init__.py
|   `-- integration/

|       |-- __init__.py
|   `-- gui/
|       `-- __init__.py

`-- .pre-commit-config.yaml
```

## Architecture Patterns

- Keep top-level window/dialog classes thin and delegate feature logic to focused collaborators.
- Split large concerns into separate modules (actions/layout/operations/persistence/status) while preserving public imports.
- Split GUI tests by feature domain instead of building one large end-to-end test file.
- See `docs/architecture/qt_composition_playbook.md` for the reusable Qt decomposition workflow.
- Legacy traceability map: `docs/architecture/legacy_pointer_map.md` (`LEGACY_PTR:` anchors in code map Python behavior to legacy C/VB6 references).

## Development

```bat
hatch run test
hatch run test-cov
hatch run lint:check
hatch run lint:fmt
hatch run lint:types
hatch run lint:policy
hatch run lint:all
hatch build
```

## Troubleshooting

<!-- TODO: Document common issues and fixes. -->

---

<!-- legal-disclaimer:start -->
## Legal Disclaimer

THIS SOFTWARE IS PROVIDED "AS IS" AND "AS AVAILABLE," WITHOUT WARRANTIES OF ANY KIND, WHETHER EXPRESS, IMPLIED, STATUTORY, OR OTHERWISE, INCLUDING, WITHOUT LIMITATION, ANY IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, NON-INFRINGEMENT, ACCURACY, OR QUIET ENJOYMENT. TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, THE AUTHORS, CONTRIBUTORS, MAINTAINERS, DISTRIBUTORS, AND AFFILIATED PARTIES SHALL NOT BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, EXEMPLARY, OR PUNITIVE DAMAGES, OR FOR ANY LOSS OF DATA, PROFITS, GOODWILL, BUSINESS OPPORTUNITY, OR SERVICE INTERRUPTION, ARISING OUT OF OR RELATING TO THE USE OF, OR INABILITY TO USE, THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGES. THIS SOFTWARE HAS BEEN DEVELOPED, IN WHOLE OR IN PART, BY "INTELLIGENT TOOLS"; ACCORDINGLY, OUTPUTS MAY CONTAIN ERRORS OR OMISSIONS, AND YOU ASSUME FULL RESPONSIBILITY FOR INDEPENDENT VALIDATION, TESTING, LEGAL COMPLIANCE, AND SAFE OPERATION PRIOR TO ANY RELIANCE OR DEPLOYMENT.
<!-- legal-disclaimer:end -->
