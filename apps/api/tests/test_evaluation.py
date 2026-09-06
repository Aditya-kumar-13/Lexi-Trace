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
