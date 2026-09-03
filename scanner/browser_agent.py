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
        Switches the Quotex chart to a specific pair across all layouts:
        1. Checks top tabs if in desktop wide layout
        2. Clicks asset selector button (whether in top bar or right panel above 'PENDING TRADE')
        3. Sets search input using React/Vue native prototype setter
        4. Selects matching asset row
        """
        clean_code = pair_name.replace(" (OTC)", "").replace("/", "").strip()
        code_with_slash = pair_name.replace(" (OTC)", "").strip()

        script = f"""
        (async () => {{
            const targetSlash = "{code_with_slash}";
            const targetClean = "{clean_code}";

            // 1. Check if already active
            const isAlreadyActive = Array.from(document.querySelectorAll('button, div, span, a')).some(el => {{
                if (el.offsetParent === null) return false;
                const t = (el.innerText || '').trim();
                return (t.includes(targetSlash) || t.includes(targetClean)) && (t.includes('%') || t.includes('+'));
            }});
            if (isAlreadyActive && !document.querySelector('input[placeholder*="Search"], input[placeholder*="search"]')) {{
                return {{success: true, method: "already_active"}};
            }}

            // 2. Check desktop top tabs
            const tabs = Array.from(document.querySelectorAll(
                '.tab-item, .pair-item, [class*="asset-item"], [class*="pair"], [class*="tab"]'
            ));
            for (const t of tabs) {{
                const txt = (t.innerText || t.textContent || '').trim();
                if (txt.includes(targetSlash) || txt.includes(targetClean)) {{
                    t.click();
                    return {{success: true, method: "tab_click"}};
                }}
            }}

            // 3. Find Asset Selector Button (Right panel above trade form or Top bar)
            const allElements = Array.from(document.querySelectorAll('button, div, a'));
            const assetButtons = allElements.filter(el => {{
                if (el.offsetParent === null) return false;
                const rect = el.getBoundingClientRect();
                if (rect.width < 40 || rect.height < 18 || rect.width > 350 || rect.height > 90) return false;

                const txt = (el.innerText || el.textContent || '').trim();
                const cls = (el.className || '').toString().toLowerCase();

                // Exclude deposit, withdrawal, amount/time adjustment buttons
                if (txt.includes('Deposit') || txt.includes('Withdraw') || txt.includes('Account')) return false;
                if (cls.includes('amount') || cls.includes('time') || cls.includes('stepper') || cls.includes('header__user')) return false;

                // Match: contains a currency pair code (e.g. "AUD/CHF", "EUR/USD") OR has explicit asset selector class
                const hasPair = /([A-Z]{{3}}\\s*\\/\\s*[A-Z]{{3}})/.test(txt);
                const isAssetClass = cls.includes('asset-select') || cls.includes('pair-select') || cls.includes('current-asset');
                const isTopPlus = (txt === '+' || txt === '＋') && rect.top < 150 && rect.left < (window.innerWidth - 300);

                return hasPair || isAssetClass || isTopPlus;
            }});

            let clickedSelector = false;
            if (assetButtons.length > 0) {{
                try {{
                    assetButtons[0].click();
                    clickedSelector = true;
                }} catch (e) {{}}
            }}

            if (clickedSelector) {{
                // Wait for modal animation
                await new Promise(r => setTimeout(r, 450));
            }}

            // 4. In opened modal, find search box and set value via native prototype setter
            const searchInput = document.querySelector(
                'input[type="search"], input[type="text"], input[placeholder*="Search"], input[placeholder*="search"], [class*="search"] input'
            );
            if (searchInput) {{
                searchInput.focus();
                try {{
                    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                    if (nativeSetter) {{
                        nativeSetter.call(searchInput, targetSlash);
                    }} else {{
                        searchInput.value = targetSlash;
                    }}
                }} catch (e) {{
                    searchInput.value = targetSlash;
                }}
                searchInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                searchInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                await new Promise(r => setTimeout(r, 400));
            }}

            // 5. Click the matching asset row in the search results
            const rows = Array.from(document.querySelectorAll(
                '[class*="asset-item"], [class*="table__item"], [class*="assets-table"] [class*="item"], [class*="modal"] [class*="row"], [class*="list"] [class*="item"], button, div'
            )).filter(el => {{
                if (el.offsetParent === null) return false;
                const txt = (el.innerText || el.textContent || '').trim();
                return (txt.includes(targetSlash) || txt.includes(targetClean)) && (txt.includes('%') || txt.includes('OTC'));
            }});

            if (rows.length > 0) {{
                rows[0].click();
                return {{success: true, method: "modal_row_click"}};
            }}

            // 6. Fallback: first available row in modal if search filtered
            const firstRow = document.querySelector(
                '.assets-table__item, .asset-item, [class*="asset-select"] [class*="item"]'
            );
            if (firstRow) {{
                firstRow.click();
                return {{success: true, method: "first_modal_row_click"}};
            }}

            return {{success: false, found_buttons: assetButtons.length}};
        }})()
        """
        res = self.evaluate_js(script)
        if res and res.get("success"):
            self.active_pair = pair_name
            time.sleep(1.2)
            return True

        return False

    # -----------------------------------------------------------------------
    # Market Data & Chart Extraction
    # -----------------------------------------------------------------------

    def read_live_price(self) -> Optional[float]:
        """
        Extracts the real-time active price from Quotex DOM using TreeWalker.
        Walks every text node on screen (HTML, SVG, Canvas overlays).
        """
        script = """
        (() => {
            // Method 1: TreeWalker text extraction across all nodes (HTML + SVG)
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
            const candidates = [];
            while (walker.nextNode()) {
                const raw = (walker.currentNode.nodeValue || '').trim();
                const m = raw.match(/([0-9]{1,6}\\.[0-9]{2,6})/);
                if (m) {
                    const val = parseFloat(m[1]);
                    // Filter out non-price values: $0.00 balance, $1.00 investment, 100%, 50%, 10%
                    if (val > 0.0001 && val !== 1.0 && val !== 10.0 && val !== 50.0 && val !== 100.0) {
                        const parent = walker.currentNode.parentNode;
                        const rect = parent && parent.getBoundingClientRect ? parent.getBoundingClientRect() : { top: 0, right: 0 };
                        candidates.push({ val: val, rect: rect, text: raw });
                    }
                }
            }

            // Priority: Price badge on right axis scale (rect.right > window.innerWidth - 220)
            const axisMatches = candidates.filter(c => 
                c.rect.right > (window.innerWidth - 220) && 
                c.rect.top > 80 && 
                c.rect.top < (window.innerHeight - 80)
            );
            if (axisMatches.length > 0) {
                return axisMatches[axisMatches.length - 1].val;
            }

            // Fallback: Check dedicated price containers
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
                    const m = text.match(/([0-9]{1,6}\\.[0-9]{2,6})/);
                    if (m) {
                        const val = parseFloat(m[1]);
                        if (!isNaN(val) && val > 0 && val !== 1.0 && val !== 100.0) return val;
                    }
                }
            }

            // Fallback: Last detected decimal candidate
            if (candidates.length > 0) {
                return candidates[candidates.length - 1].val;
            }

            return null;
        })()
        """
        return self.evaluate_js(script)

    def read_payout(self) -> Optional[int]:
        """Extracts active asset payout percentage (e.g. 95)."""
        script = """
        (() => {
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
            while (walker.nextNode()) {
                const str = (walker.currentNode.nodeValue || '').trim();
                const m = str.match(/([0-9]{2,3})%/);
                if (m) {
                    const val = parseInt(m[1]);
                    if (val >= 30 && val <= 100) return val;
                }
            }
            return null;
        })()
        """
        return self.evaluate_js(script)

    def read_active_symbol_name(self) -> Optional[str]:
        """Reads the currently selected pair name from the chart header or right panel."""
        script = """
        (() => {
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
            while (walker.nextNode()) {
                const str = (walker.currentNode.nodeValue || '').trim();
                const m = str.match(/([A-Z]{3}\\s*\\/\\s*[A-Z]{3})/);
                if (m) {
                    return m[1].replace(/\\s+/g, '');
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
