import unittest
from datetime import date

from tests._helpers import cleanup_runtime, isolated_runtime


class ProceduralEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = isolated_runtime()

    @classmethod
    def tearDownClass(cls):
        cleanup_runtime(cls.runtime)

    def setUp(self):
        from wakili.modules.procedural_engine import build_procedural_engine
        self.build = build_procedural_engine

    def test_kenya_article_22_schedule_is_monotonic(self):
        case = {
            "id": 1,
            "title": "Test",
            "description": "",
            "jurisdiction": "ke",
            "legal_track": "article_22_petition",
            "metadata": {},
        }
        codex = {"timeline": [{"date": "2024-06-24", "summary": "x"}], "issue_heatmap": [], "officers": [], "stations": []}
        result = self.build(case, codex, today=date(2024, 6, 30))
        deadlines = [s["deadline"] for s in result["schedule"]]
        self.assertEqual(deadlines, sorted(deadlines))
        # First filing should target ~14 days from incident
        self.assertEqual(result["schedule"][0]["deadline"], "2024-07-08")

    def test_drafted_motions_render_placeholders(self):
        case = {
            "id": 1,
            "title": "Demo",
            "description": "Demo facts.",
            "jurisdiction": "ke",
            "legal_track": "article_22_petition",
            "metadata": {"petitioner": "Jane Doe (next friend)"},
        }
        codex = {
            "timeline": [{"date": "2024-06-24", "summary": "Arrest at Parliament Road"}],
            "issue_heatmap": [{"name": "unlawful detention", "score": 5}],
            "officers": [{"rank": "PC", "name": "Kariuki", "mentions": 2, "sources": ["a.txt"]}],
            "stations": ["Central Police Station"],
        }
        result = self.build(case, codex, today=date(2024, 6, 30))
        self.assertGreaterEqual(len(result["drafted_motions"]), 1)
        # The list_of_authorities template has no petitioner block — we only
        # require that at least one motion renders the petitioner.
        joined = "\n\n".join(m["content"] for m in result["drafted_motions"])
        self.assertIn("Jane Doe", joined)
        # SIGN BEFORE FILING must remain in every drafted motion (no auto-sign).
        for motion in result["drafted_motions"]:
            self.assertIn("SIGN BEFORE FILING", motion["content"])

    def test_track_label_carries_rule_citation(self):
        case = {
            "id": 1,
            "title": "Test",
            "description": "",
            "jurisdiction": "ke",
            "legal_track": "article_22_petition",
            "metadata": {},
        }
        codex = {"timeline": [], "issue_heatmap": [], "officers": [], "stations": []}
        result = self.build(case, codex, today=date(2024, 6, 30))
        self.assertEqual(result["track_label"], "Article 22 Constitutional Petition")
        self.assertIn("Mutunga", result["citation"])


if __name__ == "__main__":
    unittest.main()
