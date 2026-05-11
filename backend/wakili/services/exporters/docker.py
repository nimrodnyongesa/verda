"""Self-hosted Docker export — produces a single-file tarball deliverable.

The output is ``wakili_case_N_docker.tar.gz`` containing:

  - Dockerfile (python:3.12-slim base)
  - requirements.txt (fastapi + uvicorn + python-multipart + pydantic)
  - wakili_case_server/ — standalone read-only viewer for THIS case
  - case_data/ — copy of runtime/generated/case_N/
  - templates/ — pure-string HTML templates
  - static/styles.css — palette-matching styles
  - README.md — build & run instructions
  - docker-compose.yml — single-line deployment

The viewer reuses NOTHING from the main wakili package; it boots in ~3s on
any Docker host and serves timeline/petition/precedents/procedure for the
single embedded case.
"""
from __future__ import annotations

import io
import shutil
import tarfile
import tempfile
from pathlib import Path

from ...config import EXPORTS_DIR, GENERATED_DIR, ensure_directories
from ..audit import record_audit


def export(case_id: int) -> Path:
    ensure_directories()
    src = GENERATED_DIR / f"case_{case_id}"
    if not src.exists():
        raise FileNotFoundError(f"No generated artifacts for case {case_id}")

    out_path = EXPORTS_DIR / f"wakili_case_{case_id}_docker.tar.gz"

    # Build the deliverable in a tempdir, then tar it up.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / f"wakili_case_{case_id}"
        root.mkdir()

        # Static files
        (root / "Dockerfile").write_text(_dockerfile(case_id), encoding="utf-8")
        (root / "requirements.txt").write_text(_requirements(), encoding="utf-8")
        (root / "docker-compose.yml").write_text(_compose(case_id), encoding="utf-8")
        (root / "README.md").write_text(_readme(case_id), encoding="utf-8")

        # Server package
        server_dir = root / "wakili_case_server"
        server_dir.mkdir()
        (server_dir / "__init__.py").write_text("", encoding="utf-8")
        (server_dir / "main.py").write_text(_server_main(case_id), encoding="utf-8")

        # Templates
        templates_dir = root / "templates"
        templates_dir.mkdir()
        (templates_dir / "base.html").write_text(_tpl_base(), encoding="utf-8")
        (templates_dir / "index.html").write_text(_tpl_index(), encoding="utf-8")
        (templates_dir / "timeline.html").write_text(_tpl_timeline(), encoding="utf-8")
        (templates_dir / "petition.html").write_text(_tpl_petition(), encoding="utf-8")
        (templates_dir / "precedents.html").write_text(_tpl_precedents(), encoding="utf-8")
        (templates_dir / "procedure.html").write_text(_tpl_procedure(), encoding="utf-8")

        # Static
        static_dir = root / "static"
        static_dir.mkdir()
        (static_dir / "styles.css").write_text(_styles(), encoding="utf-8")

        # Case data — copy of generated/case_N/
        case_data_dir = root / "case_data"
        case_data_dir.mkdir()
        for path in sorted(src.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(src)
            dest = case_data_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)

        # Tar.gz the whole tree (with a single top-level dir)
        with tarfile.open(out_path, "w:gz") as tar:
            tar.add(root, arcname=root.name)

    record_audit(
        actor="exporter",
        action="export_docker",
        case_id=case_id,
        resource=str(out_path),
        payload={"size_bytes": out_path.stat().st_size},
    )
    return out_path


# ---------------------------------------------------------------------------


def _dockerfile(case_id: int) -> str:
    return f"""# Verda case-{case_id} self-hosted viewer
FROM python:3.12-slim

WORKDIR /opt/wakili

COPY requirements.txt /opt/wakili/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY wakili_case_server /opt/wakili/wakili_case_server
COPY templates /opt/wakili/templates
COPY static /opt/wakili/static
COPY case_data /opt/wakili/case_data

ENV WAKILI_CASE_ID={case_id}
EXPOSE 8765

CMD ["python", "-m", "uvicorn", "wakili_case_server.main:app", "--host", "0.0.0.0", "--port", "8765"]
"""


