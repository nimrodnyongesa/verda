"""End-to-end test: seed sample case → plan → approve → generate → inspect outputs."""
import unittest

from tests._helpers import cleanup_runtime, isolated_runtime, seed_test_case


class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = isolated_runtime()

    @classmethod
    def tearDownClass(cls):
        cleanup_runtime(cls.runtime)

    def test_sample_case_runs_end_to_end(self):
        from wakili.services.orchestrator import latest_run, list_events, run_generation
        from wakili.services.planning import approve_plan

        case = seed_test_case()
        self.assertIsNotNone(case)
        self.assertGreater(len(case["files"]), 5)
        self.assertEqual(case["plan"]["modules"][0]["key"], "evidence_codex")

        approve_plan(case["id"])
        result = run_generation(case["id"])
        self.assertEqual(result["case_id"], case["id"])
        self.assertGreater(result["summary"]["events_extracted"], 5)
        self.assertGreaterEqual(result["summary"]["precedents_ranked"], 1)

        run = latest_run(case["id"])
        self.assertIsNotNone(run)
        events = list_events(run["id"])
        self.assertGreater(len(events), 5)

    def test_generation_blocked_without_plan_approval(self):
        from wakili.services.case_service import create_case
        from wakili.services.orchestrator import run_generation

        case = create_case({
            "title": "Unapproved test",
            "jurisdiction": "ke",
            "legal_track": "article_22_petition",
            "description": "x",
            "metadata": {},
        })
        with self.assertRaises(ValueError):
            run_generation(case["id"])


if __name__ == "__main__":
    unittest.main()
