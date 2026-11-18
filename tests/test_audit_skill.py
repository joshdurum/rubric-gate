"""Unit tests for scripts/audit_skill.py (including self-audit of rubric-gate)."""

import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from audit_skill import audit_skill_dir, check_worthiness  # noqa: E402


class TestAuditSkill(unittest.TestCase):
    def test_rubric_gate_passes_all_self_audit_checks(self) -> None:
        report = audit_skill_dir(SKILL_ROOT)
        self.assertTrue(report["all_passed"], msg=f"Self-audit failed: {report}")
        for cid, info in report["checks"].items():
            self.assertTrue(info["passed"], msg=f"{cid} failed: {info}")

    def test_gate_a_worthiness_threshold(self) -> None:
        low = check_worthiness(steps=1, reuses=2, lines_if_rule=10, has_helpers=False)
        self.assertFalse(low["worthy_as_skill"])
        high = check_worthiness(steps=4, reuses=5, lines_if_rule=80, has_helpers=True)
        self.assertTrue(high["worthy_as_skill"])

    def test_detects_missing_intent_and_missing_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad_dir = Path(tmp) / "bad-skill"
            bad_dir.mkdir()
            (bad_dir / "SKILL.md").write_text(
                "---\nname: build-prompt\ndescription: Generic helper.\n---\n# Bad\n",
                encoding="utf-8",
            )
            report = audit_skill_dir(bad_dir)
            self.assertFalse(report["all_passed"])
            self.assertFalse(report["checks"]["S1_valid_frontmatter"]["passed"])
            self.assertFalse(report["checks"]["S4_deterministic_offload"]["passed"])
            self.assertFalse(report["checks"]["S5_zero_overlap"]["passed"])
            self.assertFalse(report["checks"]["S6_tests_and_triggers"]["passed"])


if __name__ == "__main__":
    unittest.main()