def _requirements() -> str:
    return "\n".join(
        [
            "fastapi==0.118.0",
            "uvicorn[standard]==0.32.0",
            "python-multipart==0.0.20",
            "pydantic==2.10.3",
        ]
    ) + "\n"


def _compose(case_id: int) -> str:
    return f"""services:
  wakili-case-{case_id}:
    build: .
    image: wakili-case-{case_id}:local
    ports:
      - "8765:8765"
    restart: unless-stopped
"""


def _readme(case_id: int) -> str:
    return f"""# Verda case {case_id} — self-hosted viewer

Single-file deliverable: extract this tarball and you have a working,
read-only Verda case viewer. No connection back to the original Verda
instance is needed.

## Build & run

```bash
tar xzf wakili_case_{case_id}_docker.tar.gz
cd wakili_case_{case_id}
docker build -t wakili-case-{case_id} .
docker run --rm -p 8765:8765 wakili-case-{case_id}
```

Or via docker-compose:

```bash
docker compose up
```

Then open http://localhost:8765/.

## What's inside

- `wakili_case_server/` — minimal FastAPI app (~200 lines, no Verda runtime)
- `case_data/` — bundle.json + petition_draft.md + drafted motions
- `templates/` — pure-string HTML, palette matches Verda
- `static/styles.css` — gold/ink/paper

## Security

- No outbound network calls. Read-only viewer.
- Bind-mount case_data read-only if you want belt-and-braces:
  `docker run -v ./case_data:/opt/wakili/case_data:ro -p 8765:8765 wakili-case-{case_id}`.
- Telemetry: off. There is none.
"""


