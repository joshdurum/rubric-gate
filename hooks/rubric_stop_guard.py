#!/usr/bin/env python3
"""Antigravity Stop hook: prevent finishing if auto_code blocker items in rubric.json fail."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _common import load_json  # noqa: E402
from check_rubric import evaluate_rubric, validate_rubric_schema  # noqa: E402


def handle_stop_event(payload: dict) -> dict:
    """Evaluate Stop hook JSON payload and return Antigravity decision JSON."""
    if payload.get("continuationActive"):
        return {}

    term_reason = payload.get("terminationReason", "")
    if term_reason in {"USER_CANCELED", "ERROR"}:
        return {}

    cwd_str = payload.get("cwd") or "."
    cwd = Path(cwd_str).resolve()
    rubric_path = cwd / "rubric.json"
    if not rubric_path.is_file():
        return {}

    try:
        data = load_json(rubric_path)
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "decision": "continue",
            "reason": f"rubric.json is unreadable or invalid JSON ({exc}). Fix before finishing.",
        }

    errors = validate_rubric_schema(data)
    if errors:
        return {
            "decision": "continue",
            "reason": f"rubric.json schema errors: {'; '.join(errors[:3])}",
        }

    report = evaluate_rubric(data, root=cwd, run_auto=True)
    if report["failing_blockers"]:
        failed = ", ".join(report["failing_blockers"])
        return {
            "decision": "continue",
            "reason": f"Blocker rubric checks failed ({failed}). Fix them or update state before finishing.",
        }

    return {}


def main() -> int:
    raw = sys.stdin.read().strip()
    payload = json.loads(raw) if raw else {}
    response = handle_stop_event(payload)
    print(json.dumps(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
