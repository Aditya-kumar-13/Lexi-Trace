from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(label: str, command: list[str], *, cwd: Path = ROOT) -> None:
    print(f"\n[{label}] {' '.join(command)}", flush=True)
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode:
        raise SystemExit(f"{label} failed with exit code {completed.returncode}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the cross-platform LexiTrace quality gate.")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Skip long behavioral evaluations, calibration, soak, and frontend build.",
    )
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="quality-", dir=ROOT / "data") as test_temp:
        run(
            "tests",
            [PYTHON, "-m", "pytest", "apps/api/tests", "--basetemp", test_temp],
        )
    run("format", [PYTHON, "-m", "ruff", "format", "--check", "."])
    run("lint", [PYTHON, "-m", "ruff", "check", "."])
    run("migrations", [PYTHON, "-m", "alembic", "check"])
    run("v6 baseline", [PYTHON, "scripts/freeze_v6_baseline.py", "verify"])
    if not args.quick:
        development = ROOT / "results" / "v7" / "development" / "current"
        run(
            "smoke",
            [PYTHON, "evaluation/run.py", "--output", str(development / "smoke")],
        )
        run(
            "robustness",
            [
                PYTHON,
                "evaluation/run.py",
                "--dataset",
                "data/benchmark/robustness.jsonl",
                "--output",
                str(development / "robustness"),
            ],
        )
        run(
            "journeys",
            [PYTHON, "evaluation/run_journeys.py", "--output", str(development / "journeys")],
        )
        run(
            "ASR learning",
            [
                PYTHON,
                "evaluation/run_asr_learning.py",
                "--output",
                str(development / "asr-learning"),
            ],
        )
        run(
            "lifecycle",
            [
                PYTHON,
                "evaluation/run_lifecycle.py",
                "--output",
                str(development / "lifecycle"),
            ],
        )
        run(
            "conflicts",
            [
                PYTHON,
                "evaluation/run_conflicts.py",
                "--output",
                str(development / "conflicts"),
            ],
        )
        run(
            "calibration",
            [
                PYTHON,
                "evaluation/calibrate_policy.py",
                "--cases",
                str(development / "robustness" / "cases.jsonl"),
                "--safety-cases",
                str(development / "smoke" / "cases.jsonl"),
                "--output",
                str(development / "calibration"),
            ],
        )
        run(
            "v7 instrumentation",
            [
                PYTHON,
                "evaluation/run_v7_instrumentation.py",
                "--cases",
                str(development / "smoke" / "cases.jsonl"),
                "--cases",
                str(development / "robustness" / "cases.jsonl"),
                "--output",
                str(development / "instrumentation"),
            ],
        )
        run(
            "soak",
            [
                PYTHON,
                "evaluation/run_soak.py",
                "--output",
                str(development / "soak"),
            ],
        )
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
        if npm is None:
            raise SystemExit("npm is required for the full quality gate")
        run("frontend", [npm, "run", "build"], cwd=ROOT / "apps" / "web")
    run("submission preflight", [PYTHON, "scripts/verify_submission.py"])


if __name__ == "__main__":
    main()
