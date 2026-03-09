"""Quick comparison script: run ReplayGain analysis on original MP3s
and compare dB/steps against mp3gain.exe reference values.

Usage:
    hatch run python scripts/compare_analysis.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path for development use
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mp3gain_gui_py._engine.pcm_reader import decode_to_stereo_chunks, read_mp3_info
from mp3gain_gui_py._engine.replaygain import GainAnalyzer
from mp3gain_gui_py._mp3.file_info import scan_file, scan_max_amplitude

ORIGINAL_DIR = Path("c:/tmp/mp3/original")
REFERENCE_DIR = Path("c:/tmp/mp3/89db")
TARGET_DB = 89.0

# Reference values from mp3gain.exe -q -o (track dB gain, volume, track gain steps)
# File | mp3gain-steps | raw-dB | max-amp | max-global-gain | min-global-gain
REFERENCE = {
    "1.mp3": {"mp3gain_steps": -6, "raw_db": -9.21, "max_amp": 33973.51, "max_gain": 210, "min_gain": 82},
    "2.mp3": {"mp3gain_steps": -4, "raw_db": -6.29, "max_amp": 32255.55, "max_gain": 210, "min_gain": 76},
    "3.mp3": {"mp3gain_steps": -6, "raw_db": -9.10, "max_amp": 35503.78, "max_gain": 210, "min_gain": 38},
    "4.mp3": {"mp3gain_steps": -6, "raw_db": -9.02, "max_amp": 34830.25, "max_gain": 210, "min_gain": 47},
    "5.mp3": {"mp3gain_steps": -7, "raw_db": -11.21, "max_amp": 34677.88, "max_gain": 188, "min_gain": 118},
    "6.mp3": {"mp3gain_steps": -5, "raw_db": -6.99, "max_amp": 38316.25, "max_gain": 210, "min_gain": 103},
    "7.mp3": {"mp3gain_steps": -7, "raw_db": -9.85, "max_amp": 35637.46, "max_gain": 187, "min_gain": 117},
}


def analyze_file(path: Path) -> dict[str, object]:
    """Run full analysis on one MP3: ReplayGain dB + frame scan."""
    sample_rate, _nch = read_mp3_info(path)
    ga = GainAnalyzer(sample_rate)

    for _sr, left, right in decode_to_stereo_chunks(path, chunk_frames=8192):
        ga.analyze_samples(left, right, len(left))

    raw_db = ga.get_title_gain()

    # Gain steps: how many 1.5dB global_gain increments to reach TARGET_DB
    # volume = TARGET_DB - raw_db (i.e., current perceived volume)
    volume = TARGET_DB - raw_db
    # steps = round(raw_db / 1.5) to reach target
    steps = round(raw_db / 1.5)
    applied_db = steps * 1.5  # exact dB applied

    min_gain, max_gain = scan_file(path)
    max_amp = scan_max_amplitude(path)

    return {
        "raw_db": raw_db,
        "volume": volume,
        "steps": steps,
        "applied_db": applied_db,
        "max_amp": max_amp,
        "max_gain": max_gain,
        "min_gain": min_gain,
    }


def main() -> None:
    print(f"{'File':<12} {'Volume':>7} {'RawdB':>8} {'Steps':>6} {'AppliedDB':>10} "
          f"{'MaxAmp':>12} {'MaxG':>5} {'MinG':>5}  "
          f"{'vs ref raw_db':>14} {'steps?':>7} {'max?':>6} {'min?':>6}")
    print("-" * 123)

    all_ok = True
    for fname in sorted(REFERENCE.keys()):
        src = ORIGINAL_DIR / fname
        if not src.exists():
            print(f"{fname:<12}  MISSING")
            continue

        result = analyze_file(src)
        ref = REFERENCE[fname]

        raw_db = float(result["raw_db"])  # type: ignore[arg-type]
        volume = float(result["volume"])  # type: ignore[arg-type]
        steps = int(result["steps"])  # type: ignore[arg-type]
        applied_db = float(result["applied_db"])  # type: ignore[arg-type]
        max_amp = float(result["max_amp"])  # type: ignore[arg-type]
        max_gain = int(result["max_gain"])  # type: ignore[arg-type]
        min_gain = int(result["min_gain"])  # type: ignore[arg-type]

        ref_raw_db: float = ref["raw_db"]  # type: ignore[assignment]
        ref_steps: int = ref["mp3gain_steps"]  # type: ignore[assignment]
        ref_max_gain: int = ref["max_gain"]  # type: ignore[assignment]
        ref_min_gain: int = ref["min_gain"]  # type: ignore[assignment]

        delta_db = raw_db - ref_raw_db
        steps_match = steps == ref_steps
        max_gain_match = max_gain == ref_max_gain
        min_gain_match = min_gain == ref_min_gain

        status = "OK" if (abs(delta_db) < 0.15 and steps_match and max_gain_match and min_gain_match) else "MISMATCH"
        if status != "OK":
            all_ok = False

        print(
            f"{fname:<12} {volume:>7.1f} {raw_db:>8.3f} {steps:>6d} {applied_db:>10.1f} "
            f"{max_amp:>12.2f} {max_gain:>5d} {min_gain:>5d}  "
            f"{delta_db:>+14.3f} {steps_match!s:>7} {max_gain_match!s:>6} {min_gain_match!s:>6}  {status}"
        )

    print()
    if all_ok:
        print("OK  All results match reference within tolerance.")
    else:
        print("FAIL  Some results differ from reference.")
    print()

    # Now verify the 89db reference files with mp3gain.exe
    print("Running mp3gain.exe on reference 89db files for cross-check...")
    import subprocess
    ref_files = sorted(REFERENCE_DIR.glob("*.mp3"))
    if ref_files:
        r = subprocess.run(
            ["c:/bin/mp3gain-win-1_2_5/mp3gain.exe", "-q", "-o"] + [str(f) for f in ref_files],
            capture_output=True, text=True
        )
        print(r.stdout or r.stderr)


if __name__ == "__main__":
    main()
