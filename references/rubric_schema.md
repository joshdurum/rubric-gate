# Project `rubric.json` Schema Reference

Store mutable rubric state in JSON rather than Markdown prose so AI agents cannot accidentally rewrite criteria mid-task.

## Top-Level Format

```json
{
  "project": "adhd-capture-mvp",
  "version": "0.1",
  "tier_mode": "FULL",
  "criteria": [
    {
      "id": "R1",
      "statement": "Quick capture screen loads with at most 1 required field",
      "tier": "blocker",
      "verification_type": "auto_code",
      "check": {
        "kind": "command",
        "command": "python3 -m unittest tests/test_capture.py"
      },
      "passed": null
    },
    {
      "id": "R2",
      "statement": "AGENTS.md stays under 150 lines",
      "tier": "blocker",
      "verification_type": "auto_code",
      "check": {
        "kind": "line_count_max",
        "path": "AGENTS.md",
        "max_lines": 150
      },
      "passed": null
    },
    {
      "id": "R3",
      "statement": "Capture screen works cleanly one-handed on iPhone",
      "tier": "polish",
      "verification_type": "human_check",
      "check": {
        "kind": "manual",
        "prompt": "Open on phone with thumb only and save 1 note."
      },
      "passed": null
    }
  ]
}
```

## Field Rules
- `tier_mode`: Optional `"LIGHT"` or `"FULL"` matching `complexity_check.py`. When `"FULL"`, include at least 1 `"blocker"` and 1 `"polish"` item.
- `tier`: Strictly `"blocker"` (must be `true` to ship) or `"polish"` (non-blocking v2 item).
- `verification_type`: Strictly `"auto_code"`, `"auto_eval"`, or `"human_check"`.
- `passed`: Strictly `true`, `false`, or `null` (never numbers, percentages, or `"1-5"` strings).
- `statement`: Must describe a concrete, observable pass/fail condition (avoid vague phrases like `"looks good"`, `"clean code"`, `"helpful"`, `"works well"`).

## Built-In Declarative `auto_code` Checks (Zero Shell Overhead)
- `file_exists`: `{"kind": "file_exists", "path": "relative/path"}`
- `line_count_max`: `{"kind": "line_count_max", "path": "relative/path", "max_lines": 150}`
- `json_valid`: `{"kind": "json_valid", "path": "relative/path"}`
- `regex_present`: `{"kind": "regex_present", "path": "relative/path", "pattern": "^@AGENTS\\.md"}`
- `regex_absent`: `{"kind": "regex_absent", "path": "relative/path", "pattern": "TODO|FIXME"}`
- `command`: `{"kind": "command", "command": "python3 -m unittest discover -s tests"}`
