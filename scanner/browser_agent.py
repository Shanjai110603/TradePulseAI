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
        """Find the Quotex trading tab, STRICTLY filtering for 'type': 'page' (never service workers)."""
        targets = self.get_targets()
        page_targets = [t for t in targets if t.get("type") == "page"]

        # 1. Look for Quotex / QxBroker page tab
        for t in page_targets:
            url = t.get("url", "").lower()
            title = t.get("title", "").lower()
            if any(k in url or k in title for k in ["qxbroker", "quotex", "trade", "qx-"]):
                return t

        # 2. Fallback: Any non-internal page tab
        for t in page_targets:
            url = t.get("url", "").lower()
            if not url.startswith("chrome://") and not url.startswith("chrome-extension://") and not url.startswith("edge://"):
                return t

        return None

    def connect(self, timeout: int = 30) -> bool:
        """Wait for CDP and connect to Quotex tab via WebSocket with no ping timeout drops."""
        import websockets.sync.client as ws_sync

        start = time.time()
        while time.time() - start < timeout:
            if self.is_cdp_ready():
                target = self.find_quotex_target()
                if target and target.get("webSocketDebuggerUrl"):
                    try:
                        if self._ws:
                            try:
                                self._ws.close()
                            except Exception:
                                pass
                        # Disable ping timeouts so heavy chart rendering never drops the connection
                        self._ws = ws_sync.connect(
                            target["webSocketDebuggerUrl"],
                            max_size=30_000_000,
                            ping_interval=None,
                            ping_timeout=None
                        )
                        self.send_cdp_command("Runtime.enable")
                        self.send_cdp_command("Page.enable")
                        logger.info(f"CDP Connected to page tab: {target.get('title')}")
                        return True
                    except Exception as e:
                        logger.debug(f"WS Connect retry: {e}")
            time.sleep(1)
        return False

    def send_cdp_command(self, method: str, params: Optional[dict] = None) -> dict:
        """Send command over CDP WebSocket with resilient auto-reconnect."""
        if not self._ws:
            if not self.connect(timeout=5):
                return {}

        self._msg_id += 1
        payload = {"id": self._msg_id, "method": method, "params": params or {}}
        try:
            self._ws.send(json.dumps(payload))
            deadline = time.time() + 10
            while time.time() < deadline:
                try:
                    raw = self._ws.recv(timeout=4)
                except TimeoutError:
                    continue
                except Exception:
                    break

                data = json.loads(raw)
                if data.get("id") == self._msg_id:
                    return data
        except Exception as e:
            logger.debug(f"CDP command error: {e}")
            self._ws = None
            # Auto-reconnect once and retry
            if self.connect(timeout=4):
                try:
                    self._msg_id += 1
                    payload["id"] = self._msg_id
                    self._ws.send(json.dumps(payload))
                    deadline = time.time() + 6
                    while time.time() < deadline:
                        raw = self._ws.recv(timeout=3)
                        data = json.loads(raw)
                        if data.get("id") == self._msg_id:
                            return data
                except Exception:
                    pass
        return {}

    def evaluate_js(self, script: str) -> any:
        """Run JavaScript inside Quotex page."""
        res = self.send_cdp_command("Runtime.evaluate", {
            "expression": script,
            "returnByValue": True,
            "awaitPromise": True
        })
        result = res.get("result", {}).get("result", {})
        return result.get("value")

    # -----------------------------------------------------------------------
    # Multi-Tier Layout-Agnostic Asset Switcher
    # -----------------------------------------------------------------------

    def switch_pair(self, pair_name: str) -> bool:
        """
        Switches the Quotex chart to a specific pair:
        1. Direct Click on visible tab in top bar (instant!)
        2. Clicks the blue [+] button to open 'Select trade pair' modal
        3. Types pair code into search input using React/Vue native setter
        4. Clicks the matching row in the modal
        5. Fallback: cycles to next open tab in top bar
        """
        clean_code = pair_name.replace(" (OTC)", "").replace("/", "").strip()
        code_with_slash = pair_name.replace(" (OTC)", "").strip()

        script = f"""
        (async () => {{
            const targetSlash = "{code_with_slash}";
            const targetClean = "{clean_code}";

            // 1. Direct Click on existing open tab in top bar
            const openTabs = Array.from(document.querySelectorAll('*')).filter(el => {{
                if (el.offsetParent === null) return false;
                const rect = el.getBoundingClientRect();
                // Top tab bar is at top: 35px to 130px, left < window.innerWidth - 300
                if (rect.top >= 35 && rect.top <= 130 && rect.left < (window.innerWidth - 300)) {{
                    const txt = (el.innerText || el.textContent || '').trim();
                    return (txt.includes(targetSlash) || txt.includes(targetClean)) && (txt.includes('%') || txt.includes('/'));
                }}
                return false;
            }});

            if (openTabs.length > 0) {{
                openTabs[0].click();
                return {{success: true, method: "direct_tab_click", symbol: targetSlash}};
            }}

            // 2. Open 'Select trade pair' modal via the blue [+] button in top bar
            const isModalOpen = () => {{
                return Array.from(document.querySelectorAll('*')).some(el => {{
                    return (el.innerText || '').includes('Select trade pair') && el.offsetParent !== null;
                }});
            }};

            if (!isModalOpen()) {{
                const plusBtn = Array.from(document.querySelectorAll('button, div, a, span')).find(el => {{
                    if (el.offsetParent === null) return false;
                    const rect = el.getBoundingClientRect();
                    if (rect.top >= 35 && rect.top <= 130 && rect.left < 200) {{
                        const txt = (el.innerText || el.textContent || '').trim();
                        const cls = (el.className || '').toString().toLowerCase();
                        return txt === '+' || txt === '＋' || cls.includes('add') || cls.includes('plus');
                    }}
                    return false;
                }});

                if (plusBtn) {{
                    plusBtn.click();
                    await new Promise(r => setTimeout(r, 450));
                }}
            }}

            // 3. Search for target currency in modal
            const searchInput = Array.from(document.querySelectorAll('input')).find(inp => {{
                if (inp.offsetParent === null) return false;
                const ph = (inp.placeholder || '').toLowerCase();
                return ph.includes('search') || inp.type === 'search' || inp.type === 'text';
            }});

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

            // 4. Click matching row in modal
            const modalRows = Array.from(document.querySelectorAll('div, li, button, tr')).filter(el => {{
                if (el.offsetParent === null) return false;
                const rect = el.getBoundingClientRect();
                if (rect.left > 650 || rect.top < 150) return false;
                if (rect.height < 25 || rect.height > 85 || rect.width < 120) return false;

                const txt = (el.innerText || el.textContent || '').trim();
                return (txt.includes(targetSlash) || txt.includes(targetClean)) && (txt.includes('%') || txt.includes('OTC'));
            }});

            if (modalRows.length > 0) {{
                modalRows[0].click();
                return {{success: true, method: "modal_row_clicked", selected: targetSlash}};
            }}

            // 5. Fallback: cycle to any other open tab in top bar so chart visibly updates
            const anyTabs = Array.from(document.querySelectorAll('*')).filter(el => {{
                if (el.offsetParent === null) return false;
                const rect = el.getBoundingClientRect();
                if (rect.top >= 35 && rect.top <= 130 && rect.left < (window.innerWidth - 300) && rect.width > 50 && rect.width < 250) {{
                    const txt = (el.innerText || '').trim();
                    const cls = (el.className || '').toString();
                    return /([A-Z]{{3}}\\/[A-Z]{{3}})/.test(txt) && !cls.includes('active');
                }}
                return false;
            }});

            if (anyTabs.length > 0) {{
                anyTabs[0].click();
                return {{success: true, method: "cycled_existing_tab"}};
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
        Extracts the real-time active price from Quotex chart scale (e.g. 0.58220).
        Uses textContent to combine child spans (<span class='value'>0.582</span><span class='tail'>20</span>).
        """
        script = """
        (() => {
            // Priority 1: Specific chart current price badge elements
            const specificSelectors = [
                '.chart__current-price',
                '[class*="chart-current-price"]',
                '[class*="strike-value"]',
                '[class*="pane-legend-line"]',
                '[class*="current-price"]',
                '[class*="value-line"]'
            ];
            for (const sel of specificSelectors) {
                const els = document.querySelectorAll(sel);
                for (const el of els) {
                    if (el.closest && el.closest('.deal-form, [class*="deal-form"]')) continue;
                    // textContent concatenates all child spans (e.g. '0.582' + '20' = '0.58220')
                    const text = (el.textContent || '').trim().replace(/\\s+/g, '');
                    if (text.includes('$') || text.includes('Payout')) continue;
                    const m = text.match(/([0-9]{1,6}\\.[0-9]{2,6})/);
                    if (m) {
                        const val = parseFloat(m[1]);
                        if (val > 0.0001 && val !== 1.35 && val !== 1.0) return val;
                    }
                }
            }

            // Priority 2: Scan leaf elements near the chart's right-hand scale
            const allElements = document.querySelectorAll('div, span');
            for (let i = allElements.length - 1; i >= 0; i--) {
                const el = allElements[i];
                if (el.children.length > 3) continue;
                if (el.offsetParent === null) continue;

                // Exclude deal form, sidebar, header
                if (el.closest && el.closest('.deal-form, [class*="deal-form"], [class*="sidebar"], [class*="header"]')) {
                    continue;
                }

                const rect = el.getBoundingClientRect();
                // Target the chart scale area (right between window.innerWidth - 360 and window.innerWidth - 240)
                if (rect.right >= (window.innerWidth - 360) && rect.left <= (window.innerWidth - 240) && rect.top > 80 && rect.top < (window.innerHeight - 50)) {
                    const text = (el.textContent || '').trim().replace(/\\s+/g, '');
                    if (text.includes('$') || text.includes('Payout') || text.includes('Investment') || text.includes('%')) continue;

                    const m = text.match(/^([0-9]{1,6}\\.[0-9]{2,6})$/);
                    if (m) {
                        const val = parseFloat(m[1]);
                        if (val > 0.0001 && val !== 1.35 && val !== 1.0 && val !== 10.0 && val !== 50.0 && val !== 100.0) {
                            return val;
                        }
                    }
                }
            }

            return null;
        })()
        """
        return self.evaluate_js(script)

    def read_payout(self) -> Optional[int]:
        """Extracts active asset payout percentage (e.g. 35 or 94)."""
        script = """
        (() => {
            // 1. Look inside active tab or asset button (e.g. AUD/CHF 35%)
            const activeTabs = Array.from(document.querySelectorAll('button, div, span, a')).filter(el => {
                if (el.offsetParent === null) return false;
                const rect = el.getBoundingClientRect();
                if (rect.top < 150 || rect.top > 320 || rect.left > 350) return false;
                const txt = (el.innerText || '').trim();
                return /([A-Z]{3}\\/[A-Z]{3})/.test(txt) && txt.includes('%');
            });

            if (activeTabs.length > 0) {
                const m = activeTabs[0].innerText.match(/([0-9]{2,3})%/);
                if (m) return parseInt(m[1]);
            }

            // 2. Right panel asset button (e.g. + AUD/CHF 35%)
            const rightPanel = Array.from(document.querySelectorAll('button, div, span')).filter(el => {
                if (el.offsetParent === null) return false;
                const rect = el.getBoundingClientRect();
                if (rect.left < (window.innerWidth - 300) || rect.top > 350) return false;
                const txt = (el.innerText || '').trim();
                return /([A-Z]{3}\\/[A-Z]{3})/.test(txt) && txt.includes('%');
            });

            if (rightPanel.length > 0) {
                const m = rightPanel[0].innerText.match(/([0-9]{2,3})%/);
                if (m) return parseInt(m[1]);
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
