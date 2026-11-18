"""Unit tests for hooks/rubric_stop_guard.py."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = SKILL_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from rubric_stop_guard import handle_stop_event  # noqa: E402


class TestStopGuard(unittest.TestCase):
    def test_allows_stop_when_continuation_active(self) -> None:
        res = handle_stop_event({"continuationActive": True, "cwd": str(SKILL_ROOT)})
        self.assertEqual(res, {})

    def test_allows_stop_when_no_rubric_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = handle_stop_event({"continuationActive": False, "cwd": tmp})
            self.assertEqual(res, {})

    def test_blocks_stop_when_auto_code_blocker_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            rubric = {
                "project": "hook-test",
                "criteria": [
                    {
                        "id": "H1",
                        "statement": "Manifest file must exist before finishing",
                        "tier": "blocker",
                        "verification_type": "auto_code",
                        "check": {"kind": "file_exists", "path": "missing.txt"},
                        "passed": None,
                    }
                ],
            }
            (tmp_path / "rubric.json").write_text(json.dumps(rubric), encoding="utf-8")
            res = handle_stop_event({"continuationActive": False, "cwd": tmp})
            self.assertEqual(res.get("decision"), "continue")
            self.assertIn("H1", res.get("reason", ""))

    def test_allows_stop_when_auto_code_blocker_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "present.txt").write_text("ok\n", encoding="utf-8")
            rubric = {
                "project": "hook-test-pass",
                "criteria": [
                    {
                        "id": "H1",
                        "statement": "Required file present.txt exists",
                        "tier": "blocker",
                        "verification_type": "auto_code",
                        "check": {"kind": "file_exists", "path": "present.txt"},
                        "passed": None,
                    }
                ],
            }
            (tmp_path / "rubric.json").write_text(json.dumps(rubric), encoding="utf-8")
            res = handle_stop_event({"continuationActive": False, "cwd": tmp})
            self.assertEqual(res, {})


if __name__ == "__main__":
    unittest.main()
