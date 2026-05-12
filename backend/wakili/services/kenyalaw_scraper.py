"""Kenya Law scraper.

Pulls real judgments from new.kenyalaw.org and writes them to
``backend/wakili/data/corpora/kenyalaw/judgments.json`` — the same file the
``kenyalaw-mcp`` reads from. Output schema is identical to the curated
fixtures so the precedent linker keeps working unchanged.

Why scrape the HTML? The new site (peachjam-based) does not expose a public
JSON API; judgments are server-rendered with the Akoma Ntoso XML embedded
inside a ``<la-akoma-ntoso>`` web component. Stripping tags from that
container gives the usable judgment text.

Usage:

    python -m wakili.services.kenyalaw_scraper --limit 50
    python -m wakili.services.kenyalaw_scraper --urls /akn/ke/judgment/kesc/2026/31/eng@2026-03-31

The scraper is polite: a 1.5s delay between fetches, a User-Agent of
``wakili-research/0.2``, and resilient to individual 4xx/5xx (skips and moves
on). Re-running merges by ``expression_frbr_uri`` (so the cache grows; nothing
gets duplicated).
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import logging
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from ..config import CORPORA_DIR

USER_AGENT = "wakili-research/0.2 (research; non-commercial; respects robots)"
BASE = "https://new.kenyalaw.org"
LISTING_URL = f"{BASE}/judgments/all/"
DEFAULT_DELAY = 1.5  # seconds between requests
JUDGMENT_LINK = re.compile(r'href="(/akn/ke/judgment/[^"#?]+)"')
ARTICLE_REGEX = re.compile(r"\bArticle\s+(\d{1,3})(?:\(\d+\))?", re.IGNORECASE)
COURT_FROM_PATH = {
    "kesc": "Supreme Court",
    "keca": "Court of Appeal",
    "kehc": "High Court",
    "keelc": "Environment & Land Court",
    "keelrc": "Employment & Labour Relations Court",
    "kemc": "Magistrate's Court",
    "kekc": "Kadhi's Court",
    "kepokc": "Political Parties Disputes Tribunal",
}
ISSUE_BUCKETS: list[tuple[str, str]] = [
    ("unlawful detention", "detain"),
    ("unlawful detention", "custody"),
    ("denial of counsel", "advocate"),
    ("denial of counsel", "counsel"),
    ("freedom of assembly", "protest"),
    ("freedom of assembly", "demonstrat"),
    ("freedom of expression", "expression"),
    ("freedom of expression", "speech"),
    ("right to fair trial", "fair trial"),
    ("right to fair trial", "arraign"),
    ("right to dignity", "dignity"),
    ("torture", "torture"),
    ("habeas corpus", "habeas"),
    ("constitutional petition", "constitutional petition"),
    ("conservatory orders", "conservatory"),
    ("compensation", "compensation"),
    ("Article 22", "article 22"),
    ("Article 23", "article 23"),
    ("Article 24", "article 24"),
    ("Article 27", "article 27"),
    ("Article 33", "article 33"),
    ("Article 37", "article 37"),
    ("Article 49", "article 49"),
    ("Article 50", "article 50"),
]
SUPERIOR_COURTS = {"Supreme Court", "Court of Appeal", "High Court"}

log = logging.getLogger("wakili.kenyalaw")


@dataclass
class Judgment:
    citation: str
    title: str
    court: str
    year: int
    url: str
    expression_frbr_uri: str
    articles_cited: list[str]
    issues: list[str]
    summary: str
    binding: bool
    body_text: str
    source: str = "kenyalaw.org"


# ---------------------------------------------------------------------------


def _fetch(url: str, *, retries: int = 2, timeout: int = 25) -> str:
    last: Exception | None = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                return resp.read().decode(charset, errors="replace")
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt < retries:
                # Exponential backoff with jitter.
                time.sleep(1.5 * (attempt + 1) + random.random())
    assert last is not None
    raise last


def _strip_tags(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_title(html: str) -> str:
    m = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
    if m:
        return html_lib.unescape(m.group(1)).strip()
    m = re.search(r"<title>\s*(.+?)\s*-\s*Kenya Law\s*</title>", html, re.DOTALL)
    if m:
        return re.sub(r"\s+", " ", html_lib.unescape(m.group(1))).strip()
    return "Untitled judgment"


def _extract_citation(title: str) -> str:
    m = re.search(r"\[\d{4}\]\s+KE\w+\s+\d+\s*\([^)]*\)", title)
    if m:
        return m.group(0).strip()
    return title


def _classify_court(path: str) -> str:
    parts = path.strip("/").split("/")
    if len(parts) >= 4:
        court_slug = parts[3].lower()
        return COURT_FROM_PATH.get(court_slug, "Court")
    return "Court"


def _extract_year(path: str) -> int:
    parts = path.strip("/").split("/")
    if len(parts) >= 5:
        try:
            return int(parts[4])
        except ValueError:
            return 0
    return 0


def _extract_articles(text: str) -> list[str]:
    articles = sorted({m.group(1) for m in ARTICLE_REGEX.finditer(text)}, key=int)
    return articles


def _extract_issues(text: str) -> list[str]:
    lower = text.lower()
    found = []
    for label, keyword in ISSUE_BUCKETS:
        if keyword in lower and label not in found:
            found.append(label)
    return found


def _extract_summary(text: str, *, max_chars: int = 600) -> str:
    body = text.strip()
    if len(body) <= max_chars:
        return body
    cut = body[:max_chars]
    last_period = cut.rfind(". ")
    if last_period > max_chars * 0.5:
        return cut[: last_period + 1].strip()
    return cut.strip() + "…"


def _extract_akn_body(html: str) -> str:
    m = re.search(r"<la-akoma-ntoso[^>]*>([\s\S]*?)</la-akoma-ntoso>", html)
    if not m:
        # Older layout fallback
        m = re.search(r'<article[^>]*class="[^"]*akn[^"]*"[^>]*>([\s\S]*?)</article>', html)
    if not m:
        return ""
    return _strip_tags(m.group(1))


def _judgment_links_from_listing(html: str) -> list[str]:
    return sorted(set(JUDGMENT_LINK.findall(html)))


def _list_recent_judgments(*, pages: int) -> Iterator[str]:
    """Yield judgment paths from the listing pages, newest first."""
    seen: set[str] = set()
    for page in range(1, pages + 1):
        url = f"{LISTING_URL}?country=ke&page={page}"
        try:
            html = _fetch(url)
        except Exception as exc:  # noqa: BLE001
            log.warning("listing page %s failed: %s", page, exc)
            continue
        for path in _judgment_links_from_listing(html):
            if path in seen:
                continue
            seen.add(path)
            yield path
        time.sleep(DEFAULT_DELAY)


def parse_judgment(path: str, html: str) -> Judgment:
    title = _extract_title(html)
    court = _classify_court(path)
    year = _extract_year(path)
    citation = _extract_citation(title)
    body = _extract_akn_body(html)
    articles = _extract_articles(body)
    issues = _extract_issues(body)
    summary = _extract_summary(body)
    if not summary:
        # Fall back to the title-derived note (for e.g. PDF-only judgments).
        summary = title
    return Judgment(
        citation=citation or title,
        title=title,
        court=court,
        year=year,
        url=urllib.parse.urljoin(BASE, path),
        expression_frbr_uri=path,
        articles_cited=articles,
        issues=issues,
        summary=summary,
        binding=court in SUPERIOR_COURTS,
        body_text=body[:25_000],  # cap so the JSON file stays sane
    )


def fetch_judgments(paths: Iterable[str], *, delay: float = DEFAULT_DELAY) -> list[Judgment]:
    out: list[Judgment] = []
    for path in paths:
        url = urllib.parse.urljoin(BASE, path)
        try:
            html = _fetch(url)
        except Exception as exc:  # noqa: BLE001
            log.warning("fetch %s failed: %s", path, exc)
            time.sleep(delay)
            continue
        try:
            judgment = parse_judgment(path, html)
        except Exception as exc:  # noqa: BLE001
            log.warning("parse %s failed: %s", path, exc)
            time.sleep(delay)
            continue
        out.append(judgment)
        log.info("ok %s — %s", path, judgment.citation[:60])
        time.sleep(delay)
    return out


# ---------------------------------------------------------------------------


def _corpus_path() -> Path:
    return CORPORA_DIR / "kenyalaw" / "judgments.json"


def load_corpus() -> list[dict]:
    p = _corpus_path()
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def save_corpus(items: list[dict]) -> Path:
    p = _corpus_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def merge_into_corpus(new_items: list[Judgment]) -> tuple[Path, int, int]:
    """Insert/update by ``expression_frbr_uri``. Returns (path, added, updated)."""
    existing = load_corpus()
    by_key: dict[str, dict] = {}
    for item in existing:
        key = item.get("expression_frbr_uri") or item.get("citation") or item.get("url", "")
        if key:
            by_key[key] = item
    added = updated = 0
    for j in new_items:
        record = {
            "citation": j.citation,
            "title": j.title,
            "court": j.court,
            "year": j.year,
            "url": j.url,
            "expression_frbr_uri": j.expression_frbr_uri,
            "articles_cited": j.articles_cited,
            "issues": j.issues,
            "summary": j.summary,
            "binding": j.binding,
            "body_text": j.body_text,
            "source": j.source,
        }
        key = j.expression_frbr_uri
        if key in by_key:
            updated += 1
        else:
            added += 1
        by_key[key] = record
    merged = sorted(
        by_key.values(),
        key=lambda r: (r.get("year", 0), r.get("citation", "")),
        reverse=True,
    )
    path = save_corpus(merged)
    return path, added, updated


# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape Kenya Law judgments.")
    parser.add_argument("--limit", type=int, default=50, help="Max judgments to fetch")
    parser.add_argument(
        "--pages",
        type=int,
        default=2,
        help="How many listing pages (50 results each) to scan",
    )
    parser.add_argument(
        "--urls",
        nargs="*",
        default=None,
        help="Explicit /akn/... paths (or full URLs) to fetch instead of the listing",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help="Seconds to sleep between requests",
    )
    parser.add_argument(
        "--filter",
        type=str,
        default=None,
        help="Optional case-insensitive substring filter on title (e.g. 'article 22', 'detention')",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    paths: list[str] = []
    if args.urls:
        for u in args.urls:
            if u.startswith("http"):
                paths.append(urllib.parse.urlparse(u).path)
            else:
                paths.append(u)
    else:
        for path in _list_recent_judgments(pages=args.pages):
            paths.append(path)
            if len(paths) >= args.limit * 4:  # over-fetch when filter is on
                break

    if not paths:
        log.error("no judgments to fetch")
        return 1

    judgments = fetch_judgments(paths, delay=args.delay)

    if args.filter:
        needle = args.filter.lower()
        judgments = [
            j for j in judgments if needle in j.title.lower() or needle in j.body_text.lower()
        ]

    judgments = judgments[: args.limit]

    if not judgments:
        log.warning("no judgments matched filters")
        return 0

    path, added, updated = merge_into_corpus(judgments)
    log.info("wrote %s · added=%d updated=%d total=%d", path, added, updated, len(load_corpus()))
    print(json.dumps({"path": str(path), "added": added, "updated": updated, "total": len(load_corpus())}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
