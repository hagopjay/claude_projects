"""Local HTTP server for the dashboard; data.json is rebuilt from the DB per request."""

from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .db import ProjectsDB
from .export import DASHBOARD_HTML, snapshot


def make_server(db: ProjectsDB, port: int = 0, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                self._send(200, "text/html; charset=utf-8", DASHBOARD_HTML.read_bytes())
            elif path == "/data.json":
                body = json.dumps(snapshot(db)).encode()
                self._send(200, "application/json", body)
            else:
                self._send(404, "text/plain", b"not found")

        def _send(self, status: int, ctype: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):  # keep the terminal quiet
            pass

    return ThreadingHTTPServer((host, port), Handler)


def serve(db: ProjectsDB, port: int = 0, open_browser: bool = True) -> None:
    httpd = make_server(db, port)
    url = f"http://{httpd.server_address[0]}:{httpd.server_address[1]}/"
    print(f"dashboard: {url}  (ctrl-c to stop)")
    if open_browser:
        threading.Timer(0.3, webbrowser.open, (url,)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
