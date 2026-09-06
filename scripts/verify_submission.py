from __future__ import annotations

import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PATHS = [
    "README.md",
    "RUN.md",
    ".env.example",
    "alembic.ini",
    "docker-compose.yml",
    "apps/api/lexitrace/main.py",
    "apps/web/src/App.tsx",
    "migrations/versions/0004_semantic_context.py",
    "migrations/versions/0005_asr_outcomes.py",
    "migrations/versions/0006_observation_lifecycle.py",
    "data/benchmark/smoke.jsonl",
    "data/benchmark/robustness.jsonl",
    "data/benchmark/journeys.jsonl",
    "data/benchmark/asr_journeys.jsonl",
    "data/benchmark/lifecycle_journeys.jsonl",
    "data/benchmark/conflict_journeys.jsonl",
    "results/latest/summary.json",
    "results/latest/cases.jsonl",
    "results/robustness/summary.json",
    "results/robustness/cases.jsonl",
    "results/journeys/summary.json",
    "results/journeys/cases.json",
    "results/asr-learning/summary.json",
    "results/asr-learning/cases.json",
    "results/lifecycle/summary.json",
    "results/lifecycle/cases.json",
    "results/calibration/policy.json",
    "results/calibration/report.md",
    "results/conflicts/summary.json",
    "results/conflicts/cases.json",
    "results/conflicts/report.md",
    "results/soak/summary.json",
    "results/soak/failures.json",
    "results/soak/report.md",
    "scripts/reviewer_demo.py",
    "docs/brief-alignment.md",
    "docs/evaluation.md",
    "docs/v7-definition-of-done.md",
    "docs/v7-experimental-protocol.md",
    "docs/v7-phase1-findings.md",
    "docs/v7-phase2-phonetic-experiment.md",
    "docs/v7-phase2-asr-confidence-experiment.md",
    "docs/v7-phase2-semantic-retrieval-experiment.md",
    "docs/v7-phase2-semantic-safety-findings.md",
    "docs/v7-phase2-conflict-floor-experiment.md",
    "evaluation/v7_holdout_seal.json",
    "data/benchmark/v7_indic_phonetic_development.jsonl",
    "data/benchmark/v7_semantic_multimodal_development.jsonl",
    "data/benchmark/v7_semantic_safety_development.jsonl",
    "results/baselines/v6/manifest.json",
    "results/v7/development/baseline-v6-instrumented/summary.json",
    "results/v7/development/baseline-v6-instrumented/failures.json",
    "scripts/freeze_v6_baseline.py",
    "evaluation/run_conflict_floor_sweep.py",
    "scripts/holdout_guard.py",
    "scripts/run_quality_gate.py",
    "evaluation/run_v7_instrumentation.py",
    "evaluation/run_phonetic_ground_truth.py",
    "evaluation/compare_structural_runs.py",
    "results/v7/development/indic-transliteration-experiment-v1/summary.json",
    "results/v7/development/indic-transliteration-experiment-v1/cases.json",
    "results/v7/development/asr-confidence-experiment-v1/instrumentation-summary.json",
    "results/v7/development/asr-confidence-experiment-v1/robustness-summary.json",
    "results/v7/development/semantic-retrieval-experiment-v1/centroid-summary.json",
    "results/v7/development/semantic-retrieval-experiment-v1/nearest-summary.json",
    "results/v7/development/semantic-retrieval-experiment-v1/mean-top-three-summary.json",
    "results/v7/development/semantic-safety-experiment-v1/centroid-lifecycle-summary.json",
    "results/v7/development/semantic-safety-experiment-v1/nearest-lifecycle-summary.json",
    "results/v7/development/semantic-safety-experiment-v1/centroid-fixed-summary.json",
    "results/v7/development/semantic-safety-experiment-v1/nearest-fixed-summary.json",
    "results/v7/development/conflict-floor-experiment-v1/comparison.json",
    "results/v7/development/conflict-floor-experiment-v1/combined-smoke-summary.json",
    "results/v7/development/conflict-floor-experiment-v1/combined-robustness-summary.json",
    "results/v7/development/conflict-floor-experiment-v1/combined-journeys-summary.json",
    "results/v7/development/conflict-floor-experiment-v1/combined-multimodal-summary.json",
]
RUN_TOKENS = [
    "Primary review method",
    "Docker Desktop",
    "Environment variables",
    "docker compose up --build",
    "scripts/seed.py",
    "http://localhost:5173",
    "evaluation/run.py",
    "evaluation/run_asr_learning.py",
    "evaluation/run_lifecycle.py",
    "evaluation/calibrate_policy.py",
    "evaluation/run_conflicts.py",
    "evaluation/run_soak.py",
    "data/benchmark/robustness.jsonl",
    "results/robustness",
    "scripts/reviewer_demo.py",
    "api/v1/reset",
    "docker compose down --volumes",
]
SECRET_PATTERNS = {
    "OpenAI-style API key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
TEXT_SUFFIXES = {
    ".css",
    ".env",
    ".example",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
EXCLUDED_PARTS = {".git", ".venv", "node_modules", "dist", "models", "__pycache__"}


def add(checks: list[dict], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "passed": passed, "detail": detail})


def check_results(checks: list[dict], result_dir: str) -> None:
    summary_path = ROOT / result_dir / "summary.json"
    if not summary_path.exists():
        add(checks, f"result:{result_dir}", False, "summary.json is missing")
        return
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    dataset_path = ROOT / summary["dataset"]
    expected_hash = summary["dataset_sha256"]
    actual_hash = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    count_key = "case_count" if "case_count" in summary else "journeys"
    source_count = sum(
        bool(line.strip()) for line in dataset_path.read_text(encoding="utf-8").splitlines()
    )
    passed = actual_hash == expected_hash and source_count == summary[count_key]
    add(
        checks,
        f"result:{result_dir}",
        passed,
        f"hash_match={actual_hash == expected_hash}, {count_key}={source_count}",
    )


def scan_for_secrets() -> list[str]:
    findings: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or EXCLUDED_PARTS.intersection(path.parts):
            continue
        if path.suffix.casefold() not in TEXT_SUFFIXES and path.name != ".env.example":
            continue
        try:
            value = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(value):
                findings.append(f"{path.relative_to(ROOT).as_posix()}: {label}")
    return findings


def check_calibration_artifact(checks: list[dict]) -> None:
    artifact_path = ROOT / "results" / "calibration" / "policy.json"
    if not artifact_path.exists():
        add(checks, "calibration_release_gate", False, "policy.json is missing")
        return
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    source = ROOT / artifact["source_cases"]
    safety = ROOT / artifact["safety_cases"]
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    safety_hash = hashlib.sha256(safety.read_bytes()).hexdigest()
    policy = tomllib.loads((ROOT / "apps/api/lexitrace/policy.toml").read_text(encoding="utf-8"))
    checks_pass = (
        source_hash == artifact["source_cases_sha256"]
        and safety_hash == artifact["safety_cases_sha256"]
        and artifact["heldout_rows_accessed"] == 0
        and artifact["selected"]["apply_threshold"] == policy["thresholds"]["apply"]
    )
    add(
        checks,
        "calibration_release_gate",
        checks_pass,
        "source_hash_match={}, safety_hash_match={}, heldout_rows={}, selected={}".format(
            source_hash == artifact["source_cases_sha256"],
            safety_hash == artifact["safety_cases_sha256"],
            artifact["heldout_rows_accessed"],
            artifact["selected"]["apply_threshold"],
        ),
    )


def check_soak_artifact(checks: list[dict]) -> None:
    path = ROOT / "results" / "soak" / "summary.json"
    if not path.exists():
        add(checks, "local_soak", False, "summary.json is missing")
        return
    summary = json.loads(path.read_text(encoding="utf-8"))
    passed = (
        summary["iterations"] >= 500
        and summary["unique_traces"] == summary["iterations"]
        and summary["failures"] == 0
        and summary["hosted_requests"] == 0
    )
    add(
        checks,
        "local_soak",
        passed,
        "iterations={}, unique_traces={}, failures={}, p95_ms={}".format(
            summary["iterations"],
            summary["unique_traces"],
            summary["failures"],
            summary["latency_ms"]["p95"],
        ),
    )


def check_v7_protocol(checks: list[dict]) -> None:
    baseline_path = ROOT / "results" / "baselines" / "v6" / "manifest.json"
    seal_path = ROOT / "evaluation" / "v7_holdout_seal.json"
    if not baseline_path.is_file() or not seal_path.is_file():
        add(checks, "v7_protocol", False, "baseline manifest or holdout seal is missing")
        return
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    changed = []
    for relative, expected in baseline["files"].items():
        path = ROOT / relative
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "missing"
        if actual != expected:
            changed.append(relative)
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    seal_valid = seal["status"] in {"awaiting_independent_custodian", "sealed"}
    add(
        checks,
        "v7_protocol",
        not changed and seal_valid,
        f"changed_v6_artifacts={changed!r}, holdout_status={seal['status']!r}",
    )


def main() -> None:
    checks: list[dict] = []
    missing = [path for path in REQUIRED_PATHS if not (ROOT / path).exists()]
    add(checks, "required_files", not missing, "missing=" + repr(missing))

    run_text = (ROOT / "RUN.md").read_text(encoding="utf-8")
    missing_run_tokens = [token for token in RUN_TOKENS if token not in run_text]
    add(
        checks,
        "documented_review_path",
        not missing_run_tokens,
        "missing=" + repr(missing_run_tokens),
    )

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_version = pyproject["project"]["version"]
    init_match = re.search(
        r'__version__\s*=\s*"([^"]+)"',
        (ROOT / "apps/api/lexitrace/__init__.py").read_text(encoding="utf-8"),
    )
    init_version = init_match.group(1) if init_match else "missing"
    web_version = json.loads((ROOT / "apps/web/package.json").read_text(encoding="utf-8"))[
        "version"
    ]
    add(
        checks,
        "version_alignment",
        len({package_version, init_version, web_version}) == 1,
        f"python={package_version}, package={init_version}, web={web_version}",
    )

    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    heads = ScriptDirectory.from_config(config).get_heads()
    add(checks, "single_migration_head", len(heads) == 1, f"heads={heads}")

    robustness_count = sum(
        bool(line.strip())
        for line in (ROOT / "data/benchmark/robustness.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    add(
        checks,
        "robustness_corpus",
        robustness_count >= 200,
        f"cases={robustness_count}",
    )

    for result_dir in (
        "results/latest",
        "results/robustness",
        "results/journeys",
        "results/asr-learning",
        "results/lifecycle",
        "results/conflicts",
    ):
        check_results(checks, result_dir)

    check_calibration_artifact(checks)
    check_soak_artifact(checks)
    check_v7_protocol(checks)

    secret_findings = scan_for_secrets()
    add(checks, "credential_scan", not secret_findings, "findings=" + repr(secret_findings))

    failed = [check for check in checks if not check["passed"]]
    report = {
        "status": "pass" if not failed else "fail",
        "checks": checks,
        "failed": len(failed),
    }
    print(json.dumps(report, indent=2))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
