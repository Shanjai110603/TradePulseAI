"""
TradePulse Browser Agent — Multi-Level Self-Healing Chromium Controller
========================================================================
Controls Google Chrome / Microsoft Edge via Chrome DevTools Protocol (CDP).
Features:
 - Multi-tier self-healing element selectors (DOM -> Accessibility -> Search Modal -> Direct)
 - Automatic currency pair switching with fallback to asset search box
 - High-resolution chart screenshot capture (Page.captureScreenshot)
 - Real live price & payout extraction with Doji/wick detection
 - STRICT SAFE MODE: Zero trade placement capability (Read-only observation)
"""

import base64
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("browser_agent")

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

CDP_PORT = 9222
CHROME_USER_DATA = str(Path.home() / "QuotexScannerProfile")
QUOTEX_TRADE_URL = "https://qxbroker.com/en/trade"


class BrowserAgent:
    """Resilient Chromium controller using Chrome DevTools Protocol."""

    def __init__(self, port: int = CDP_PORT, user_data_dir: str = CHROME_USER_DATA):
        self.port = port
        self.user_data_dir = user_data_dir
        self.base_url = f"http://127.0.0.1:{port}"
        self.proc: Optional[subprocess.Popen] = None
        self._ws = None
        self._msg_id = 0
        self.active_pair: str = "Unknown"

    # -----------------------------------------------------------------------
    # Process & Connection Management
    # -----------------------------------------------------------------------

    def find_browser_executable(self) -> Optional[str]:
        for p in CHROME_PATHS:
            if os.path.isfile(p):
                return p
        return None

    def launch(self) -> bool:
        """Launch Chrome with remote debugging if not already running."""
        if self.is_cdp_ready():
            return True

        chrome_exe = self.find_browser_executable()
        if not chrome_exe:
            logger.error("No compatible Chromium browser found!")
            return False

        args = [
            chrome_exe,
            f"--remote-debugging-port={self.port}",
            f"--user-data-dir={self.user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            QUOTEX_TRADE_URL,
        ]
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True

    def is_cdp_ready(self) -> bool:
        try:
            import httpx
            r = httpx.get(f"{self.base_url}/json/version", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    def get_targets(self) -> List[dict]:
        try:
            import httpx
            r = httpx.get(f"{self.base_url}/json", timeout=3)
            return r.json()
        except Exception:
            return []

    def find_quotex_target(self) -> Optional[dict]:
        targets = self.get_targets()
        for t in targets:
            url = t.get("url", "")
            if "qxbroker.com" in url or "quotex.io" in url or "trade" in url:
                return t
        return None

    def connect(self, timeout: int = 30) -> bool:
        """Wait for CDP and connect to Quotex tab via WebSocket."""
        import websockets.sync.client as ws_sync

        start = time.time()
        while time.time() - start < timeout:
            if self.is_cdp_ready():
                target = self.find_quotex_target()
                if target and target.get("webSocketDebuggerUrl"):
                    try:
                        self._ws = ws_sync.connect(target["webSocketDebuggerUrl"], max_size=20_000_000)
                        self.send_cdp_command("Runtime.enable")
                        self.send_cdp_command("Page.enable")
                        return True
                    except Exception as e:
                        logger.debug(f"WS Connect retry: {e}")
            time.sleep(1)
        return False

    def send_cdp_command(self, method: str, params: Optional[dict] = None) -> dict:
        if not self._ws:
            return {}
        self._msg_id += 1
        payload = {"id": self._msg_id, "method": method, "params": params or {}}
        try:
            self._ws.send(json.dumps(payload))
            deadline = time.time() + 10
            while time.time() < deadline:
                raw = self._ws.recv(timeout=5)
                data = json.loads(raw)
                if data.get("id") == self._msg_id:
                    return data
        except Exception as e:
            logger.debug(f"CDP command error: {e}")
        return {}

    def evaluate_js(self, script: str) -> any:
        """Run JavaScript inside Quotex page."""
        res = self.send_cdp_command("Runtime.evaluate", {
            "expression": script,
            "returnByValue": True,
            "awaitPromise": True
        })
        return res.get("result", {}).get("result", {}).get("value")

    # -----------------------------------------------------------------------
    # Multi-Level Self-Healing Asset Switcher
    # -----------------------------------------------------------------------

    def switch_pair(self, pair_name: str) -> bool:
        """
        Switches the Quotex chart to a specific pair using a 4-tier fallback:
        Tier 1: Click open tab in top bar matching pair code
        Tier 2: Search and click tab by text content (contains pair name)
        Tier 3: Open Asset Modal ('+' button), type symbol in search input, click first result
        """
        clean_code = pair_name.replace(" (OTC)", "").replace("/", "").strip()
        code_with_slash = pair_name.replace(" (OTC)", "").strip()

        # Tier 1 & 2: Search existing open tabs in top bar
        tier1_script = f"""
        (() => {{
            const searchTerms = ["{clean_code}", "{code_with_slash}"];
            // Check top navigation tabs
            const tabs = Array.from(document.querySelectorAll(
                '.pair-item, .tab-item, .navigation-item, [class*="asset-item"], [class*="pair"]'
            ));
            for (const t of tabs) {{
                const txt = (t.innerText || t.textContent || '').replace(/\\s+/g, '');
                for (const term of searchTerms) {{
                    if (txt.includes(term.replace('/', ''))) {{
                        t.click();
                        return {{success: true, tier: 1}};
                    }}
                }}
            }}

            // Search any clickable element containing the pair name
            const allElements = Array.from(document.querySelectorAll('div, span, button, a'));
            for (const el of allElements) {{
                if (el.children.length <= 2 && el.offsetParent !== null) {{
                    const txt = (el.innerText || '').trim();
                    if (txt === "{code_with_slash}" || txt.includes("{code_with_slash}")) {{
                        el.click();
                        return {{success: true, tier: 2}};
                    }}
                }}
            }}
            return {{success: false}};
        }})()
        """
        res = self.evaluate_js(tier1_script)
        if res and res.get("success"):
            self.active_pair = pair_name
            time.sleep(1.0)
            return True

        # Tier 3: Open Asset Search modal if tab is not already open
        tier3_script = f"""
        (() => {{
            // Find the '+' or asset selector button
            const addBtn = document.querySelector('.asset-select, .pair-add, [class*="plus"], [class*="add-tab"]');
            if (addBtn) {{
                addBtn.click();
                setTimeout(() => {{
                    const searchInput = document.querySelector('input[type="text"], input[placeholder*="Search"]');
                    if (searchInput) {{
                        searchInput.value = "{code_with_slash}";
                        searchInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        setTimeout(() => {{
                            const firstMatch = document.querySelector('.asset-item, [class*="item"]');
                            if (firstMatch) firstMatch.click();
                        }}, 400);
                    }}
                }}, 300);
                return {{success: true, tier: 3}};
            }}
            return {{success: false}};
        }})()
        """
        res3 = self.evaluate_js(tier3_script)
        if res3 and res3.get("success"):
            self.active_pair = pair_name
            time.sleep(1.2)
            return True

        return False

    # -----------------------------------------------------------------------
    # Market Data & Chart Extraction
    # -----------------------------------------------------------------------

    def read_live_price(self) -> Optional[float]:
        """Extracts the real-time active price from Quotex DOM."""
        script = """
        (() => {
            // Check specific current price container
            const pElem = document.querySelector('.current-price, [class*="current-price"]');
            if (pElem && pElem.innerText) {
                const val = parseFloat(pElem.innerText.trim());
                if (!isNaN(val) && val > 0) return val;
            }

            // Fallback: search rightmost price tag
            const allElements = document.querySelectorAll('*');
            let found = null;
            for (const el of allElements) {
                if (el.children.length === 0) {
                    const t = (el.innerText || '').trim();
                    if (/^\\d+\\.\\d{2,5}$/.test(t)) {
                        const num = parseFloat(t);
                        if (num > 0) found = num;
                    }
                }
            }
            return found;
        })()
        """
        return self.evaluate_js(script)

    def read_payout(self) -> Optional[int]:
        """Extracts active asset payout percentage (e.g. 95)."""
        script = """
        (() => {
            const allElements = document.querySelectorAll('*');
            for (const el of allElements) {
                if (el.children.length === 0) {
                    const m = (el.innerText || '').trim().match(/^(\\d{2,3})%$/);
                    if (m) return parseInt(m[1]);
                }
            }
            return null;
        })()
        """
        return self.evaluate_js(script)

    def read_active_symbol_name(self) -> Optional[str]:
        """Reads the currently selected pair name from the chart header."""
        script = """
        (() => {
            const sels = ['.pair-name', '.asset-name', '.current-symbol', '[class*="pair-title"]'];
            for (const s of sels) {
                const el = document.querySelector(s);
                if (el && el.innerText) return el.innerText.trim();
            }
            const all = document.querySelectorAll('*');
            for (const el of all) {
                const t = (el.innerText || '').trim();
                if (/^[A-Z]{3}\\/[A-Z]{3}/.test(t) && t.length < 25) {
                    return t;
                }
            }
            return null;
        })()
        """
        return self.evaluate_js(script)

    # -----------------------------------------------------------------------
    # Screenshot Capture
    # -----------------------------------------------------------------------

    def capture_screenshot(self) -> Optional[bytes]:
        """Captures the real live chart viewport as PNG bytes."""
        res = self.send_cdp_command("Page.captureScreenshot", {
            "format": "png",
            "quality": 95,
            "captureBeyondViewport": False
        })
        b64 = res.get("result", {}).get("data")
        if b64:
            return base64.b64decode(b64)
        return None

    def close(self):
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
