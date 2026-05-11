"""Evidence Codex — per-case parser that turns messy uploads into a queryable timeline.

Per the Verda technical architecture (sec. 4.1), this module:
  - identifies recurring entity types (officer ranks, station codes, OB numbers, dates)
  - builds case-specific extractors using regex + lightweight heuristics
  - normalises into a timeline schema with provenance pointers back to source files
  - flags gaps in the record

The runtime version below is the deterministic baseline. When OPENAI_API_KEY is
configured, planning may augment entities or summaries via the LLM adapter.
The deterministic baseline alone produces a credible courtroom-ready chronology
on the demo case folder.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Detection patterns (Kenya-specific defaults; extensible per jurisdiction).
# ---------------------------------------------------------------------------

DATE_PATTERNS: list[tuple[str, str]] = [
    # 24/06/2024
    (r"\b(?P<d>\d{1,2})/(?P<m>\d{1,2})/(?P<y>\d{2,4})\b", "dmy_slash"),
    # 2024-06-24
    (r"\b(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})\b", "iso"),
    # 24 June 2024
    (
        r"\b(?P<d>\d{1,2})\s+(?P<mname>January|February|March|April|May|June|July|August|September|October|November|December)\s+(?P<y>\d{4})\b",
        "dmy_text",
    ),
]

MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

OB_PATTERN = re.compile(r"\bOB\s*(?:No\.?|NO\.?|number)?\s*[:#]?\s*(\d+(?:[\/\-]\d+){0,3})\b", re.IGNORECASE)
STATION_PATTERN = re.compile(r"\b((?:Central|Kamukunji|Pangani|Industrial Area|Kileleshwa|Parklands|Kasarani|Buruburu)\s+(?:Police\s+)?Station)\b", re.IGNORECASE)
RANK_PATTERN = re.compile(
    r"\b(IP|Inspector|CPL|Cpl|Cpl\.|Corporal|PC|P\.C\.|Sgt|Sgt\.|Sergeant|Insp|ASP|SP|CIP|Chief Inspector|OCS|OCPD)\b\s+([A-Z][a-zA-Z']+(?:\s+[A-Z][a-zA-Z']+){0,2})",
    re.MULTILINE,
)
PHONE_PATTERN = re.compile(r"\b(?:\+254|0)\s?7\d{2}\s?\d{3}\s?\d{3}\b")
ID_PATTERN = re.compile(r"\bID\s*(?:No\.?|number)?\s*[:#]?\s*(\d{6,9})\b", re.IGNORECASE)
ARTICLE_PATTERN = re.compile(r"\bArticle\s+(\d{1,3}(?:\(\d+\))?)\b")

# Article 22/23 issue keywords used to score relevance per file and surface a heatmap.
ISSUE_KEYWORDS = {
    "unlawful detention": [
        "detain", "detention", "held", "custody", "no charge", "incommunicado",
        "produce", "production",
    ],
    "denial of counsel": [
        "advocate", "lawyer", "counsel", "denied access", "refused access",
    ],
    "use of force": [
        "force", "beat", "beaten", "bruis", "injur", "tear gas", "baton", "rubber bullet",
    ],
    "freedom of assembly": [
        "protest", "picket", "rally", "march", "demonstrat", "gen-z", "gen z", "finance bill",
    ],
    "freedom of expression": [
        "journalist", "press", "speech", "social media", "post", "tweet",
    ],
    "right to fair trial": [
        "bail", "bond", "magistrate", "court", "arraign",
    ],
    "torture or cruel treatment": [
        "torture", "abuse", "ill-treatment", "mistreat",
    ],
    "right to dignity": [
        "stripped", "naked", "humiliat",
    ],
}

WHATSAPP_LINE = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),\s*(?P<time>\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)\s*-\s*(?P<author>[^:]{1,80}?):\s*(?P<msg>.+)$"
)


# ---------------------------------------------------------------------------
# Public surface.
# ---------------------------------------------------------------------------


@dataclass
class FileEntities:
    file_id: int
    file_name: str
    dates: list[dict[str, Any]]
    officers: list[dict[str, Any]]
    stations: list[str]
    ob_numbers: list[str]
    articles: list[str]
    phones: list[str]
    ids: list[str]
    issues: dict[str, int]


def build_evidence_codex(case_row: dict[str, Any], files: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the Evidence Codex artifact for a case.

    Output schema is stable and mirrors what the auto-generated parser module
    would write to disk. Provenance pointers tie each event back to a file.
    """
    file_entities: list[FileEntities] = []
    for file_row in files:
        text = file_row.get("extracted_text") or ""
        entities = _extract_from_text(file_row["id"], file_row["original_name"], text)
        file_entities.append(entities)

    timeline = _build_timeline(file_entities, files)
    issue_heatmap = _aggregate_issues(file_entities)
    officers = _aggregate_officers(file_entities)
    stations = sorted({s for fe in file_entities for s in fe.stations})
    ob_numbers = sorted({o for fe in file_entities for o in fe.ob_numbers})
    articles = sorted({a for fe in file_entities for a in fe.articles})
    gaps = _find_gaps(timeline)

    summary = {
        "case_id": case_row["id"],
        "files_indexed": len(files),
        "events_extracted": len(timeline),
        "officers_named": len(officers),
        "stations_named": len(stations),
        "ob_numbers_seen": len(ob_numbers),
        "articles_invoked": articles,
        "issue_heatmap": issue_heatmap,
        "gaps": gaps,
        "timeline": timeline,
        "officers": officers,
        "stations": stations,
        "ob_numbers": ob_numbers,
    }
    return summary


