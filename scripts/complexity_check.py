#!/usr/bin/env python3
"""Evaluate task complexity to decide whether a True/False rubric is required."""

from __future__ import annotations

import argparse
import json
from typing import Any


def evaluate_complexity(
    files: int = 1,
    integrations: int = 0,
    multi_session: bool = False,
    high_risk: bool = False,
    plan_requested: bool = False,
) -> dict[str, Any]:
    """Return objective True/False triggers and resulting rubric tier (SKIP/LIGHT/FULL)."""
    triggers = {
        "files_ge_3": files >= 3,
        "new_integrations_ge_1": integrations >= 1,
        "multi_session": bool(multi_session),
        "high_risk": bool(high_risk),
        "plan_requested": bool(plan_requested),
    }
    trigger_count = sum(1 for hit in triggers.values() if hit)

    if trigger_count == 0:
        tier = "SKIP"
        reason = "Small, low-risk single-session edit; execute directly without rubric overhead."
    elif trigger_count == 1:
        tier = "LIGHT"
        reason = "One complexity trigger met; use 3-5 blocker True/False checks only."
    else:
        tier = "FULL"
        reason = "Multiple complexity triggers met; generate full rubric.json with automated tests."

    return {
        "rubric_required": trigger_count > 0,
        "tier": tier,
        "trigger_count": trigger_count,
        "triggers": triggers,
        "reason": reason,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check if a task needs a True/False rubric.")
    parser.add_argument("--files", type=int, default=1, help="Estimated number of files to create/edit.")
    parser.add_argument("--integrations", type=int, default=0, help="Count of new APIs/libraries/services.")
    parser.add_argument("--multi-session", action="store_true", help="Work spans more than one session.")
    parser.add_argument("--high-risk", action="store_true", help="Touches auth, payments, security, or data loss.")
    parser.add_argument("--plan-requested", action="store_true", help="User explicitly requested planning/spec.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")
    args = parser.parse_args(argv)

    result = evaluate_complexity(
        files=args.files,
        integrations=args.integrations,
        multi_session=args.multi_session,
        high_risk=args.high_risk,
        plan_requested=args.plan_requested,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"COMPLEXITY_TIER={result['tier']} (rubric_required={result['rubric_required']})")
        print(f"Reason: {result['reason']}")
        for name, hit in result["triggers"].items():
            print(f"  - {name}: {str(hit).upper()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
