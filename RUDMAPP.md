# Full Legacy CLI Byte-Parity Program (89 dB, All Valid Switches)

## Summary
Build a strict command-line parity harness that compares `c:\bin\mp3gain-win-1_2_5\mp3gain.exe` vs Python CLI on `c:\tmp\mp3\original\*.mp3`, using only temporary writable copies under `c:\tmp\mp3\89dbcodex\...`, with parallel execution and byte-level output gates.
The gate is behavioral core parity: exit behavior + file mutation behavior + binary equality for outputs (not exact help/version text).
Target baseline stays 89 dB.

## Locked Decisions
- Dataset: all MP3 files in `c:\tmp\mp3\original` (currently 39 files).
- Workspace: `c:\tmp\mp3\89dbcodex\cli_option_parity\run_<timestamp>\...`.
- Source safety: never mutate source files; always copy first; always clear read-only on copies.
- Jobs: default `8` (cap by workload size), override with `--jobs`.
- Switch scope: full valid switch surface; invalid-usage cases are out of scope.
- Prefix support: Python CLI must accept both legacy `/` and `-` options.
- `/c` handling in automation: always include `/c` in mutating matrix cases to avoid interactive prompts.
- `/s d`: required gating case.
- `/s i` and `/s a`: required gating cases.
- Gate type: behavioral core; `/v`, `/h`, `/?`, and help text diffs are informational (captured, non-blocking).
- Acceptance: strict PASS only if all required case gates pass and source-dir non-mutation checks pass.

## Implementation Changes
### 1) Legacy CLI parity surface
- Extend CLI parsing in [legacy_cli.py](C:/prj/aidev/py/mp3gain-gui-py/src/mp3gain_gui_py/legacy_cli.py) to support:
  - `/` and `-` prefixes.
  - Attached and separated arg forms (`/d1.5` and `/d 1.5`, `/m-2`, `/g4`, `/s s`, `/l 0 3`).
  - Switches: `/v /h /? /g /l /r /k /a /m /d /c /o /t /q /p /x /f /s c|d|s|r|i|a /u /w /e`.
- Implement legacy precedence rules from C behavior:
  - `/r` vs `/a`: last one wins.
  - Execution branch order matches legacy behavior classes (check-tag-only, undo, direct single-channel, direct gain, delete-tag, analysis/apply).
- Keep 89 dB as baseline target and apply `/d` and `/m` exactly as legacy modifiers.
- Add support plumbing for:
  - stored-tag policy (`c/d/s/r`),
  - tag backend select (`i/a`),
  - max-amp-only mode (`/x`),
  - track-only analysis mode (`/e`),
  - album apply mode (`/a`),
  - auto-clip (`/k`) and wrap (`/w`) math parity,
  - preserve timestamp (`/p`).

### 2) Processor behavior parity
- Extend processor/options in [processor.py](C:/prj/aidev/py/mp3gain-gui-py/src/mp3gain_gui_py/_legacy_exact/processor.py) to expose the missing CLI behaviors:
  - direct gain (`/g`),
  - single-channel gain (`/l`) with legacy constraints (reject mono/joint-stereo in same situations as legacy),
  - delete MP3Gain tags (`/s d`) with selected tag backend,
  - analysis modes and album apply flow.
- Add explicit low-level write mode parity for `/t` vs default path (legacy temp-file behavior switch), instead of treating `/t` as a parse-only no-op.
- Ensure auto-clip step computation matches legacy integer math path for track/album operations.
- Ensure Unicode fallback and skip-tags behavior remain deterministic for parity runs.

### 3) Full CLI matrix orchestrator
- Upgrade or replace [parity_cli_matrix.py](C:/prj/aidev/py/mp3gain-gui-py/scripts/parity_cli_matrix.py) with a full switch harness:
  - Precompute source SHA256 map.
  - Create per-case sandbox copies for oracle and python.
  - Clear read-only on all sandbox files before running commands.
  - Execute oracle and python commands in parallel process tasks.
  - Use `hatch run` environment requirement; fail fast with explicit error if dependencies (e.g., `miniaudio`) are unavailable.
- Required case catalog (valid cases only):
  - Informational/non-gating: `/v`, `/h`, `/?`, `/? wrap`.
  - Non-mutating gating: `/q /o`, `/q /o /s c`, `/q /o /x`, `/q /o /s r`, `/q /o /s s`, `/q /o /e`.
  - Mutating track gating: `/q /r /c`, `/q /r /c /s s`, `/q /r /c /s r`, `/q /r /c /d 1.5`, `/q /r /c /m 1`, `/q /r /c /w`, `/q /r /k`, `/q /r /c /t`, `/q /r /c /p`, `/q /r /c /f`.
  - Mutating album gating: `/q /a /c`, `/q /a /c /k`, `/q /a /c /m -1 /d -1.5`.
  - Direct/undo/tag gating: `/q /g 4`, `/q /l 0 3`, `/q /l 1 -3`, `/q /u` (after controlled apply), `/q /s a /s d`, `/q /s i /s d`.
- Comparison gates per case:
  - Exit code parity (oracle vs python).
  - Mutating cases: post-run file SHA256 parity (oracle vs python).
  - Non-mutating cases: both outputs must equal pre-run input SHA256.
  - Table cases (`/o`): parse normalized table and compare structured fields.
  - Timestamp case (`/p`): preserve-time behavior parity check.
- Source non-mutation gate:
  - Pre/post full SHA256 map of `c:\tmp\mp3\original` must match exactly.

### 4) Progress + artifacts
- Live progress output:
  - copy progress,
  - command execution progress (`completed/total`, running pass/fail counters, ETA),
  - periodic failure snapshots.
- Artifact outputs in `c:\tmp\pycompa` (timestamped):
  - `parity_cli_full_run_<ts>.json` (run metadata + gates),
  - `parity_cli_full_results_<ts>.json` (per-case/per-file details),
  - `parity_cli_full_progress_<ts>.jsonl` (streamed progress events),
  - `parity_cli_full_report_<ts>.xlsx` (Summary, Cases, PerFile, Failures sheets with PASS/FAIL formatting).

## Test Plan
- Unit tests:
  - parser coverage for `/` and `-` forms, attached/separate values, and precedence.
  - switch semantics for `/s` modes (`c,d,s,r,i,a`).
  - auto-clip integer math parity for `/k`.
  - single-channel constraints parity for `/l`.
- Integration tests:
  - matrix smoke run on small sample (`--sample 2`) with deterministic pass/fail accounting.
  - full run on all files from `c:\tmp\mp3\original`.
  - verify copied files are writable (read-only removed) before mutation.
  - verify source directory SHA256 unchanged pre/post.
- Acceptance gates:
  - all required gating cases PASS,
  - all mutating case outputs byte-identical (oracle vs python),
  - all non-mutating cases unchanged,
  - source files unchanged,
  - no harness execution failures.

## Assumptions and defaults
- Canonical oracle is `c:\bin\mp3gain-win-1_2_5\mp3gain.exe`.
- Target baseline is always 89 dB.
- Valid switch combinations only are in scope for gating.
- Interactive clipping behavior without `/c` is intentionally excluded from gate.
- Runs are executed via Hatch-managed environment to ensure codec dependencies.
