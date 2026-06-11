from http.server import BaseHTTPRequestHandler
import json
import os

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        result = {
            "engine": "anthropic",
            "serp_key_set": False,
            "anthropic_key_set": bool(anthropic_key),
        }
        self._respond(200, result)

    def do_OPTIONS(self):
        self._respond(200, {})

    def _respond(self, code, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
