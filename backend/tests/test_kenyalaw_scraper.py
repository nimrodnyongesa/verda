import unittest


class StripTagsTests(unittest.TestCase):
    """Regression cover for the HTML-to-text pass used when building the
    Kenya Law corpus. Script and style bodies must never reach the corpus —
    they are not evidence, and a judgment page carrying leaked JavaScript
    would poison precedent matching with junk tokens.
    """

    def setUp(self):
        from wakili.services.kenyalaw_scraper import _strip_tags
        self.strip = _strip_tags

    def test_strips_plain_script_block(self):
        html = "<p>Petition</p><script>var secret = 1;</script><p>Ruling</p>"
        out = self.strip(html)
        self.assertNotIn("secret", out)
        self.assertIn("Petition", out)
        self.assertIn("Ruling", out)

    def test_strips_script_with_whitespace_in_closing_tag(self):
        # HTML permits whitespace before the closing angle bracket. The
        # original filter only matched `</script>`, so this variant leaked
        # the whole script body into the extracted text.
        html = "<p>Petition</p><script>var secret = 1;</script >Ruling"
        out = self.strip(html)
        self.assertNotIn("secret", out)
        self.assertNotIn("var", out)
        self.assertIn("Petition", out)
        self.assertIn("Ruling", out)

    def test_strips_style_with_whitespace_in_closing_tag(self):
        html = "<p>Petition</p><style>.a{color:red}</style >Ruling"
        out = self.strip(html)
        self.assertNotIn("color", out)
        self.assertIn("Petition", out)
        self.assertIn("Ruling", out)

    def test_strips_script_with_tab_and_newline_in_closing_tag(self):
        html = "Before<script>leak()</script\n\t>After"
        out = self.strip(html)
        self.assertNotIn("leak", out)
        self.assertIn("Before", out)
        self.assertIn("After", out)

    def test_uppercase_closing_tag_still_stripped(self):
        html = "Before<SCRIPT>leak()</SCRIPT >After"
        out = self.strip(html)
        self.assertNotIn("leak", out)
        self.assertIn("Before", out)
        self.assertIn("After", out)

    def test_entities_unescaped_and_whitespace_collapsed(self):
        html = "<p>Rex   &amp;   Republic</p>\n\n<p>v.  Kariuki</p>"
        self.assertEqual(self.strip(html), "Rex & Republic v. Kariuki")


if __name__ == "__main__":
    unittest.main()
