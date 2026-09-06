import json
import subprocess
import sys
from pathlib import Path


def test_smoke_evaluation_is_reproducible(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[3]
    output = tmp_path / "results"
    completed = subprocess.run(
        [
            sys.executable,
            str(root / "evaluation" / "run.py"),
            "--dataset",
            str(root / "data" / "benchmark" / "smoke.jsonl"),
            "--output",
            str(output),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["case_count"] == 28
    assert summary["systems"]["lexitrace"]["exact_match_rate"] >= 0.90
    assert summary["systems"]["lexitrace"]["incorrect_intervention_rate"] <= 0.05
    assert (output / "cases.jsonl").exists()
    assert (output / "report.md").exists()


def test_asr_learning_evaluation_is_reproducible(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[3]
    output = tmp_path / "asr-results"
    completed = subprocess.run(
        [
            sys.executable,
            str(root / "evaluation" / "run_asr_learning.py"),
            "--output",
            str(output),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    learned = summary["systems"]["learned_asr"]
    ablation = summary["systems"]["no_learning_ablation"]
    assert summary["journeys"] >= 4
    assert learned["wrong_interventions"] == 0
    assert learned["exact_match_rate"] == 1.0
    assert learned["exact_match_rate"] > ablation["exact_match_rate"]


def test_memory_lifecycle_evaluation_is_reproducible(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[3]
    output = tmp_path / "lifecycle-results"
    completed = subprocess.run(
        [
            sys.executable,
            str(root / "evaluation" / "run_lifecycle.py"),
            "--output",
            str(output),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    lifecycle = summary["systems"]["event_lifecycle"]
    ablation = summary["systems"]["no_lifecycle_ablation"]
    assert lifecycle["event_accuracy"] == 1.0
    assert lifecycle["wrong_interventions"] == 0
    assert lifecycle["event_accuracy"] > ablation["event_accuracy"]


def test_policy_calibration_is_split_safe_and_reproducible(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[3]
    output = tmp_path / "calibration-results"
    completed = subprocess.run(
        [
            sys.executable,
            str(root / "evaluation" / "calibrate_policy.py"),
            "--output",
            str(output),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    policy = json.loads((output / "policy.json").read_text(encoding="utf-8"))
    assert policy["split_used"] == "calibration"
    assert policy["heldout_rows_accessed"] == 0
    assert policy["calibration_candidate"]["apply_threshold"] == 0.9
    assert policy["selected"]["apply_threshold"] == 0.93
    assert policy["selected"]["wrong_interventions"] == 0
    assert policy["calibration_candidate"]["exact_matches"] > policy["baseline"]["exact_matches"]
    assert policy["calibration_candidate_safety"]["wrong_interventions"] == 2
    assert policy["deployment_gate"]["status"] == "reject_candidate_keep_active"
