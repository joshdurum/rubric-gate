"""Unit tests for tightened grading checks in scripts/eval_live.py."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from eval_live import _grade_workspace  # noqa: E402


class TestEvalLiveGrader(unittest.TestCase):
    def test_prose_full_and_light_words_do_not_trigger_g6(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "VERIFICATION.md").write_text(
                "# Verification\nRun full test suite for this lightweight CLI app.\n",
                encoding="utf-8",
            )
            grade = _grade_workspace(tmp_path, "Created a full and lightweight markdown plan.")
            self.assertFalse(grade["checks"]["G6_complexity_gate_evaluated"])
            self.assertEqual(grade["score"], 0)

    def test_valid_tier_mode_in_rubric_json_passes_all_five_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
            rubric = {
                "project": "adhd-cli",
                "tier_mode": "FULL",
                "criteria": [
                    {
                        "id": "R1",
                        "statement": "app.py file exists in project root",
                        "tier": "blocker",
                        "verification_type": "auto_code",
                        "check": {"kind": "file_exists", "path": "app.py"},
                        "passed": None,
                    },
                    {
                        "id": "R2",
                        "statement": "Quick capture flow completes under 5 seconds",
                        "tier": "polish",
                        "verification_type": "human_check",
                        "passed": None,
                    },
                ],
            }
            (tmp_path / "rubric.json").write_text(json.dumps(rubric), encoding="utf-8")
            grade = _grade_workspace(tmp_path, "Validated rubric.json.")
            self.assertTrue(grade["all_passed"])
            self.assertEqual(grade["score"], 5)


if __name__ == "__main__":
    unittest.main()
