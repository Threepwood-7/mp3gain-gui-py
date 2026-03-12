from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


def _load_module() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "run_normalize.py"
    spec = importlib.util.spec_from_file_location(
        "run_normalize_for_tests", script_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load run_normalize.py module for tests.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_db_mapping_uses_legacy_step_math() -> None:
    module = _load_module()

    assert module.db_to_legacy_steps(89.0 - module.DEFAULT_TARGET_DB) == 0
    assert module.db_to_legacy_steps(87.0 - module.DEFAULT_TARGET_DB) == -1
    assert module.db_to_legacy_steps(81.0 - module.DEFAULT_TARGET_DB) == -5
    assert module.db_to_legacy_steps(90.5 - module.DEFAULT_TARGET_DB) == 1


def test_parse_analysis_mp3_gain_ignores_header_and_album_row() -> None:
    module = _load_module()
    target = Path(r"c:\tmp\audio\sample.mp3")
    output = (
        "File\tMP3 gain\tdB gain\tMax Amplitude\tMax global_gain\tMin global_gain\n"
        f"{target}\t-7\t-10.410000\t12345.000000\t210\t90\n"
        '"Album"\t-7\t-10.410000\t12345.000000\t210\t90\n'
    )

    parsed = module._parse_analysis_mp3_gain(output, target_file=target)
    assert parsed == -7


def test_parse_analysis_mp3_gain_fails_on_malformed_output() -> None:
    module = _load_module()
    target = Path(r"c:\tmp\audio\sample.mp3")
    output = "File\tMP3 gain\tdB gain\n"

    with pytest.raises(ValueError, match="Could not parse MP3 gain steps"):
        module._parse_analysis_mp3_gain(output, target_file=target)


def test_process_file_runs_analyze_then_apply_and_skips_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    target = Path(r"c:\tmp\audio\sample.mp3")
    env: dict[str, str] = {}
    repo_root = Path(__file__).resolve().parents[2]

    calls: list[list[str]] = []

    def fake_run(
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> SimpleNamespace:
        _ = cwd
        _ = env
        _ = check
        _ = capture_output
        _ = text
        calls.append(command)
        if "/o" in command:
            stdout = (
                "File\tMP3 gain\tdB gain\tMax Amplitude\t"
                "Max global_gain\tMin global_gain\n"
                f"{target}\t0\t-0.180000\t12011.450678\t204\t76\n"
                '"Album"\t0\t-0.180000\t12011.450678\t204\t76\n'
            )
            return SimpleNamespace(returncode=0, stdout=stdout, stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    skip_result = module._process_file(
        index=1,
        total=1,
        target_file=target,
        repo_root=repo_root,
        env=env,
        step_offset=0,
    )
    assert skip_result.error is None
    assert skip_result.apply_command is None
    assert len(calls) == 1
    assert "/o" in calls[0]

    calls.clear()
    apply_result = module._process_file(
        index=1,
        total=1,
        target_file=target,
        repo_root=repo_root,
        env=env,
        step_offset=1,
    )
    assert apply_result.error is None
    assert apply_result.apply_command is not None
    assert apply_result.final_steps == 1
    assert len(calls) == 2
    assert "/o" in calls[0]
    assert calls[1][calls[1].index("/g") + 1] == "1"
    assert "/t" in calls[1]


def test_main_parallel_keeps_analyze_before_apply_per_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    repo_root = Path(__file__).resolve().parents[2]

    first = tmp_path / "a.mp3"
    second = tmp_path / "b.mp3"
    first.write_bytes(b"a")
    second.write_bytes(b"b")

    call_order: dict[str, list[str]] = {}

    def fake_run(
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> SimpleNamespace:
        _ = cwd
        _ = env
        _ = check
        _ = capture_output
        _ = text
        file_path = command[-1]
        stage = "analyze" if "/o" in command else "apply"
        call_order.setdefault(file_path, []).append(stage)
        if stage == "analyze":
            time.sleep(0.01)
            stdout = (
                "File\tMP3 gain\tdB gain\tMax Amplitude\t"
                "Max global_gain\tMin global_gain\n"
                f"{file_path}\t-2\t-2.810000\t23093.614593\t210\t78\n"
                '"Album"\t-2\t-2.810000\t23093.614593\t210\t78\n'
            )
            return SimpleNamespace(returncode=0, stdout=stdout, stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(
        module,
        "_parse_args",
        lambda: SimpleNamespace(
            src_dir=tmp_path,
            db=89.0,
            recurse=False,
            dst_dir=None,
            jobs=2,
        ),
    )
    monkeypatch.setattr(module, "REPO_ROOT", repo_root)

    exit_code = module.main()
    assert exit_code == 0
    assert len(call_order) == 2
    for stages in call_order.values():
        assert stages == ["analyze", "apply"]
