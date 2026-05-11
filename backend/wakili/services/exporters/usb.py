"""USB-portable export — produces ``wakili_case_N_usb.zip``.

Inside the zip:

  - case_data/         (full bundle: bundle.json + petition_draft.md + …)
  - viewer.html        (single-file static viewer; loads case_data/*.json)
  - wakili-launcher.py (stdlib-only http.server launcher; opens browser)
  - RUN.sh / RUN.bat   (Linux/macOS / Windows convenience launchers)
  - INSTALL_TAILS.md   (copy onto Tails 6.x persistent volume)
  - verify.sh          (sha256sum verification against MANIFEST.json)
  - MANIFEST.json      (sha256 of every file in the pack)

Works under Firefox via ``file://`` open of viewer.html. Chrome/Chromium
users either run the launcher OR pass --allow-file-access-from-files. The
launcher boots a localhost http.server on a chosen port, opens the browser.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from ...config import EXPORTS_DIR, GENERATED_DIR, ensure_directories
from ..audit import record_audit


def export(case_id: int) -> Path:
    ensure_directories()
    src = GENERATED_DIR / f"case_{case_id}"
    if not src.exists():
        raise FileNotFoundError(f"No generated artifacts for case {case_id}")

    out_path = EXPORTS_DIR / f"wakili_case_{case_id}_usb.zip"

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / f"wakili_case_{case_id}"
        root.mkdir()

        # case_data: copy the bundle directory in.
        case_data_dir = root / "case_data"
        case_data_dir.mkdir()
        for path in sorted(src.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(src)
            dest = case_data_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)

        (root / "viewer.html").write_text(_viewer_html(case_id), encoding="utf-8")
        (root / "wakili-launcher.py").write_text(_launcher_py(), encoding="utf-8")
        (root / "RUN.sh").write_text(_run_sh(), encoding="utf-8")
        (root / "RUN.bat").write_text(_run_bat(), encoding="utf-8")
        (root / "INSTALL_TAILS.md").write_text(_install_tails(case_id), encoding="utf-8")
        (root / "verify.sh").write_text(_verify_sh(), encoding="utf-8")

        # Compute MANIFEST.json AFTER all other files are written.
        manifest = _compute_manifest(root)
        (root / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        # Zip the whole directory tree, with the top-level dir included.
        with zipfile.ZipFile(out_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    arc = path.relative_to(root.parent).as_posix()
                    zf.write(path, arcname=arc)

    record_audit(
        actor="exporter",
        action="export_usb",
        case_id=case_id,
        resource=str(out_path),
        payload={"size_bytes": out_path.stat().st_size},
    )
    return out_path


def _compute_manifest(root: Path) -> dict:
    files = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name == "MANIFEST.json":
            continue
        rel = path.relative_to(root).as_posix()
        files[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"version": 1, "algorithm": "sha256", "files": files}


def _run_sh() -> str:
    return """#!/usr/bin/env bash
# Verda — launch the viewer on Linux / macOS.
set -euo pipefail
cd "$(dirname "$0")"
exec python3 wakili-launcher.py "$@"
"""


def _run_bat() -> str:
    return """@echo off
cd /d "%~dp0"
python wakili-launcher.py %*
"""


def _install_tails(case_id: int) -> str:
    return f"""# Verda case {case_id} — Tails 6.x install

This pack runs without an installer. To use it on a Tails persistent volume:

1. Boot Tails 6.x. Set up a persistent volume (Applications → Configure
   persistent volume) with **Personal Documents** enabled and a strong
   passphrase.
2. Mount the persistent volume at `/home/amnesia/Persistent`.
3. Copy this entire directory to `/home/amnesia/Persistent/wakili-case-{case_id}/`.
4. Open a terminal in that directory and run:

       chmod +x RUN.sh && ./RUN.sh

   The viewer opens at http://127.0.0.1:8765/viewer.html.

5. To verify integrity before opening:

       chmod +x verify.sh && ./verify.sh

   `OK` means every file matches `MANIFEST.json`.

## Air-gap notes

- The launcher only binds 127.0.0.1. No outbound network calls.
- The viewer can also be opened directly under `file://` in Firefox.
- To panic-wipe: `srm -rfv /home/amnesia/Persistent/wakili-case-{case_id}`
  (or simply unplug the USB; Tails is amnesic).
