#!/usr/bin/env python3
"""LOCAL TEST TOOLING ONLY - never deployed.

Bridges the ActorBase service's Gemini client to the user's connected
Gemini API through the custom.gemini connector credential flow
(dynamic_credentials surrogate swap to
generativelanguage.googleapis.com), so the local proof battery runs
the service's unmodified pipeline code against the real engine.

The deployed service calls the same REST endpoint directly with the
owner's GEMINI_API_KEY in its environment (the lane's standard key
step, as on SwiftRewrite and SwiftTranslate). The bridge listens on
127.0.0.1 only, forwards request bodies unchanged, and returns the
upstream response verbatim. It reads no key and prints none.

Run: python3 connector_bridge.py [port]   (default 8899)
Then start actorbase/app.py with:
  GEMINI_API_KEY=local-bridge (any non-empty placeholder)
  GEMINI_BASE_URL=http://127.0.0.1:8899/v1beta
"""
import json
import sys
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import add_surrogate_to_request, read_json_response

HOST = "generativelanguage.googleapis.com"
CONNECTOR = "custom.gemini"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise RuntimeError("redirect refused")


class Bridge(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length)
        url = f"https://{HOST}{self.path}"
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json"})
        add_surrogate_to_request(req, CONNECTOR, allowed_hosts=[HOST])
        try:
            with urllib.request.build_opener(NoRedirect()).open(
                    req, timeout=180) as resp:
                payload = json.dumps(read_json_response(resp)).encode()
                status = resp.status
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            status = exc.code
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    ThreadingHTTPServer(("127.0.0.1", port), Bridge).serve_forever()
