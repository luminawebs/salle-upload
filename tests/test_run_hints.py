"""
The hints catalog (core/run_hints.py): every entry must match the real error
message it was written for, and hints reach the end-of-run summary.

    python -m unittest tests.test_run_hints -v
"""
import logging
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.run_hints import HINTS, hints_for  # noqa: E402
from core.run_summary import RunIssueTracker  # noqa: E402


class RunHintsTests(unittest.TestCase):
    def test_every_hint_matches_its_example(self):
        for hint in HINTS:
            with self.subTest(hint=hint["id"]):
                self.assertIn(hint, hints_for([hint["ejemplo"]]))

    def test_unrelated_message_has_no_hint(self):
        self.assertEqual(hints_for(["Successfully uploaded rubric for ACTIVIDAD 1"]), [])

    def test_hints_reach_the_summary_from_errors_and_warnings(self):
        tracker = RunIssueTracker()
        log = logging.getLogger("actions.test_hints")
        log.addHandler(tracker)
        self.addCleanup(log.removeHandler, tracker)
        log.propagate = False
        self.addCleanup(setattr, log, "propagate", True)
        log.warning("[ACTIVIDAD 4] Could not find visible 'una pregunta aleatoria' button.")
        has_problems, lines = tracker.summary_lines("c1")
        self.assertFalse(has_problems)  # a warning alone isn't a problem…
        self.assertTrue(any("Pista:" in line and "banco de preguntas" in line for line in lines))  # …but gets its hint
        log.error("Could not load course 61980. Skipping all workflows for this course.")
        has_problems, lines = tracker.summary_lines("c1")
        self.assertTrue(has_problems)
        self.assertEqual(sum("Pista:" in line for line in lines), 2)


if __name__ == "__main__":
    unittest.main()