def _server_main(case_id: int) -> str:
    return f'''"""Verda case-{case_id} self-hosted viewer — FastAPI app.

This file is intentionally self-contained. It does NOT import the wakili
package — it reads case_data/*.json from the bundle alongside it.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
CASE_DATA = ROOT / "case_data"
TEMPLATES = ROOT / "templates"

app = FastAPI(title="Verda case viewer", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")


def _read_json(name: str) -> dict:
    path = CASE_DATA / name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{{name}} not in bundle")
    return json.loads(path.read_text(encoding="utf-8"))


def _bundle() -> dict:
    return _read_json("bundle.json")


def _tpl(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def _layout(title: str, body: str, active: str) -> str:
    base = _tpl("base.html")
    nav_items = [
        ("/", "Overview", "overview"),
        ("/timeline", "Timeline", "timeline"),
        ("/petition", "Petition", "petition"),
        ("/precedents", "Precedents", "precedents"),
        ("/procedure", "Procedure", "procedure"),
    ]
    parts = []
    for href, label, key in nav_items:
        cls = "nav-item active" if key == active else "nav-item"
        parts.append('<a href="' + href + '" class="' + cls + '">' + label + '</a>')
    nav_html = "".join(parts)
    return base.replace("{{{{title}}}}", title).replace("{{{{nav}}}}", nav_html).replace("{{{{body}}}}", body)


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _md_to_html(md: str) -> str:
    """Tiny markdown subset — headings, bold/italic, lists."""
    lines = md.split("\\n")
    out = []
    in_list = None
    para = []

    def flush_para():
        if para:
            out.append(f"<p>{{_inline(' '.join(para))}}</p>")
            para.clear()

    def close_list():
        nonlocal in_list
        if in_list:
            out.append(f"</{{in_list}}>")
            in_list = None

    for raw in lines:
        line = raw.rstrip()
        if not line:
            flush_para()
            close_list()
            continue
        if line.startswith("#"):
            flush_para()
            close_list()
            level = len(line) - len(line.lstrip("#"))
            text = line.lstrip("#").strip()
            out.append(f"<h{{level}}>{{_inline(text)}}</h{{level}}>")
            continue
        if line[:2] == "- " or line[:2] == "* ":
            flush_para()
            if in_list != "ul":
                close_list()
                out.append("<ul>")
                in_list = "ul"
            out.append(f"<li>{{_inline(line[2:])}}</li>")
            continue
        m = line.split(". ", 1)
        if len(m) == 2 and m[0].isdigit():
            flush_para()
            if in_list != "ol":
                close_list()
                out.append("<ol>")
                in_list = "ol"
            out.append(f"<li>{{_inline(m[1])}}</li>")
            continue
        if in_list:
            flush_para()
            close_list()
        para.append(line)
    flush_para()
    close_list()
    return "\\n".join(out)


def _inline(s: str) -> str:
    s = _esc(s)
    # bold then italic then code
    out = []
    i = 0
    while i < len(s):
        if s.startswith("**", i):
            j = s.find("**", i + 2)
            if j != -1:
                out.append(f"<strong>{{s[i+2:j]}}</strong>")
                i = j + 2
                continue
        if s[i] == "*":
            j = s.find("*", i + 1)
            if j != -1:
                out.append(f"<em>{{s[i+1:j]}}</em>")
                i = j + 1
                continue
        if s[i] == "`":
            j = s.find("`", i + 1)
            if j != -1:
                out.append(f"<code>{{s[i+1:j]}}</code>")
                i = j + 1
                continue
        out.append(s[i])
        i += 1
    return "".join(out)


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    bundle = _bundle()
    case = bundle["case_summary"]
    body = _tpl("index.html")
    body = body.replace("{{{{case_title}}}}", _esc(case["title"]))
    body = body.replace("{{{{case_track}}}}", _esc(case["track_label"]))
    body = body.replace("{{{{case_citation}}}}", _esc(case.get("citation", "")))
    body = body.replace("{{{{case_jurisdiction}}}}", _esc(case["jurisdiction"].upper()))
    body = body.replace("{{{{case_description}}}}", _esc(case.get("description", "")))
    body = body.replace("{{{{events_extracted}}}}", str(bundle["evidence_codex"]["events_extracted"]))
    body = body.replace("{{{{officers_named}}}}", str(bundle["evidence_codex"]["officers_named"]))
    body = body.replace("{{{{ob_numbers_seen}}}}", str(bundle["evidence_codex"]["ob_numbers_seen"]))
    body = body.replace("{{{{precedents_ranked}}}}", str(bundle["precedent_linker"]["result_count"]))
    return HTMLResponse(_layout(case["title"], body, "overview"))


@app.get("/timeline", response_class=HTMLResponse)
def timeline() -> HTMLResponse:
    bundle = _bundle()
    codex = bundle["evidence_codex"]
    rows = []
    for ev in codex.get("timeline", []):
        rows.append(
            f"""<li class="evt">
              <div class="evt-date">{{_esc(ev.get('date') or 'undated')}}</div>
              <div class="evt-body">
                <div class="evt-summary">{{_esc(ev.get('summary',''))}}</div>
                <div class="evt-source">{{_esc(ev.get('source_file',''))}}:{{ev.get('line_number','?')}}</div>
              </div>
            </li>"""
        )
    body = _tpl("timeline.html").replace("{{{{rows}}}}", "\\n".join(rows))
    body = body.replace("{{{{events_extracted}}}}", str(codex["events_extracted"]))
    return HTMLResponse(_layout("Timeline", body, "timeline"))


@app.get("/petition", response_class=HTMLResponse)
def petition() -> HTMLResponse:
    md = (CASE_DATA / "petition_draft.md").read_text(encoding="utf-8")
    body = _tpl("petition.html").replace("{{{{petition_html}}}}", _md_to_html(md))
    return HTMLResponse(_layout("Petition", body, "petition"))


@app.get("/precedents", response_class=HTMLResponse)
def precedents() -> HTMLResponse:
    pl = _bundle()["precedent_linker"]
    rows = []
    for r in pl.get("results", []):
        rows.append(
            f"""<li class="prec">
              <div class="prec-head">
                <span class="prec-title">{{_esc(r['title'])}}</span>
                <span class="prec-rel">relevance {{r['relevance_score']:.2f}}</span>
              </div>
              <div class="prec-meta">{{_esc(r['court'])}} · {{r['year']}}</div>
              <div class="prec-summary">{{_esc(r['summary'])}}</div>
              <a class="prec-url" href="{{_esc(r['url'])}}" target="_blank" rel="noreferrer">verify on Kenya Law ↗</a>
            </li>"""
        )
    body = _tpl("precedents.html").replace("{{{{rows}}}}", "\\n".join(rows))
    return HTMLResponse(_layout("Precedents", body, "precedents"))


@app.get("/procedure", response_class=HTMLResponse)
def procedure() -> HTMLResponse:
    pe = _bundle()["procedural_engine"]
    rows = []
    for s in pe.get("schedule", []):
        rows.append(
            f"""<li class="step">
              <div class="step-deadline">{{_esc(s['deadline'])}}</div>
              <div class="step-body">
                <div class="step-filing">{{_esc(s['filing'])}}</div>
                <div class="step-rule">{{_esc(s.get('rule',''))}}</div>
              </div>
              <div class="step-status step-{{s['status']}}">{{s['status']}}</div>
            </li>"""
        )
    body = _tpl("procedure.html").replace("{{{{rows}}}}", "\\n".join(rows))
    body = body.replace("{{{{track_label}}}}", _esc(pe["track_label"]))
    body = body.replace("{{{{citation}}}}", _esc(pe.get("citation", "")))
    return HTMLResponse(_layout("Procedure", body, "procedure"))


@app.get("/api/bundle")
def bundle_json() -> JSONResponse:
    return JSONResponse(_bundle())


@app.get("/healthz")
def healthz() -> dict:
    return {{"ok": True, "case_id": {case_id}}}
'''


