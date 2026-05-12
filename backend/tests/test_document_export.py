"""PDF / DOCX / Markdown export coverage.

These tests:
  1. Exercise the renderer in isolation against pathological inputs
     (empty, very long signature underscores, super-long URLs, hundreds
     of paragraphs, unicode, leading blanks, parens / backslashes,
     mixed markdown). Each must produce parseable bytes.
  2. Drive the FastAPI surface end-to-end — seed a sample case, run
     generation, and download the petition + every drafted motion in
     PDF, DOCX, and Markdown form. Each download must be 200, non-empty,
     and the PDF stream must parse via PyPDF.
"""
from __future__ import annotations

import io
import unittest

from tests._helpers import isolated_runtime, seed_test_case


SAMPLE_CASES: dict[str, str] = {
    "empty": "",
    "one_word": "hello",
    "no_headings": "just paragraphs " * 200,
    "long_signature": "_" * 2000,
    "long_url": "https://" + ("x" * 500) + ".example.com/very/deep/path",
    "tons_of_lines": "\n".join(f"paragraph line {i} of many" for i in range(500)),
    "unicode": "Yusuf Zsófia · José · café · 中文 · العربية · «emdash—»",
    "leading_blanks": "\n\n\n# After blanks\nbody",
    "parens_special": "Has parens (left) and (right) and \\backslash chars",
    "mixed_md": "# H1\n## H2\n### H3\n\n- list item\n- another\n\nparagraph **bold** *italic* `code`",
}


class DocumentRendererTests(unittest.TestCase):
    """Direct unit tests on render_pdf / render_docx."""

    def test_render_pdf_pathological_inputs(self):
        from wakili.services.document_exporter import render_pdf

        for name, src in SAMPLE_CASES.items():
            with self.subTest(case=name):
                blob = render_pdf(src)
                self.assertTrue(blob.startswith(b"%PDF-"), msg=f"{name} not a PDF")
                self.assertIn(b"%%EOF", blob[-32:], msg=f"{name} missing %%EOF")
                self.assertGreater(len(blob), 200, msg=f"{name} suspiciously small")

    def test_render_pdf_parses_with_pypdf(self):
        from wakili.services.document_exporter import render_pdf

        try:
            from pypdf import PdfReader
        except ImportError:
            self.skipTest("pypdf not installed in this venv")

        for name, src in SAMPLE_CASES.items():
            with self.subTest(case=name):
                blob = render_pdf(src)
                reader = PdfReader(io.BytesIO(blob))
                self.assertGreaterEqual(len(reader.pages), 1, msg=f"{name} 0 pages")
                # Make sure at least one page extracts without raising.
                for page in reader.pages:
                    page.extract_text()  # raises if catalog/stream is malformed

    def test_render_docx_zip_shape(self):
        import zipfile
        from wakili.services.document_exporter import render_docx

        for name, src in SAMPLE_CASES.items():
            with self.subTest(case=name):
                blob = render_docx(src)
                with zipfile.ZipFile(io.BytesIO(blob)) as z:
                    names = set(z.namelist())
                self.assertIn("word/document.xml", names, msg=f"{name} no document.xml")
                self.assertIn("[Content_Types].xml", names, msg=f"{name} no [Content_Types]")

    def test_resolve_placeholders_handles_curly_braces(self):
        from wakili.services.document_exporter import resolve_placeholders

        out = resolve_placeholders(
            "Header {{petitioner_block}} body {{ unknown.token }} tail."
        )
        self.assertNotIn("{{", out)
        self.assertIn("[TO BE COMPLETED BEFORE FILING]", out)


class DocumentExportApiTests(unittest.TestCase):
    """End-to-end through FastAPI."""

    @classmethod
    def setUpClass(cls):
        cls.runtime = isolated_runtime()
        from fastapi.testclient import TestClient
        from wakili.main import create_app

        cls.client = TestClient(create_app())
        cls.case_id = seed_test_case()["id"]
        cls.client.post(f"/api/cases/{cls.case_id}/plan/approve")
        cls.client.post(f"/api/cases/{cls.case_id}/generate")

    def test_petition_pdf_docx_md(self):
        for fmt, ct, magic in (
            ("pdf", "application/pdf", b"%PDF-"),
            (
                "docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                b"PK\x03\x04",
            ),
            ("md", "text/markdown", b"#"),  # the petition starts with a heading
        ):
            with self.subTest(fmt=fmt):
                r = self.client.get(
                    f"/api/cases/{self.case_id}/petition/document?fmt={fmt}"
                )
                self.assertEqual(r.status_code, 200, msg=r.text)
                self.assertIn(ct, r.headers.get("content-type", ""))
                self.assertGreater(len(r.content), 200)
                self.assertTrue(r.content.startswith(magic))

    def test_every_motion_in_every_format(self):
        proc = self.client.get(f"/api/cases/{self.case_id}/procedure").json()
        motions = proc.get("drafted_motions") or []
        self.assertGreater(len(motions), 0)
        for idx in range(len(motions)):
            for fmt in ("pdf", "docx", "md"):
                with self.subTest(motion=idx, fmt=fmt):
                    r = self.client.get(
                        f"/api/cases/{self.case_id}/motions/{idx}?fmt={fmt}"
                    )
                    self.assertEqual(r.status_code, 200, msg=r.text)
                    self.assertGreater(len(r.content), 100)

    def test_unsupported_format_returns_400(self):
        r = self.client.get(f"/api/cases/{self.case_id}/petition/document?fmt=xlsx")
        self.assertEqual(r.status_code, 400)

    def test_unknown_motion_index_returns_404(self):
        r = self.client.get(f"/api/cases/{self.case_id}/motions/99")
        self.assertEqual(r.status_code, 404)

    def test_motion_pdfs_parse_via_pypdf(self):
        try:
            from pypdf import PdfReader
        except ImportError:
            self.skipTest("pypdf not installed in this venv")

        proc = self.client.get(f"/api/cases/{self.case_id}/procedure").json()
        motions = proc.get("drafted_motions") or []
        for idx in range(len(motions)):
            with self.subTest(motion=idx):
                r = self.client.get(
                    f"/api/cases/{self.case_id}/motions/{idx}?fmt=pdf"
                )
                self.assertEqual(r.status_code, 200)
                reader = PdfReader(io.BytesIO(r.content))
                self.assertGreaterEqual(len(reader.pages), 1)
                # Read text from every page — raises if any object stream
                # is malformed.
                for page in reader.pages:
                    page.extract_text()


if __name__ == "__main__":
    unittest.main()
