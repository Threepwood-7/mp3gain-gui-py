# Changelog

## 2026-03-10
- Enforced `legacy_cli` as a pure-Python runtime path by removing `mp3gain.exe` passthrough/delegation logic from `src/mp3gain_gui_py/legacy_cli.py`.
- Added runtime unit coverage for `legacy_cli` Python execution paths (`/q /o /s r`, `/g`, `/m`, `/d`, `/u`) and regression checks that oracle passthrough symbols are absent.
- Added per-branch `legacy_cli` unit coverage for check-only, delete-tag, direct gain, single-channel gain, track/album apply, undo, and clipping-guard paths.
- Added a compiled C-oracle harness (`tests/unit/c_oracle/legacy_math_oracle.c`) plus ctypes-backed unit tests to validate legacy math/tag-update behavior against C execution.
- Codified the project rule in `AGENTS.md`: `legacy_cli` runtime must not delegate to external `mp3gain.exe`; the executable is oracle-only for parity tooling.
- Added `scripts/normalize_89db.py` helper to normalize all MP3 files in a directory to 89 dB track target, with optional `--recurse` discovery and optional `--dst-dir` copy-then-normalize mode.
- Documented `normalize_89db.py` usage and command variants in README.
- Fixed module invocation argument handling in `legacy_cli` so `python -m mp3gain_gui_py.legacy_cli ...` consumes `sys.argv[1:]` when `main()` is called without an explicit argv list.
- Documented practical legacy CLI and parity-matrix usage in `README.md`, including common `/o /s r`, `/g`, `/m`, and `/d` command examples.
- Expanded README documentation with a ReplayGain primer, full per-switch legacy CLI reference, concrete 89/87/81 workflow recipes, parity harness artifacts, and `rgain3` integration notes.
- Incorporated guidance from the original MP3Gain FAQ into README: ReplayGain vs peak normalization, non-transcoding gain behavior, and MP3Gain tag compatibility caveats/workarounds.
- Corrected `legacy_cli` runtime parity behaviors for legacy oracle alignment: `/?` now exits with code 1 when no files are provided, `/e` is reported as an unrecognized option (non-fatal), `/s i` and `/s a` are rejected for this binary target, and `/t` now enables temp-file mode instead of being on by default.
- Reworked `legacy_cli` mutation flows to update MP3Gain tags after apply/undo/direct/single-channel operations using C-style `changeGainAndTag` semantics (undo accumulation, 1.505 dB step approximation, peak scaling, wrap/clamp rules), including tag writes during `/s r` recalculation paths.
- Improved table parity paths by emitting 11-column check-only (`/s c /o`) rows with `NA` placeholders, and by restoring album summary/output handling for non-track table modes.
- Switched MP3Gain tag float formatting to 6-decimal half-up rounding to better match legacy C `sprintf` behavior for gain/peak fields.
- Updated and expanded legacy CLI unit tests to cover new parser/runtime parity rules and branch behavior changes.
- Added `/s r` legacy-compat fallback logic that preserves prior >1.0 track-peak/tag gain values when decoder clipping/variance would otherwise degrade byte-level parity.
- Matched legacy 1.2.5 direct/single-channel tag side effects: single-channel error paths now still emit undo tags, and gain-tag text formatting now mirrors legacy 9-char truncation behavior for larger magnitudes.
- Re-ran the CLI parity matrix (`--sample 2 --jobs 2`): parity improved to 50/54 task pass, with remaining deltas isolated to tiny max-amplitude table precision differences in `/s s` and `/s r` scan-mode output.
