import json
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

from tests._helpers import cleanup_runtime, isolated_runtime


class PackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = isolated_runtime()

    @classmethod
    def tearDownClass(cls):
        cleanup_runtime(cls.runtime)

    def setUp(self):
        from wakili.services.exporters.zip import export as export_zip
        from wakili.services.packaging import (
            collect_bundle_bytes,
            write_bundle,
        )
        self.write_bundle = write_bundle
        self.export_zip = export_zip
        self.collect = collect_bundle_bytes

    def _bundle(self, case_id: int = 99) -> dict:
        return {
            "case_id": case_id,
            "case_summary": {
                "title": "Test case",
                "jurisdiction": "ke",
                "legal_track": "article_22_petition",
                "track_label": "Article 22 Constitutional Petition",
                "citation": "Articles 22 and 23",
                "description": "facts",
            },
            "generator_mode": "deterministic",
            "plan": {"modules": [], "deadlines": [], "risks": []},
            "evidence_codex": {
                "case_id": case_id,
                "files_indexed": 1,
                "events_extracted": 0,
                "officers_named": 0,
                "ob_numbers_seen": 0,
                "stations_named": 0,
                "issue_heatmap": [],
                "timeline": [],
                "officers": [],
            },
            "procedural_engine": {
                "track_label": "Article 22 Constitutional Petition",
                "citation": "Articles 22 and 23",
                "schedule": [],
                "drafted_motions": [],
                "jurisdiction": "ke",
                "track": "article_22_petition",
            },
            "precedent_linker": {
                "results": [],
                "result_count": 0,
                "suggested_queries": [],
            },
            "defender_safety_build": {
                "telemetry_default": "off",
                "supported_targets": [],
                "default_target": "hosted",
                "advisories": [],
                "bundle_contents": [],
                "encryption_at_rest": {},
                "panic_wipe_supported": True,
                "tor_onion_optional": True,
            },
            "petition_draft": "# petition\n\nbody.",
        }

    def test_bundle_round_trip(self):
        path = self.write_bundle(99, self._bundle(99))
        self.assertTrue(Path(path).exists())
        loaded = json.loads(Path(path).read_text())
        self.assertEqual(loaded["case_id"], 99)

    def test_zip_export_contains_petition(self):
        self.write_bundle(99, self._bundle(99))
        zip_path = self.export_zip(99)
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
        self.assertIn("petition_draft.md", names)
        self.assertIn("evidence_codex.json", names)
        self.assertIn("README.md", names)

    def test_collect_bundle_bytes_is_zip(self):
        self.write_bundle(99, self._bundle(99))
        blob = self.collect(99)
        with zipfile.ZipFile(BytesIO(blob)) as zf:
            self.assertIn("bundle.json", zf.namelist())


if __name__ == "__main__":
    unittest.main()