def _tpl_base() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{{title}} — Verda</title>
  <link rel="stylesheet" href="/static/styles.css" />
</head>
<body>
  <header class="topbar">
    <div class="brand">
      <span class="brand-name">Verda</span>
      <span class="brand-tag">case viewer · self-hosted</span>
    </div>
    <nav class="nav">{{nav}}</nav>
  </header>
  <main class="main">{{body}}</main>
  <footer class="footer">
    <span>Lawyer in the loop. Telemetry off. AES-256-GCM bundles available.</span>
  </footer>
</body>
</html>
"""


def _tpl_index() -> str:
    return """<section class="hero">
  <p class="kicker">{{case_jurisdiction}} · {{case_track}}</p>
  <h1>{{case_title}}</h1>
  <p class="lead">{{case_description}}</p>
  <p class="citation">{{case_citation}}</p>
</section>
<section class="stats">
  <div class="stat"><dt>Events</dt><dd>{{events_extracted}}</dd></div>
  <div class="stat"><dt>Officers</dt><dd>{{officers_named}}</dd></div>
  <div class="stat"><dt>OB numbers</dt><dd>{{ob_numbers_seen}}</dd></div>
  <div class="stat"><dt>Precedents</dt><dd>{{precedents_ranked}}</dd></div>
</section>
"""


def _tpl_timeline() -> str:
    return """<section><h2>Timeline · {{events_extracted}} events</h2>
<ol class="timeline">{{rows}}</ol></section>"""


def _tpl_petition() -> str:
    return """<article class="petition">{{petition_html}}</article>"""


def _tpl_precedents() -> str:
    return """<section><h2>Ranked precedents</h2>
<ul class="precedents">{{rows}}</ul></section>"""


def _tpl_procedure() -> str:
    return """<section><h2>{{track_label}}</h2>
