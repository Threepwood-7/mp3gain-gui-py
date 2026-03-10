from __future__ import annotations

import argparse
import hashlib
import io
import json
import pstats
import random
import shutil
import stat
import subprocess
import time
from datetime import datetime
from pathlib import Path


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(1024 * 1024)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _normalize_output(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n").strip()


def _clear_readonly(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IWRITE)


class Runner:
    def __init__(self, exec_log: Path) -> None:
        self.exec_log = exec_log
        self.exec_log.parent.mkdir(parents=True, exist_ok=True)
        self.exec_log.write_text("", encoding="utf-8", newline="\n")

    def _log_cmd(self, cmd: list[str]) -> None:
        with self.exec_log.open("a", encoding="utf-8", newline="\n") as f:
            f.write(subprocess.list2cmdline(cmd) + "\n")

    def run(self, cmd: list[str], *, cwd: Path) -> dict[str, object]:
        self._log_cmd(cmd)
        t0 = time.perf_counter()
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            check=False,
        )
        dt = time.perf_counter() - t0
        return {
            "cmd": cmd,
            "returncode": int(proc.returncode),
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "elapsed_s": dt,
        }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run C mp3gain vs mp3gain_gui_py legacy_cli parity and performance matrix, "
            "with command logging and profiling."
        )
    )
    parser.add_argument(
        "--source-dir",
        required=True,
        help="Directory containing original mp3 files to sample from.",
    )
    parser.add_argument(
        "--temp-root",
        default=r"c:\\tmp\\mp3\\89dbcodex",
        help="Root temp directory for run outputs and exec.log.",
    )
    parser.add_argument(
        "--c-exe",
        default=r"C:\\bin\\mp3gain-win-1_2_5\\mp3gain.exe",
        help="Path to C mp3gain executable.",
    )
    parser.add_argument(
        "--pick",
        type=int,
        default=3,
        help="How many random files to sample.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional RNG seed for reproducible sampling.",
    )
    parser.add_argument(
        "--exec-log",
        default=None,
        help="Optional explicit exec.log path. Defaults to <temp-root>/exec.log",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    temp_root = Path(args.temp_root)
    c_exe = Path(args.c_exe)
    exec_log = Path(args.exec_log) if args.exec_log else (temp_root / "exec.log")

    repo_root = Path(__file__).resolve().parents[2]

    if not source_dir.exists():
        raise SystemExit(f"Source folder not found: {source_dir}")
    if not c_exe.exists():
        raise SystemExit(f"C mp3gain binary not found: {c_exe}")
    if args.pick <= 0:
        raise SystemExit("--pick must be > 0")

    temp_root.mkdir(parents=True, exist_ok=True)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = temp_root / f"run_{run_id}"
    seed_dir = run_dir / "seed"
    scen_dir = run_dir / "scenarios"
    profile_dir = run_dir / "profiles"
    for d in (seed_dir, scen_dir, profile_dir):
        d.mkdir(parents=True, exist_ok=True)

    runner = Runner(exec_log=exec_log)

    all_mp3 = [p for p in source_dir.rglob("*.mp3") if p.is_file()]
    if len(all_mp3) < args.pick:
        raise SystemExit(f"Need at least {args.pick} mp3 files, found {len(all_mp3)} in {source_dir}")

    rng = random.Random(args.seed) if args.seed is not None else random.SystemRandom()
    selected = rng.sample(all_mp3, args.pick)
    selected = sorted(selected, key=lambda p: str(p).lower())

    seed_files: list[Path] = []
    source_map: dict[str, str] = {}
    for i, src in enumerate(selected, 1):
        dst = seed_dir / f"{i:02d}_{src.name}"
        n = 1
        while dst.exists():
            dst = seed_dir / f"{i:02d}_{src.stem}_{n}{src.suffix}"
            n += 1
        shutil.copy2(src, dst)
        _clear_readonly(dst)
        seed_files.append(dst)
        source_map[dst.name] = str(src)

    scenarios: list[dict[str, object]] = [
        {
            "name": "analysis_o_sr",
            "args": ["/q", "/o", "/s", "r"],
            "desc": "analysis table with forced recalc",
        },
        {
            "name": "g_target_89",
            "args": ["/q", "/r", "/c", "/s", "r", "/g", "0"],
            "desc": "track lane baseline ~89 dB",
        },
        {
            "name": "g_target_87",
            "args": ["/q", "/r", "/c", "/s", "r", "/g", "0", "/d", "-2"],
            "desc": "track lane ~87 dB via dB modifier",
        },
        {
            "name": "g_target_81",
            "args": ["/q", "/r", "/c", "/s", "r", "/g", "0", "/d", "-8"],
            "desc": "track lane ~81 dB via dB modifier",
        },
        {
            "name": "m_plus_1",
            "args": ["/q", "/r", "/c", "/s", "r", "/m", "1"],
            "desc": "mp3 step modifier +1",
        },
        {
            "name": "d_plus_1_5",
            "args": ["/q", "/r", "/c", "/s", "r", "/d", "1.5"],
            "desc": "dB modifier +1.5",
        },
    ]

    results: dict[str, object] = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "source_root": str(source_dir),
        "repo_root": str(repo_root),
        "c_exe": str(c_exe),
        "exec_log": str(exec_log),
        "run_dir": str(run_dir),
        "selected_sources": source_map,
        "scenarios": [],
        "profiles": [],
    }

    for scen in scenarios:
        name = str(scen["name"])
        args_list = list(scen["args"])
        scen_root = scen_dir / name
        work_dir = scen_root / "work"
        c_snapshot = scen_root / "c_snapshot"
        for d in (work_dir, c_snapshot):
            d.mkdir(parents=True, exist_ok=True)

        for sf in seed_files:
            dst = work_dir / sf.name
            shutil.copy2(sf, dst)
            _clear_readonly(dst)

        file_args = [str((work_dir / sf.name).resolve()) for sf in seed_files]

        c_cmd = [str(c_exe)] + args_list + file_args
        c_res = runner.run(c_cmd, cwd=repo_root)

        (scen_root / "c_stdout.bin").write_bytes(c_res["stdout"])
        (scen_root / "c_stderr.bin").write_bytes(c_res["stderr"])
        for sf in seed_files:
            src = work_dir / sf.name
            dst = c_snapshot / sf.name
            shutil.copy2(src, dst)
            _clear_readonly(dst)

        for sf in seed_files:
            dst = work_dir / sf.name
            shutil.copy2(sf, dst)
            _clear_readonly(dst)

        py_cmd = ["hatch", "run", "python", "-m", "mp3gain_gui_py.legacy_cli"] + args_list + file_args
        py_res = runner.run(py_cmd, cwd=repo_root)

        (scen_root / "py_stdout.bin").write_bytes(py_res["stdout"])
        (scen_root / "py_stderr.bin").write_bytes(py_res["stderr"])

        c_out = c_res["stdout"] + b"\n__STDERR__\n" + c_res["stderr"]
        py_out = py_res["stdout"] + b"\n__STDERR__\n" + py_res["stderr"]

        output_exact = c_out == py_out
        output_norm = _normalize_output(c_out) == _normalize_output(py_out)

        byte_matches: list[dict[str, object]] = []
        all_equal = True
        for sf in seed_files:
            c_file = c_snapshot / sf.name
            py_file = work_dir / sf.name
            c_hash = _sha256_file(c_file)
            py_hash = _sha256_file(py_file)
            same = c_hash == py_hash
            if not same:
                all_equal = False
            byte_matches.append(
                {
                    "file": sf.name,
                    "c_sha256": c_hash,
                    "py_sha256": py_hash,
                    "equal": same,
                    "size_c": c_file.stat().st_size,
                    "size_py": py_file.stat().st_size,
                }
            )

        scenario_list = results["scenarios"]
        assert isinstance(scenario_list, list)
        scenario_list.append(
            {
                "name": name,
                "description": scen["desc"],
                "args": args_list,
                "c_returncode": c_res["returncode"],
                "py_returncode": py_res["returncode"],
                "c_elapsed_s": c_res["elapsed_s"],
                "py_elapsed_s": py_res["elapsed_s"],
                "py_vs_c_slowdown": (py_res["elapsed_s"] / c_res["elapsed_s"]) if c_res["elapsed_s"] > 0 else None,
                "output_exact_match": output_exact,
                "output_normalized_match": output_norm,
                "byte_exact_all_files": all_equal,
                "byte_matches": byte_matches,
                "work_dir": str(work_dir),
                "c_snapshot_dir": str(c_snapshot),
            }
        )

    profile_target = seed_files[0]
    profile_specs = [
        ("profile_analysis_o_sr", ["/q", "/o", "/s", "r"]),
        ("profile_d_plus_1_5", ["/q", "/r", "/c", "/s", "r", "/d", "1.5"]),
    ]

    for profile_name, profile_args in profile_specs:
        pdir = profile_dir / profile_name
        pdir.mkdir(parents=True, exist_ok=True)
        prof_file = pdir / "run.prof"
        work_file = pdir / profile_target.name
        shutil.copy2(profile_target, work_file)
        _clear_readonly(work_file)

        profile_cmd = [
            "hatch",
            "run",
            "python",
            "-m",
            "cProfile",
            "-o",
            str(prof_file),
            "-m",
            "mp3gain_gui_py.legacy_cli",
        ] + profile_args + [str(work_file.resolve())]

        profile_res = runner.run(profile_cmd, cwd=repo_root)

        cum_sio = io.StringIO()
        pstats.Stats(str(prof_file), stream=cum_sio).sort_stats("cumulative").print_stats(30)
        (pdir / "cumulative_top30.txt").write_text(cum_sio.getvalue(), encoding="utf-8", newline="\n")

        tot_sio = io.StringIO()
        pstats.Stats(str(prof_file), stream=tot_sio).sort_stats("tottime").print_stats(30)
        (pdir / "tottime_top30.txt").write_text(tot_sio.getvalue(), encoding="utf-8", newline="\n")

        (pdir / "stdout.bin").write_bytes(profile_res["stdout"])
        (pdir / "stderr.bin").write_bytes(profile_res["stderr"])

        profile_list = results["profiles"]
        assert isinstance(profile_list, list)
        profile_list.append(
            {
                "name": profile_name,
                "args": profile_args,
                "returncode": profile_res["returncode"],
                "elapsed_s": profile_res["elapsed_s"],
                "profile_file": str(prof_file),
                "cumulative_top30_file": str(pdir / "cumulative_top30.txt"),
                "tottime_top30_file": str(pdir / "tottime_top30.txt"),
            }
        )

    report_path = run_dir / "report.json"
    report_path.write_text(json.dumps(results, indent=2), encoding="utf-8", newline="\n")

    print(f"RUN_DIR={run_dir}")
    print(f"REPORT={report_path}")
    print(f"EXEC_LOG={exec_log}")

    scenario_list = results["scenarios"]
    assert isinstance(scenario_list, list)
    for s in scenario_list:
        assert isinstance(s, dict)
        print(
            "SCEN="
            + str(s["name"])
            + f" C={float(s['c_elapsed_s']):.3f}s"
            + f" PY={float(s['py_elapsed_s']):.3f}s"
            + f" SLOW={float(s['py_vs_c_slowdown']):.3f}x"
            + f" OUT_EXACT={int(bool(s['output_exact_match']))}"
            + f" OUT_NORM={int(bool(s['output_normalized_match']))}"
            + f" BYTE={int(bool(s['byte_exact_all_files']))}"
            + f" RC_C={int(s['c_returncode'])}"
            + f" RC_PY={int(s['py_returncode'])}"
        )

    profile_list = results["profiles"]
    assert isinstance(profile_list, list)
    for p in profile_list:
        assert isinstance(p, dict)
        print(
            "PROF="
            + str(p["name"])
            + f" ELAPSED={float(p['elapsed_s']):.3f}s"
            + f" RC={int(p['returncode'])}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
