# rubric-gate — Project Instructions & Verification Gates

## Stack Overview
- **Primary Stack:** Python 3 (standard library only, zero external dependencies), Markdown (`SKILL.md`), JSON schemas.
- **Target Ecosystem:** Hybrid Antigravity (`agy` orchestrator) + Claude Code (`claude` executor), standalone GitHub-ready skill repo.

## Key Files (Read Before Editing)
- [SKILL.md](./SKILL.md) — Core skill instructions loaded on trigger.
- [references/rubric_schema.md](./references/rubric_schema.md) — Strict JSON schema for `rubric.json`.
- [references/skill_usefulness_rubric.md](./references/skill_usefulness_rubric.md) — Gate A & Gate B True/False checks for evaluating skills.

## Working Rules
- Keep `SKILL.md` under 180 lines; put detailed docs and examples in `references/`.
- Keep all scripts pure Python stdlib so verification requires zero `pip install` steps.
- Never allow 1–5 rating scales or vague criteria (e.g., "looks good") in rubric schemas.

## Verification Gates
Run these exact commands before marking any change complete:
- **Test:** `python3 -m unittest discover -s tests -v`
- **Skill Self-Audit:** `python3 scripts/audit_skill.py .`
- **Syntax Check:** `python3 -m compileall -q scripts hooks tests`
