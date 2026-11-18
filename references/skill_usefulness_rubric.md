# Skill Usefulness Rubric (Strictly True / False)

Use this rubric before creating or shipping any Agent Skill to ensure it improves outcomes rather than causing **negative transfer** or token bloat.

## Gate A: Worthiness Metric (Should this be a Skill at all?)
Build a standalone `SKILL.md` only if **3 of 4** checks are `TRUE` (otherwise use a short rule in `AGENTS.md` / `CLAUDE.md`):
1. **Multi-Step Procedure:** Requires 3 or more ordered steps or conditional decisions (`TRUE / FALSE`).
2. **Cross-Project Reuse:** Expected to run across 3 or more sessions or repositories (`TRUE / FALSE`).
3. **Context Weight:** Putting the full guide in `AGENTS.md` would waste >30 always-loaded lines (`TRUE / FALSE`).
4. **Helper Value:** Benefits from bundling deterministic scripts (`scripts/`) or schemas (`references/`) (`TRUE / FALSE`).

## Gate B: Skill Quality & ROI Checks
| ID | Criterion | Pass Condition (`TRUE`) | Verification Mode |
| :--- | :--- | :--- | :--- |
| **S1** | Valid `SKILL.md` Frontmatter | `name` is lowercase hyphenated (`<=64` chars); `description` (`<=1024` chars) states **what** it does and **when** to use it. | `auto_code` |
| **S2** | Token & Line Leanness | `SKILL.md` is `<=180` lines and `<=2500` estimated tokens. | `auto_code` |
| **S3** | Progressive Disclosure | Heavy reference docs live in `references/` or scripts in `scripts/`, and all relative links in `SKILL.md` resolve to real files. | `auto_code` |
| **S4** | Deterministic Offload | Includes executable helper code in `scripts/` rather than asking the LLM to perform brittle counting/parsing mentally. | `auto_code` |
| **S5** | Zero Conflict / Overlap | Skill name does not collide with installed baseline skills in `references/installed_skills.json`. | `auto_code` |
| **S6** | Automated Tests & Trigger Eval | Repo contains runnable `tests/` and `tests/trigger_cases.json` (`>=3` positive + `>=2` negative prompts). | `auto_code` |
| **U1** | Measurable Eval Lift | Agent passes a test task **with** the skill that it fails or drifts on **without** the skill. | `auto_eval` |
| **U7** | Net Turn / Token Efficiency | Cuts total user retries or wasted context across real usage. | `human_check` |
