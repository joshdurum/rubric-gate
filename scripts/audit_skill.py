#!/usr/bin/env python3
"""Audit any Agent Skill directory against the True/False Skill Usefulness Rubric."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT_DEFAULT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _common import estimate_tokens, load_json, parse_frontmatter  # noqa: E402

NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
INTENT_PATTERN = re.compile(r"\b(use when|use this skill|when the user|invoke|trigger|whenever)\b", re.IGNORECASE)
LINK_PATTERN = re.compile(r"\[[^\]]+\]\((\.?/?[^)#:\s]+)\)")


def check_worthiness(steps: int, reuses: int, lines_if_rule: int, has_helpers: bool) -> dict[str, Any]:
    """Evaluate Gate A (Complexity Worthiness) using 4 True/False criteria."""
    checks = {
        "multi_step_ge_3": steps >= 3,
        "reuses_ge_3": reuses >= 3,
        "heavy_for_rule_gt_30_lines": lines_if_rule > 30,
        "needs_scripts_or_refs": bool(has_helpers),
    }
    score = sum(1 for ok in checks.values() if ok)
    return {"worthy_as_skill": score >= 3, "score": score, "max_score": 4, "checks": checks}


def _check_relative_links(body: str, skill_dir: Path) -> tuple[bool, list[str]]:
    missing: list[str] = []
    for rel in LINK_PATTERN.findall(body):
        if rel.startswith("http"):
            continue
        if not (skill_dir / rel).exists():
            missing.append(rel)
    return len(missing) == 0, missing


def audit_skill_dir(skill_dir: Path, baseline_path: Path | None = None) -> dict[str, Any]:
    """Run deterministic Gate B True/False checks (S1-S6) on a skill directory."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return {
            "all_passed": False,
            "skill_dir": str(skill_dir),
            "checks": {"S1_valid_frontmatter": {"passed": False, "detail": "Missing SKILL.md"}},
        }

    text = skill_md.read_text(encoding="utf-8")
    lines = len(text.splitlines())
    tokens = estimate_tokens(text)
    meta, body = parse_frontmatter(text)

    name = meta.get("name", "")
    desc = meta.get("description", "")
    s1_ok = (
        bool(NAME_PATTERN.match(name))
        and len(name) <= 64
        and 1 <= len(desc) <= 1024
        and bool(INTENT_PATTERN.search(desc))
    )
    s2_ok = lines <= 180 and tokens <= 2500

    links_ok, missing_links = _check_relative_links(body, skill_dir)
    has_disclosure_dirs = (skill_dir / "references").is_dir() or (skill_dir / "scripts").is_dir()
    s3_ok = links_ok and (lines <= 80 or has_disclosure_dirs)

    scripts_dir = skill_dir / "scripts"
    helper_files = [p for p in scripts_dir.glob("*") if p.suffix in {".py", ".sh"}] if scripts_dir.is_dir() else []
    s4_ok = len(helper_files) > 0

    bpath = baseline_path or (SKILL_ROOT_DEFAULT / "references" / "installed_skills.json")
    baseline_names = set(load_json(bpath).get("skills", [])) if bpath.is_file() else set()
    s5_ok = bool(name) and name not in baseline_names

    tests_dir = skill_dir / "tests"
    test_files = list(tests_dir.glob("test_*.py")) if tests_dir.is_dir() else []
    triggers_file = tests_dir / "trigger_cases.json"
    triggers_ok = False
    if triggers_file.is_file():
        tdata = load_json(triggers_file)
        triggers_ok = len(tdata.get("should_trigger", [])) >= 3 and len(tdata.get("should_not_trigger", [])) >= 2
    s6_ok = len(test_files) > 0 and triggers_ok

    checks = {
        "S1_valid_frontmatter": {
            "passed": s1_ok,
            "detail": f"name={name!r}, desc_len={len(desc)}, intent_cue={bool(INTENT_PATTERN.search(desc))}",
        },
        "S2_token_leanness": {
            "passed": s2_ok,
            "detail": f"lines={lines}/180, est_tokens={tokens}/2500",
        },
        "S3_progressive_disclosure": {
            "passed": s3_ok,
            "detail": "all links resolved" if links_ok else f"broken links: {missing_links}",
        },
        "S4_deterministic_offload": {
            "passed": s4_ok,
            "detail": f"helper_scripts={[p.name for p in helper_files]}",
        },
        "S5_zero_overlap": {
            "passed": s5_ok,
            "detail": f"{name!r} unique vs {len(baseline_names)} baseline skills",
        },
        "S6_tests_and_triggers": {
            "passed": s6_ok,
            "detail": f"unit_tests={len(test_files)}, trigger_eval_valid={triggers_ok}",
        },
    }

    all_passed = all(c["passed"] for c in checks.values())
    return {"all_passed": all_passed, "skill_name": name, "skill_dir": str(skill_dir), "checks": checks}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit an Agent Skill folder using True/False checks.")
    parser.add_argument("skill_dir", nargs="?", type=Path, default=Path("."), help="Path to skill directory.")
    parser.add_argument("--baseline", type=Path, default=None, help="Path to installed_skills.json.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    report = audit_skill_dir(args.skill_dir.resolve(), baseline_path=args.baseline)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"SKILL_AUDIT_PASSED={str(report['all_passed']).upper()} ({report.get('skill_name', 'unknown')})")
        for cid, info in report["checks"].items():
            tag = "PASS" if info["passed"] else "FAIL"
            print(f"  [{tag}] {cid}: {info['detail']}")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
