#!/usr/bin/env python3
"""Local HTTP API for the BioPathway Explorer (standard library only).

    python3 scripts/bpm_api.py            # http://127.0.0.1:8790
    python3 scripts/bpm_api.py --port 9000 --offline

GET /api/health                      -> {"ok": true, "ops": [...]}
GET /api/<op>?param=value&genes=A,B  -> JSON from bpm.service (see /api/health)
Anything else is served from explorer/dist if it has been built, so one
command runs the whole Explorer.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bpm.http import HttpClient, SourceError  # noqa: E402
from bpm.service import Service  # noqa: E402

DIST = Path(__file__).resolve().parent.parent / "explorer" / "dist"


def make_handler(service: Service):
    class Handler(BaseHTTPRequestHandler):
        server_version = "BioPathwayAPI/2.0"

        def log_message(self, fmt, *args):  # quieter console
            sys.stderr.write("[api] " + fmt % args + "\n")

        def _send(self, status: int, body: bytes, ctype: str):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "http://localhost:5173")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, data):
            self._send(status, json.dumps(data, default=str).encode(), "application/json")

        def do_GET(self):
            url = urllib.parse.urlparse(self.path)
            if url.path.startswith("/api/"):
                op = url.path[5:].strip("/").replace("-", "_")
                params = {k: v[-1] for k, v in urllib.parse.parse_qs(url.query).items()}
                if op == "health":
                    return self._json(200, {"ok": True, "ops": sorted(service.ops()),
                                            "kegg": service.ctx.use_kegg, "offline": service.ctx.http.offline})
                try:
                    return self._json(200, service.call(op, params))
                except KeyError as exc:
                    return self._json(404, {"error": str(exc)})
                except ValueError as exc:
                    return self._json(400, {"error": str(exc)})
                except SourceError as exc:
                    return self._json(502, {"error": exc.message, "source": exc.source})
                except Exception as exc:  # report, don't crash the server
                    traceback.print_exc()
                    return self._json(500, {"error": f"{type(exc).__name__}: {exc}"})
            return self._static(url.path)

        def _static(self, path: str):
            if not DIST.exists():
                return self._send(404, b"Explorer not built. Run: cd explorer && npm install && npm run build",
                                  "text/plain")
            target = (DIST / path.lstrip("/")).resolve()
            if DIST.resolve() not in target.parents and target != DIST.resolve():
                return self._send(403, b"forbidden", "text/plain")
            if not target.is_file():
                target = DIST / "index.html"   # single-page app routing
            ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            return self._send(200, target.read_bytes(), ctype)

    return Handler


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="BioPathway Explorer API")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--offline", action="store_true", help="serve from cache only")
    ap.add_argument("--no-kegg", action="store_true", help="do not call KEGG (academic-use licence)")
    ap.add_argument("--taxid", type=int, default=9606)
    args = ap.parse_args(argv)
    service = Service(HttpClient(offline=args.offline), taxid=args.taxid, use_kegg=not args.no_kegg)
    httpd = ThreadingHTTPServer((args.host, args.port), make_handler(service))
    print(f"BioPathway API on http://{args.host}:{args.port}  (explorer: {'built' if DIST.exists() else 'not built'})",
          file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
