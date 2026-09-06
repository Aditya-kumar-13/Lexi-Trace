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


def test_conflict_journeys_are_reproducible(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[3]
    output = tmp_path / "conflict-results"
    completed = subprocess.run(
        [
            sys.executable,
            str(root / "evaluation" / "run_conflicts.py"),
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
    assert summary["journeys"] == 4
    assert summary["exact_match_rate"] == 1.0
    assert summary["wrong_interventions"] == 0
    assert summary["deterministic_journeys"] == 4


def test_local_soak_runner_preserves_outputs_and_unique_traces(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[3]
    output = tmp_path / "soak-results"
    completed = subprocess.run(
        [
            sys.executable,
            str(root / "evaluation" / "run_soak.py"),
            "--iterations",
            "20",
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
    assert summary["iterations"] == 20
    assert summary["unique_traces"] == 20
    assert summary["failures"] == 0
    assert summary["database"]["rows"]["decisions"] == 20


def test_disposable_reviewer_demo_completes() -> None:
    root = Path(__file__).resolve().parents[3]
    completed = subprocess.run(
        [sys.executable, str(root / "scripts" / "reviewer_demo.py")],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["positive"]["output"] == "Review the Kivi service deployment."
    assert result["negative"]["action"] == "abstain"
