#!/usr/bin/env python3
"""NOP Mobile Bridge — Common API for Android & iOS WebView wrappers.

This module provides a JSON-over-HTTP bridge that mobile WebView apps
can call to resolve Web3 domains, check ad/tracker blocks, and sign
transactions.  The mobile app runs a local Flask server on a random port
and the native WebView communicates with it via JavaScript injection.
"""

import sys
import os
import json
import urllib.request
import urllib.parse
import socket
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from core.browser.nop_resolver import NOPResolver
from core.browser.nop_privacy import NOPPrivacy
from core.browser.nop_wallet_bridge import NOPWalletBridge


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class NOPMobileBridge:
    def __init__(self):
        self.resolver = NOPResolver()
        self.privacy = NOPPrivacy()
        self.wallet = NOPWalletBridge()
        self._server = None
        self._thread = None
        self.port = find_free_port()

    def serve(self):
        handler = self._make_handler()
        self._server = HTTPServer(("127.0.0.1", self.port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self.port

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server = None

    def _make_handler(self):
        bridge = self

        class NOPHandler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                pass

            def _send(self, data, status=200):
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())

            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                path = parsed.path
                params = urllib.parse.parse_qs(parsed.query)

                if path == "/resolve":
                    url = params.get("url", [""])[0]
                    self._send(bridge.resolver.resolve(url))

                elif path == "/check_url":
                    url = params.get("url", [""])[0]
                    blocked, rule = bridge.privacy.is_blocked(url)
                    self._send({"blocked": blocked, "rule": rule if blocked else None})

                elif path == "/privacy/stats":
                    self._send(bridge.privacy.stats())

                elif path == "/wallet/status":
                    self._send({"available": bridge.wallet.is_available()})

                elif path == "/wallet/balance":
                    addr = params.get("address", [None])[0]
                    self._send(bridge.wallet.get_balance(addr))

                elif path == "/supported_domains":
                    self._send({"domains": bridge.resolver.supported_domains()})

                elif path == "/stats":
                    self._send({
                        "resolver_cache": len(bridge.resolver.cache),
                        "ad_domains": len(bridge.privacy.ad_domains),
                        "tracker_domains": len(bridge.privacy.tracker_domains),
                        "wallet_available": bridge.wallet.is_available(),
                    })

                else:
                    self._send({"error": "unknown endpoint"}, 404)

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length)) if length else {}
                path = urllib.parse.urlparse(self.path).path

                if path == "/resolve":
                    url = body.get("url", "")
                    self._send(bridge.resolver.resolve(url))

                elif path == "/check_url":
                    url = body.get("url", "")
                    blocked, rule = bridge.privacy.is_blocked(url)
                    self._send({"blocked": blocked, "rule": rule if blocked else None})

                elif path == "/sign_tx":
                    self._send(bridge.wallet.sign_transaction(body))

                elif path == "/clear_cache":
                    self._send(bridge.resolver.clear_cache())

                elif path == "/update_blocklists":
                    self._send(bridge.privacy.update_lists())

                else:
                    self._send({"error": "unknown endpoint"}, 404)

        return NOPHandler


# ═══════════════════════════════════════════════════════════
#  JavaScript injection snippet for mobile WebViews
# ═══════════════════════════════════════════════════════════

def get_injection_js(port: int) -> str:
    return f"""
(function() {{
    const NOP_API = 'http://127.0.0.1:{port}';

    window.NOP = {{
        resolve: async (url) => {{
            const r = await fetch(NOP_API + '/resolve?url=' + encodeURIComponent(url));
            return r.json();
        }},
        checkUrl: async (url) => {{
            const r = await fetch(NOP_API + '/check_url?url=' + encodeURIComponent(url));
            return r.json();
        }},
        signTx: async (tx) => {{
            const r = await fetch(NOP_API + '/sign_tx', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify(tx)
            }});
            return r.json();
        }},
        walletStatus: async () => {{
            const r = await fetch(NOP_API + '/wallet/status');
            return r.json();
        }},
        walletBalance: async (addr) => {{
            const q = addr ? '?address=' + addr : '';
            const r = await fetch(NOP_API + '/wallet/balance' + q);
            return r.json();
        }},
        stats: async () => {{
            const r = await fetch(NOP_API + '/stats');
            return r.json();
        }},
        clearCache: async () => {{
            const r = await fetch(NOP_API + '/clear_cache', {{method: 'POST'}});
            return r.json();
        }}
    }};

    console.log('[NOP Bridge] Initialized on port {port}');
}})();
"""
