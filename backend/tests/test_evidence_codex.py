import unittest

from tests._helpers import cleanup_runtime, isolated_runtime


class EvidenceCodexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = isolated_runtime()

    @classmethod
    def tearDownClass(cls):
        cleanup_runtime(cls.runtime)

    def setUp(self):
        from wakili.modules.evidence_codex import build_evidence_codex, classify_evidence_kind
        self.build = build_evidence_codex
        self.classify = classify_evidence_kind

    def test_classify_whatsapp_export(self):
        text = "24/06/2024, 8:15 PM - Amina: They have not been released."
        self.assertEqual(self.classify("messages.txt", text), "whatsapp_export")

    def test_classify_ob_extract(self):
        text = "OB No. 47/25/06/24 — Central Police Station, Cpl. Otieno reporting."
        self.assertEqual(self.classify("ob_central.txt", text), "ob_extract")

    def test_timeline_extracted_with_provenance(self):
        case_row = {"id": 1, "jurisdiction": "ke", "legal_track": "article_22_petition"}
        files = [
            {
                "id": 10,
                "case_id": 1,
                "original_name": "ob.txt",
                "evidence_kind": "ob_extract",
                "extracted_text": (
                    "On 24 June 2024 at 1410 hrs, six suspects were brought to Central Police Station. "
                    "PC Kariuki recorded OB No. 47/25/06/24. Cpl. Otieno counter-signed."
                ),
            }
        ]
        codex = self.build(case_row, files)
        self.assertGreaterEqual(codex["events_extracted"], 1)
        for event in codex["timeline"]:
            self.assertIn("source_file_id", event)
            self.assertIn("line_number", event)

    def test_officers_aggregated(self):
        case_row = {"id": 1, "jurisdiction": "ke", "legal_track": "article_22_petition"}
        files = [
            {
                "id": 1,
                "case_id": 1,
                "original_name": "a.txt",
                "evidence_kind": "ob_extract",
                "extracted_text": "PC Kariuki and PC Njoroge attended Parliament Road on 24 June 2024.",
            },
            {
                "id": 2,
                "case_id": 1,
                "original_name": "b.txt",
                "evidence_kind": "ob_extract",
                "extracted_text": "PC Kariuki signed the OB on 25 June 2024.",
            },
        ]
        codex = self.build(case_row, files)
        names = {(o["rank"], o["name"]) for o in codex["officers"]}
        self.assertIn(("PC", "Kariuki"), names)
        kariuki = next(o for o in codex["officers"] if o["name"] == "Kariuki")
        self.assertEqual(kariuki["mentions"], 2)


if __name__ == "__main__":
    unittest.main()
