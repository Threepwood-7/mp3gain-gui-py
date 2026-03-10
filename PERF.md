# PERF

## Purpose
This document captures a direct C `mp3gain.exe` vs Python `mp3gain_gui_py.legacy_cli` parity and performance run on real MP3 files, and gives exact reproduction steps.

## Tested Baseline Run
- Run timestamp: `2026-03-10`
- Run folder: `c:\tmp\mp3\89dbcodex\run_20260310_094335`
- Machine command log: `c:\tmp\mp3\89dbcodex\exec.log`
- Report JSON: `c:\tmp\mp3\89dbcodex\run_20260310_094335\report.json`

### Source pool
- Source root: `<YOUR_MP3_SOURCE_DIR>`
- Randomly sampled files (3):
1. `sample_01.mp3`
2. `sample_02.mp3`
3. `sample_03.mp3`

Copied seed files are under:
- `c:\tmp\mp3\89dbcodex\run_20260310_094335\seed\`

All processed files were kept under:
- `c:\tmp\mp3\89dbcodex\run_20260310_094335\scenarios\*\work\`

## Scenario Matrix
The run used this exact matrix:
1. `analysis_o_sr`: `/q /o /s r`
2. `g_target_89`: `/q /r /c /s r /g 0`
3. `g_target_87`: `/q /r /c /s r /g 0 /d -2`
4. `g_target_81`: `/q /r /c /s r /g 0 /d -8`
5. `m_plus_1`: `/q /r /c /s r /m 1`
6. `d_plus_1_5`: `/q /r /c /s r /d 1.5`

## Parity Results (Baseline Run)

### Summary
- Full output parity and byte parity passed for:
1. `g_target_89`
2. `g_target_87`
3. `g_target_81`

- Output parity and byte parity failed for:
1. `analysis_o_sr`
2. `m_plus_1`
3. `d_plus_1_5`

### Detailed timing + parity
1. `analysis_o_sr`
- C: `5.146s`
- Python: `826.349s`
- Slowdown: `160.592x`
- Output exact: `False`
- Output normalized: `False`
- Byte exact all files: `False`

2. `g_target_89`
- C: `0.018s`
- Python: `0.634s`
- Slowdown: `34.298x`
- Output exact: `True`
- Output normalized: `True`
- Byte exact all files: `True`

3. `g_target_87`
- C: `0.019s`
- Python: `0.625s`
- Slowdown: `33.039x`
- Output exact: `True`
- Output normalized: `True`
- Byte exact all files: `True`

4. `g_target_81`
- C: `0.019s`
- Python: `0.639s`
- Slowdown: `33.251x`
- Output exact: `True`
- Output normalized: `True`
- Byte exact all files: `True`

5. `m_plus_1`
- C: `6.113s`
- Python: `423.376s`
- Slowdown: `69.257x`
- Output exact: `False`
- Output normalized: `False`
- Byte exact all files: `False`

6. `d_plus_1_5`
- C: `5.494s`
- Python: `410.423s`
- Slowdown: `74.697x`
- Output exact: `False`
- Output normalized: `False`
- Byte exact all files: `False`

### Aggregate runtime
- C total: `16.810s`
- Python total: `1662.045s`
- Total slowdown: `98.873x`

## Byte-Level Mismatch Pattern
For mismatched scenarios (`analysis_o_sr`, `m_plus_1`, `d_plus_1_5`):
- File sizes match between C and Python outputs.
- First differing offset is near EOF.
- Number of differing bytes is small.

Observed values:

### `analysis_o_sr`
1. `sample_01.mp3`: first diff `9788693`, diff bytes `15`, size `9788979`
2. `sample_02.mp3`: first diff `12158776`, diff bytes `12`, size `12159018`
3. `sample_03.mp3`: first diff `11016516`, diff bytes `17`, size `11016802`

### `m_plus_1`
1. `sample_01.mp3`: first diff `9788689`, diff bytes `4`, size `9788895`
2. `sample_02.mp3`: first diff `12158772`, diff bytes `2`, size `12158934`
3. `sample_03.mp3`: first diff `11016512`, diff bytes `6`, size `11016718`

### `d_plus_1_5`
1. `sample_01.mp3`: first diff `9788689`, diff bytes `4`, size `9788895`
2. `sample_02.mp3`: first diff `12158772`, diff bytes `2`, size `12158934`
3. `sample_03.mp3`: first diff `11016512`, diff bytes `6`, size `11016718`

Interpretation: mismatches are concentrated in trailing metadata/tag region, not broad file-wide audio payload divergence.

## Output Differences
### `analysis_o_sr`
- Table values differ for dB gain, max amplitude, and album row.
- Python run through Hatch also emits `Checking dependencies` on stderr, which breaks strict output parity even when main stdout text is close.

### `m_plus_1` and `d_plus_1_5`
- C prints per-file apply lines.
- Python is quiet under `/q`.
- This causes output-parity failure even before byte-parity checks.

## Profiling Findings
Profiles were captured with `cProfile` and written to:
- `...\profiles\profile_analysis_o_sr\`
- `...\profiles\profile_d_plus_1_5\`

### `profile_analysis_o_sr` (single-file profile)
- Elapsed: `282.721s`
- Top tottime hotspots:
1. `filter_np.py:filter_yule`: `199.969s`
2. `filter_np.py:filter_butter`: `50.095s`

Combined filter share is dominant (~88%+ of runtime).

### `profile_d_plus_1_5` (single-file profile)
- Elapsed: `145.660s`
- Top tottime hotspots:
1. `filter_np.py:filter_yule`: `102.390s`
2. `filter_np.py:filter_butter`: `25.435s`

`apply_gain_change` is comparatively small (~`0.064s` tottime in that profile).

Conclusion: ReplayGain DSP filter loops dominate runtime, not file write/apply path.

## Exact Reproduction Instructions

### Prerequisites
1. Windows machine with Python and Hatch available on `PATH`.
2. Project repo checked out at `c:\prj\aidev\py\mp3gain-gui-py`.
3. C reference binary at `C:\bin\mp3gain-win-1_2_5\mp3gain.exe`.
4. Source MP3 corpus at a non-personal path you control, for example `F:\mp3-corpus`.

## One command to run the full matrix
Run from repo root (`c:\prj\aidev\py\mp3gain-gui-py`):

```text
hatch run python scripts/perf/run_c_python_parity_perf.py --source-dir "F:\mp3-corpus" --temp-root "c:\tmp\mp3\89dbcodex" --c-exe "C:\bin\mp3gain-win-1_2_5\mp3gain.exe" --pick 3
```

Notes:
- This runner does not set a subprocess timeout.
- It resets `c:\tmp\mp3\89dbcodex\exec.log` at start of each run.
- It logs every external command it executes to `exec.log`.
- It copies sampled files into a timestamped `run_YYYYMMDD_HHMMSS` folder.
- It clears read-only attributes on copied working files.

## Optional deterministic sampling
To make random selection reproducible, add `--seed`:

```text
hatch run python scripts/perf/run_c_python_parity_perf.py --source-dir "F:\mp3-corpus" --temp-root "c:\tmp\mp3\89dbcodex" --c-exe "C:\bin\mp3gain-win-1_2_5\mp3gain.exe" --pick 3 --seed 42
```

## Exact files produced by the harness
For each run folder (`c:\tmp\mp3\89dbcodex\run_<timestamp>`):
1. `report.json`: machine-readable parity + timing summary.
2. `seed\`: copied initial sampled MP3 files.
3. `scenarios\<name>\work\`: Python-processed outputs.
4. `scenarios\<name>\c_snapshot\`: C-processed outputs.
5. `scenarios\<name>\c_stdout.bin`, `c_stderr.bin`, `py_stdout.bin`, `py_stderr.bin`.
6. `profiles\...\run.prof`, `cumulative_top30.txt`, `tottime_top30.txt`.

## How to inspect results quickly
1. Open `exec.log` for exact commands.
2. Open `report.json` for scenario timings and parity flags.
3. For profile hotspots, inspect:
- `profiles\profile_analysis_o_sr\tottime_top30.txt`
- `profiles\profile_d_plus_1_5\tottime_top30.txt`

## Commands actually executed in baseline run
The baseline run commands are preserved in:
- `c:\tmp\mp3\89dbcodex\exec.log`

This includes:
1. C `mp3gain.exe` commands for all 6 scenarios.
2. Python `legacy_cli` commands for all 6 scenarios.
3. Two `cProfile` commands.

## Performance Gap Focus Areas
Priority order for runtime parity work:
1. Move ReplayGain filter core (`filter_yule`, `filter_butter`) to compiled code.
2. Reduce Python per-sample overhead in analysis path.
3. Investigate scan-mode numeric parity (`/o /s r`) and tail-tag byte deltas in `m_plus_1`/`d_plus_1_5` scenarios.
4. For strict output parity measurements, avoid wrapper noise from environment bootstrap output.
