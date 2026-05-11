"""Procedural Engine — state machine that encodes the relevant procedure for a jurisdiction.

For Kenya Article 22/23, this module loads the per-jurisdiction rule pack from
data/jurisdictions/ke/procedural_rules.json and computes:
  - the list of required filings in sequence
  - the deadline associated with each filing
  - the next required action given current state
  - drafted motions that are *case-specific* (not generic boilerplate) — each
    motion is rendered with extracted parties, officer names, OB numbers,
    chronology, gaps, articles invoked, and (when present) verified
    precedents.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from ..config import GENERATED_DIR, JURISDICTIONS_DIR


def _load_rules(jurisdiction: str, track: str) -> dict[str, Any]:
    path = JURISDICTIONS_DIR / jurisdiction / "procedural_rules.json"
    if not path.exists():
        raise FileNotFoundError(f"Procedural rules not found for {jurisdiction}: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    tracks = payload.get("tracks", {})
    if track not in tracks:
        # Fallback: first track defined.
        track = next(iter(tracks))
    return {
        "jurisdiction": jurisdiction,
        "track": track,
        "label": tracks[track]["label"],
        "citation": tracks[track].get("citation", ""),
        "filings": tracks[track]["filings"],
        "templates": tracks[track].get("templates", {}),
    }


def _load_template(jurisdiction: str, template_name: str) -> str:
    path = JURISDICTIONS_DIR / jurisdiction / "templates" / template_name
    if not path.exists():
        return f"# Template missing: {template_name}\n"
    return path.read_text(encoding="utf-8")


def build_procedural_engine(
    case_row: dict[str, Any],
    evidence_codex: dict[str, Any],
    *,
    today: date | None = None,
) -> dict[str, Any]:
    today = today or date.today()
    jurisdiction = case_row.get("jurisdiction") or "ke"
    track = case_row.get("legal_track") or "article_22_petition"
    rules = _load_rules(jurisdiction, track)

    incident_date = _earliest_incident_date(evidence_codex) or today
    schedule = _compute_schedule(rules["filings"], incident_date, today)
    next_action = next((s for s in schedule if s["status"] in {"due_soon", "overdue", "pending"}), None)

    motions = _draft_motions(case_row, evidence_codex, rules, today=today)

    return {
        "jurisdiction": jurisdiction,
        "track": track,
        "track_label": rules["label"],
        "citation": rules["citation"],
        "anchor_date": incident_date.isoformat(),
        "today": today.isoformat(),
        "schedule": schedule,
        "next_action": next_action,
        "required_filings": [s["filing"] for s in schedule],
        "drafted_motions": motions,
        "state": "ready_for_review",
    }


def _earliest_incident_date(evidence_codex: dict[str, Any]) -> date | None:
    timeline = evidence_codex.get("timeline") or []
    for event in timeline:
        iso = event.get("date")
        if not iso:
            continue
        try:
            return datetime.strptime(iso, "%Y-%m-%d").date()
        except ValueError:
            continue
    return None


def _compute_schedule(
    filings: list[dict[str, Any]], incident_date: date, today: date
) -> list[dict[str, Any]]:
    schedule: list[dict[str, Any]] = []
    for entry in filings:
        offset_days = entry.get("offset_days_from_incident", 0)
        deadline = incident_date + timedelta(days=offset_days)
        days_remaining = (deadline - today).days
        if days_remaining < 0:
            status = "overdue"
        elif days_remaining <= 3:
            status = "due_soon"
        else:
            status = "pending"
        schedule.append({
            "filing": entry["filing"],
            "purpose": entry.get("purpose", ""),
            "rule": entry.get("rule", ""),
            "deadline": deadline.isoformat(),
            "days_remaining": days_remaining,
            "status": status,
            "template": entry.get("template"),
            "annexures": entry.get("annexures", []),
        })
    return schedule


# ---------------------------------------------------------------------------
# Motion drafting — the engine returns *case-specific* prose, not generic
# templates with a single placeholder. Each section below is computed from
# the evidence codex (and the precedent linker output when available) so a
# motion for case A reads differently from a motion for case B.
# ---------------------------------------------------------------------------


def _format_petitioners(meta: dict[str, Any]) -> tuple[str, str]:
    """Return (block, count_phrase). Accepts ``metadata.petitioners`` as a
    list of names, or ``metadata.petitioner`` as a single string. Renders
    a numbered list when there is more than one petitioner so the title
    of the petition reads naturally for class actions."""
    petitioners = meta.get("petitioners")
    if isinstance(petitioners, list) and petitioners:
        names = [str(n).strip() for n in petitioners if str(n).strip()]
    else:
        single = meta.get("petitioner")
        names = [str(single).strip()] if single and str(single).strip() else []
    if not names:
        return ("[PETITIONER NAME — SIGN BEFORE FILING]", "Petitioner")
    if len(names) == 1:
        return (names[0], "Petitioner")
    block = "\n".join(f"   {idx + 1}. {name}" for idx, name in enumerate(names))
    return (block, f"Petitioners ({len(names)})")


def _ordinal(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        return f"{n}TH"
    suf = {1: "ST", 2: "ND", 3: "RD"}.get(n % 10, "TH")
    return f"{n}{suf}"


def _format_respondents(stations: list[str]) -> str:
    """Build the BETWEEN block respondents. The Inspector-General is the
    1st respondent; each station OCS becomes its own numbered respondent
    so the cause title reflects the institutional defendants accurately."""
    out: list[str] = []
    out.append(
        "THE INSPECTOR GENERAL, NATIONAL POLICE SERVICE ............................. 1ST RESPONDENT"
    )
    next_idx = 2
    for station in stations[:8]:
        label = station.strip()
        if not label:
            continue
        out.append(
            f"THE OFFICER COMMANDING STATION, {label.upper()} ............................. {_ordinal(next_idx)} RESPONDENT"
        )
        next_idx += 1
    out.append(
        f"THE HONOURABLE ATTORNEY-GENERAL ............................. {_ordinal(next_idx)} RESPONDENT"
    )
    return "\n".join(out)


def _format_chronology(timeline: list[dict[str, Any]]) -> str:
    """Per-event paragraph form, each numbered with date, summary, source
    file, and any OB numbers / officers extracted from the surrounding
    snippet. The lawyer can cross-reference these to the evidence_codex
    timeline by paragraph number."""
    if not timeline:
        return "   - [Chronology pending — no events were extracted from the evidence.]"
    lines: list[str] = []
    for idx, event in enumerate(timeline[:30], start=1):
        when = event.get("date") or "undated"
        summary = (event.get("summary") or "").strip().replace("\n", " ")[:280]
        source = event.get("source_file") or ""
        line_no = event.get("line_number")
        cite_bits: list[str] = []
        if source:
            cite_bits.append(source)
        if isinstance(line_no, int) and line_no > 0:
            cite_bits.append(f"line {line_no}")
        cite = f" [source: {' · '.join(cite_bits)}]" if cite_bits else ""
        ob_inline = ", ".join(event.get("ob_numbers_in_context") or [])
        ob_part = f" OB ref: {ob_inline}." if ob_inline else ""
        officers_inline = ", ".join(
            f"{o.get('rank', '').strip()} {o.get('name', '').strip()}".strip()
            for o in (event.get("officers_in_context") or [])[:3]
        )
        off_part = f" Officers in context: {officers_inline}." if officers_inline else ""
        lines.append(
            f"   {idx}. ON {when.upper()}: {summary}.{ob_part}{off_part}{cite}"
        )
    return "\n".join(lines)


def _format_officers(officers: list[dict[str, Any]]) -> str:
    if not officers:
        return "   - [Officers to be confirmed by counsel before filing.]"
    out: list[str] = []
    for idx, o in enumerate(officers[:12], start=1):
        rank = (o.get("rank") or "").strip()
        name = (o.get("name") or "").strip()
        mentions = int(o.get("mentions") or 0)
        sources = o.get("sources") or []
        src_count = len(sources)
        sources_inline = ", ".join(sources[:3])
        if src_count > 3:
            sources_inline += f", and {src_count - 3} other(s)"
        out.append(
            f"   ({idx}) {rank} {name} — referenced {mentions} time(s) across {src_count} evidence file(s){f': {sources_inline}' if sources_inline else ''}."
        )
    return "\n".join(out)


def _format_obs(ob_numbers: list[str]) -> str:
    if not ob_numbers:
        return "   - [No Occurrence Book numbers were extracted from the record.]"
    out: list[str] = []
    for idx, ob in enumerate(ob_numbers[:25], start=1):
        out.append(f"   ({idx}) OB No. {ob}")
    return "\n".join(out)


def _format_articles(articles: list[str]) -> str:
    if not articles:
        return "Articles 22, 23, 29, 49, and 51 of the Constitution of Kenya, 2010"
    cleaned = [str(a).strip() for a in articles if str(a).strip()]
    if not cleaned:
        return "Articles 22, 23, 29, 49, and 51 of the Constitution of Kenya, 2010"
    if len(cleaned) == 1:
        joined = cleaned[0]
    elif len(cleaned) == 2:
        joined = f"{cleaned[0]} and {cleaned[1]}"
    else:
        joined = ", ".join(cleaned[:-1]) + f", and {cleaned[-1]}"
    return f"{joined} of the Constitution of Kenya, 2010"


def _format_gaps(gaps: list[dict[str, Any]]) -> str:
    if not gaps:
        return ""
    lines = ["", "## C. Gaps in the record disclosed to the Court", ""]
    for idx, g in enumerate(gaps[:10], start=1):
        lines.append(
            f"   {idx}. Between {g.get('from', '?')} and {g.get('to', '?')} ({g.get('days', 0)} days): "
            f"{(g.get('note') or '').strip() or 'no contemporaneous record located.'}"
        )
    return "\n".join(lines)


def _format_issues(issue_heatmap: list[dict[str, Any]]) -> tuple[str, list[str]]:
    """Return (inline summary, list of issue keys) — used both inline and
    to drive issue-specific prayers below."""
    pairs = [(i.get("name") or "").strip() for i in issue_heatmap[:8]]
    pairs = [p for p in pairs if p]
    inline = ", ".join(pairs) if pairs else "fundamental rights and freedoms"
    return inline, pairs


_ISSUE_PRAYERS: dict[str, str] = {
    "denial of counsel": "An order compelling the Respondents to permit the petitioner(s) immediate, unimpeded, and confidential access to counsel of their choosing.",
    "unlawful detention": "A writ of habeas corpus directing the Respondents to produce the body of each named petitioner before this Honourable Court forthwith.",
    "use of force": "A declaration that any use of force documented in the evidence record is excessive and contrary to Articles 25(a) and 29 of the Constitution.",
    "fair-trial": "An order that the petitioner(s), if any are charged, be charged before a competent court within twenty-four (24) hours of arrest, in accordance with Article 49(1)(f).",
    "fair_trial": "An order that the petitioner(s), if any are charged, be charged before a competent court within twenty-four (24) hours of arrest, in accordance with Article 49(1)(f).",
    "freedom of assembly": "A declaration that the conduct complained of violates Article 37 of the Constitution and is unlawful.",
    "freedom of expression": "A declaration that the conduct complained of violates Article 33 of the Constitution.",
    "torture": "A declaration that any conduct amounting to torture, cruel, inhuman, or degrading treatment is non-derogable and violates Article 25 of the Constitution.",
}


def _format_prayers(issues: list[str]) -> str:
    """Build the prayer block. Always includes urgency, the conservatory
    order, and costs; appends issue-specific prayers from the heatmap."""
    base: list[str] = [
        "1. **THAT** this Application be certified as urgent and be heard ex-parte in the first instance.",
        "2. **THAT** a conservatory order do issue compelling the Respondents to produce the petitioner(s) before this Honourable Court forthwith and to disclose to the Court the lawful basis for any continued detention.",
    ]
    counter = 3
    seen: set[str] = set()
    for issue in issues:
        key = issue.lower().strip()
        prayer = _ISSUE_PRAYERS.get(key)
        if not prayer or key in seen:
            continue
        seen.add(key)
        base.append(f"{counter}. **THAT** {prayer}")
        counter += 1
    base.append(
        f"{counter}. **THAT** the Respondents and their agents, servants, or representatives be restrained from further detaining, harassing, intimidating, or otherwise interfering with the rights of the petitioner(s) pending the hearing and determination of this Petition."
    )
    counter += 1
    base.append(
        f"{counter}. **THAT** general damages, exemplary damages, and aggravated damages do issue against the Respondents jointly and severally for the violations particularised herein."
    )
    counter += 1
    base.append(f"{counter}. **THAT** costs of this Application be provided for.")
    counter += 1
    base.append(
        f"{counter}. **THAT** this Honourable Court do grant such further or other relief as it may deem just and expedient in the circumstances."
    )
    return "\n".join(base)


def _detention_window(timeline: list[dict[str, Any]], today: date) -> str:
    if not timeline:
        return "[Detention window pending evidence review.]"
    earliest = _earliest_incident_date({"timeline": timeline})
    if not earliest:
        return "[Detention window pending evidence review.]"
    days = (today - earliest).days
    if days <= 0:
        return f"The arrest documented in the record was effected on {earliest.isoformat()}."
    return (
        f"The arrest documented in the record was effected on {earliest.isoformat()}, "
        f"and the petitioner(s) have therefore been deprived of liberty for not less "
        f"than {days} day(s) at the time of filing."
    )


def _load_precedents(case_id: int | None) -> list[dict[str, Any]]:
    if not case_id:
        return []
    path: Path = GENERATED_DIR / f"case_{int(case_id)}" / "precedent_linker.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return list(data.get("results") or [])


def _format_precedents(precedents: list[dict[str, Any]]) -> str:
    if not precedents:
        return (
            "[The Precedent Linker has not yet completed for this case. Once it has, "
            "verified citations from kenyalaw-mcp will be inserted here automatically. "
            "Until then, counsel must satisfy this Court that any case-law cited has "
            "been independently verified.]"
        )
    out: list[str] = []
    for idx, p in enumerate(precedents[:12], start=1):
        title = (p.get("title") or "").strip() or "[Untitled]"
        citation = (p.get("citation") or "").strip()
        court = (p.get("court") or "").strip()
        year = p.get("year")
        url = (p.get("url") or "").strip()
        binding = "binding" if p.get("binding") else "persuasive"
        articles = ", ".join(p.get("articles_cited") or [])
        summary = (p.get("summary") or "").strip()
        line = f"   {idx}. *{title}*"
        if citation:
            line += f", {citation}"
        if court or year:
            line += f" ({court}{', ' if court and year else ''}{year or ''})"
        line += f" — {binding}."
        if articles:
            line += f" Articles cited: {articles}."
        if url:
            line += f" Verified URL: {url}"
        if summary:
            line += f"\n      Holding: {summary[:280]}"
        out.append(line)
    return "\n".join(out)


def _format_evidence_summary(evidence_codex: dict[str, Any]) -> str:
    return (
        f"   - Files indexed: {evidence_codex.get('files_indexed') or 0}\n"
        f"   - Events extracted: {evidence_codex.get('events_extracted') or 0}\n"
        f"   - Distinct officers named: {evidence_codex.get('officers_named') or 0}\n"
        f"   - Distinct stations named: {evidence_codex.get('stations_named') or 0}\n"
        f"   - Occurrence Book numbers seen: {evidence_codex.get('ob_numbers_seen') or 0}"
    )


def _draft_motions(
    case_row: dict[str, Any],
    evidence_codex: dict[str, Any],
    rules: dict[str, Any],
    *,
    today: date,
) -> list[dict[str, Any]]:
    drafted: list[dict[str, Any]] = []
    timeline = evidence_codex.get("timeline") or []
    first = timeline[0] if timeline else {}

    petitioner_block, _phrase = _format_petitioners(case_row.get("metadata") or {})
    issues_inline, issue_keys = _format_issues(evidence_codex.get("issue_heatmap") or [])
    chronology = _format_chronology(timeline)
    officers_block = _format_officers(evidence_codex.get("officers") or [])
    obs_block = _format_obs(evidence_codex.get("ob_numbers") or [])
    stations_inline = ", ".join(evidence_codex.get("stations") or []) or "[STATION NAMES TO BE CONFIRMED BY COUNSEL]"
    respondents_block = _format_respondents(evidence_codex.get("stations") or [])
    articles_phrase = _format_articles(evidence_codex.get("articles_invoked") or [])
    prayers_block = _format_prayers(issue_keys)
    gaps_block = _format_gaps(evidence_codex.get("gaps") or [])
    detention_window = _detention_window(timeline, today)
    precedents_block = _format_precedents(_load_precedents(case_row.get("id")))
    evidence_summary = _format_evidence_summary(evidence_codex)

    context = {
        # Identity
        "case_title": case_row["title"],
        "case_description": case_row.get("description") or "[Case facts pending counsel review]",
        "track_label": rules["label"],
        "citation": rules["citation"],
        "petitioner_block": petitioner_block,
        "respondents_block": respondents_block,
        # Inline summaries
        "issues_inline": issues_inline,
        "stations_inline": stations_inline,
        "articles_phrase": articles_phrase,
        # Block bodies
        "officers_block": officers_block,
        "ob_numbers_block": obs_block,
        "chronology_block": chronology,
        "prayers_block": prayers_block,
        "gaps_block": gaps_block,
        "evidence_summary_block": evidence_summary,
        "precedents_block": precedents_block,
        # Dates
        "first_event_date": first.get("date") or "[FIRST EVENT DATE]",
        "detention_window": detention_window,
        "today": today.isoformat(),
    }

    for entry in rules["filings"]:
        template_name = entry.get("template")
        if not template_name:
            continue
        raw = _load_template(rules["jurisdiction"], template_name)
        rendered = _render(raw, context)
        drafted.append({
            "filing": entry["filing"],
            "template": template_name,
            "content": rendered,
        })
    return drafted


def _render(template: str, context: dict[str, Any]) -> str:
    out = template
    for key, value in context.items():
        out = out.replace("{{" + key + "}}", str(value))
    return out
