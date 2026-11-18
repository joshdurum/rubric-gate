#!/usr/bin/env python3
"""Validate and execute strict True/False checks defined in a rubric.json file."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _common import load_json, save_json  # noqa: E402

ALLOWED_TIERS = {"blocker", "polish"}
ALLOWED_TYPES = {"auto_code", "auto_eval", "human_check"}
VAGUE_PATTERNS = re.compile(
    r"\b(1\s*[-–to]+\s*5|likert|rating scale|looks good|nice ui|clean code|works well|is helpful|high quality)\b",
    re.IGNORECASE,
)


def _resolve_target(root: Path, rel_path: str) -> Path:
    return (root / rel_path).resolve()


def _check_file_exists(check: dict[str, Any], root: Path) -> tuple[bool, str]:
    target = _resolve_target(root, check["path"])
    ok = target.exists()
    return ok, f"{check['path']} exists={ok}"


def _check_line_count_max(check: dict[str, Any], root: Path) -> tuple[bool, str]:
    target = _resolve_target(root, check["path"])
    if not target.is_file():
        return False, f"Missing file: {check['path']}"
    lines = len(target.read_text(encoding="utf-8").splitlines())
    limit = int(check["max_lines"])
    return lines <= limit, f"{check['path']} has {lines} lines (max {limit})"


def _check_json_valid(check: dict[str, Any], root: Path) -> tuple[bool, str]:
    target = _resolve_target(root, check["path"])
    if not target.is_file():
        return False, f"Missing file: {check['path']}"
    try:
        load_json(target)
        return True, f"{check['path']} is valid JSON"
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"Invalid JSON in {check['path']}: {exc}"


def _check_regex(check: dict[str, Any], root: Path, expect_present: bool) -> tuple[bool, str]:
    target = _resolve_target(root, check["path"])
    if not target.is_file():
        return False, f"Missing file: {check['path']}"
    content = target.read_text(encoding="utf-8")
    matched = bool(re.search(check["pattern"], content, re.MULTILINE))
    ok = matched if expect_present else not matched
    verb = "matched" if expect_present else "absent"
    return ok, f"Pattern {check['pattern']!r} {verb}={ok} in {check['path']}"


def _check_command(check: dict[str, Any], root: Path) -> tuple[bool, str]:
    timeout = int(check.get("timeout", 30))
    proc = subprocess.run(
        check["command"],
        shell=True,
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    ok = proc.returncode == 0
    snippet = (proc.stdout or proc.stderr or "").strip().splitlines()
    tail = snippet[-1] if snippet else f"exit={proc.returncode}"
    return ok, f"exit={proc.returncode} ({tail[:120]})"


AUTO_CHECK_HANDLERS: dict[str, Callable[[dict[str, Any], Path], tuple[bool, str]]] = {
    "file_exists": _check_file_exists,
    "line_count_max": _check_line_count_max,
    "json_valid": _check_json_valid,
    "regex_present": lambda c, r: _check_regex(c, r, expect_present=True),
    "regex_absent": lambda c, r: _check_regex(c, r, expect_present=False),
    "command": _check_command,
}


def validate_rubric_schema(data: Any) -> list[str]:
    """Validate strict True/False rubric schema and reject vague or 1-5 criteria."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Root rubric must be a JSON object."]

    criteria = data.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        return ["Rubric must contain a non-empty 'criteria' list."]

    tier_mode = data.get("tier_mode")
    if tier_mode is not None and tier_mode not in {"LIGHT", "FULL"}:
        errors.append(f"tier_mode must be 'LIGHT' or 'FULL' (got {tier_mode!r}).")

    seen_ids: set[str] = set()
    for idx, item in enumerate(criteria):
        prefix = f"criteria[{idx}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix}: item must be an object.")
            continue

        cid = str(item.get("id", "")).strip()
        if not cid:
            errors.append(f"{prefix}: missing 'id'.")
        elif cid in seen_ids:
            errors.append(f"{prefix}: duplicate id {cid!r}.")
        seen_ids.add(cid)

        stmt = str(item.get("statement", "")).strip()
        if len(stmt) < 8:
            errors.append(f"{cid or prefix}: statement is too short.")
        elif VAGUE_PATTERNS.search(stmt):
            errors.append(f"{cid or prefix}: vague or 1-5 scale phrasing is disallowed ({stmt!r}).")

        if item.get("tier") not in ALLOWED_TIERS:
            errors.append(f"{cid or prefix}: tier must be 'blocker' or 'polish'.")

        vtype = item.get("verification_type")
        if vtype not in ALLOWED_TYPES:
            errors.append(f"{cid or prefix}: verification_type must be one of {sorted(ALLOWED_TYPES)}.")

        passed = item.get("passed")
        if passed is not None and not isinstance(passed, bool):
            errors.append(f"{cid or prefix}: 'passed' must be strictly true, false, or null (got {passed!r}).")

        check = item.get("check")
        if vtype == "auto_code":
            if not isinstance(check, dict) or check.get("kind") not in AUTO_CHECK_HANDLERS:
                errors.append(
                    f"{cid or prefix}: auto_code check.kind must be one of {sorted(AUTO_CHECK_HANDLERS)}."
                )

    if tier_mode == "FULL":
        tiers = {c.get("tier") for c in criteria if isinstance(c, dict)}
        if "blocker" not in tiers or "polish" not in tiers:
            errors.append("tier_mode='FULL' requires at least one 'blocker' and one 'polish' item.")

    return errors