<p class="citation">{{citation}}</p>
<ol class="schedule">{{rows}}</ol></section>"""


def _styles() -> str:
    return """:root {
  --ink: #0a1429;
  --ink-soft: #14223e;
  --paper: #faf6ec;
  --paper-deep: #f1ead7;
  --gold: #d4a534;
  --gold-bright: #f0c14b;
  --rust: #b85c20;
  --fern: #4f7a4f;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: var(--paper); color: var(--ink); font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
.topbar { display: flex; align-items: center; justify-content: space-between; background: var(--ink); color: var(--paper); padding: 14px 24px; border-bottom: 2px solid var(--gold); }
.brand { display: flex; gap: 12px; align-items: baseline; }
.brand-name { font-weight: 700; letter-spacing: -0.02em; font-size: 18px; }
.brand-tag { color: var(--gold); font-size: 11px; letter-spacing: 0.18em; text-transform: uppercase; }
.nav { display: flex; gap: 6px; }
.nav-item { color: rgba(250,246,236,0.75); text-decoration: none; padding: 6px 12px; border-radius: 6px; font-size: 14px; }
.nav-item:hover { color: var(--gold-bright); background: rgba(255,255,255,0.05); }
.nav-item.active { background: var(--gold); color: var(--ink); }
.main { max-width: 1100px; margin: 32px auto; padding: 0 24px; }
.footer { max-width: 1100px; margin: 48px auto 24px; padding: 0 24px; color: rgba(10,20,41,0.5); font-size: 12px; }
.hero { border-left: 4px solid var(--gold); padding: 4px 16px; margin-bottom: 24px; }
.kicker { color: var(--gold); font-size: 11px; text-transform: uppercase; letter-spacing: 0.18em; margin: 0 0 8px; }
.hero h1 { font-size: 32px; margin: 0 0 8px; line-height: 1.15; }
.lead { color: rgba(10,20,41,0.75); }
.citation { color: rgba(10,20,41,0.5); font-family: ui-monospace, Consolas, monospace; font-size: 12px; }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.stat { background: white; border: 1px solid rgba(10,20,41,0.1); border-radius: 12px; padding: 12px 16px; }
.stat dt { color: rgba(10,20,41,0.5); font-size: 11px; text-transform: uppercase; letter-spacing: 0.12em; }
.stat dd { margin: 4px 0 0; font-family: ui-monospace, Consolas, monospace; font-size: 24px; font-weight: 600; color: var(--ink); }
.timeline, .precedents, .schedule { list-style: none; padding: 0; display: grid; gap: 8px; }
.evt { display: grid; grid-template-columns: 130px 1fr; gap: 12px; background: white; border: 1px solid rgba(10,20,41,0.1); border-radius: 8px; padding: 10px 14px; }
.evt-date { font-family: ui-monospace, monospace; font-size: 12px; color: rgba(10,20,41,0.7); }
.evt-summary { font-size: 14px; }
.evt-source { font-family: ui-monospace, monospace; font-size: 11px; color: rgba(10,20,41,0.4); margin-top: 4px; }
.prec { background: white; border: 1px solid rgba(10,20,41,0.1); border-radius: 12px; padding: 14px; }
.prec-head { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }
.prec-title { font-family: serif; font-size: 18px; font-weight: 600; }
.prec-rel { font-family: ui-monospace, monospace; font-size: 11px; color: rgba(10,20,41,0.6); }
.prec-meta { color: rgba(10,20,41,0.5); font-size: 12px; margin-top: 4px; }
.prec-summary { margin-top: 8px; font-size: 13px; }
.prec-url { display: inline-block; margin-top: 8px; color: var(--ink); border-bottom: 1px solid var(--gold); text-decoration: none; font-size: 12px; }
.step { display: grid; grid-template-columns: 110px 1fr 100px; gap: 12px; background: white; border: 1px solid rgba(10,20,41,0.1); border-radius: 8px; padding: 10px 14px; }
.step-deadline { font-family: ui-monospace, monospace; font-size: 13px; }
.step-rule { color: rgba(10,20,41,0.4); font-size: 11px; }
.step-status { text-align: right; font-size: 12px; text-transform: uppercase; letter-spacing: 0.1em; }
.step-pending { color: var(--fern); }
.step-due_soon { color: var(--gold); }
.step-overdue { color: var(--rust); }
.petition { background: white; border: 1px solid rgba(10,20,41,0.1); border-radius: 12px; padding: 32px; font-family: serif; line-height: 1.7; }
.petition h1, .petition h2, .petition h3 { font-family: serif; }
.petition code { font-family: ui-monospace, monospace; background: var(--paper-deep); padding: 1px 4px; border-radius: 3px; }
"""
