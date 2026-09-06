from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "results" / "baselines" / "v6" / "manifest.json"
FROZEN_COMMIT = "ca9cbe7"
FROZEN_POLICY = "2026-09-06-hybrid-v6-conflict-safe"
FROZEN_GIT_PATHS = (
    "apps/api/lexitrace/engine.py",
    "apps/api/lexitrace/policy.py",
    "apps/api/lexitrace/policy.toml",
)
FROZEN_PATHS = (
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
    "results/conflicts/summary.json",
    "results/conflicts/cases.json",
    "results/soak/summary.json",
    "results/soak/failures.json",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()


def git_blob(relative: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{FROZEN_COMMIT}:{relative}"], cwd=ROOT)


def current_policy_version() -> str:
    lines = (ROOT / "apps/api/lexitrace/policy.toml").read_text(encoding="utf-8").splitlines()
    for line in lines:
        if line.startswith("version = "):
            return line.split('"', 2)[1]
    raise RuntimeError("policy version is missing")


def build_manifest() -> dict:
    missing = [relative for relative in FROZEN_PATHS if not (ROOT / relative).is_file()]
    if missing:
        raise SystemExit(f"Cannot freeze v6; missing files: {missing}")
    head = git("rev-parse", "--short", "HEAD")
    if head != FROZEN_COMMIT:
        raise SystemExit(f"Expected v6 HEAD {FROZEN_COMMIT}, found {head}")
    policy = current_policy_version()
    if policy != FROZEN_POLICY:
        raise SystemExit(f"Expected policy {FROZEN_POLICY}, found {policy}")
    return {
        "schema_version": 1,
        "baseline": "v6",
        "git_commit": git("rev-parse", "HEAD"),
        "policy_version": policy,
        "frozen_at_utc": datetime.now(UTC).isoformat(),
        "compatibility": "immutable_json_artifacts",
        "git_files": {
            relative: hashlib.sha256(git_blob(relative)).hexdigest()
            for relative in FROZEN_GIT_PATHS
        },
        "files": {relative: sha256(ROOT / relative) for relative in FROZEN_PATHS},
    }


def verify() -> None:
    if not MANIFEST.is_file():
        raise SystemExit(f"Missing baseline manifest: {MANIFEST}")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    failures = []
    for relative, expected in manifest["git_files"].items():
        actual = hashlib.sha256(git_blob(relative)).hexdigest()
        if actual != expected:
            failures.append({"path": relative, "expected": expected, "actual": actual})
    for relative, expected in manifest["files"].items():
        path = ROOT / relative
        actual = sha256(path) if path.is_file() else "missing"
        if actual != expected:
            failures.append({"path": relative, "expected": expected, "actual": actual})
    print(
        json.dumps({"status": "pass" if not failures else "fail", "failures": failures}, indent=2)
    )
    if failures:
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze or verify immutable v6 evidence.")
    parser.add_argument("mode", choices=("freeze", "verify"))
    args = parser.parse_args()
    if args.mode == "verify":
        verify()
        return
    if MANIFEST.exists():
        raise SystemExit("The v6 baseline is already frozen; use verify instead.")
    payload = build_manifest()
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Frozen {len(payload['files'])} v6 artifacts in {MANIFEST}")


if __name__ == "__main__":
    main()
