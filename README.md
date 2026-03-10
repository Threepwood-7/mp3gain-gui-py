# mp3gain-gui-py

PySide6 port of MP3Gain GUI - ReplayGain analysis and gain adjustment

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Normalize Helper](#normalize-helper)
- [What Is ReplayGain?](#what-is-replaygain)
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

## Legacy CLI

The project exposes a legacy-compatible CLI surface through:

```bat
python -m mp3gain_gui_py.legacy_cli [switches] <file1.mp3> [file2.mp3 ...]
```

Switches accept either `/` or `-` prefixes. Attached and separated values are supported (`/d1.5` and `/d 1.5`).

### Switch Reference

| Switch | Meaning |
|---|---|
| `/v` | Show version-style info. |
| `/h`, `/?` | Show help text. `/? wrap` asks for wrap-topic help. |
| `/q` | Quiet mode (minimal status output). |
| `/o` | Tabular output (database-friendly fields). |
| `/s c` | Check stored gain/tag info only (no recalc). |
| `/s d` | Delete MP3Gain stored tag info. |
| `/s s` | Skip stored tag info (ignore read/write tags). |
| `/s r` | Force recalculation (do not read tag info). |
| `/s i` | Use ID3v2 backend for MP3Gain tag fields. |
| `/s a` | Use APEv2 backend for MP3Gain tag fields (legacy default). |
| `/r` | Apply Track gain automatically. |
| `/a` | Apply Album gain automatically. |
| `/e` | Skip album analysis even with multiple files (track-only behavior). |
| `/g <i>` | Apply explicit integer MP3 gain steps directly (no analysis). |
| `/l <ch> <i>` | Apply explicit integer steps to one channel only (stereo-only path). |
| `/m <i>` | Add integer step modifier to suggested gain. |
| `/d <n>` | Add floating-point dB modifier to suggested gain. |
| `/k` | Auto-lower gain to avoid clipping. |
| `/c` | Continue/apply despite clipping warning. |
| `/w` | Wrap gain arithmetic at boundaries (legacy wrap behavior). |
| `/p` | Preserve original file timestamps when mutating files. |
| `/t` | Use alternate write mode (legacy temp-file behavior switch). |
| `/x` | Max-amplitude-focused mode (analysis emphasis). |
| `/f` | Force mode for legacy compatibility paths. |
| `/u` | Undo prior MP3Gain change using stored undo metadata. |

Behavior notes:
- `/r` and `/a`: if both are present, the last one wins.
- `/g` and `/l` are direct apply modes (bypass normal analysis/recommend flow).
- Legacy MP3 global gain math is step-based, so exact dB targets can round to nearest step.
- `legacy_cli` runtime execution is DLL-backed from vendored C sources (`src/c/legacy/mp3gain-1_5_2-src` + `src/mp3gain_gui_py/_c_backend`).
- Pure-Python runtime code is reference-only and is not maintained or tested.
- There is no supported Python runtime fallback path; if DLL backend initialization fails, runtime commands fail.
- Local `mp3gain.exe` remains oracle-only for parity/benchmark scripts and must not be used as runtime backend.

### Tag Behavior and Player Compatibility

MP3Gain stores analysis/undo state in MP3 tags. Historically this is often APEv2 (`/s a`) and can also be ID3-based (`/s i`).

Practical guidance:
- Use `/s r` when you want forced recalculation and no tag reads.
- Use `/s s` when you want to skip both reading and writing MP3Gain tags.
- Use `/s d` to remove MP3Gain analysis/undo tags already written.

Compatibility note (from MP3Gain FAQ experience):
- Some players with non-standard tag handling can display garbage metadata after APEv2 tag writes. If that happens, prefer skip/delete-tag flows (`/s s`, `/s d`) or switch tag backend strategy.

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
| Source pool | `f:\M\H06T01\dldz\MORE_SHR\mp3-albums\!car-selected` |
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
