from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEAL_PATH = ROOT / "evaluation" / "v7_holdout_seal.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def case_count(path: Path) -> int:
    return sum(bool(line.strip()) for line in path.read_text(encoding="utf-8").splitlines())


def load_seal() -> dict:
    return json.loads(SEAL_PATH.read_text(encoding="utf-8"))


def save_seal(payload: dict) -> None:
    SEAL_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def seal(dataset: Path, dataset_id: str, custodian: str) -> None:
    current = load_seal()
    if current["status"] != "awaiting_independent_custodian":
        raise SystemExit(f"Holdout cannot be sealed from state {current['status']!r}")
    resolved = dataset.resolve()
    if ROOT in resolved.parents:
        raise SystemExit("Final holdout must remain outside the development working tree.")
    count = case_count(resolved)
    if count == 0:
        raise SystemExit("Cannot seal an empty holdout.")
    current.update(
        {
            "status": "sealed",
            "dataset_id": dataset_id,
            "dataset_sha256": sha256(resolved),
            "case_count": count,
            "custodian": custodian,
            "sealed_at_utc": datetime.now(UTC).isoformat(),
            "opened_receipt": None,
        }
    )
    current.pop("note", None)
    save_seal(current)
    print(json.dumps(current, indent=2))


def verify_dataset(dataset: Path) -> dict:
    dataset = dataset.resolve()
    current = load_seal()
    if current["status"] != "sealed":
        raise SystemExit(f"Holdout is not sealed: {current['status']!r}")
    actual_hash = sha256(dataset)
    actual_count = case_count(dataset)
    if actual_hash != current["dataset_sha256"] or actual_count != current["case_count"]:
        raise SystemExit("Supplied holdout does not match the committed seal.")
    return current


def open_once(dataset: Path, output: Path, command: list[str]) -> None:
    current = verify_dataset(dataset)
    if current["opened_receipt"] is not None:
        raise SystemExit("The sealed holdout already has an opening receipt.")
    output = output.resolve()
    if ROOT not in output.parents:
        raise SystemExit("Holdout result and receipt must be written inside the repository.")
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()
    policy_line = next(
        line
        for line in (ROOT / "apps/api/lexitrace/policy.toml")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.startswith("version = ")
    )
    receipt = {
        "schema_version": 1,
        "status": "opened",
        "dataset_id": current["dataset_id"],
        "dataset_sha256": current["dataset_sha256"],
        "case_count": current["case_count"],
        "git_commit": commit,
        "policy_version": policy_line.split('"', 2)[1],
        "opened_at_utc": datetime.now(UTC).isoformat(),
        "command": command,
        "output": str(output),
    }
    output.mkdir(parents=True, exist_ok=False)
    receipt_path = output / "opening-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    current["opened_receipt"] = str(receipt_path.relative_to(ROOT))
    save_seal(current)
    completed = subprocess.run(command, cwd=ROOT, check=False)
    receipt["exit_code"] = completed.returncode
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(completed.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seal and audit one-time v7 holdout access.")
    subparsers = parser.add_subparsers(dest="mode", required=True)
    seal_parser = subparsers.add_parser("seal")
    seal_parser.add_argument("dataset", type=Path)
    seal_parser.add_argument("--dataset-id", required=True)
    seal_parser.add_argument("--custodian", required=True)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("dataset", type=Path)
    open_parser = subparsers.add_parser("open")
    open_parser.add_argument("dataset", type=Path)
    open_parser.add_argument("--output", type=Path, required=True)
    open_parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.mode == "seal":
        seal(args.dataset, args.dataset_id, args.custodian)
    elif args.mode == "verify":
        print(json.dumps(verify_dataset(args.dataset), indent=2))
    else:
        if not args.command:
            raise SystemExit("Provide the evaluation command after --.")
        command = args.command[1:] if args.command[0] == "--" else args.command
        open_once(args.dataset, args.output, command)


if __name__ == "__main__":
    main()
