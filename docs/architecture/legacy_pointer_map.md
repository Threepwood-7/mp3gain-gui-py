# Legacy Pointer Map

Canonical traceability map for Python parity-critical logic to legacy MP3Gain C/VB6 sources.

## Schema

Each row is a pointer contract entry:

- `pointer_id`: Stable token referenced in code comments/docstrings as `LEGACY_PTR:<UPPER_SNAKE_ID>`.
- `python_symbol`: Python symbol in `<module_path>::<symbol>` form.
- `legacy_ref`: Legacy source anchor in `<file>:<function_or_block>@L<start>-L<end>` form.
- `oracle_ref`: Oracle executable behavior tie-in when applicable.
- `parity_status`: `exact`, `partial`, or `todo`.
- `notes`: Compatibility contract / caveat.

## Pointer Table

| pointer_id | python_symbol | legacy_ref | oracle_ref | parity_status | notes |
|---|---|---|---|---|---|
| LEGACY_PTR:DSP_COEFFICIENT_TABLES | `src/mp3gain_gui_py/_engine/coefficients.py::AB_YULE/AB_BUTTER` | `gain_analysis.c:ABYule_ABButter_tables@L147-L189` | `mp3gain.exe -q -o` analysis output | `partial` | Coefficient tables are intended to be literal ports; keep row ordering identical. |
| LEGACY_PTR:DSP_FILTER_YULE | `src/mp3gain_gui_py/_engine/filter_py.py::filter_yule` | `gain_analysis.c:filterYule@L190-L221` | `mp3gain.exe` DSP path | `partial` | Includes denormal guard `1e-10` like legacy. |
| LEGACY_PTR:DSP_FILTER_BUTTER | `src/mp3gain_gui_py/_engine/filter_py.py::filter_butter` | `gain_analysis.c:filterButter@L222-L300` | `mp3gain.exe` DSP path | `partial` | Preserve coefficient ordering and recurrence indices. |
| LEGACY_PTR:DSP_ANALYZE_SAMPLES | `src/mp3gain_gui_py/_engine/replaygain.py::GainAnalyzer.analyze_samples` | `gain_analysis.c:AnalyzeSamples@L301-L453` | `mp3gain.exe -q -o` analysis output | `partial` | Histogram fill and RMS windowing must remain legacy-equivalent. |
| LEGACY_PTR:DSP_GET_TITLE_GAIN | `src/mp3gain_gui_py/_engine/replaygain.py::GainAnalyzer.get_title_gain` | `gain_analysis.c:GetTitleGain@L454-L520` | `mp3gain.exe -q -o` table `dB gain` | `partial` | Includes A->B histogram merge and per-track reset semantics. |
| LEGACY_PTR:MP3_CRC_UPDATE | `src/mp3gain_gui_py/_mp3/crc.py::crc16_update` | `mp3gain.c:crcUpdate@L458-L474` | `mp3gain.exe` mutated file CRC bytes | `partial` | Bit-walk polynomial logic must remain bit-identical. |
| LEGACY_PTR:MP3_CRC_WRITE_HEADER | `src/mp3gain_gui_py/_mp3/crc.py::write_frame_crc` | `mp3gain.c:crcWriteHeader@L475-L489` | `mp3gain.exe` mutated file CRC bytes | `partial` | Scope is header bytes [2:4] plus sideinfo region only. |
| LEGACY_PTR:MP3_SCAN_FRAME_GAIN | `src/mp3gain_gui_py/_mp3/file_info.py::scan_file` | `mp3gain.c:scanFrameGain@L616-L684` | `mp3gain.exe -q -o` min/max columns | `partial` | Must keep first Xing/Info frame skip behavior aligned. |
| LEGACY_PTR:MP3_FRAME_OFFSETS | `src/mp3gain_gui_py/_mp3/frame_parser.py::global_gain_offsets` | `mp3gain.c:scanFrameGain@L616-L684` | `mp3gain.exe` frame mutation/readback | `partial` | Bit offsets per MPEG version/channel mode must match legacy walk. |
| LEGACY_PTR:MP3_SKIP_XING_INFO | `src/mp3gain_gui_py/_mp3/frame_parser.py::has_xing_or_info_tag` | `mp3gain.c:changeGain@L813-L818` | `mp3gain.exe` no-change on first Xing/Info frame | `exact` | Mirrors first-frame Xing/Info guard semantics. |
| LEGACY_PTR:MP3_CHANGE_GAIN | `src/mp3gain_gui_py/_mp3/gain_writer.py::apply_gain_change` | `mp3gain.c:changeGain@L685-L1109` | `mp3gain.exe` mutated file bytes | `partial` | Covers per-frame gain delta, clamp/wrap, and CRC rewrite. |
| LEGACY_PTR:MP3_TEMPFILE_REPLACE | `src/mp3gain_gui_py/_mp3/gain_writer.py::_legacy_tmp_path/_replace_with_retry` | `mp3gain.c:changeGain_temp_replace@L1010-L1109` | `mp3gain.exe` temp file behavior | `partial` | Temp naming/replacement semantics are still being tightened. |
| LEGACY_PTR:TAGS_FORMAT_CONTRACT | `src/mp3gain_gui_py/_tags/formats.py::format_*` | `mp3gain.c:changeGainAndTag@L1128-L1198` | `mp3gain.exe -s c` tag table readback | `partial` | String formatting must match legacy contract exactly in strict lane. |
| LEGACY_PTR:TAGS_APEV2_READ | `src/mp3gain_gui_py/_tags/reader.py::read_tags` | `apetag.c:ReadMP3GainAPETag@L356-L389` | `mp3gain.exe -s c` | `partial` | APE takes precedence over ID3 path where available. |
| LEGACY_PTR:TAGS_APEV2_WRITE | `src/mp3gain_gui_py/_tags/legacy_apev2.py::write_legacy_apev2_tags` | `apetag.c:WriteMP3GainAPETag@L390-L642` | `mp3gain.exe` post-apply tag bytes | `partial` | Field ordering and trailer handling are parity-critical. |
| LEGACY_PTR:TAGS_ID3_READ | `src/mp3gain_gui_py/_tags/reader.py::read_tags` | `id3tag.c:ReadMP3GainID3Tag@L1056-L1102` | `mp3gain.exe -s c` | `partial` | ReplayGain/mp3gain frame decode semantics must align. |
| LEGACY_PTR:TAGS_ID3_WRITE | `src/mp3gain_gui_py/_tags/writer.py::_write_id3` | `id3tag.c:WriteMP3GainID3Tag@L1103-L1292` | `mp3gain.exe` post-apply tag bytes | `partial` | Current mutagen path is not yet byte-exact to legacy layout. |
| LEGACY_PTR:TAGS_DELETE_KEYS | `src/mp3gain_gui_py/_tags/writer.py::delete_tags` | `mp3gain.c:WriteMP3GainTag@L1110-L1127` | `mp3gain.exe /s d` flows | `partial` | Remove only MP3Gain keys and preserve foreign fields. |
| LEGACY_PTR:EXACT_DB_STEP_MATH | `src/mp3gain_gui_py/_legacy_exact/math.py::db_to_legacy_steps` | `mp3gain.c:intGainChange_math@L2410-L2576` | `mp3gain.exe` reported mp3 gain steps | `partial` | Uses `5*log10(2)` conversion path and legacy rounding behavior. |
| LEGACY_PTR:EXACT_PROCESSOR_APPLY | `src/mp3gain_gui_py/_legacy_exact/processor.py::LegacyExactProcessor.apply_steps` | `mp3gain.c:changeGainAndTag@L1128-L1198` | `mp3gain.exe /r` semantics | `partial` | Processor is the API surface for legacy-compatible apply behavior. |
| LEGACY_PTR:EXACT_PROCESSOR_UNDO | `src/mp3gain_gui_py/_legacy_exact/processor.py::LegacyExactProcessor.undo` | `mp3gain.c:undo_flow@L1975-L1989` | `mp3gain.exe /u` semantics | `partial` | Depends on parsed `MP3GAIN_UNDO` tag contract. |
| LEGACY_PTR:CLI_SWITCH_SURFACE | `src/mp3gain_gui_py/legacy_cli.py::main` | `mp3gain.c:main_switch_dispatch@L1455-L2607` | `mp3gain.exe` CLI behavior | `partial` | Exit-code and side-effect parity is in-progress. |
| LEGACY_PTR:PARITY_SHARED_PATHS | `scripts/parity_common.py::LEGACY_ORACLE_EXE/LEGACY_SOURCE_DIR` | `mp3gain.c:cli_runtime_paths@L1455-L2607` | `mp3gain.exe` | `exact` | Canonical source/oracle path constants for parity scripts. |
| LEGACY_PTR:PARITY_BUILD_89DB | `scripts/parity_build_codex_89db.py::main` | `mp3gain.c:changeGainAndTag@L1128-L1198` | `mp3gain.exe` 89 dB outputs | `partial` | Build pipeline mirrors apply/tag flow over isolated working copy. |
| LEGACY_PTR:PARITY_COMPARE_STRICT | `scripts/parity_compare.py::main` | `mp3gain.c:scanFrameGain@L616-L684` | `mp3gain.exe -s c` + file bytes | `partial` | Strict lane compares frame gains, metadata, container, and bytes. |
