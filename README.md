# mp3gain-gui-py

PySide6 port of MP3Gain GUI - ReplayGain analysis and gain adjustment

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Normalize 89 dB Helper](#normalize-89-db-helper)
- [What Is ReplayGain?](#what-is-replaygain)
- [Legacy CLI](#legacy-cli)
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

### Normalize 89 dB Helper

Normalize every MP3 in a directory with legacy track-apply switches (`/r /c /s r`) using the C-backed legacy CLI runtime.

In place (default):

```bat
python scripts\normalize_89db.py "C:\music\album"
```

Recurse through subdirectories:

```bat
python scripts\normalize_89db.py "C:\music" --recurse
```

Copy to destination then normalize there (source files unchanged):

```bat
python scripts\normalize_89db.py "C:\music" --dst-dir "C:\tmp\music-89db"
```

Recurse + preserve source-relative folder structure under destination:

```bat
python scripts\normalize_89db.py "C:\music" --recurse --dst-dir "C:\tmp\music-89db"
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
