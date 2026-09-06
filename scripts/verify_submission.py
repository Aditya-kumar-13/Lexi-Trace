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
    "data/benchmark/smoke.jsonl",
    "data/benchmark/robustness.jsonl",
    "data/benchmark/journeys.jsonl",
    "results/latest/summary.json",
    "results/latest/cases.jsonl",
    "results/robustness/summary.json",
    "results/robustness/cases.jsonl",
    "results/journeys/summary.json",
    "results/journeys/cases.json",
    "docs/brief-alignment.md",
    "docs/evaluation.md",
]
RUN_TOKENS = [
    "Primary review method",
    "Docker Desktop",
    "Environment variables",
    "docker compose up --build",
    "scripts/seed.py",
    "http://localhost:5173",
    "evaluation/run.py",
    "data/benchmark/robustness.jsonl",
    "results/robustness",
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

    for result_dir in ("results/latest", "results/robustness", "results/journeys"):
        check_results(checks, result_dir)

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
