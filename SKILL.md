---
name: rubric-gate
description: >-
  Evaluate task complexity and enforce strict True/False quality rubrics backed
  by automated tests. Use when starting a feature or project with 3+ files, new
  integrations, multi-session scope, or when auditing whether a proposed Agent
  Skill passes objective usefulness gates. Skip for tiny single-file edits.
---

# Rubric Gate (`rubric-gate`)

## Role & Constraints
- **Role:** Objective Verification & Gatekeeper Engineer.
- **Constraints:**
  - Every rubric criterion MUST resolve to strictly `true` or `false` (no `1–5` or subjective ratings).
  - Never invent vague criteria (e.g., `"clean code"`, `"looks nice"`, `"works well"`). Tie every check to a failure mode or observable behavior.
  - Store mutable rubric state in JSON (`rubric.json`), not editable Markdown prose.
  - Separate checks into `blocker` (must pass to ship) and `polish` (nice-to-have for v2). In `FULL` mode, include at least 1 `blocker` and at least 1 `polish` item so non-critical v2 ideas never creep into MVP blockers.
  - Prefer deterministic `auto_code` tests over `auto_eval` or `human_check` whenever possible.

## Step 1: Run the Complexity Threshold Gate
Before writing a rubric, run [scripts/complexity_check.py](./scripts/complexity_check.py) (from this skill's directory) to check whether the task needs one:
```bash
python3 <skill_dir>/scripts/complexity_check.py --files <N> --integrations <N> [--multi-session] [--high-risk] [--plan-requested]
```
- **`SKIP`:** `< 3` files, `0` new integrations, single-session, low risk -> skip `rubric.json` and build directly.
- **`LIGHT`:** 1 trigger met -> create 3–5 `blocker` True/False items only.
- **`FULL`:** 2+ triggers met -> create full `rubric.json` (`tier_mode: "FULL"`, with both `blocker` and `>=1` `polish` items) using [references/rubric_schema.md](./references/rubric_schema.md).

## Step 2: Author `rubric.json` & Map Automated Tests
1. Read [references/rubric_schema.md](./references/rubric_schema.md) for the exact JSON layout.
2. Tag every criterion with a `verification_type`:
   - `auto_code`: Declarative check (`file_exists`, `line_count_max`, `regex_present`, `regex_absent`, `json_valid`) or shell `command`.
   - `auto_eval`: Binary prompt-eval assertion for qualitative rules.
   - `human_check`: Only for physical/UX checks code cannot verify.
3. For auditing **Agent Skills** themselves, read [references/skill_usefulness_rubric.md](./references/skill_usefulness_rubric.md) and run [scripts/audit_skill.py](./scripts/audit_skill.py):
   ```bash
   python3 <skill_dir>/scripts/audit_skill.py <path/to/skill_dir>
   ```

## Step 3: Verify & Enforce Gates
Run [scripts/check_rubric.py](./scripts/check_rubric.py) to validate schema (pre-code) or execute gates (post-code):
```bash
python3 <skill_dir>/scripts/check_rubric.py <path/to/rubric.json> --validate-only
python3 <skill_dir>/scripts/check_rubric.py <path/to/rubric.json> --root <project_root> --run-auto
```
For deterministic enforcement at turn end in Antigravity, see [hooks/hooks.json.example](./hooks/hooks.json.example) and [hooks/rubric_stop_guard.py](./hooks/rubric_stop_guard.py).

## Output Contract & Self-Check
Return a concise pass/fail digest showing:
1. Complexity tier (`SKIP` / `LIGHT` / `FULL`).
2. `SHIP_READY`: `TRUE` or `FALSE` (true only when all `blocker` items are `true`).
3. Failing or pending item IDs with exact command output.
