from copy import deepcopy
import unittest
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from check_progress import validate


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.plan = "- T01.1 Review\n- T02.1 Build\n"
        self.state = {
            "schema_version": 1,
            "updated_at": "2026-10-31T10:00:00+00:00",
            "authorization": {
                "application_development": "authorized",
                "evidence": "Owner instruction",
            },
            "current_task": "T02.1",
            "next_action": "Build the locked environment",
            "last_checks": [
                {"command": "make check", "result": "passed", "scope": "Documentation"}
            ],
            "tasks": [
                {
                    "id": "T01.1",
                    "status": "done",
                    "evidence": ["Reviewed spec"],
                    "blocker": None,
                },
                {
                    "id": "T02.1",
                    "status": "in_progress",
                    "evidence": [],
                    "blocker": None,
                },
            ],
        }

    def test_valid_resume_and_completed_task(self):
        self.assertEqual(len(validate(self.state, self.plan)), 2)
        self.state["tasks"][1].update(status="done", evidence=["Tests passed"])
        self.state["current_task"] = None
        validate(self.state, self.plan)

    def test_inventory_drift_and_duplicate_fail(self):
        for tasks in (self.state["tasks"][:1], self.state["tasks"] * 2):
            state = deepcopy(self.state)
            state["tasks"] = tasks
            with self.assertRaises(ValueError):
                validate(state, self.plan)

    def test_done_requires_evidence_and_blocked_requires_reason(self):
        self.state["tasks"][0]["evidence"] = []
        with self.assertRaises(ValueError):
            validate(self.state, self.plan)
        self.state["tasks"][0].update(status="blocked", blocker="Missing decision")
        validate(self.state, self.plan)
        self.state["tasks"][0]["blocker"] = None
        with self.assertRaises(ValueError):
            validate(self.state, self.plan)

    def test_unrecorded_authorization_and_wrong_current_task_fail(self):
        self.state["authorization"]["application_development"] = "not_authorized"
        with self.assertRaises(ValueError):
            validate(self.state, self.plan)
        self.state["authorization"]["application_development"] = "authorized"
        self.state["current_task"] = None
        with self.assertRaises(ValueError):
            validate(self.state, self.plan)

    def test_fresh_process_reads_saved_state_and_rejects_corruption(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs/plans").mkdir(parents=True)
            (root / "docs/plans/implementation.md").write_text(self.plan)
            progress = root / "docs/plans/progress.json"
            state = deepcopy(self.state)
            state["blockers"] = []
            progress.write_text(json.dumps(state))
            command = [
                sys.executable,
                str(Path(__file__).with_name("check_progress.py")),
                str(root),
            ]
            restored = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(restored.returncode, 0, restored.stderr)
            self.assertIn("Current task: T02.1", restored.stdout)
            self.assertIn("done=1", restored.stdout)
            progress.write_text("{broken")
            broken = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(broken.returncode, 1)
            self.assertIn("Invalid progress state", broken.stderr)

    def test_unknown_status_and_false_check_result_fail(self):
        self.state["tasks"][1]["status"] = "almost_done"
        with self.assertRaises(ValueError):
            validate(self.state, self.plan)
        self.state["tasks"][1]["status"] = "in_progress"
        self.state["last_checks"][0]["result"] = "probably_passed"
        with self.assertRaises(ValueError):
            validate(self.state, self.plan)


if __name__ == "__main__":
    unittest.main()
