import unittest

from tests._helpers import cleanup_runtime, isolated_runtime


class PrecedentLinkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = isolated_runtime()

    @classmethod
    def tearDownClass(cls):
        cleanup_runtime(cls.runtime)

    def setUp(self):
        from wakili.modules.precedent_linker import build_precedent_linker
        self.build = build_precedent_linker

    def test_results_carry_url_provenance(self):
        case = {"id": 1, "jurisdiction": "ke", "legal_track": "article_22_petition"}
        codex = {
            "articles_invoked": ["29", "33", "37", "49"],
            "issue_heatmap": [
                {"name": "unlawful detention", "score": 6},
                {"name": "freedom of assembly", "score": 5},
            ],
        }
        result = self.build(case, codex)
        self.assertGreater(result["result_count"], 0)
        for r in result["results"]:
            self.assertTrue(
                r["url"].startswith("https://kenyalaw.org")
                or r["url"].startswith("https://new.kenyalaw.org"),
                msg=f"unexpected URL: {r['url']}",
            )
            self.assertIn("relevance_score", r)
            self.assertIn("match_reasons", r)

    def test_results_are_ranked_descending(self):
        case = {"id": 1, "jurisdiction": "ke", "legal_track": "article_22_petition"}
        codex = {
            "articles_invoked": ["49", "33", "37"],
            "issue_heatmap": [
                {"name": "unlawful detention", "score": 6},
                {"name": "freedom of assembly", "score": 5},
            ],
        }
        result = self.build(case, codex)
        scores = [r["relevance_score"] for r in result["results"]]
        self.assertEqual(scores, sorted(scores, reverse=True))


if __name__ == "__main__":
    unittest.main()