def evaluate_rubric(data: dict[str, Any], root: Path, run_auto: bool = False) -> dict[str, Any]:
    """Evaluate criteria (optionally executing auto_code checks) and compute SHIP_READY."""
    results: list[dict[str, Any]] = []
    for item in data["criteria"]:
        passed = item.get("passed")
        detail = "recorded state"

        if run_auto and item["verification_type"] == "auto_code":
            handler = AUTO_CHECK_HANDLERS[item["check"]["kind"]]
            try:
                passed, detail = handler(item["check"], root)
            except (KeyError, OSError, subprocess.TimeoutExpired) as exc:
                passed, detail = False, f"Check error: {exc}"
            item["passed"] = passed

        results.append({
            "id": item["id"],
            "tier": item["tier"],
            "verification_type": item["verification_type"],
            "statement": item["statement"],
            "passed": passed,
            "detail": detail,
        })

    blockers = [r for r in results if r["tier"] == "blocker"]
    polish = [r for r in results if r["tier"] == "polish"]
    failing_blockers = [r["id"] for r in blockers if r["passed"] is False]
    pending_blockers = [r["id"] for r in blockers if r["passed"] is None]
    ship_ready = bool(blockers) and not failing_blockers and not pending_blockers

    return {
        "schema_valid": True,
        "ship_ready": ship_ready,
        "blocker_passed": sum(1 for r in blockers if r["passed"] is True),
        "blocker_total": len(blockers),
        "polish_passed": sum(1 for r in polish if r["passed"] is True),
        "polish_total": len(polish),
        "failing_blockers": failing_blockers,
        "pending_blockers": pending_blockers,
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and run True/False rubric.json checks.")
    parser.add_argument("rubric", type=Path, help="Path to rubric.json")
    parser.add_argument("--root", type=Path, default=None, help="Root directory for relative check paths.")
    parser.add_argument("--run-auto", action="store_true", help="Execute auto_code checks.")
    parser.add_argument("--write", action="store_true", help="Write updated passed flags back to rubric.json.")
    parser.add_argument("--validate-only", action="store_true", help="Validate schema without requiring blockers to pass.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    rubric_path = args.rubric.resolve()
    root = args.root.resolve() if args.root else rubric_path.parent
    data = load_json(rubric_path)
    errors = validate_rubric_schema(data)

    if errors:
        payload = {"schema_valid": False, "ship_ready": False, "errors": errors}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("SCHEMA_VALID=FALSE")
            for err in errors:
                print(f"  ERROR: {err}")
        return 1

    report = evaluate_rubric(data, root=root, run_auto=args.run_auto)
    if args.run_auto and args.write:
        save_json(rubric_path, data)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(
            f"SHIP_READY={str(report['ship_ready']).upper()} "
            f"(blockers: {report['blocker_passed']}/{report['blocker_total']}, "
            f"polish: {report['polish_passed']}/{report['polish_total']})"
        )
        for r in report["results"]:
            status = "PASS" if r["passed"] is True else ("FAIL" if r["passed"] is False else "PENDING")
            print(f"  [{status}] {r['id']} ({r['tier']}/{r['verification_type']}): {r['statement']} -> {r['detail']}")

    if args.validate_only:
        return 0
    return 0 if report["ship_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
