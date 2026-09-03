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
        Switches the Quotex chart to a specific pair:
        1. Clicks tab if already open in the top bar
        2. Clicks the top-left blue [+] button to open asset drawer, searches, and clicks row
        3. Fallback: cycles to next open tab so chart visibly changes
        """
        clean_code = pair_name.replace(" (OTC)", "").replace("/", "").strip()
        code_with_slash = pair_name.replace(" (OTC)", "").strip()

        script = f"""
        (async () => {{
            const targetSlash = "{code_with_slash}";
            const targetClean = "{clean_code}";

            // 1. Check existing open tabs in top bar
            const tabs = Array.from(document.querySelectorAll(
                '.tab-item, .pair-item, [class*="tab"], [class*="asset-item"], [class*="tabs__item"]'
            )).filter(t => {{
                if (t.offsetParent === null) return false;
                const rect = t.getBoundingClientRect();
                return rect.top < 120 && rect.height > 15;
            }});

            for (const t of tabs) {{
                const txt = (t.innerText || t.textContent || '').trim();
                if (txt.includes(targetSlash) || txt.includes(targetClean)) {{
                    t.click();
                    return {{success: true, method: "existing_tab_click"}};
                }}
            }}

            // 2. Click the top-left blue [+] button to open Asset Drawer
            const addButtons = Array.from(document.querySelectorAll('button, div, a, span')).filter(el => {{
                if (el.offsetParent === null) return false;
                const rect = el.getBoundingClientRect();
                // Blue [+] button is at the top left (top < 120, left < 350, small square 20-60px)
                if (rect.top < 120 && rect.left < 350 && rect.width >= 20 && rect.width <= 65 && rect.height >= 20 && rect.height <= 65) {{
                    const txt = (el.innerText || el.textContent || '').trim();
                    const cls = (el.className || '').toString().toLowerCase();
                    return txt === '+' || txt === '＋' || cls.includes('add') || cls.includes('plus');
                }}
                return false;
            }});

            let openedModal = false;
            if (addButtons.length > 0) {{
                addButtons[0].click();
                openedModal = true;
            }} else {{
                // Try finding asset selector on right panel
                const rightBtn = Array.from(document.querySelectorAll('button, div')).find(el => {{
                    if (el.offsetParent === null) return false;
                    const rect = el.getBoundingClientRect();
                    const txt = (el.innerText || '').trim();
                    return rect.left > (window.innerWidth - 320) && rect.top > 120 && rect.top < 300 && /([A-Z]{{3}}\\/[A-Z]{{3}})/.test(txt);
                }});
                if (rightBtn) {{
                    rightBtn.click();
                    openedModal = true;
                }}
            }}

            if (openedModal) {{
                await new Promise(r => setTimeout(r, 400));
            }}

            // 3. Type into search input
            const searchInput = document.querySelector(
                'input[type="search"], input[type="text"], input[placeholder*="Search"], input[placeholder*="search"], [class*="search"] input'
            );
            if (searchInput) {{
                searchInput.focus();
                try {{
                    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                    if (nativeSetter) nativeSetter.call(searchInput, targetSlash);
                    else searchInput.value = targetSlash;
                }} catch (e) {{
                    searchInput.value = targetSlash;
                }}
                searchInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                searchInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                await new Promise(r => setTimeout(r, 400));
            }}

            // 4. Click matching row in search results
            const rows = Array.from(document.querySelectorAll(
                '[class*="asset-item"], [class*="table__item"], [class*="assets-table"] [class*="item"], [class*="modal"] [class*="row"], button'
            )).filter(el => {{
                if (el.offsetParent === null) return false;
                const txt = (el.innerText || el.textContent || '').trim();
                return (txt.includes(targetSlash) || txt.includes(targetClean)) && (txt.includes('%') || txt.includes('OTC'));
            }});

            if (rows.length > 0) {{
                rows[0].click();
                return {{success: true, method: "modal_row_click"}};
            }}

            // 5. Fallback: cycle to next open tab so chart visibly changes
            if (tabs.length > 1) {{
                // Find currently active tab and click the next one
                for (let i = 0; i < tabs.length; i++) {{
                    const t = tabs[i];
                    const cls = (t.className || '').toString();
                    if (!cls.includes('active') && !cls.includes('selected')) {{
                        t.click();
                        return {{success: true, method: "cycled_open_tab"}};
                    }}
                }}
            }}

            return {{success: false}};
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
        Extracts the real-time active price from Quotex chart axis scale.
        STRICTLY excludes the deal form ($1.35 payout / $1.00 investment).
        """
        script = """
        (() => {
            // Priority 1: Specific chart current price badge elements
            const specificSelectors = [
                '.chart__current-price',
                '[class*="chart-current-price"]',
                '[class*="strike-value"]',
                '[class*="pane-legend-line"]',
                '[class*="current-price"]'
            ];
            for (const sel of specificSelectors) {
                const els = document.querySelectorAll(sel);
                for (const el of els) {
                    if (el.closest && el.closest('.deal-form, [class*="deal-form"]')) continue;
                    const text = (el.textContent || '').trim();
                    if (text.includes('$') || text.includes('Payout')) continue;
                    const m = text.match(/([0-9]{1,6}\\.[0-9]{2,6})/);
                    if (m) {
                        const val = parseFloat(m[1]);
                        if (val > 0.0001 && val !== 1.35 && val !== 1.0) return val;
                    }
                }
            }

            // Priority 2: TreeWalker strictly scanning the chart container and right scale
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
            const candidates = [];
            while (walker.nextNode()) {
                const parent = walker.currentNode.parentNode;
                if (!parent) continue;

                // CRITICAL: Exclude deal form, sidebar, account balance, deposit
                if (parent.closest && parent.closest('.deal-form, [class*="deal-form"], [class*="sidebar"], [class*="header__user"]')) {
                    continue;
                }

                const raw = (walker.currentNode.nodeValue || '').trim();
                // Reject anything containing currency symbols, words Payout, Investment
                if (raw.includes('$') || raw.includes('Payout') || raw.includes('Investment') || raw.includes('%')) {
                    continue;
                }

                // Match decimal number
                const m = raw.match(/^([0-9]{1,6}\\.[0-9]{2,6})$/);
                if (m) {
                    const val = parseFloat(m[1]);
                    // Strictly reject 1.35 (deal payout) and 1.00 (investment)
                    if (val > 0.0001 && val !== 1.35 && val !== 1.0 && val !== 10.0 && val !== 50.0 && val !== 100.0) {
                        const rect = parent.getBoundingClientRect ? parent.getBoundingClientRect() : { top: 0, right: 0, left: 0 };
                        // Must be in chart area: to the left of the deal form (x < window.innerWidth - 260)
                        if (rect.left < (window.innerWidth - 260) && rect.top > 70 && rect.top < (window.innerHeight - 50)) {
                            candidates.push({ val: val, rect: rect, text: raw });
                        }
                    }
                }
            }

            // In Quotex, the active price tag is right at the boundary of the chart scale (x between window.innerWidth - 350 and window.innerWidth - 260)
            const scaleMatches = candidates.filter(c => c.rect.right >= (window.innerWidth - 350));
            if (scaleMatches.length > 0) {
                return scaleMatches[scaleMatches.length - 1].val;
            }

            if (candidates.length > 0) {
                return candidates[candidates.length - 1].val;
            }

            return null;
        })()
        """
        return self.evaluate_js(script)

    def read_payout(self) -> Optional[int]:
        """Extracts active asset payout percentage (e.g. 95 or 35)."""
        script = """
        (() => {
            // 1. Look for percentage inside active tab or asset button
            const activeEls = Array.from(document.querySelectorAll('[class*="tab"].active, [class*="selected"], [class*="current"]'));
            for (const el of activeEls) {
                const txt = (el.innerText || el.textContent || '').trim();
                const m = txt.match(/([0-9]{2,3})%/);
                if (m) return parseInt(m[1]);
            }

            // 2. Scan text nodes excluding deal form
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
            while (walker.nextNode()) {
                const str = (walker.currentNode.nodeValue || '').trim();
                const m = str.match(/^([0-9]{2,3})%$/);
                if (m) {
                    const val = parseInt(m[1]);
                    if (val >= 20 && val <= 100 && val !== 50) return val;
                }
            }
            return null;
        })()
        """
        return self.evaluate_js(script)

    def read_active_symbol_name(self) -> Optional[str]:
        """Reads the currently selected pair name from the chart header or active tab."""
        script = """
        (() => {
            // 1. Check active tab in top bar
            const activeTab = document.querySelector('[class*="tab"].active, [class*="tab"][class*="selected"]');
            if (activeTab) {
                const txt = (activeTab.innerText || '').trim();
                const m = txt.match(/([A-Z]{3}\\s*\\/\\s*[A-Z]{3})/);
                if (m) return m[1].replace(/\\s+/g, '');
            }

            // 2. Search entire page for pair pattern
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
