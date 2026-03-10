# PERF

## Purpose
This file records the latest oracle-vs-Python performance/parity execution for `legacy_cli` after the C-DLL runtime migration.

This supersedes the earlier python-only baseline run.

## Latest Execution (C-backed Python CLI)
- Date: `2026-03-10`
- Source pool: `f:\M\H06T01\dldz\MORE_SHR\mp3-albums\!car-selected`
- Random sample size: `6` files
- Total sampled bytes: `46,178,377` (`~46.18 MB`)
- Command log: `c:\tmp\mp3\89dbcodex\exec.log`
- Machine report: `c:\tmp\mp3\89dbcodex\parity_perf_report.json`
- Scenario outputs left in: `c:\tmp\mp3\89dbcodex\runs\`

## Selected Files
1. `Adam Lambert - Another Lonely Night.mp3`
2. `Charlie Puth Feat. Meghan Trainor - Marvin Gaye.mp3`
3. `David Puentez - Focus.mp3`
4. `One Direction - What Makes You Beautiful.mp3`
5. `Rag'n'bone Man - Skin.mp3`
6. `Selena Gomez - Selfish Love (With Dj Snake).mp3`

## Scenario Matrix
1. `analysis_o_sr`: `/q /o /s r`
2. `g_89`: `/q /r /c /s r /g 0`
3. `g_87`: `/q /r /c /s r /g 0 /d -2`
4. `g_81`: `/q /r /c /s r /g 0 /d -8`
5. `m_plus_1`: `/q /r /c /s r /m 1`
6. `d_plus_1_5`: `/q /r /c /s r /d 1.5`

## Parity Results
All scenarios passed:
1. `output_parity = True`
2. `byte_parity_all_files = True`
3. `oracle_returncode = 0`
4. `python_returncode = 0`

No byte mismatches were reported for any file in any scenario.

## Detailed Timing (Oracle vs Python DLL)

`ratio = python_elapsed / oracle_elapsed`

1. `analysis_o_sr`
- Oracle: `7.428429s`
- Python DLL: `9.650772s`
- Ratio: `1.299x` (Python slower)
- Delta: `+2.222343s`

2. `g_89`
- Oracle: `0.030019s`
- Python DLL: `0.120492s`
- Ratio: `4.014x` (Python slower)
- Delta: `+0.090473s`

3. `g_87`
- Oracle: `0.029601s`
- Python DLL: `0.118373s`
- Ratio: `3.999x` (Python slower)
- Delta: `+0.088772s`

4. `g_81`
- Oracle: `0.028959s`
- Python DLL: `0.127494s`
- Ratio: `4.403x` (Python slower)
- Delta: `+0.098535s`

5. `m_plus_1`
- Oracle: `7.888899s`
- Python DLL: `5.210642s`
- Ratio: `0.661x` (Python faster)
- Delta: `-2.678256s`

6. `d_plus_1_5`
- Oracle: `7.797092s`
- Python DLL: `5.274918s`
- Ratio: `0.677x` (Python faster)
- Delta: `-2.522175s`

## Aggregate Timing
- Oracle total: `23.202999s`
- Python DLL total: `20.502690s`
- Aggregate ratio (`python/oracle`): `0.8836x`

Interpretation:
1. Python DLL path is slower for very short direct-gain lanes (`/g` family), where process/CLI overhead dominates.
2. Python DLL path is faster for longer apply lanes (`/m`, `/d`) in this sample.
3. Combined run time is better on Python DLL by about `11.64%`.

## Exact Commands
All commands executed in this run are stored verbatim in:
- `c:\tmp\mp3\89dbcodex\exec.log`

This includes:
1. Oracle commands (`C:\bin\mp3gain-win-1_2_5\mp3gain.exe ...`) for each scenario.
2. Python commands (`python -m mp3gain_gui_py.legacy_cli ...`) for each scenario.
