# Pixel OS — Copyright 2026
# Free License — Verifiable and Reliable for Internet Users
# Pixel Software Design — Copyright 2026
#!/usr/bin/env python3
"""NOP Desktop Bridge â€” Connects the Qt browser to NOP core modules.

Provides a standalone server mode so that mobile/remote WebViews
can also use the NOP resolution, privacy, and wallet services.
"""

import sys
import os
import json
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from core.browser.nop_resolver import NOPResolver
from core.browser.nop_privacy import NOPPrivacy
from core.browser.nop_wallet_bridge import NOPWalletBridge


class NOPBridgeHandler(BaseHTTPRequestHandler):
    """HTTP handler for the bridge server."""

    resolver = NOPResolver()
    privacy = NOPPrivacy()
    wallet = NOPWalletBridge()

    def log_message(self, fmt, *args):
        pass

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self._send_json({})

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/resolve":
            url = params.get("url", [""])[0]
            self._send_json(self.resolver.resolve(url))

        elif path == "/check_url":
            url = params.get("url", [""])[0]
            blocked, rule = self.privacy.is_blocked(url)
            self._send_json({"blocked": blocked, "rule": rule if blocked else None})

        elif path == "/privacy/stats":
            self._send_json(self.privacy.stats())

        elif path == "/wallet/status":
            self._send_json({"available": self.wallet.is_available()})

        elif path == "/wallet/balance":
            addr = params.get("address", [None])[0]
            self._send_json(self.wallet.get_balance(addr))

        elif path == "/supported_domains":
            self._send_json({"domains": self.resolver.supported_domains()})

        elif path == "/stats":
            self._send_json({
                "resolver_cache": len(self.resolver.cache),
                "ad_domains": len(self.privacy.ad_domains),
                "tracker_domains": len(self.privacy.tracker_domains),
                "wallet_available": self.wallet.is_available(),
            })

        else:
            self._send_json({"error": "unknown"}, 404)

    def do_POST(self):
        from urllib.parse import urlparse
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        path = urlparse(self.path).path

        if path == "/resolve":
            url = body.get("url", "")
            self._send_json(self.resolver.resolve(url))

        elif path == "/sign_tx":
            self._send_json(self.wallet.sign_transaction(body))

        elif path == "/clear_cache":
            self._send_json(self.resolver.clear_cache())

        elif path == "/update_blocklists":
            self._send_json(self.privacy.update_lists())

        else:
            self._send_json({"error": "unknown"}, 404)


class NOPBridgeServer:
    """Run the bridge server in a background thread."""

    def __init__(self, host="127.0.0.1", port=9876):
        self.host = host
        self.port = port
        self._server = None
        self._thread = None

    def start(self):
        self._server = HTTPServer((self.host, self.port), NOPBridgeHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self.port

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server = None


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9876
    server = NOPBridgeServer(port=port)
    p = server.start()
    print(f"NOP Bridge running on http://127.0.0.1:{p}")
    print("Endpoints: /resolve /check_url /privacy/stats /wallet/status /wallet/balance /sign_tx /clear_cache /update_blocklists /stats")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        server.stop()
        print("Stopped")