"""


def _verify_sh() -> str:
    return """#!/usr/bin/env bash
# Verify file hashes against MANIFEST.json (stdlib-only, sha256sum).
set -euo pipefail
cd "$(dirname "$0")"
python3 - <<'PY'
import hashlib, json, sys
from pathlib import Path

root = Path(__file__).resolve().parent if "__file__" in dir() else Path.cwd()
mf = json.loads(Path("MANIFEST.json").read_text())
fail = 0
for rel, expected in mf["files"].items():
    p = Path(rel)
    if not p.exists():
        print(f"MISSING {rel}"); fail += 1; continue
    actual = hashlib.sha256(p.read_bytes()).hexdigest()
    if actual != expected:
        print(f"MISMATCH {rel}\\n  expected={expected}\\n  actual  ={actual}")
        fail += 1
if fail == 0:
    print(f"OK · {len(mf['files'])} files match MANIFEST.json")
    sys.exit(0)
sys.exit(1)
PY
"""


def _launcher_py() -> str:
    return '''#!/usr/bin/env python3
"""Verda portable viewer launcher (pure standard library).

Boots an http.server on 127.0.0.1, finds a free port, opens the user's
default browser on /viewer.html, and serves the bundle directory until
Ctrl-C. No FastAPI, no installs, Python 3.10+.
"""
from __future__ import annotations

import http.server
import os
import socket
import socketserver
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _free_port(preferred: int = 8765) -> int:
    for candidate in (preferred, *range(8765, 8800)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", candidate))
                return candidate
            except OSError:
                continue
    # Last resort: ephemeral.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):  # quieter
        sys.stderr.write("[wakili] " + (fmt % args) + "\\n")


def main(argv):
    port = _free_port()
    open_browser = "--no-browser" not in argv
    url = f"http://127.0.0.1:{port}/viewer.html"
    httpd = socketserver.TCPServer(("127.0.0.1", port), Handler)
    print(f"Verda viewer at {url}", flush=True)
    print("Ctrl-C to stop.", flush=True)

    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main(sys.argv[1:])
'''


def _viewer_html(case_id: int) -> str:
    return r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Verda case viewer</title>
  <style>
    :root { --ink:#0a1429; --ink-soft:#14223e; --paper:#faf6ec; --paper-deep:#f1ead7; --gold:#d4a534; --gold-bright:#f0c14b; --rust:#b85c20; --fern:#4f7a4f; }
    *, *::before, *::after { box-sizing: border-box; }
    html, body { margin: 0; background: var(--paper); color: var(--ink); font-family: ui-sans-serif, system-ui, -apple-system, sans-serif; }
    header { background: var(--ink); color: var(--paper); padding: 14px 24px; border-bottom: 2px solid var(--gold); display: flex; align-items: center; justify-content: space-between; }
    .brand { font-weight: 700; letter-spacing: -0.02em; }
    .brand small { color: var(--gold); font-size: 11px; text-transform: uppercase; letter-spacing: 0.18em; margin-left: 10px; }
    nav { display: flex; gap: 4px; }
    nav button { background: transparent; color: rgba(250,246,236,.75); border: 0; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 14px; }
    nav button.active { background: var(--gold); color: var(--ink); }
    main { max-width: 1100px; margin: 28px auto; padding: 0 24px; }
    .panel { display: none; }
    .panel.active { display: block; }
    h1 { font-size: 30px; margin: 0 0 6px; }
    h2 { font-size: 20px; margin: 0 0 12px; font-weight: 600; }
    .kicker { color: var(--gold); font-size: 11px; text-transform: uppercase; letter-spacing: 0.18em; margin-bottom: 8px; }
    .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 20px; }
    .stat { background: white; border: 1px solid rgba(10,20,41,.1); border-radius: 12px; padding: 12px 14px; }
    .stat dt { color: rgba(10,20,41,.5); font-size: 11px; text-transform: uppercase; letter-spacing: 0.12em; }
    .stat dd { margin: 4px 0 0; font-family: ui-monospace, monospace; font-size: 24px; font-weight: 600; }
    .evt { display: grid; grid-template-columns: 120px 1fr; gap: 12px; background: white; border: 1px solid rgba(10,20,41,.1); border-radius: 8px; padding: 10px 12px; margin-bottom: 8px; }
    .evt-date { font-family: ui-monospace, monospace; font-size: 12px; }
    .evt-source { font-family: ui-monospace, monospace; font-size: 11px; color: rgba(10,20,41,.4); margin-top: 4px; }
    article.petition { background: white; border: 1px solid rgba(10,20,41,.1); border-radius: 12px; padding: 32px; font-family: serif; line-height: 1.7; }
    article.petition h1, article.petition h2, article.petition h3 { font-family: serif; }
    .prec { background: white; border: 1px solid rgba(10,20,41,.1); border-radius: 12px; padding: 14px; margin-bottom: 8px; }
    .prec-title { font-family: serif; font-size: 17px; font-weight: 600; }
    .prec-rel { font-family: ui-monospace, monospace; font-size: 11px; color: rgba(10,20,41,.6); }
    .prec-meta { color: rgba(10,20,41,.5); font-size: 12px; margin-top: 2px; }
    .prec-url { color: var(--ink); border-bottom: 1px solid var(--gold); text-decoration: none; font-size: 12px; }
    .schedule { list-style: none; padding: 0; }
    .step { display: grid; grid-template-columns: 110px 1fr 100px; gap: 12px; background: white; border: 1px solid rgba(10,20,41,.1); border-radius: 8px; padding: 10px 14px; margin-bottom: 6px; }
    .step-pending { color: var(--fern); } .step-due_soon { color: var(--gold); } .step-overdue { color: var(--rust); }
    .err { color: var(--rust); font-size: 13px; padding: 10px 12px; background: rgba(184,92,32,.08); border: 1px solid rgba(184,92,32,.3); border-radius: 6px; }
    footer { color: rgba(10,20,41,.5); font-size: 12px; margin: 32px auto; max-width: 1100px; padding: 0 24px; }
  </style>
</head>
<body>
<header>
  <div class="brand">Verda <small>portable viewer · case __CASE_ID__</small></div>
  <nav id="nav">
    <button data-panel="overview" class="active">Overview</button>
    <button data-panel="timeline">Timeline</button>
    <button data-panel="petition">Petition</button>
    <button data-panel="precedents">Precedents</button>
    <button data-panel="procedure">Procedure</button>
  </nav>
</header>
<main>
  <section id="overview" class="panel active">
    <div class="kicker" id="overview-kicker">loading…</div>
    <h1 id="overview-title">…</h1>
    <p id="overview-desc"></p>
    <div class="stats" id="overview-stats"></div>
  </section>
  <section id="timeline" class="panel"><h2>Timeline</h2><div id="timeline-body">loading…</div></section>
  <section id="petition" class="panel"><article class="petition" id="petition-body">loading…</article></section>
  <section id="precedents" class="panel"><h2>Ranked precedents</h2><div id="precedents-body">loading…</div></section>
  <section id="procedure" class="panel"><h2 id="procedure-title">Procedure</h2><ol class="schedule" id="procedure-body">loading…</ol></section>
</main>
<footer>Lawyer in the loop. Telemetry off. AES-256-GCM bundles available.</footer>
<script>
(function(){
  const ESC = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
  // Tab switching
  const buttons = document.querySelectorAll("nav button");
  buttons.forEach(b => b.addEventListener("click", () => {
    buttons.forEach(x => x.classList.remove("active"));
    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
    b.classList.add("active");
    document.getElementById(b.dataset.panel).classList.add("active");
  }));

  function md(s){
    const lines = String(s).split("\n");
    let out = []; let inList = null; let para = [];
    const flushPara = () => { if(para.length){ out.push("<p>"+inline(para.join(" "))+"</p>"); para = []; } };
    const closeList = () => { if(inList){ out.push("</"+inList+">"); inList = null; } };
    for(const raw of lines){
      const line = raw.replace(/\s+$/, "");
      if(!line){ flushPara(); closeList(); continue; }
      const h = /^(#{1,6})\s+(.*)$/.exec(line);
      if(h){ flushPara(); closeList(); out.push("<h"+h[1].length+">"+inline(h[2])+"</h"+h[1].length+">"); continue; }
      const ol = /^(\d+)\.\s+(.*)$/.exec(line);
      if(ol){ flushPara(); if(inList!=="ol"){ closeList(); out.push("<ol>"); inList="ol"; } out.push("<li>"+inline(ol[2])+"</li>"); continue; }
      const ul = /^[-*]\s+(.*)$/.exec(line);
      if(ul){ flushPara(); if(inList!=="ul"){ closeList(); out.push("<ul>"); inList="ul"; } out.push("<li>"+inline(ul[1])+"</li>"); continue; }
      if(inList){ flushPara(); closeList(); }
      para.push(line);
    }
    flushPara(); closeList(); return out.join("\n");
  }
  function inline(s){
    return ESC(s)
      .replace(/\*\*([^*]+)\*\*/g,"<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g,"<em>$1</em>")
      .replace(/`([^`]+)`/g,"<code>$1</code>");
  }

  function showError(id, e){ document.getElementById(id).innerHTML = '<div class="err">Could not load · '+ESC(e&&e.message||e)+'</div>'; }

  Promise.all([
    fetch("case_data/bundle.json").then(r => r.json()),
    fetch("case_data/petition_draft.md").then(r => r.text())
  ]).then(([bundle, petition]) => {
    const cs = bundle.case_summary;
    document.getElementById("overview-kicker").textContent = (cs.jurisdiction||"").toUpperCase()+" · "+cs.track_label;
    document.getElementById("overview-title").textContent = cs.title;
    document.getElementById("overview-desc").textContent = cs.description||"";
    const ec = bundle.evidence_codex; const pl = bundle.precedent_linker;
    document.getElementById("overview-stats").innerHTML = [
      ["Events", ec.events_extracted],
      ["Officers", ec.officers_named],
      ["OB numbers", ec.ob_numbers_seen],
      ["Precedents", pl.result_count],
    ].map(([k,v]) => '<div class="stat"><dt>'+ESC(k)+'</dt><dd>'+ESC(v)+'</dd></div>').join("");

    document.getElementById("timeline-body").innerHTML = (ec.timeline||[]).map(e =>
      '<div class="evt"><div class="evt-date">'+ESC(e.date||"undated")+'</div><div><div>'+ESC(e.summary||"")+'</div><div class="evt-source">'+ESC(e.source_file||"")+":"+ESC(e.line_number||"?")+'</div></div></div>'
    ).join("") || "<p>No timeline events.</p>";

    document.getElementById("petition-body").innerHTML = md(petition);

    document.getElementById("precedents-body").innerHTML = (pl.results||[]).map(r =>
      '<div class="prec"><div style="display:flex;justify-content:space-between;align-items:baseline;gap:12px"><span class="prec-title">'+ESC(r.title)+'</span><span class="prec-rel">relevance '+(r.relevance_score||0).toFixed(2)+'</span></div><div class="prec-meta">'+ESC(r.court)+" · "+ESC(r.year)+'</div><div style="margin-top:6px;font-size:13px">'+ESC(r.summary)+'</div><a class="prec-url" href="'+ESC(r.url)+'" target="_blank" rel="noreferrer">verify on Kenya Law ↗</a></div>'
    ).join("") || "<p>No precedents matched.</p>";

    const pe = bundle.procedural_engine;
    document.getElementById("procedure-title").textContent = pe.track_label;
    document.getElementById("procedure-body").innerHTML = (pe.schedule||[]).map(s =>
      '<li class="step"><div style="font-family:ui-monospace,monospace;font-size:13px">'+ESC(s.deadline)+'</div><div><div>'+ESC(s.filing)+'</div><div style="color:rgba(10,20,41,.4);font-size:11px">'+ESC(s.rule||"")+'</div></div><div class="step-'+ESC(s.status)+'" style="text-align:right;font-size:12px;text-transform:uppercase;letter-spacing:0.1em">'+ESC(s.status)+'</div></li>'
    ).join("");
  }).catch(e => {
    showError("overview-stats", e);
    showError("timeline-body", e);
    showError("petition-body", e);
    showError("precedents-body", e);
    showError("procedure-body", e);
  });
})();
</script>
</body>
</html>
""".replace("__CASE_ID__", str(case_id))
