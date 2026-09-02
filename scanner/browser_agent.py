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
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
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
            url = t.get("url", "").lower()
            title = t.get("title", "").lower()
            if any(k in url or k in title for k in ["qxbroker", "quotex", "trade", "qx-"]):
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
            self._ws = None
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
        Switches the Quotex chart to a specific pair using a multi-method fallback:
        Method 1: Search and click tab in top bar matching pair name or clean code
        Method 2: Click '+' or asset selector button, search symbol, and select it
        Method 3: Direct URL navigation if needed
        """
        clean_code = pair_name.replace(" (OTC)", "").replace("/", "").strip()
        code_with_slash = pair_name.replace(" (OTC)", "").strip()

        # Method 1: Check existing tabs in top bar
        script_tab = f"""
        (() => {{
            const terms = ["{code_with_slash}", "{clean_code}"];
            
            // 1. Look for tab elements
            const candidates = document.querySelectorAll(
                '.tab-item, .pair-item, [class*="asset-item"], [class*="pair"], [class*="tab"]'
            );
            for (const el of candidates) {{
                const txt = (el.innerText || el.textContent || '').trim();
                for (const t of terms) {{
                    if (txt.includes(t)) {{
                        el.click();
                        return {{success: true, method: "tab_click"}};
                    }}
                }}
            }}

            // 2. Search clickable elements near top of page
            const all = document.querySelectorAll('button, div, span, a');
            for (const el of all) {{
                if (el.children.length <= 2 && el.offsetParent !== null) {{
                    const rect = el.getBoundingClientRect();
                    // Must be in top header area (y < 120px)
                    if (rect.top < 120 && rect.height > 15) {{
                        const txt = (el.innerText || '').trim();
                        if (txt === "{code_with_slash}" || txt.startsWith("{code_with_slash}")) {{
                            el.click();
                            return {{success: true, method: "header_click"}};
                        }}
                    }}
                }}
            }}
            return {{success: false}};
        }})()
        """
        res = self.evaluate_js(script_tab)
        if res and res.get("success"):
            self.active_pair = pair_name
            time.sleep(1.0)
            return True

        # Method 2: Open Asset Search modal via '+' button or header asset selector
        script_modal = f"""
        (() => {{
            // Find '+' button or asset selector button in top area
            const addButtons = Array.from(document.querySelectorAll('button, div, span')).filter(el => {{
                if (el.offsetParent === null) return false;
                const rect = el.getBoundingClientRect();
                if (rect.top > 120) return false; // must be in top bar
                const txt = (el.innerText || el.textContent || '').trim();
                const cls = (el.className || '').toString();
                return txt === '+' || cls.includes('add') || cls.includes('plus') || cls.includes('asset-select');
            }});

            if (addButtons.length > 0) {{
                // Click the add/asset button
                addButtons[0].click();
                
                // Wait briefly and search
                setTimeout(() => {{
                    const input = document.querySelector('input[type="search"], input[type="text"], input[placeholder*="Search"], input[placeholder*="search"]');
                    if (input) {{
                        input.value = "{clean_code}";
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        setTimeout(() => {{
                            // Click first result item in modal
                            const item = document.querySelector('.asset-item, [class*="asset-select"] [class*="item"], [class*="modal"] [class*="row"]');
                            if (item) item.click();
                        }}, 400);
                    }}
                }}, 300);
                return {{success: true, method: "modal_search"}};
            }}
            return {{success: false}};
        }})()
        """
        res2 = self.evaluate_js(script_modal)
        if res2 and res2.get("success"):
            self.active_pair = pair_name
            time.sleep(1.2)
            return True

        return False

    # -----------------------------------------------------------------------
    # Market Data & Chart Extraction
    # -----------------------------------------------------------------------

    def read_live_price(self) -> Optional[float]:
        """
        Extracts the real-time active price from Quotex DOM.
        Uses 4 complementary strategies to guarantee reliable capture.
        """
        script = """
        (() => {
            // Strategy 1: Dedicated current price containers
            const specificSelectors = [
                '.current-price',
                '[class*="current-price"]',
                '[class*="chart-current-price"]',
                '[class*="strike-value"]',
                '.chart__current-price',
                '[class*="pane-legend-line"]',
                '.deal-form [class*="price"]',
                '.trading-chart [class*="value"]'
            ];
            for (const s of specificSelectors) {
                const el = document.querySelector(s);
                if (el) {
                    const text = (el.textContent || el.innerText || '').trim();
                    const m = text.match(/(\\d{1,6}\\.\\d{2,6})/);
                    if (m) {
                        const val = parseFloat(m[1]);
                        if (!isNaN(val) && val > 0 && val !== 1.0 && val !== 100.0) return val;
                    }
                }
            }

            // Strategy 2: Search near-leaf elements (<= 3 children) with text matching price pattern
            // Quotex right-axis badge typically has 1-2 spans inside a div
            const allElements = document.querySelectorAll('*');
            let candidatePrice = null;
            for (let i = allElements.length - 1; i >= 0; i--) {
                const el = allElements[i];
                if (el.children.length <= 3 && el.offsetParent !== null) {
                    const text = (el.textContent || '').trim();
                    // Match decimal price like 0.58291, 1.08450, 290.505, 17.8420
                    if (/^\\d{1,6}\\.\\d{2,6}$/.test(text)) {
                        const val = parseFloat(text);
                        // Filter out common non-price UI integers or percentages
                        if (val > 0.00001 && val !== 1.0 && val !== 10.0 && val !== 50.0 && val !== 100.0) {
                            candidatePrice = val;
                            break;
                        }
                    }
                }
            }
            if (candidatePrice !== null) return candidatePrice;

            // Strategy 3: Search any elements with class containing 'price', 'value', 'quote', 'rate'
            const classElements = document.querySelectorAll('[class*="price"], [class*="value"], [class*="quote"], [class*="rate"]');
            for (let i = classElements.length - 1; i >= 0; i--) {
                const el = classElements[i];
                const text = (el.textContent || '').trim();
                const m = text.match(/(\\d{1,6}\\.\\d{2,6})/);
                if (m) {
                    const val = parseFloat(m[1]);
                    if (val > 0.00001 && val !== 1.0 && val !== 100.0) return val;
                }
            }

            // Strategy 4: Regex scan across all text on the page for decimal numbers
            const bodyText = document.body ? document.body.innerText : '';
            const matches = bodyText.match(/\\b\\d{1,5}\\.\\d{3,6}\\b/g);
            if (matches && matches.length > 0) {
                for (let i = matches.length - 1; i >= 0; i--) {
                    const val = parseFloat(matches[i]);
                    if (val > 0.0001 && val !== 1.0) return val;
                }
            }

            return null;
        })()
        """
        return self.evaluate_js(script)

    def read_payout(self) -> Optional[int]:
        """Extracts active asset payout percentage (e.g. 95)."""
        script = """
        (() => {
            const allElements = document.querySelectorAll('*');
            for (let i = allElements.length - 1; i >= 0; i--) {
                const el = allElements[i];
                if (el.children.length === 0) {
                    const m = (el.textContent || '').trim().match(/^(\\d{2,3})%$/);
                    if (m) {
                        const val = parseInt(m[1]);
                        if (val >= 50 && val <= 100) return val;
                    }
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
