"""Read-only, loopback-only stdlib research dashboard; no private keys or answer keys."""
from __future__ import annotations

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit

from .platform import ResearchWorkspace, PlatformError


def _text(value: object) -> str:
    return escape(str(value), quote=True)


def render_dashboard(overview: dict) -> str:
    artifacts = overview['artifacts']
    cards = []
    for a in reversed(artifacts):
        s = a['summary']
        label = s.get('study_id', s['type'].replace('_',' ').title())
        type_name = a['kind'].upper()
        desc = ''
        if a['kind'] == 'experiment':
            rows=[]
            for name, rec in s['results'].items():
                fraction=float(rec['overall_success'])
                pct=max(0, min(100, fraction*100))
                rows.append(f'<div class="metric"><span>{_text(name)}</span>'
                            f'<div class="bar"><div style="width:{pct:.1f}%"></div></div>'
                            f'<b>{pct:.0f}%</b></div>')
            desc=(f'<div class="meta">Mode: {_text(s["provider_mode"])} · '
                  f'{_text(s["evaluation_cases"])} evaluation cases · '
                  f'Compute: {_text(s["resource_comparability"])} · '
                  f'Confirmatory design eligible: {_text(s["confirmatory_design_eligible"])}</div>'
                  + ''.join(rows))
        elif a['kind'] == 'graph':
            desc=(f'<div class="meta">{_text(s["nodes"])} nodes · '
                  f'{_text(s["edges"])} edges · {_text(s["open_questions"])} open questions</div>')
        elif a['kind'] == 'revision':
            states=', '.join(f'{_text(k)}: {_text(v)}' for k,v in s['state_counts'].items())
            desc=(f'<div class="meta">{_text(s["revision_events"])} revisions · '
                  f'{_text(s["claims_assessed"])} assessed claims · {states}</div>')
        cards.append(f'<article><div class="top"><span class="pill">{_text(type_name)}</span>'
                     f'<small>{_text(a["imported_at"])}</small></div>'
                     f'<h3>{_text(label)}</h3><code>{_text(a["id"])}</code>{desc}'
                     f'<p class="warning">{_text(s["warning"])}</p></article>')
    body=''.join(cards) if cards else '<p>No validated research artifacts imported yet.</p>'
    integrity=overview['integrity']
    css='''
:root{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;color:#1f3043;background:#f5f7fb}
*{box-sizing:border-box}body{margin:0}header{background:#13283f;color:white;padding:30px max(22px,calc((100% - 1100px)/2))}
header h1{margin:0;font-size:1.8rem}header p{color:#b9d0e2;margin:10px 0 0;font-size:.95rem}
main{max-width:1100px;margin:auto;padding:24px} .summary{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:18px}
.kpi{flex:1;min-width:140px;background:white;border:1px solid #e0e6ef;border-radius:12px;padding:18px}
.kpi strong{display:block;font-size:1.65rem}.kpi span{font-size:.85rem;color:#526579}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:16px}
article{background:white;border:1px solid #dce4ee;border-radius:12px;padding:20px;overflow-wrap:anywhere}
.top{display:flex;justify-content:space-between;gap:8px;color:#68788d}.pill{font-size:.73rem;font-weight:750;background:#e2eef9;color:#15517f;padding:4px 8px;border-radius:30px}
h3{font-size:1.13rem;margin:14px 0 6px}code{font-size:.72rem;color:#748295}
.meta{margin:16px 0;font-size:.85rem;color:#4d6175}.metric{display:grid;grid-template-columns:92px 1fr 42px;gap:10px;align-items:center;font-size:.8rem;margin:9px 0}
.metric b{text-align:right}.bar{height:10px;background:#eaf0f6;border-radius:99px;overflow:hidden}.bar div{height:100%;background:#3485bd}
.warning{font-size:.75rem;color:#875e24;background:#fff6e5;padding:8px;border-radius:6px}
footer{color:#65798e;font-size:.8rem;padding:24px 0}a{color:#12669c}
'''
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>REI-1.0 Research Dashboard</title><style>{css}</style></head>
<body><header><h1>REI 1.0 · Research Observatory</h1><p>Local, read-only summaries of validated research artifacts</p></header>
<main><section class="summary"><div class="kpi"><strong>{len(artifacts)}</strong><span>Imported artifacts</span></div>
<div class="kpi"><strong>{overview['counts'].get('experiment',0)}</strong><span>Experiments</span></div>
<div class="kpi"><strong>{overview['counts'].get('graph',0)}</strong><span>Epistemic graphs</span></div>
<div class="kpi"><strong>{overview['counts'].get('revision',0)}</strong><span>Revision journals</span></div></section>
<h2>Research records</h2><section class="grid">{body}</section>
<footer>Local audit head: <code>{_text(integrity['audit_head'])}</code>. No external attestation, truth guarantee, or real-model advantage is implied. Private grading keys and source documents are not served. · <a href="/api/summary">Summary JSON</a></footer></main></body></html>'''


def make_handler(workspace: str | Path):
    ws = ResearchWorkspace(workspace)

    class Handler(BaseHTTPRequestHandler):
        def _response(self, *, head_only: bool = False):
            host = self.headers.get('Host','').split(':',1)[0].lower()
            if host not in ('localhost','127.0.0.1'):
                self.send_error(403, 'Local Host header required')
                return
            path = urlsplit(self.path).path
            if path not in ('/','/api/summary'):
                self.send_error(404)
                return
            try:
                overview = ws.overview()
                if path == '/api/summary':
                    data = json.dumps(overview,sort_keys=True,ensure_ascii=False).encode('utf-8')
                    content_type = 'application/json; charset=utf-8'
                else:
                    data = render_dashboard(overview).encode('utf-8')
                    content_type = 'text/html; charset=utf-8'
            except (PlatformError, OSError, ValueError):
                self.send_error(500, 'Workspace integrity check failed')
                return
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('X-Frame-Options','DENY')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
            self.end_headers()
            if not head_only:
                self.wfile.write(data)

        def do_GET(self):
            self._response()

        def do_HEAD(self):
            self._response(head_only=True)

        def do_POST(self):
            self.send_error(405, 'read-only dashboard')

        def log_message(self, fmt, *args):
            pass  # Avoid logging query strings and other private details.

    return Handler


def serve(workspace: str | Path, port: int = 8787):
    if not isinstance(port,int) or not 0 <= port <= 65535:
        raise PlatformError('port must be 0-65535')
    ws = ResearchWorkspace(workspace)
    ws.verify()
    return ThreadingHTTPServer(('127.0.0.1', port), make_handler(workspace))