# ---------------------------------------------------------------------------
# Internals.
# ---------------------------------------------------------------------------


def _extract_from_text(file_id: int, file_name: str, text: str) -> FileEntities:
    dates = _extract_dates(text)
    officers = [{"rank": rank, "name": name.strip()} for rank, name in RANK_PATTERN.findall(text)]
    stations = [m.group(1).title().replace("Police Station", "Police Station") for m in STATION_PATTERN.finditer(text)]
    ob_numbers = [m.group(1) for m in OB_PATTERN.finditer(text)]
    articles = ARTICLE_PATTERN.findall(text)
    phones = PHONE_PATTERN.findall(text)
    ids = ID_PATTERN.findall(text)
    issues = _score_issues(text)
    return FileEntities(
        file_id=file_id,
        file_name=file_name,
        dates=dates,
        officers=officers,
        stations=stations,
        ob_numbers=ob_numbers,
        articles=articles,
        phones=phones,
        ids=ids,
        issues=issues,
    )


def _extract_dates(text: str) -> list[dict[str, Any]]:
    dates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_no, line in enumerate(text.splitlines(), start=1):
        for pattern, kind in DATE_PATTERNS:
            for m in re.finditer(pattern, line):
                iso = _normalize_date(m, kind)
                if not iso:
                    continue
                snippet = line.strip()
                key = f"{iso}|{snippet[:80]}"
                if key in seen:
                    continue
                seen.add(key)
                dates.append({
                    "iso": iso,
                    "line_number": line_no,
                    "snippet": snippet[:200],
                })
    return dates


def _normalize_date(match: re.Match[str], kind: str) -> str | None:
    g = match.groupdict()
    try:
        if kind in {"dmy_slash", "dmy_text"}:
            d = int(g["d"])
            if kind == "dmy_text":
                m = MONTH_NAMES[g["mname"].lower()]
            else:
                m = int(g["m"])
            y = int(g["y"])
            if y < 100:
                y += 2000
        else:  # iso
            y, m, d = int(g["y"]), int(g["m"]), int(g["d"])
        if not (1 <= m <= 12 and 1 <= d <= 31 and 1900 <= y <= 2100):
            return None
        return f"{y:04d}-{m:02d}-{d:02d}"
    except (KeyError, ValueError):
        return None


def _score_issues(text: str) -> dict[str, int]:
    lower = text.lower()
    return {
        issue: sum(lower.count(kw) for kw in keywords)
        for issue, keywords in ISSUE_KEYWORDS.items()
    }


