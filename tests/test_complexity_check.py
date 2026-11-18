"""Unit tests for scripts/complexity_check.py."""

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from complexity_check import evaluate_complexity  # noqa: E402


class TestComplexityCheck(unittest.TestCase):
    def test_tiny_edit_skips_rubric(self) -> None:
        res = evaluate_complexity(files=2, integrations=0, multi_session=False, high_risk=False)
        self.assertFalse(res["rubric_required"])
        self.assertEqual(res["tier"], "SKIP")
        self.assertEqual(res["trigger_count"], 0)

    def test_single_trigger_returns_light_tier(self) -> None:
        res = evaluate_complexity(files=3, integrations=0)
        self.assertTrue(res["rubric_required"])
        self.assertEqual(res["tier"], "LIGHT")
        self.assertEqual(res["trigger_count"], 1)

    def test_multiple_triggers_return_full_tier(self) -> None:
        res = evaluate_complexity(files=5, integrations=1, multi_session=True)
        self.assertTrue(res["rubric_required"])
        self.assertEqual(res["tier"], "FULL")
        self.assertEqual(res["trigger_count"], 3)


if __name__ == "__main__":
    unittest.main()
