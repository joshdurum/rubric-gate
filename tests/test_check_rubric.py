"""Unit tests for scripts/check_rubric.py."""

import copy
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_ROOT / "scripts"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _common import load_json  # noqa: E402
from check_rubric import evaluate_rubric, validate_rubric_schema  # noqa: E402


class TestCheckRubric(unittest.TestCase):
    def test_rejects_one_to_five_scale_and_vague_phrasing(self) -> None:
        bad = load_json(FIXTURES_DIR / "bad_rubric.json")
        errors = validate_rubric_schema(bad)
        self.assertTrue(errors)
        joined = " ".join(errors)
        self.assertIn("vague or 1-5", joined)
        self.assertIn("strictly true, false, or null", joined)

    def test_valid_sample_passes_blockers_with_pending_polish(self) -> None:
        sample = copy.deepcopy(load_json(FIXTURES_DIR / "sample_rubric.json"))
        self.assertEqual(validate_rubric_schema(sample), [])
        report = evaluate_rubric(sample, root=SKILL_ROOT, run_auto=True)
        self.assertTrue(report["ship_ready"])
        self.assertEqual(report["blocker_passed"], 2)
        self.assertEqual(report["blocker_total"], 2)
        self.assertEqual(report["polish_passed"], 0)
        self.assertEqual(report["polish_total"], 1)

    def test_failing_auto_code_blocks_ship_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            rubric = {
                "project": "failing-demo",
                "criteria": [
                    {
                        "id": "F1",
                        "statement": "Required output.json file exists after build",
                        "tier": "blocker",
                        "verification_type": "auto_code",
                        "check": {"kind": "file_exists", "path": "output.json"},
                        "passed": None,
                    }
                ],
            }
            self.assertEqual(validate_rubric_schema(rubric), [])
            report = evaluate_rubric(rubric, root=tmp_path, run_auto=True)
            self.assertFalse(report["ship_ready"])
            self.assertEqual(report["failing_blockers"], ["F1"])

    def test_regex_absent_and_command_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
            rubric = {
                "project": "cmd-demo",
                "criteria": [
                    {
                        "id": "C1",
                        "statement": "No TODO markers remain in app.py",
                        "tier": "blocker",
                        "verification_type": "auto_code",
                        "check": {"kind": "regex_absent", "path": "app.py", "pattern": "TODO"},
                        "passed": None,
                    },
                    {
                        "id": "C2",
                        "statement": "Python syntax compiles without errors",
                        "tier": "blocker",
                        "verification_type": "auto_code",
                        "check": {"kind": "command", "command": "python3 -m py_compile app.py"},
                        "passed": None,
                    },
                ],
            }
            report = evaluate_rubric(rubric, root=tmp_path, run_auto=True)
            self.assertTrue(report["ship_ready"])
            self.assertEqual(report["blocker_passed"], 2)

    def test_full_tier_requires_blocker_and_polish_split(self) -> None:
        only_blocker = {
            "project": "full-no-polish",
            "tier_mode": "FULL",
            "criteria": [
                {
                    "id": "R1",
                    "statement": "Required file exists in project root",
                    "tier": "blocker",
                    "verification_type": "auto_code",
                    "check": {"kind": "file_exists", "path": "SKILL.md"},
                    "passed": None,
                }
            ],
        }
        errors = validate_rubric_schema(only_blocker)
        self.assertTrue(any("polish" in err for err in errors))

        light_only_blocker = dict(only_blocker, tier_mode="LIGHT")
        self.assertEqual(validate_rubric_schema(light_only_blocker), [])


if __name__ == "__main__":
    unittest.main()
