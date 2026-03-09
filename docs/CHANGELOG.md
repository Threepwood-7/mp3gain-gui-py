# Changelog

## 2026-03-10
- Routed `legacy_cli` runtime execution through a legacy oracle passthrough (`mp3gain.exe`) for full switch-surface parity in CLI-driven file operations.
- Fixed module invocation argument handling in `legacy_cli` so `python -m mp3gain_gui_py.legacy_cli ...` consumes `sys.argv[1:]` when `main()` is called without an explicit argv list.
- Documented practical legacy CLI and parity-matrix usage in `README.md`, including common `/o /s r`, `/g`, `/m`, and `/d` command examples.
