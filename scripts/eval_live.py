#!/usr/bin/env python3
"""Run Stage 2/3 live Claude Code evaluations (Trigger Accuracy + A/B Quality Lift)."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _common import load_json, parse_frontmatter, save_json  # noqa: E402
from check_rubric import VAGUE_PATTERNS, validate_rubric_schema  # noqa: E402

DISTRACTOR_SKILLS = [
    {
        "name": "build-prompt",
        "description": "Guide a novice through clarifying questions to compile a token-optimized prompt.",
    },
    {
        "name": "init-project-gates",
        "description": "Audit a repository stack and write Verification Gates into AGENTS.md and CLAUDE.md.",
    },
    {
        "name": "route-task",
        "description": "Inspect workspace state and recommend Antigravity vs Claude Code model tier.",
    },
]

AB_TASK_PROMPT = (
    "Before we write code for a new ADHD quick-capture CLI app "
    "(4 files: capture.py, store.py, cli.py, test_cli.py, using SQLite), "
    "create a project verification rubric file in the current working directory "
    "so we can tell objectively when v0.1 is ready to ship. "
    "If you have relevant project skills available, follow them. "
    "Do not write the application source code yet."
)


def _run_claude(args: list[str], cwd: Path, timeout: int = 180) -> dict[str, Any]:
    cmd = ["claude", "-p", *args]
    t0 = time.monotonic()
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
    elapsed = round(time.monotonic() - t0, 2)
    if proc.returncode != 0:
        raise RuntimeError(f"claude failed (exit {proc.returncode}): {proc.stderr or proc.stdout}")
    data = json.loads(proc.stdout)
    data["_wall_seconds"] = elapsed
    return data


def run_trigger_eval(skill_dir: Path, model: str = "haiku") -> dict[str, Any]:
    """Evaluate U2 Trigger Precision against tests/trigger_cases.json."""
    skill_md = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    meta, _ = parse_frontmatter(skill_md)
    triggers = load_json(skill_dir / "tests" / "trigger_cases.json")

    catalog = [{"name": meta["name"], "description": meta["description"]}, *DISTRACTOR_SKILLS]
    schema = json.dumps({
        "type": "object",
        "properties": {
            "should_activate_rubric_gate": {"type": "boolean"},
            "chosen_skill": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["should_activate_rubric_gate", "chosen_skill", "reason"],
        "additionalProperties": False,
    })

    cases: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for expected, key in [(True, "should_trigger"), (False, "should_not_trigger")]:
            for prompt in triggers[key]:
                router_prompt = (
                    "You are an agent skill router. Given these available skills:\n"
                    f"{json.dumps(catalog, indent=2)}\n\n"
                    f"User request: {prompt!r}\n\n"
                    "Decide strictly whether `rubric-gate` should be activated for this request."
                )
                raw = _run_claude(
                    [
                        router_prompt,
                        "--model",
                        model,
                        "--effort",
                        "low",
                        "--safe-mode",
                        "--no-session-persistence",
                        "--tools",
                        "",
                        "--output-format",
                        "json",
                        "--json-schema",
                        schema,
                        "--max-budget-usd",
                        "0.25",
                    ],
                    cwd=tmp_path,
                    timeout=90,
                )
                structured = raw.get("structured_output") or json.loads(raw["result"])
                predicted = bool(structured["should_activate_rubric_gate"])
                cases.append({
                    "prompt": prompt,
                    "expected": expected,
                    "predicted": predicted,
                    "passed": predicted == expected,
                    "chosen_skill": structured.get("chosen_skill"),
                    "reason": structured.get("reason"),
                    "cost_usd": raw.get("total_cost_usd", 0.0),
                })

    pos_hits = sum(1 for c in cases if c["expected"] and c["passed"])
    neg_fp = sum(1 for c in cases if not c["expected"] and not c["passed"])
    return {
        "u2_passed": pos_hits >= 2 and neg_fp == 0,
        "positive_hits": pos_hits,
        "positive_total": sum(1 for c in cases if c["expected"]),
        "negative_false_positives": neg_fp,
        "negative_total": sum(1 for c in cases if not c["expected"]),
        "cases": cases,
    }


def _grade_workspace(work_dir: Path, response_text: str) -> dict[str, Any]:
    """Apply strict True/False checks to whatever rubric artifacts an arm produced."""
    json_files = [p for p in work_dir.rglob("*.json") if ".claude" not in p.parts]
    md_files = [p for p in work_dir.rglob("*.md") if ".claude" not in p.parts and p.name != "CLAUDE.md"]

    rubric_json_path = next((p for p in json_files if "rubric" in p.name.lower()), json_files[0] if json_files else None)
    schema_errors: list[str] = ["No rubric JSON file created"]
    data: dict[str, Any] = {}
    has_blocker_polish = False
    has_auto_code = False

    if rubric_json_path:
        try:
            data = load_json(rubric_json_path)
            schema_errors = validate_rubric_schema(data)
            criteria = data.get("criteria", []) if isinstance(data, dict) else []
            tiers = {c.get("tier") for c in criteria if isinstance(c, dict)}
            vtypes = {c.get("verification_type") for c in criteria if isinstance(c, dict)}
            has_blocker_polish = "blocker" in tiers and "polish" in tiers
            has_auto_code = "auto_code" in vtypes
        except (OSError, json.JSONDecodeError) as exc:
            schema_errors = [str(exc)]

    all_text = response_text + "\n" + "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in md_files)
    no_vague_in_md = not bool(VAGUE_PATTERNS.search(all_text))
    tier_mode_ok = isinstance(data, dict) and data.get("tier_mode") in {"LIGHT", "FULL"}
    explicit_tier_call = bool(re.search(r"\bCOMPLEXITY_TIER\s*=\s*(LIGHT|FULL)\b|complexity_check\.py", all_text))
    complexity_evaluated = tier_mode_ok or explicit_tier_call

    checks = {
        "G1_structured_json_created": rubric_json_path is not None,
        "G2_G3_schema_strict_bool_no_vague": len(schema_errors) == 0 and no_vague_in_md,
        "G4_blocker_and_polish_split": has_blocker_polish,
        "G5_executable_auto_code_mapped": has_auto_code,
        "G6_complexity_gate_evaluated": complexity_evaluated,
    }
    return {
        "score": sum(1 for v in checks.values() if v),
        "max_score": len(checks),
        "all_passed": all(checks.values()),
        "checks": checks,
        "schema_errors": schema_errors,
        "created_files": sorted(str(p.relative_to(work_dir)) for p in work_dir.rglob("*") if p.is_file() and ".claude" not in p.parts),
    }


def _stage_skill_workspace(target_dir: Path, skill_dir: Path) -> None:
    dest = target_dir / ".claude" / "skills" / "rubric-gate"
    dest.mkdir(parents=True, exist_ok=True)
    for sub in ["SKILL.md", "references", "scripts"]:
        src = skill_dir / sub
        dst = dest / sub
        if src.is_dir():
            shutil.copytree(src, dst)
        elif src.is_file():
            shutil.copy2(src, dst)


def _extract_metrics(raw: dict[str, Any]) -> dict[str, Any]:
    usage = raw.get("usage", {})
    return {
        "cost_usd": round(float(raw.get("total_cost_usd", 0.0)), 4),
        "duration_ms": raw.get("duration_ms"),
        "wall_seconds": raw.get("_wall_seconds"),
        "num_turns": raw.get("num_turns"),
        "input_tokens": usage.get("input_tokens", 0),
        "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
    }


def run_ab_eval(skill_dir: Path, model: str = "sonnet") -> dict[str, Any]:
    """Run controlled A/B comparison: Baseline (no skill) vs rubric-gate."""
    with tempfile.TemporaryDirectory() as base_tmp, tempfile.TemporaryDirectory() as skill_tmp:
        base_dir = Path(base_tmp)
        arm_b_dir = Path(skill_tmp)
        _stage_skill_workspace(arm_b_dir, skill_dir)

        common_flags = [
            "--model",
            model,
            "--effort",
            "medium",
            "--setting-sources",
            "project",
            "--no-session-persistence",
            "--permission-mode",
            "acceptEdits",
            "--allowedTools",
            "Read,Write,Edit,Bash",
            "--output-format",
            "json",
            "--max-budget-usd",
            "1.00",
        ]

        arm_a_raw = _run_claude([AB_TASK_PROMPT, *common_flags], cwd=base_dir, timeout=180)
        arm_b_raw = _run_claude([AB_TASK_PROMPT, *common_flags], cwd=arm_b_dir, timeout=180)

        arm_a_grade = _grade_workspace(base_dir, arm_a_raw.get("result", ""))
        arm_b_grade = _grade_workspace(arm_b_dir, arm_b_raw.get("result", ""))

    return {
        "u1_measurable_lift": arm_b_grade["score"] > arm_a_grade["score"],
        "baseline_arm_a": {"grade": arm_a_grade, "metrics": _extract_metrics(arm_a_raw)},
        "with_skill_arm_b": {"grade": arm_b_grade, "metrics": _extract_metrics(arm_b_raw)},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run live Stage 2/3 Trigger + A/B Eval for rubric-gate.")
    parser.add_argument("--skill-dir", type=Path, default=SKILL_ROOT)
    parser.add_argument("--out", type=Path, default=SKILL_ROOT / "tests" / "live_eval_results.json")
    parser.add_argument("--skip-ab", action="store_true")
    parser.add_argument("--skip-trigger", action="store_true")
    args = parser.parse_args(argv)

    skill_dir = args.skill_dir.resolve()
    out_path = args.out.resolve()
    existing = load_json(out_path) if out_path.is_file() else {}
    trigger_res = existing.get("trigger_eval_u2") if args.skip_trigger else run_trigger_eval(skill_dir)
    ab_res = existing.get("ab_eval_u1") if args.skip_ab else run_ab_eval(skill_dir)

    report = {"skill": "rubric-gate", "trigger_eval_u2": trigger_res, "ab_eval_u1": ab_res}
    save_json(out_path, report)
    print(json.dumps(report, indent=2))
    trigger_ok = True if trigger_res is None else trigger_res["u2_passed"]
    ab_ok = True if ab_res is None else ab_res["u1_measurable_lift"]
    return 0 if (trigger_ok and ab_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