def _build_timeline(file_entities: list[FileEntities], files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    file_lookup = {f["id"]: f for f in files}
    events: list[dict[str, Any]] = []
    for fe in file_entities:
        file_row = file_lookup.get(fe.file_id, {})
        for d in fe.dates:
            event = {
                "id": _stable_id(f"{fe.file_id}:{d['iso']}:{d['snippet']}"),
                "date": d["iso"],
                "summary": d["snippet"],
                "source_file": fe.file_name,
                "source_file_id": fe.file_id,
                "source_kind": file_row.get("evidence_kind", "unknown"),
                "line_number": d["line_number"],
                "officers_in_context": _officers_in_snippet(d["snippet"]),
                "ob_numbers_in_context": [m.group(1) for m in OB_PATTERN.finditer(d["snippet"])],
            }
            events.append(event)
        if not fe.dates and any(fe.issues.values()):
            # File contributes context but lacks a date; record a placeholder.
            events.append({
                "id": _stable_id(f"{fe.file_id}:undated"),
                "date": None,
                "summary": f"Undated context from {fe.file_name}",
                "source_file": fe.file_name,
                "source_file_id": fe.file_id,
                "source_kind": file_row.get("evidence_kind", "unknown"),
                "line_number": 0,
                "officers_in_context": [],
                "ob_numbers_in_context": [],
            })
    events.sort(key=lambda e: (e["date"] or "9999-12-31", e["source_file"]))
    return events


def _officers_in_snippet(snippet: str) -> list[dict[str, str]]:
    return [{"rank": rank, "name": name.strip()} for rank, name in RANK_PATTERN.findall(snippet)]


def _aggregate_issues(file_entities: list[FileEntities]) -> list[dict[str, Any]]:
    totals: dict[str, int] = {key: 0 for key in ISSUE_KEYWORDS}
    for fe in file_entities:
        for k, v in fe.issues.items():
            totals[k] += v
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    return [{"name": name, "score": score} for name, score in ranked if score > 0]


def _aggregate_officers(file_entities: list[FileEntities]) -> list[dict[str, Any]]:
    counter: dict[tuple[str, str], int] = {}
    sources: dict[tuple[str, str], set[str]] = {}
    for fe in file_entities:
        for officer in fe.officers:
            key = (officer["rank"], officer["name"])
            counter[key] = counter.get(key, 0) + 1
            sources.setdefault(key, set()).add(fe.file_name)
    out = [
        {"rank": rank, "name": name, "mentions": count, "sources": sorted(sources[(rank, name)])}
        for (rank, name), count in counter.items()
    ]
    out.sort(key=lambda o: (-o["mentions"], o["name"]))
    return out


def _find_gaps(timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Surface days where evidence stops between two dates — useful red flag for detention cases."""
    gaps: list[dict[str, Any]] = []
    dated = [e for e in timeline if e.get("date")]
    for i in range(1, len(dated)):
        prev_iso, this_iso = dated[i - 1]["date"], dated[i]["date"]
        if prev_iso == this_iso:
            continue
        try:
            prev = _iso_to_ordinal(prev_iso)
            curr = _iso_to_ordinal(this_iso)
        except ValueError:
            continue
        if curr - prev >= 2:
            gaps.append({
                "from": prev_iso,
                "to": this_iso,
                "days": curr - prev,
                "note": "Possible undocumented period; verify whether a station refused production.",
            })
    return gaps


def _iso_to_ordinal(iso: str) -> int:
    from datetime import date

    y, m, d = (int(part) for part in iso.split("-"))
    return date(y, m, d).toordinal()


def _stable_id(seed: str) -> str:
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Helpers used by intake to classify a single file's evidence kind from text.
# ---------------------------------------------------------------------------


def classify_evidence_kind(filename: str, text: str) -> str:
    name = filename.lower()
    if name.endswith((".jpg", ".jpeg", ".png", ".heic")):
        return "photo"
    if name.endswith((".mp3", ".wav", ".m4a", ".ogg", ".aac")):
        return "audio"
    if name.endswith(".pdf"):
        return "pdf"
    if name.endswith(".csv"):
        return "csv"
    sample = (text or "")[:4000]
    if WHATSAPP_LINE.search(sample):
        return "whatsapp_export"
    if OB_PATTERN.search(sample) or STATION_PATTERN.search(sample):
        return "ob_extract"
    if "medical" in sample.lower() or "clinic" in sample.lower() or "diagnos" in sample.lower():
        return "medical_report"
    if name.endswith(".md") or name.startswith("note"):
        return "case_notes"
    return "text"
