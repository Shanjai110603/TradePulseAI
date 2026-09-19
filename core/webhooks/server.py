"""
TradePulse Local Webhook Relay Server
Listens on http://127.0.0.1:8765/webhook for incoming TradingView alerts and MetaTrader signals.
"""
import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from typing import Callable, Optional

from core.config import settings

logger = logging.getLogger(__name__)

MAX_WEBHOOK_BODY_BYTES = 65536  # 64 KB


class WebhookHandler(BaseHTTPRequestHandler):
    on_webhook_received: Optional[Callable[[dict], None]] = None

    def _check_token_match(self, token_candidate: Optional[str]) -> bool:
        configured_token = getattr(settings, "WEBHOOK_TOKEN", "") or ""
        if not configured_token:
            return True
        return bool(token_candidate and token_candidate.strip() == configured_token)

    def do_POST(self):
        from urllib.parse import urlparse, parse_qs
        parsed_url = urlparse(self.path)
        if parsed_url.path != "/webhook":
            self.send_response(404)
            self.end_headers()
            return

        configured_token = getattr(settings, "WEBHOOK_TOKEN", "") or ""

        # Check token in headers
        header_token = self.headers.get("X-Webhook-Token", "")
        if not header_token:
            auth_header = self.headers.get("Authorization", "")
            if auth_header.lower().startswith("bearer "):
                header_token = auth_header[7:].strip()

        # Check token in query params
        qs = parse_qs(parsed_url.query)
        query_token = (qs.get("token") or qs.get("key") or [None])[0]

        is_authed = False
        if not configured_token:
            is_authed = True
        elif header_token == configured_token or query_token == configured_token:
            is_authed = True

        # Enforce Request Size Limit (P1-4: 64 KB max)
        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except (ValueError, TypeError):
            content_length = 0

        if content_length > MAX_WEBHOOK_BODY_BYTES:
            try:
                remaining = content_length
                while remaining > 0:
                    chunk = self.rfile.read(min(remaining, 65536))
                    if not chunk:
                        break
                    remaining -= len(chunk)
            except Exception as e:
                logger.debug(f"[WEBHOOK] Exception while draining oversized body: {e}")

            self.send_response(413)
            self.send_header("Content-Type", "application/json")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "Payload Too Large: maximum body size is 64KB",
                "received_bytes": content_length,
                "limit_bytes": MAX_WEBHOOK_BODY_BYTES
            }).encode("utf-8"))
            return

        post_data = self.rfile.read(content_length)

        try:
            payload = json.loads(post_data.decode("utf-8"))
        except Exception as e:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Invalid JSON: {e}"}).encode("utf-8"))
            return

        # Check token in payload body if not already authed via headers/query
        if not is_authed and isinstance(payload, dict):
            body_token = str(payload.get("token") or payload.get("key") or "").strip()
            if body_token == configured_token:
                is_authed = True

        if not is_authed:
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Unauthorized: invalid or missing webhook token"}).encode("utf-8"))
            return

        logger.info(f"[WEBHOOK] Received external alert: {payload}")

        if WebhookHandler.on_webhook_received:
            try:
                WebhookHandler.on_webhook_received(payload)
            except Exception as e:
                logger.error(f"[WEBHOOK] Processing exception: {e}", exc_info=True)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "message": "Signal processed"}).encode("utf-8"))

    def do_GET(self):
        if self.path in ("/webhook", "/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "service": "TradePulse Webhook Relay",
                "status": "online",
                "endpoint": f"http://{self.server.server_address[0]}:{self.server.server_address[1]}/webhook"
            }).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress standard console noise
        pass


class WebhookServer:
    """Lightweight embedded HTTP server for receiving third-party webhook alerts."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765, on_signal_callback: Optional[Callable[[dict], None]] = None):
        self.host = host
        self.port = port
        self.on_signal = on_signal_callback
        self.server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        # Non-loopback security guard: refuse to bind to external interface without token
        configured_token = getattr(settings, "WEBHOOK_TOKEN", "") or ""
        is_loopback = self.host in ("127.0.0.1", "localhost", "::1")
        if not is_loopback and not configured_token:
            logger.error(
                f"[WEBHOOK SERVER] Refusing to bind to non-loopback host '{self.host}' "
                "without WEBHOOK_TOKEN configured in settings! Server startup aborted."
            )
            return

        WebhookHandler.on_webhook_received = self.on_signal
        try:
            self.server = HTTPServer((self.host, self.port), WebhookHandler)
            self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self._thread.start()
            if not configured_token:
                logger.warning(
                    f"[WEBHOOK SERVER] Online on http://{self.host}:{self.port}/webhook "
                    "(unauthenticated loopback mode; set WEBHOOK_TOKEN to require authorization)"
                )
            else:
                logger.info(f"[WEBHOOK SERVER] Online & authenticated on http://{self.host}:{self.port}/webhook")
        except Exception as e:
            logger.warning(f"[WEBHOOK SERVER] Could not start server on port {self.port}: {e}")

    def stop(self):
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception as e:
                logger.debug(f"[WEBHOOK SERVER] Shutdown error: {e}")
            logger.info("[WEBHOOK SERVER] Offline.")
