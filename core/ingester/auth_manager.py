"""
TradePulse Frictionless Authentication & Session Manager
Handles in-app embedded OS Webview login (Email/Password or 1-click Google OAuth),
native cookie extraction on /trade navigation, and machine-keyed session caching.
"""
import json
import logging
import os
import threading
import time
from typing import Any, Dict, Optional

from core.config import settings
from core.security import load_encrypted_session, save_encrypted_session

logger = logging.getLogger(__name__)

QUOTEX_DEFAULT_MIRROR = "https://qxbroker.com"
QUOTEX_SIGNIN_URL = "https://qxbroker.com/en/sign-in"
QUOTEX_TRADE_URL = "https://qxbroker.com/en/trade"

STREAM_INJECTION_JS = r"""
(() => {
    // Persistent state container on window
    window.__tp_state = window.__tp_state || {
        initialized: false,
        workerHooked: false,
        wsHooked: false,
        canvasHooked: false,
        lastActiveSym: null,
        lastActivePrice: null,
        lastCanvasPrice: null,
        lastCanvasPriceTs: 0,
        lastPayoutCount: 0,
        lastReportTs: 0,
        frameLoggedCount: 0
    };

    const state = window.__tp_state;

    const OTC_ASSETS = [
        // OTC Currencies
        "USDINR_otc", "BRLUSD_otc", "USDPKR_otc", "USDBDT_otc", "USDMXN_otc", "USDZAR_otc",
        "USDIDR_otc", "USDDZD_otc", "USDNGN_otc", "USDEGP_otc", "USDARS_otc", "USDCOP_otc",
        "USDPHP_otc", "EURUSD_otc", "GBPUSD_otc", "GBPNZD_otc", "USDJPY_otc", "USDCHF_otc",
        "USDCAD_otc", "AUDUSD_otc", "NZDUSD_otc", "EURGBP_otc", "EURJPY_otc", "EURNZD_otc",
        "EURAUD_otc", "EURCAD_otc", "EURCHF_otc", "GBPJPY_otc", "GBPAUD_otc", "GBPCAD_otc",
        "GBPCHF_otc", "AUDCAD_otc", "AUDCHF_otc", "AUDJPY_otc", "AUDNZD_otc", "CADCHF_otc",
        "CADJPY_otc", "CHFJPY_otc", "NZDJPY_otc", "NZDCAD_otc", "NZDCHF_otc",
        // OTC Commodities
        "UKBrent_otc", "USCrude_otc", "XAUUSD_otc", "XAGUSD_otc", "XNGUSD_otc",
        // OTC Crypto
        "BTCUSD_otc", "ETHUSD_otc", "ATOUSD_otc", "LTCUSD_otc", "XRPUSD_otc", "LINKUSD_otc",
        "AVAXUSD_otc", "ETCUSD_otc", "TONUSD_otc", "TRUMPUSD_otc", "ZECUSD_otc",
        "BCHUSD_otc", "BNBUSD_otc", "DOTUSD_otc", "AXSUSD_otc", "DASHUSD_otc", "SOLUSD_otc"
    ];
    const REAL_FOREX_ASSETS = [
        "EURUSD", "GBPUSD", "USDJPY", "USDCAD", "USDCHF", "AUDUSD", "NZDUSD",
        "CADJPY", "GBPJPY", "EURJPY", "AUDJPY", "CHFJPY", "EURCHF", "EURGBP",
        "EURAUD", "EURCAD", "EURNZD", "GBPAUD", "GBPCAD", "GBPCHF", "GBPNZD",
        "AUDCAD", "AUDCHF", "AUDNZD", "CADCHF", "NZDCAD", "NZDCHF", "NZDJPY",
        "XAUUSD", "XAGUSD",
        // Live Stocks and Indices
        "CAC40", "ASX200", "FTSEChinaA50", "FTSE100", "HongKong50", "IBEX35", "Nikkei225", "STOXX50"
    ];
    const SUBSCRIBED_ASSETS = new Set(OTC_ASSETS.concat(REAL_FOREX_ASSETS));

    function postToHost(msg) {
        try {
            if (window.chrome && window.chrome.webview && window.chrome.webview.postMessage) {
                window.chrome.webview.postMessage(msg);
            } else if (window.pywebview && window.pywebview.api) {
                if (msg.type === 'frame' && window.pywebview.api.on_broker_frame) {
                    window.pywebview.api.on_broker_frame(msg.data);
                } else if (msg.type === 'session' && window.pywebview.api.on_broker_session) {
                    window.pywebview.api.on_broker_session(msg.token);
                } else if (msg.type === 'payouts' && window.pywebview.api.on_broker_payouts) {
                    window.pywebview.api.on_broker_payouts(msg.data);
                } else if (msg.type === 'instruments' && window.pywebview.api.on_broker_instruments) {
                    window.pywebview.api.on_broker_instruments(msg.data);
                } else if (msg.type === 'tick' && window.pywebview.api.on_broker_tick) {
                    window.pywebview.api.on_broker_tick(msg.symbol, msg.price, msg.source || 'unknown');
                }
            }
        } catch(err) {}
    }

    function logTele(text) {
        try { postToHost({ type: 'telemetry', text: text }); } catch(e) {}
    }

    // Diagnostic Probe (empirically logs window and state properties)
    if (!state.diagLogged) {
        state.diagLogged = true;
        try {
            const winKeys = Object.keys(window).filter(k => {
                try { return window[k] && typeof window[k] === 'object'; } catch(e) { return false; }
            }).slice(0, 30).join(",");
            logTele("WINDOW KEYS: " + winKeys);
            if (window.settings) logTele("window.settings keys: " + Object.keys(window.settings).slice(0, 30).join(","));
            if (window.gon) logTele("window.gon keys: " + Object.keys(window.gon).slice(0, 30).join(","));
            logTele("Frame check: " + window.location.href + " top=" + (window === window.top));
        } catch(e) {}
    }

    function simulateClick(el) {
        if (!el) return;
        ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(evtType => {
            try {
                el.dispatchEvent(new MouseEvent(evtType, { bubbles: true, cancelable: true, view: window }));
            } catch(e) {}
        });
        if (typeof el.click === 'function') {
            try { el.click(); } catch(e) {}
        }
    }

    // Direct parser to extract real-time tick tuples from incoming wire data
    function inspectDirectTicks(data) {
        try {
            let obj = data;
            if (typeof data === 'string') {
                const bIdx = data.indexOf('[');
                const cIdx = data.indexOf('{');
                const startIdx = (bIdx !== -1 && cIdx !== -1) ? Math.min(bIdx, cIdx) : (bIdx !== -1 ? bIdx : cIdx);
                if (startIdx !== -1) {
                    obj = JSON.parse(data.slice(startIdx));
                } else {
                    return;
                }
            }

            const activePair = state.lastActiveSym;

            const emitTick = (assetCode, priceVal, source = 'ws_stream') => {
                const p = parseFloat(priceVal);
                if (isNaN(p) || p <= 0.0001 || p === 1.0 || p === 10.0 || p === 50.0 || p === 100.0) return;
                let sym = assetCode;
                if (!sym || sym === 'undefined') sym = activePair;
                if (sym) {
                    const strSym = String(sym).trim();
                    if (strSym.includes(',') || /put|call|bonus|promo|period/i.test(strSym)) return;
                    postToHost({ type: 'tick', symbol: strSym, price: p, source: source });
                }
            };

            if (Array.isArray(obj)) {
                // If this is the instruments/list payload: [[id, code, name, cat, prec, payout, ...], ...]
                if (obj.length > 0 && Array.isArray(obj[0]) && obj[0].length >= 6 && typeof obj[0][1] === 'string') {
                    const extractedPayouts = {};
                    const instrumentsList = [];
                    for (const item of obj) {
                        if (Array.isArray(item) && item.length >= 6) {
                            const code = String(item[1]);
                            const pay = parseInt(item[5], 10);
                            if (pay >= 20 && pay <= 100) {
                                extractedPayouts[code] = pay;
                            }
                            SUBSCRIBED_ASSETS.add(code);
                            instrumentsList.push({
                                id: item[0],
                                ws_asset: code,
                                symbol: String(item[2] || code),
                                category: String(item[3] || 'currencies'),
                                precision: parseInt(item[4], 10) || 5,
                                payout: pay
                            });
                        }
                    }
                    if (instrumentsList.length > 0) {
                        postToHost({ type: 'instruments', data: instrumentsList });
                    }
                    if (Object.keys(extractedPayouts).length > 0) {
                        postToHost({ type: 'payouts', data: extractedPayouts });
                    }
                    // Trigger immediate subscription to all newly recognized assets
                    setTimeout(() => {
                        if (window.__tp_subscribe_all) window.__tp_subscribe_all();
                    }, 400);
                    return;
                }

                let itemsList = null;
                let payloadObj = null;
                if (obj.length > 0 && Array.isArray(obj[0]) && typeof obj[0][0] === 'string') {
                    itemsList = obj;
                } else {
                    const payload = obj.length > 1 ? obj[1] : obj[0];
                    if (Array.isArray(payload)) {
                        itemsList = payload;
                    } else if (payload && typeof payload === 'object') {
                        payloadObj = payload;
                    }
                }

                if (itemsList) {
                    for (const item of itemsList) {
                        if (Array.isArray(item)) {
                            if (item.length >= 3) {
                                const a = String(item[0]);
                                const p = (typeof item[1] === 'number' && item[1] > 1000000000)
                                    ? item[2]
                                    : ((typeof item[2] === 'number' && item[2] > 1000000000) ? item[1] : item[2]);
                                emitTick(a, p);
                            } else if (item.length === 2) {
                                if (typeof item[0] === 'number' && item[0] > 1000000000) {
                                    emitTick(activePair, item[1]);
                                }
                            }
                        } else if (item && typeof item === 'object') {
                            const a = item.asset || item.symbol;
                            const p = item.price || item.close || item.c || item.rate;
                            emitTick(a, p);
                        }
                    }
                } else if (payloadObj) {
                    const pObj = payloadObj;
                    const a = pObj.asset || pObj.symbol;
                    if (a) {
                        const p = pObj.price || pObj.close || pObj.c || pObj.rate;
                        if (p !== undefined && p !== null) emitTick(a, p);
                        const hist = pObj.history || pObj.candles || (Array.isArray(pObj.data) && pObj.data.length >= 5 ? pObj.data : null);
                        if (Array.isArray(hist) && hist.length > 0) {
                            if (hist.length >= 5) {
                                postToHost({ type: 'candles', asset: a, data: hist });
                            }
                            const lastBar = hist[hist.length - 1];
                            if (Array.isArray(lastBar)) {
                                if (lastBar.length >= 5) {
                                    emitTick(a, lastBar[2]);
                                } else if (lastBar.length >= 2) {
                                    emitTick(a, lastBar[1]);
                                }
                            }
                        }
                    }
                    if (Array.isArray(pObj.data)) {
                        pObj.data.forEach(d => {
                            if (d && typeof d === 'object') {
                                const a = d.asset || d.symbol;
                                const p = d.price || d.close || d.c || d.rate;
                                if (a && p !== undefined && p !== null) emitTick(a, p);
                            }
                        });
                    }
                    // Handle dictionary format where keys are asset names e.g. {"USDINR_otc": 83.925}
                    for (const k in pObj) {
                        if (k.length >= 3 && !['time', 'timestamp', 'period', 'count', 'data', 'instruments', 'history', 'candles'].includes(k)) {
                            if (k.includes(',') || /put|call|bonus|promo|profit|payout/i.test(k)) continue;
                            const val = pObj[k];
                            if (typeof val === 'number') {
                                emitTick(k, val);
                            } else if (Array.isArray(val) && val.length >= 1) {
                                if (Array.isArray(val[0]) && val[0].length >= 3) {
                                    const lastB = val[val.length - 1];
                                    emitTick(k, lastB[2]);
                                } else if (val.length >= 2) {
                                    const p = typeof val[0] === 'number' && val[0] > 1000000000 ? val[1] : val[0];
                                    emitTick(k, p);
                                }
                            }
                        }
                    }
                }
            } else if (obj && typeof obj === 'object') {
                if (obj.asset || obj.symbol) {
                    emitTick(obj.asset || obj.symbol, obj.price || obj.close);
                }
            }
        } catch(e) {}
    }

    // Handles text, binary (ArrayBuffer/Blob), and Socket.IO v4 binary-attached frames
    function forwardFrame(data) {
        if (!data) return;
        // Unwrap MessageEvent wrapper (from Worker postMessage)
        if (data instanceof MessageEvent) {
            data = data.data;
            if (!data) return;
        }
        if (typeof data === 'string' && data !== '2' && data !== '3') {
            if (!state.frameLoggedCount || state.frameLoggedCount < 30) {
                state.frameLoggedCount = (state.frameLoggedCount || 0) + 1;
                logTele("WIRE FRAME (" + data.length + "): " + data.substring(0, 150));
            }
            postToHost({ type: 'frame', data: data });
            // Socket.IO v4 binary-attached frame: "451-[...json...]" followed by binary attachment
            // Extract the JSON portion for tick inspection
            if (data.startsWith('451-') || data.startsWith('452-') || data.startsWith('46')) {
                const dashIdx = data.indexOf('-');
                if (dashIdx > 0 && dashIdx < 6) {
                    const jsonPart = data.slice(dashIdx + 1);
                    inspectDirectTicks(jsonPart);
                }
            } else {
                inspectDirectTicks(data);
            }
        } else if (data instanceof ArrayBuffer) {
            try {
                const bytes = new Uint8Array(data);
                const text = new TextDecoder('utf-8').decode(bytes);
                if (text && text.length > 2) {
                    postToHost({ type: 'frame', data: text });
                    inspectDirectTicks(text);
                }
            } catch(e) {}
        } else if (typeof Blob !== 'undefined' && data instanceof Blob) {
            data.arrayBuffer().then(buf => {
                const text = new TextDecoder('utf-8').decode(buf);
                if (text && text.length > 2) {
                    postToHost({ type: 'frame', data: text });
                    inspectDirectTicks(text);
                }
            }).catch(() => {});
        } else if (data && typeof data === 'object') {
            // Handle DataView, TypedArray, or plain objects
            if (data.buffer instanceof ArrayBuffer) {
                try {
                    const text = new TextDecoder('utf-8').decode(data.buffer);
                    if (text && text.length > 2) {
                        postToHost({ type: 'frame', data: text });
                        inspectDirectTicks(text);
                    }
                } catch(e) {}
            } else {
                inspectDirectTicks(data);
            }
        }
    }

    // 1. Currency Switcher - Seamlessly changes active Quotex chart to any OTC currency or Real Market pair
    window.__tp_switch_pair = async function(arg1, arg2) {
        if (!arg1 && !arg2) return { success: false };
        const wsCode = (arg1 && arg1.includes('_') ? arg1 : (arg2 && arg2.includes('_') ? arg2 : arg1)) || '';
        const displaySym = (arg2 && !arg2.includes('_') ? arg2 : (arg1 && !arg1.includes('_') ? arg1 : arg2)) || wsCode;

        const isTargetOtc = wsCode.toLowerCase().includes('_otc') || displaySym.toUpperCase().includes('(OTC)');
        const baseName = displaySym.replace(' (OTC)', '').replace('(OTC)', '').trim();

        // 1. Immediately dispatch full suite of Quotex WebSocket commands for instant streaming
        if (window.__tp_ws && window.__tp_ws.readyState === 1 && wsCode) {
            const nowTs = Math.floor(Date.now() / 1000);
            try {
                window.__tp_ws.send('42["instruments/update",{"asset":"' + wsCode + '","period":60}]');
                window.__tp_ws.send('42["depth/follow","' + wsCode + '"]');
                window.__tp_ws.send('42["chart/live",{"asset":"' + wsCode + '","period":60}]');
                window.__tp_ws.send('42["history/load",{"asset":"' + wsCode + '","period":60,"time":' + nowTs + ',"count":60}]');
                window.__tp_ws.send('42["chart_notification/get",{"asset":"' + wsCode + '","version":"1.0.0"}]');
                window.__tp_ws.send('42["tick"]');
            } catch(e) {}
        }

        const matchesAsset = (text) => {
            if (!text) return false;
            const t = text.toUpperCase();
            const textIsOtc = t.includes('OTC');
            if (isTargetOtc !== textIsOtc) return false;
            const cleanBase = baseName.toUpperCase().replace(/[^A-Z0-9]/g, '');
            const cleanText = t.replace(/[^A-Z0-9]/g, '');
            return cleanText.includes(cleanBase) || t.includes(baseName.toUpperCase());
        };

        // Step 1: Direct Click on existing open tab in top bar (instant multi-currency switch!)
        const openTabs = Array.from(document.querySelectorAll('button, div, a, span, li')).filter(el => {
            if (el.offsetParent === null) return false;
            const rect = el.getBoundingClientRect();
            if (rect.top >= 20 && rect.top <= 145 && rect.left < (window.innerWidth - 180) && rect.width >= 30 && rect.width <= 320 && rect.height >= 15 && rect.height <= 90) {
                const txt = (el.innerText || el.textContent || '').trim();
                return matchesAsset(txt) && (txt.includes('%') || txt.includes('/') || txt.includes('OTC'));
            }
            return false;
        });

        if (openTabs.length > 0) {
            // Sort by smallest element bounding area to click tab directly rather than container
            openTabs.sort((a, b) => {
                const rA = a.getBoundingClientRect();
                const rB = b.getBoundingClientRect();
                return (rA.width * rA.height) - (rB.width * rB.height);
            });
            simulateClick(openTabs[0]);
            return { success: true, method: "direct_tab_click", symbol: displaySym };
        }

        // Step 2: Open 'Select trade pair' modal via [+] button or asset selector anywhere across top bar
        const isModalOpen = () => {
            return Array.from(document.querySelectorAll('*')).some(el => {
                const t = (el.innerText || '').toLowerCase();
                return (t.includes('select trade pair') || t.includes('assets') || t.includes('currencies')) && el.offsetParent !== null;
            });
        };

        if (!isModalOpen()) {
            const plusOrAssetBtn = Array.from(document.querySelectorAll('button, div, a, span, svg')).find(el => {
                if (el.offsetParent === null) return false;
                const rect = el.getBoundingClientRect();
                if (rect.top >= 20 && rect.top <= 145 && rect.left < (window.innerWidth - 180) && rect.width <= 140 && rect.height <= 90) {
                    const txt = (el.innerText || el.textContent || '').trim();
                    const cls = (el.className || '').toString().toLowerCase();
                    const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                    return txt === '+' || txt === '＋' || cls.includes('add') || cls.includes('plus') || aria.includes('add') || aria.includes('plus') || cls.includes('asset-select') || cls.includes('pair-select') || cls.includes('current-asset');
                }
                return false;
            });

            if (plusOrAssetBtn) {
                simulateClick(plusOrAssetBtn);
                await new Promise(r => setTimeout(r, 350));
            }
        }

        // Step 3: Search for target currency in modal
        const searchInput = Array.from(document.querySelectorAll('input')).find(inp => {
            if (inp.offsetParent === null) return false;
            const ph = (inp.placeholder || '').toLowerCase();
            return ph.includes('search') || inp.type === 'search' || inp.type === 'text';
        });

        if (searchInput) {
            searchInput.focus();
            try {
                const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                if (nativeSetter) nativeSetter.call(searchInput, baseName);
                else searchInput.value = baseName;
            } catch (e) {
                searchInput.value = baseName;
            }
            searchInput.dispatchEvent(new Event('input', { bubbles: true }));
            searchInput.dispatchEvent(new Event('change', { bubbles: true }));
            await new Promise(r => setTimeout(r, 350));
        }

        // Step 4: Click matching row in modal
        const modalRows = Array.from(document.querySelectorAll('div, li, button, tr, a')).filter(el => {
            if (el.offsetParent === null) return false;
            const rect = el.getBoundingClientRect();
            if (rect.left > 850 || rect.top < 100) return false;
            if (rect.height < 20 || rect.height > 90 || rect.width < 80) return false;

            const txt = (el.innerText || el.textContent || '').trim();
            return matchesAsset(txt) && (txt.includes('%') || txt.includes('OTC') || txt.includes('/'));
        });

        if (modalRows.length > 0) {
            simulateClick(modalRows[0]);
            return { success: true, method: "modal_row_clicked", selected: displaySym };
        }

        // Step 5: Fallback - cycle to any other open tab
        const anyTabs = Array.from(document.querySelectorAll('*')).filter(el => {
            if (el.offsetParent === null) return false;
            const rect = el.getBoundingClientRect();
            if (rect.top >= 20 && rect.top <= 145 && rect.left < (window.innerWidth - 220) && rect.width > 50 && rect.width < 250) {
                const txt = (el.innerText || '').trim();
                const cls = (el.className || '').toString();
                return /([A-Z]{3}\/[A-Z]{3})/.test(txt) && !cls.includes('active');
            }
            return false;
        });

        if (anyTabs.length > 0) {
            simulateClick(anyTabs[0]);
            return { success: true, method: "cycled_existing_tab" };
        }

        return { success: false };
    };

    // Subscribe to all available assets smoothly in parallel over Quotex WebSocket
    // NOTE: This subscription protocol (depth/follow, history/load, chart/live, tick)
    // is an UNVERIFIED GUESS at Quotex's real subscription API. It has never been
    // confirmed against captured real Quotex WebSocket traffic. To verify, open
    // Quotex in a normal browser, DevTools → Network → WS → Messages tab, and
    // compare the real client→server messages against what this function sends.
    // DO NOT rewrite this function based on more guessing — only update once
    // real captured frames are available for comparison.
    function subscribeAllAssets(ws, initialLoad = false) {
        const target = ws || window.__tp_ws;
        if (!target || target.readyState !== 1) return;
        if (state.subInProgress) return;
        state.subInProgress = true;
        // Safety timeout to prevent permanent lock if a batch stalls
        setTimeout(() => { state.subInProgress = false; }, 25000);

        const nowTs = Math.floor(Date.now() / 1000);
        const assetsToSub = Array.from(SUBSCRIBED_ASSETS);
        logTele("Dispatching authentic multi-asset subscriptions for " + assetsToSub.length + " pairs (initial=" + initialLoad + ")...");

        let idx = 0;
        let sentMessages = [];
        function processNext() {
            try {
                if (!target || target.readyState !== 1 || idx >= assetsToSub.length) {
                    state.subInProgress = false;
                    const tickMsg = '42["tick"]';
                    try { target.send(tickMsg); sentMessages.push(tickMsg); } catch(te) {}
                    logTele("[DIAG] Subscription batch complete. Total messages sent: " + sentMessages.length);
                    return;
                }
                const asset = assetsToSub[idx++];
                try {
                    // 1. Follow depth & payout updates
                    const depthMsg = '42["depth/follow","' + asset + '"]';
                    target.send(depthMsg);
                    sentMessages.push(depthMsg);

                    // 2. Request live chart quotes stream for this asset (enables ticks for all pairs)
                    const chartMsg = '42["chart/live",{"asset":"' + asset + '","period":60}]';
                    target.send(chartMsg);
                    sentMessages.push(chartMsg);

                    // 3. Request dynamic instrument state
                    const instMsg = '42["instruments/update",{"asset":"' + asset + '","period":60}]';
                    target.send(instMsg);
                    sentMessages.push(instMsg);

                    // 4. Request recent history to immediately bootstrap latest price (full 60 bars for complete indicators)
                    const histMsg = '42["history/load",{"asset":"' + asset + '","period":60,"time":' + nowTs + ',"count":60}]';
                    target.send(histMsg);
                    sentMessages.push(histMsg);
                } catch(e) {}
                setTimeout(processNext, 50);
            } catch(err) {
                state.subInProgress = false;
            }
        }
        processNext();
    }
    window.__tp_subscribe_all = subscribeAllAssets;

    // Fast on-demand single asset stream activator
    window.__tp_prime_asset = function(assetCode) {
        if (!assetCode) return false;
        const target = window.__tp_ws;
        if (target && target.readyState === 1) {
            const nowTs = Math.floor(Date.now() / 1000);
            try {
                target.send('42["depth/follow","' + assetCode + '"]');
                target.send('42["instruments/update",{"asset":"' + assetCode + '","period":60}]');
                target.send('42["chart/live",{"asset":"' + assetCode + '","period":60}]');
                target.send('42["history/load",{"asset":"' + assetCode + '","period":60,"time":' + nowTs + ',"count":60}]');
                target.send('42["tick"]');
                return true;
            } catch(e) {}
        }
        return false;
    };

    // Recurring keepalive in V8: continuously maintains parallel multi-asset quotes stream
    if (!state.subKeepaliveStarted) {
        state.subKeepaliveStarted = true;
        setInterval(() => {
            if (window.__tp_ws && window.__tp_ws.readyState === 1) {
                subscribeAllAssets(window.__tp_ws, false);
            }
        }, 25000);
    }

    // Periodic instruments refresh: re-requests full instrument list every 60s
    // to ensure payouts are populated even if the initial frame was missed.
    if (!state.instrRefreshStarted) {
        state.instrRefreshStarted = true;
        setInterval(() => {
            try {
                const ws = window.__tp_ws;
                if (ws && ws.readyState === 1) {
                    ws.send('42["instruments/list",{}]');
                    ws.send('42["instruments/all",{}]');
                    ws.send('42["tick"]');
                }
            } catch(e) {}
        }, 60000);
    }

    function handleSocket(ws) {
        if (!ws) return;
        window.__tp_ws = ws;
        if (ws.__tp_hooked) return;
        ws.__tp_hooked = true;
        logTele("Native WebSocket stream attached: " + (ws.url || 'endpoint'));

        try {
            ws.addEventListener('message', (ev) => forwardFrame(ev.data));
            ws.addEventListener('open', () => {
                setTimeout(() => subscribeAllAssets(ws), 1500);
            });
            if (ws.readyState === 1) {
                setTimeout(() => subscribeAllAssets(ws), 1000);
            }
        } catch(e) {}
    }

    // Hook Web Worker constructor to intercept worker-based WebSocket streaming
    const OrigWorker = window.Worker;
    if (OrigWorker && !state.workerHooked) {
        state.workerHooked = true;
        logTele("Installing Web Worker message hook...");
        window.Worker = function(scriptURL, options) {
            const w = new OrigWorker(scriptURL, options);
            try {
                w.addEventListener('message', (ev) => {
                    if (ev && ev.data) forwardFrame(ev.data);
                });
            } catch(e) {}
            return w;
        };
        window.Worker.prototype = OrigWorker.prototype;
    }

    // Hook SharedWorker constructor
    const OrigSharedWorker = window.SharedWorker;
    if (OrigSharedWorker && !state.sharedWorkerHooked) {
        state.sharedWorkerHooked = true;
        window.SharedWorker = function(...args) {
            const sw = new OrigSharedWorker(...args);
            try {
                if (sw.port) {
                    sw.port.addEventListener('message', (ev) => {
                        if (ev && ev.data) forwardFrame(ev.data);
                    });
                }
            } catch(e) {}
            return sw;
        };
        window.SharedWorker.prototype = OrigSharedWorker.prototype;
    }

    // Hook window.WebSocket constructor
    const OrigWS = window.WebSocket;
    if (OrigWS && !state.wsHooked) {
        state.wsHooked = true;
        logTele("Installing window.WebSocket hook...");
        window.WebSocket = function(...args) {
            const ws = new OrigWS(...args);
            handleSocket(ws);
            return ws;
        };
        window.WebSocket.prototype = OrigWS.prototype;
        window.WebSocket.CONNECTING = OrigWS.CONNECTING;
        window.WebSocket.OPEN = OrigWS.OPEN;
        window.WebSocket.CLOSING = OrigWS.CLOSING;
        window.WebSocket.CLOSED = OrigWS.CLOSED;
    }

    // Hook WebSocket.prototype.send
    if (OrigWS && OrigWS.prototype && !state.sendHooked) {
        state.sendHooked = true;
        const origSend = OrigWS.prototype.send;
        OrigWS.prototype.send = function(...args) {
            if (!window.__tp_ws || !window.__tp_ws.__tp_hooked) {
                handleSocket(this);
            }
            try {
                if (args[0] && typeof args[0] === 'string') {
                    const msgStr = args[0];
                    if (msgStr.includes('"authorization"')) {
                        try {
                            const authMatch = msgStr.match(/"session"\s*:\s*"([^"]+)"/);
                            if (authMatch && authMatch[1]) {
                                logTele("Captured active session token from client authorization frame!");
                                postToHost({ type: 'session', token: authMatch[1] });
                            }
                        } catch(ae) {}
                        logTele("CLIENT AUTH FRAME DETECTED -> Scheduling multi-asset subscription in 1200ms...");
                        setTimeout(() => {
                            subscribeAllAssets(this, true);
                        }, 1200);
                    }
                    if (!state.sendLoggedCount || state.sendLoggedCount < 30) {
                        if (msgStr.startsWith('42')) {
                            state.sendLoggedCount = (state.sendLoggedCount || 0) + 1;
                            logTele("CLIENT WS SEND: " + msgStr.substring(0, 150));
                        }
                    }
                }
            } catch(e) {}
            return origSend.apply(this, args);
        };
    }

    // Hook CanvasRenderingContext2D text rendering to intercept chart prices drawn on canvas
    if (!state.canvasHooked && typeof CanvasRenderingContext2D !== 'undefined') {
        state.canvasHooked = true;
        const origFillText = CanvasRenderingContext2D.prototype.fillText;
        const origStrokeText = CanvasRenderingContext2D.prototype.strokeText;
        let pendingPrefix = null;
        let pendingPrefixTs = 0;

        function recordCanvasText(text) {
            if (text === null || text === undefined) return;
            const str = String(text).trim();
            if (!str || str.length < 2 || str.length > 15) return;
            if (str.includes('$') || str.includes('%') || str.includes(':')) return;

            const now = Date.now();
            // Full decimal match e.g. 83.925 or 0.58213
            const fullMatch = str.match(/^([0-9]{1,6}\.[0-9]{2,6})$/);
            if (fullMatch) {
                const val = parseFloat(fullMatch[1]);
                if (!isNaN(val) && val > 0.0001 && val !== 1.0 && val !== 10.0 && val !== 50.0 && val !== 100.0) {
                    state.lastCanvasPrice = val;
                    state.lastCanvasPriceTs = now;
                    return;
                }
            }

            // Split decimal e.g. "83.9" followed by "25"
            if (str.includes('.') && /^[0-9]{1,6}\.[0-9]{1,2}$/.test(str)) {
                pendingPrefix = str;
                pendingPrefixTs = now;
                return;
            }

            if (pendingPrefix && (now - pendingPrefixTs < 60) && /^[0-9]{1,3}$/.test(str)) {
                const combined = pendingPrefix + str;
                pendingPrefix = null;
                const val = parseFloat(combined);
                if (!isNaN(val) && val > 0.0001) {
                    state.lastCanvasPrice = val;
                    state.lastCanvasPriceTs = now;
                }
            }
        }

        CanvasRenderingContext2D.prototype.fillText = function(text, x, y, maxWidth) {
            recordCanvasText(text);
            return origFillText.apply(this, arguments);
        };
        CanvasRenderingContext2D.prototype.strokeText = function(text, x, y, maxWidth) {
            recordCanvasText(text);
            return origStrokeText.apply(this, arguments);
        };
    }

    // 2. Extracts active chart pair name
    function getActivePairName(knownPayouts) {
        const VALID_CURRENCIES = new Set([
            'USD', 'EUR', 'GBP', 'JPY', 'CHF', 'CAD', 'AUD', 'NZD',
            'INR', 'BRL', 'PKR', 'IDR', 'EGP', 'TRY', 'MXN', 'ARS',
            'CNY', 'SGD', 'HKD', 'RUB', 'ZAR'
        ]);

        const parseSym = (text) => {
            if (!text) return null;
            const clean = text.replace(/[\n\r\t]/g, ' ').trim();
            if (/gold/i.test(clean)) return clean.toUpperCase().includes('(OTC)') || clean.toUpperCase().includes('OTC') ? "GOLD (OTC)" : "Gold";
            if (/silver/i.test(clean)) return clean.toUpperCase().includes('(OTC)') || clean.toUpperCase().includes('OTC') ? "SILVER (OTC)" : "Silver";
            if (/natural.?gas|natgas|xng/i.test(clean)) return "Natural Gas (OTC)";
            if (/brent/i.test(clean)) return "UK BRENT (OTC)";
            if (/crude/i.test(clean)) return "US CRUDE (OTC)";
            if (/btc|bitcoin\s*cash/i.test(clean)) {
                if (/cash/i.test(clean)) return "Bitcoin Cash (OTC)";
                return "Bitcoin (OTC)";
            }
            if (/bch/i.test(clean)) return "Bitcoin Cash (OTC)";
            if (/eth|ethereum/i.test(clean)) {
                if (/classic|etc/i.test(clean)) return "Ethereum Classic (OTC)";
                return "Ethereum (OTC)";
            }
            if (/etc\b/i.test(clean) && !/eth/i.test(clean)) return "Ethereum Classic (OTC)";
            if (/link|chainlink/i.test(clean)) return "Chainlink (OTC)";
            if (/avax|avalanche/i.test(clean)) return "Avalanche (OTC)";
            if (/ton|toncoin/i.test(clean)) return "Toncoin (OTC)";
            if (/trump/i.test(clean)) return "Trump (OTC)";
            if (/sol|solana/i.test(clean)) return "Solana (OTC)";
            if (/ltc|litecoin/i.test(clean)) return "Litecoin (OTC)";
            if (/xrp|ripple/i.test(clean)) return "Ripple (OTC)";
            if (/zec|zcash/i.test(clean)) return "Zcash (OTC)";
            if (/dash\b/i.test(clean)) return "Dash (OTC)";
            if (/axs|axie/i.test(clean)) return "Axie Infinity (OTC)";
            if (/atom|cosmos/i.test(clean)) return "Cosmos (OTC)";
            if (/bnb|binance/i.test(clean)) return "Binance Coin (OTC)";
            if (/dot|polkadot/i.test(clean)) return "Polkadot (OTC)";

            const isOtc = /otc/i.test(clean);
            const m = clean.match(/\b([A-Z]{3})\s*[\/_]?\s*([A-Z]{3})\b/i);
            if (m) {
                const c1 = m[1].toUpperCase();
                const c2 = m[2].toUpperCase();
                if (VALID_CURRENCIES.has(c1) && VALID_CURRENCIES.has(c2) && c1 !== c2) {
                    return `${c1}/${c2}` + (isOtc ? ' (OTC)' : '');
                }
            }
            return null;
        };

        // Priority 0: Object introspection from window.settings, window.gon, window.__INITIAL_STATE__
        try {
            const candidates = [window.settings, window.gon, window.__INITIAL_STATE__];
            for (const k in window) {
                try {
                    if (window[k] && typeof window[k] === 'object') candidates.push(window[k]);
                } catch(e) {}
            }
            for (const obj of candidates) {
                if (!obj) continue;
                const activeAsset = obj.activeAsset || obj.currentAsset || obj.selectedAsset
                    || (obj.trade && (obj.trade.asset || obj.trade.symbol))
                    || (obj.deal && (obj.deal.asset || obj.deal.symbol))
                    || (obj.chart && (obj.chart.asset || obj.chart.symbol));
                if (activeAsset && typeof activeAsset === 'string') {
                    const sym = parseSym(activeAsset);
                    if (sym) return sym;
                }
            }
        } catch(e) {}

        // Priority 1: Check active tab in top bar (Valid CSS syntax, wrapped in try-catch)
        try {
            const activeTab = document.querySelector('[class*="tab"].active, [class*="tab"][class*="selected"], [class*="tab--active"], .tabs__item.active, [aria-selected="true"], [class*="tab_active"]');
            if (activeTab) {
                const sym = parseSym(activeTab.innerText || activeTab.textContent);
                if (sym) return sym;
            }
        } catch(e) {}

        // Priority 2: Check asset select button in header or chart bar
        try {
            const assetBtns = document.querySelectorAll('.asset-select, [class*="asset-select"], [class*="pair-select"], [class*="current-asset"], .header__assets');
            for (const btn of assetBtns) {
                const sym = parseSym(btn.innerText || btn.textContent);
                if (sym) return sym;
            }
        } catch(e) {}

        // Priority 3: Search tabs in top bar by layout position (y: 20-150, x < innerWidth - 200)
        try {
            const tabs = Array.from(document.querySelectorAll('*')).filter(el => {
                if (el.offsetParent === null) return false;
                const rect = el.getBoundingClientRect();
                if (rect.top >= 20 && rect.top <= 150 && rect.left < (window.innerWidth - 200) && rect.width > 50 && rect.width < 300) {
                    const txt = (el.innerText || el.textContent || '').trim();
                    return /([A-Z]{3}\/[A-Z]{3})/.test(txt) && (txt.includes('%') || txt.includes('OTC'));
                }
                return false;
            });
            if (tabs.length > 0) {
                const sym = parseSym(tabs[0].innerText || tabs[0].textContent);
                if (sym) return sym;
            }
        } catch(e) {}

        // Priority 4: If extractAllPayouts found exactly 1 symbol, that IS the active open tab!
        if (knownPayouts) {
            const keys = Object.keys(knownPayouts);
            if (keys.length === 1) return keys[0];
        }

        // Priority 5: Fallback to document.title only if it matches valid currencies
        try {
            if (typeof document !== 'undefined' && document.title) {
                const titleSym = parseSym(document.title);
                if (titleSym) return titleSym;
            }
        } catch(e) {}

        // Priority 6: Object introspection from known window candidates (no window loop)
        try {
            const candidates = [window.settings, window.gon, window.__INITIAL_STATE__];
            for (const obj of candidates) {
                if (!obj) continue;
                const activeAsset = obj.activeAsset || obj.currentAsset || obj.selectedAsset
                    || (obj.trade && (obj.trade.asset || obj.trade.symbol))
                    || (obj.deal && (obj.deal.asset || obj.deal.symbol))
                    || (obj.chart && (obj.chart.asset || obj.chart.symbol));
                if (activeAsset && typeof activeAsset === 'string') {
                    const sym = parseSym(activeAsset);
                    if (sym) return sym;
                }
            }
        } catch(e) {}

        return state.lastActiveSym || null;
    }

    // 3. Extracts real-time active price from Quotex canvas, chart scale, deal form, or legend
    function extractLivePrice() {
        const now = Date.now();

        // Priority 1: Specific chart price overlay badges and strike values (FASTEST & MOST ACCURATE)
        try {
            const specificSelectors = [
                '.chart__current-price',
                '[class*="chart-current-price"]',
                '[class*="strike-value"]',
                '[class*="current-price"]',
                '[class*="value-line"]',
                '[class*="price-label"]',
                '[class*="chart-quote"]',
                '[class*="chart__quote"]',
                '[class*="active-quote"]',
                '[class*="crosshair-value"]',
                '[class*="axis-label"]',
                '[class*="chart"] [class*="quote"]',
                '[class*="current-rate"]',
                '[class*="last-price"]',
                '[class*="price-value"]',
                '[class*="quote-value"]'
            ];
            for (const sel of specificSelectors) {
                const els = document.querySelectorAll(sel);
                for (const el of els) {
                    const text = (el.textContent || '').trim().replace(/\s+/g, '');
                    if (text.includes('$') || text.includes('Payout') || text.includes('%')) continue;
                    const m = text.match(/([0-9]{1,6}\.[0-9]{2,6})/);
                    if (m) {
                        const val = parseFloat(m[1]);
                        if (val > 0.0001 && val !== 1.35 && val !== 1.0 && val !== 10.0 && val !== 50.0 && val !== 100.0) return val;
                    }
                }
            }
        } catch(e) {}

        // Priority 2: Quotex document.title price regex (e.g. "83.925 USD/INR - Quotex")
        try {
            if (typeof document !== 'undefined' && document.title) {
                const tm = document.title.match(/([0-9]{1,6}\.[0-9]{2,6})/);
                if (tm) {
                    const val = parseFloat(tm[1]);
                    if (!isNaN(val) && val > 0.0001 && val !== 1.0 && val !== 10.0 && val !== 50.0 && val !== 100.0) {
                        return val;
                    }
                }
            }
        } catch(e) {}

        // Priority 3: Quotation in deal form inputs or labels
        try {
            const dealFormEls = document.querySelectorAll('.deal-form input, [class*="deal-form"] input, .deal-form__quote, [class*="deal-form"] [class*="quote"], [class*="deal-form"] [class*="current-quote"], [class*="strike"]');
            for (const el of dealFormEls) {
                const raw = (el.value !== undefined && el.value !== '') ? el.value : el.textContent;
                if (!raw) continue;
                const clean = raw.trim().replace(/[^0-9.]/g, '');
                const m = clean.match(/^([0-9]{1,6}\.[0-9]{2,6})$/);
                if (m) {
                    const val = parseFloat(m[1]);
                    if (!isNaN(val) && val > 0.0001 && val !== 1.35 && val !== 1.0 && val !== 10.0 && val !== 50.0 && val !== 100.0) {
                        return val;
                    }
                }
            }
        } catch(e) {}

        // Priority 4: High-frequency Canvas text capture (fresh within 3.5s)
        if (state.lastCanvasPrice && (now - state.lastCanvasPriceTs < 3500)) {
            return state.lastCanvasPrice;
        }

        // Priority 5: Search leaf elements inside chart container
        try {
            const chartContainers = document.querySelectorAll('.chart-container, [class*="chart-container"], [class*="chart_container"], .market-container, [class*="market-chart"], svg');
            for (const container of chartContainers) {
                const leaves = container.querySelectorAll('div, span, text, tspan');
                for (let i = leaves.length - 1; i >= 0; i--) {
                    const el = leaves[i];
                    if (el.children.length > 2) continue;
                    const txt = (el.textContent || '').trim();
                    if (txt.includes('$') || txt.includes('%') || txt.includes(':')) continue;
                    const m = txt.match(/^([0-9]{1,6}\.[0-9]{2,6})$/);
                    if (m) {
                        const val = parseFloat(m[1]);
                        if (!isNaN(val) && val > 0.0001 && val !== 1.0 && val !== 10.0 && val !== 50.0 && val !== 100.0) {
                            return val;
                        }
                    }
                }
            }
        } catch(e) {}

        // Priority 6: Object introspection from known window state (no window loop)
        try {
            const activeSym = state.lastActiveSym;
            const candidates = [window.settings, window.gon, window.__INITIAL_STATE__];
            for (const obj of candidates) {
                if (!obj) continue;
                const quotes = obj.quotes || obj.rates || obj.prices || (obj.chart && obj.chart.quotes);
                if (quotes && typeof quotes === 'object') {
                    for (const key of Object.keys(quotes)) {
                        if (activeSym && key.toLowerCase().includes(activeSym.replace(/[^A-Za-z]/g, '').toLowerCase())) {
                            const v = typeof quotes[key] === 'object'
                                ? (quotes[key].price || quotes[key].value || quotes[key].close)
                                : quotes[key];
                            const val = parseFloat(v);
                            if (!isNaN(val) && val > 0.0001) return val;
                        }
                    }
                }
            }
        } catch(e) {}

        // Priority 7: Fallback to last recorded canvas price even if older
        if (state.lastCanvasPrice) {
            return state.lastCanvasPrice;
        }

        return null;
    }

    // 4. Extracts authentic payouts (strictly excludes 50% deposit bonus or promo text)
    function extractAllPayouts() {
        const payouts = {};

        // 1. Probe window object for internal Quotex instruments dictionary (no window loop)
        try {
            const sources = [
                window.settings && window.settings.instruments,
                window.gon && window.gon.instruments,
                window.__INITIAL_STATE__ && window.__INITIAL_STATE__.instruments
            ];
            for (const src of sources) {
                if (Array.isArray(src) && src.length > 5) {
                    src.forEach(i => {
                        const name = i.name || i.symbol || i.asset;
                        const val = i.payout !== undefined ? i.payout : (i.profit !== undefined ? i.profit : null);
                        if (name && val !== null) {
                            const num = typeof val === 'object' ? (val.percent || val.value) : val;
                            // Accept both OTC (70+) and live market (20+) payouts
                            if (num >= 20 && num <= 100) payouts[name] = num;
                        }
                    });
                }
            }
        } catch(e) {}

        // 2. Probe all open tabs in top bar
        try {
            const tabs = Array.from(document.querySelectorAll('[class*="tab"], [class*="item"], div, span')).filter(el => {
                if (el.offsetParent === null) return false;
                const rect = el.getBoundingClientRect();
                if (rect.top < 20 || rect.top > 150 || rect.left > (window.innerWidth - 200)) return false;
                const txt = el.textContent || '';
                return (txt.includes('(OTC)') || txt.includes('/')) && txt.includes('%');
            });
            for (const tab of tabs) {
                const txt = (tab.textContent || '').trim();
                if (/bonus|deposit|promo|promocode/i.test(txt)) continue;

                const symMatch = txt.match(/([A-Z]{3}\/[A-Z]{3}\s*\(OTC\)|[A-Z]{3}\/[A-Z]{3}|[A-Z0-9/ ]+\(OTC\))/i);
                const payMatch = txt.match(/(\d{2})%/);
                if (symMatch && payMatch) {
                    let sym = symMatch[1].trim();
                    const isOtc = /otc/i.test(sym) || /otc/i.test(txt);
                    const cleanSym = sym.replace(/\s*\(OTC\)/i, '').trim();
                    const canonical = cleanSym + (isOtc ? ' (OTC)' : '');
                    const pay = parseInt(payMatch[1], 10);
                    const minP = isOtc ? 70 : 20;
                    if (pay >= minP && pay <= 100) {
                        payouts[canonical] = pay;
                    }
                }
            }
        } catch(e) {}

        // 3. Probe right deal panel payout (e.g. +85% / Payout: 85%)
        try {
            const dealForms = document.querySelectorAll('.deal-form, [class*="deal-form"], [class*="section-deal"]');
            for (const form of dealForms) {
                const txt = (form.textContent || '').trim();
                const pm = txt.match(/(?:payout|profit|\+)\s*(\d{2})%/i) || txt.match(/(\d{2})%\s*(?:payout|profit)/i);
                if (pm) {
                    const pay = parseInt(pm[1], 10);
                    if (pay >= 70 && pay <= 100) {
                        const activePair = getActivePairName();
                        if (activePair) payouts[activePair] = pay;
                    }
                }
            }
        } catch(e) {}

        return payouts;
    }

    // 5. Extracts multi-currency quotes from Quotex window state & open tabs
    function extractAllQuotes() {
        const quotes = {};
        try {
            const candidates = [window.settings, window.gon, window.__INITIAL_STATE__];
            for (const obj of candidates) {
                if (!obj) continue;
                // Probe quotes/rates/prices maps
                const q = obj.quotes || obj.rates || obj.prices || (obj.chart && obj.chart.quotes);
                if (q && typeof q === 'object') {
                    for (const key of Object.keys(q)) {
                        if (key.includes(',') || /put|call|bonus|promo/i.test(key)) continue;
                        const v = typeof q[key] === 'object' ? (q[key].price || q[key].value || q[key].close) : q[key];
                        const val = parseFloat(v);
                        if (!isNaN(val) && val > 0.0001 && val !== 1.0) {
                            quotes[key] = { price: val, source: 'instrument_object' };
                        }
                    }
                }
                // Probe instruments array for live rates
                if (Array.isArray(obj.instruments)) {
                    obj.instruments.forEach(inst => {
                        const name = inst.name || inst.symbol || inst.asset;
                        if (!name || name.includes(',') || /put|call|bonus|promo/i.test(name)) return;
                        const p = inst.rate !== undefined ? inst.rate : (inst.price !== undefined ? inst.price : (inst.close !== undefined ? inst.close : inst.last));
                        if (p !== undefined && p !== null) {
                            const val = parseFloat(typeof p === 'object' ? (p.price || p.value || p.close) : p);
                            if (!isNaN(val) && val > 0.0001 && val !== 1.0) {
                                quotes[name] = { price: val, source: 'instrument_object' };
                            }
                        }
                    });
                }
            }
        } catch(e) {}

        // Probe all open tabs in top bar for visible live rates
        try {
            const tabs = Array.from(document.querySelectorAll('[class*="tab"], [class*="item"]')).filter(el => {
                if (el.offsetParent === null) return false;
                const rect = el.getBoundingClientRect();
                return rect.top >= 20 && rect.top <= 150 && rect.left < (window.innerWidth - 200);
            });
            tabs.forEach(tab => {
                const txt = (tab.textContent || '').trim();
                const symMatch = txt.match(/([A-Z]{3}\/[A-Z]{3})/);
                const priceMatch = txt.match(/([0-9]{1,6}\.[0-9]{2,6})/);
                if (symMatch && priceMatch) {
                    const p = parseFloat(priceMatch[1]);
                    if (!isNaN(p) && p > 0.0001 && p !== 1.0) {
                        const tabIsOtc = txt.toUpperCase().includes('OTC');
                        const targetSym = symMatch[1] + (tabIsOtc ? ' (OTC)' : '');
                        quotes[targetSym] = { price: p, source: 'dom_tabscan' };
                    }
                }
            });
        } catch(e) {}

        return quotes;
    }

    function isTradeRoom() {
        return Boolean(
            (window.location.pathname && (window.location.pathname.includes('/trade') || window.location.pathname.includes('demo-trade'))) ||
            document.querySelector('.page-trade') ||
            document.querySelector('.deal-form') ||
            document.querySelector('.chart-container') ||
            document.querySelector('.market-container') ||
            document.querySelector('[class*="deal-form"]') ||
            document.querySelector('canvas') ||
            Boolean(window.__tp_ws) ||
            Boolean(window.settings) ||
            Boolean(window.gon)
        );
    }

    // Fast scanning execution cycle
    function executeScan() {
        try {
            const inTrade = isTradeRoom();
            if (!inTrade) {
                return;
            }

            const allPayouts = extractAllPayouts();
            const payoutCount = Object.keys(allPayouts).length;
            if (payoutCount > 0) {
                postToHost({ type: 'payouts', data: allPayouts });
                state.lastPayoutCount = payoutCount;
            }

            // Multi-currency simultaneous real-time quotes broadcast with client-side plausibility validation
            try {
                const multiQuotes = extractAllQuotes();
                state.lastGoodQuotes = state.lastGoodQuotes || {};
                for (const sym of Object.keys(multiQuotes)) {
                    const item = multiQuotes[sym];
                    const val = typeof item === 'object' ? item.price : item;
                    const src = (typeof item === 'object' && item.source) ? item.source : 'dom_tabscan';
                    const lastGood = state.lastGoodQuotes[sym];
                    if (lastGood && lastGood > 0) {
                        const pctDiff = Math.abs(val - lastGood) / lastGood;
                        if (pctDiff > 0.15) {
                            continue; // reject implausible jump, don't broadcast it
                        }
                    }
                    state.lastGoodQuotes[sym] = val;
                    postToHost({ type: 'tick', symbol: sym, price: val, source: src });
                }
            } catch(mqErr) {}


            const activeSym = getActivePairName(allPayouts);
            if (activeSym) {
                state.lastActiveSym = activeSym;
            }
            const activePrice = extractLivePrice();

            if (activeSym && activePrice) {
                postToHost({ type: 'tick', symbol: activeSym, price: activePrice, source: 'active_chart' });
                state.lastActivePrice = activePrice;
            }

            const now = Date.now();
            if (now - state.lastReportTs > 10000) {
                state.lastReportTs = now;
                logTele(`TradeRoom status: Active=${activeSym || 'None'}, Price=${activePrice || 'None'}, Payouts=${payoutCount}`);
            }
        } catch(e) {
            logTele("Scan error: " + e.message);
        }
    }
    window.__tp_scan_now = executeScan;

    // 5. Continuous Lightweight Telemetry Loop (every 400ms for sub-second price updates)
    if (!state.loopStarted) {
        state.loopStarted = true;
        logTele("Starting continuous telemetry loop (400ms)...");
        setInterval(executeScan, 400);
    }

    // 7. Session token detector (strictly when verified inside live trade room)
    if (!state.sessionDetectorStarted) {
        state.sessionDetectorStarted = true;
        setInterval(() => {
            try {
                if (!isTradeRoom()) return;
                let token = localStorage.getItem('token') || sessionStorage.getItem('token');
                if (token && token.length > 10 && !window.__tp_token_sent) {
                    window.__tp_token_sent = true;
                    postToHost({ type: 'session', token: token });
                }
            } catch(e) {}
        }, 1500);
    }

    logTele("STREAM_INJECTION_JS active on: " + window.location.href);
})();
"""


class AuthManager:
    """Manages Quotex authentication state and session lifecycle."""

    def __init__(self):
        self._session_token: Optional[str] = None
        self._email: Optional[str] = None
        self._is_demo: int = 0
        self._account_balance: float = 0.0

    def get_valid_session_token(self) -> Optional[str]:
        """
        Retrieves valid session token from memory, environment, or encrypted disk cache.
        """
        if self._session_token:
            return self._session_token

        # 1. Check environment / .env
        env_token = settings.QUOTEX_SESSION_TOKEN or os.environ.get("QUOTEX_SESSION_TOKEN")
        if env_token and len(env_token.strip()) > 10:
            self._session_token = env_token.strip()
            logger.info("[AUTH] Using QUOTEX_SESSION_TOKEN from environment.")
            return self._session_token

        # 2. Check encrypted disk cache (~/.tradepulse/session.enc)
        cached = load_encrypted_session("session.enc")
        if cached and "token" in cached:
            token = cached["token"]
            saved_at = cached.get("saved_at", 0)
            cookies = cached.get("cookies", {})
            # Accept if saved within 7 days and has authentic token (or cookies)
            if (time.time() - saved_at) < 7 * 86400 and (len(cookies) > 0 or (token and len(token) >= 20)):
                self._session_token = token
                self._email = cached.get("email")
                cookie_cnt = len(cookies) if cookies else 0
                logger.info(f"[AUTH] Loaded valid encrypted session ({cookie_cnt} cookies, token_len={len(token)}) from disk cache.")
                return self._session_token
            else:
                logger.info("[AUTH] Cached session token is unauthenticated, expired, or missing valid token.")

        return None

    def get_cookie_header(self) -> Optional[str]:
        """Returns the full Cookie header string from cached session."""
        cached = load_encrypted_session("session.enc")
        if cached and "cookies" in cached and cached["cookies"]:
            parts = [f"{k}={v}" for k, v in cached["cookies"].items()]
            return "; ".join(parts)
        if self._session_token:
            return f"token={self._session_token}; ssid={self._session_token}"
        return None

    def store_session(self, token: str, email: Optional[str] = None, cookies: Optional[Dict[str, str]] = None):
        """Encrypts and persists authenticated session."""
        self._session_token = token.strip()
        if email:
            self._email = email

        payload = {
            "token": self._session_token,
            "email": self._email,
            "saved_at": int(time.time()),
            "cookies": cookies or {}
        }
        save_encrypted_session(payload, "session.enc")
        logger.info(f"[AUTH] Successfully saved encrypted session ({len(payload['cookies'])} cookies) to disk.")

    def clear_session(self):
        """Clears session in memory and on disk."""
        self._session_token = None
        self._email = None
        enc_file = settings.resolved_data_dir / "session.enc"
        if enc_file.exists():
            try:
                enc_file.unlink()
            except Exception as e:
                logger.warning(f"[AUTH] Failed to unlink session cache {enc_file}: {e}")
        logger.info("[AUTH] Cleared session cache.")

    def _monitor_auth_window(self, login_win, email: Optional[str], on_success_callback):
        """
        Actively polls the login webview window for SPA route transitions into /trade.
        Injects real-time streaming bridge, extracts authentication credentials,
        and transitions the window into a persistent background broker stream.
        """
        logger.info("[AUTH MONITOR] Poller active. Watching for Quotex trade room entry...")
        session_captured = False

        for _ in range(600):  # Poll every 0.8s for up to 8 minutes
            time.sleep(0.8)
            if session_captured:
                break

            try:
                url = login_win.get_current_url() or ""

                # 1. URL pattern match
                url_indicates_trade = any(k in url.lower() for k in ["/trade", "/en/trade", "demo-trade", "platform"])

                # 2. DOM probes inside Quotex web app
                in_trade_dom = False
                token_from_js = None
                payouts_from_js = {}

                try:
                    js_probe = """
                    (() => {
                        try {
                            const isTrade = Boolean(
                                document.querySelector('.page-trade') ||
                                document.querySelector('.market-container') ||
                                document.querySelector('.deal-form') ||
                                document.querySelector('.chart-container') ||
                                document.querySelector('.balance') ||
                                document.querySelector('.header__pair') ||
                                window.location.pathname.includes('trade')
                            );

                            let token = null;
                            try {
                                token = localStorage.getItem('token') ||
                                        sessionStorage.getItem('token') ||
                                        (window.settings && window.settings.token) || null;
                            } catch(e){}

                            const payouts = {};
                            try {
                                if (window.settings && window.settings.instruments) {
                                    window.settings.instruments.forEach(i => {
                                        if (i.name && (i.payout || i.profit)) {
                                            payouts[i.name] = i.payout || i.profit;
                                        }
                                    });
                                }
                            } catch(e){}

                            return { isTrade: isTrade, token: token, payouts: payouts };
                        } catch(err) {
                            return { isTrade: false, token: null, payouts: {} };
                        }
                    })()
                    """
                    probe_res = login_win.evaluate_js(js_probe)
                    if isinstance(probe_res, dict):
                        in_trade_dom = bool(probe_res.get("isTrade"))
                        token_from_js = probe_res.get("token")
                        payouts_from_js = probe_res.get("payouts") or {}
                except Exception as e:
                    logger.debug(f"[AUTH MONITOR] JS probe evaluation error: {e}")

                # If either URL or DOM confirms user is logged in
                if url_indicates_trade or in_trade_dom:
                    logger.info("[AUTH MONITOR] Confirmed user is inside Quotex trading interface! Linking live session...")

                    # 1. Inject live WebSocket & Payout streaming hook into the active Quotex session
                    js_stream_hook = STREAM_INJECTION_JS
                    try:
                        login_win.evaluate_js(js_stream_hook)
                    except Exception as he:
                        logger.debug(f"[AUTH MONITOR] Hook injection note: {he}")

                    # 2. Extract authentic cookies from native WebView2 instance
                    cookies_dict = {}
                    try:
                        from webview.platforms.winforms import BrowserView
                        inst = BrowserView.instances.get(login_win.uid)
                        if inst and hasattr(inst, "get_cookies"):
                            for c in inst.get_cookies():
                                for k, morsel in c.items():
                                    cookies_dict[k] = morsel.value
                    except Exception as ce:
                        logger.debug(f"[AUTH MONITOR] Direct cookie read notice: {ce}")

                    extracted_token = token_from_js or cookies_dict.get('token') or cookies_dict.get('ssid')

                    if extracted_token or cookies_dict or payouts_from_js:
                        token_to_store = extracted_token or "active_session"
                        logger.info(f"[AUTH MONITOR] Session linked! Captured {len(cookies_dict)} cookies, payouts: {len(payouts_from_js)}")
                        self.store_session(token_to_store, email=email, cookies=cookies_dict)
                        session_captured = True

                        # Update asset registry with genuine payouts captured directly from Quotex DOM
                        if payouts_from_js:
                            from core.ingester.asset_registry import asset_registry
                            for ws_code, pct in payouts_from_js.items():
                                asset_registry.update_payout(ws_code, float(pct))

                        if on_success_callback:
                            try:
                                on_success_callback(token_to_store, cookies_dict)
                            except Exception as cb_err:
                                logger.error(f"[AUTH MONITOR] on_success_callback failed: {cb_err}")

                        # Keep the authenticated broker session active and streaming directly in the integrated terminal
                        self.broker_window = login_win
                        logger.info("[AUTH MONITOR] Quotex session active and streaming in integrated broker station.")
                        break

            except Exception as e:
                logger.debug(f"[AUTH MONITOR] Window closed or polling ended: {e}")
                break

    def launch_embedded_login(self, email: Optional[str] = None, password: Optional[str] = None, on_success_callback=None, js_api=None):
        """
        Launches an embedded native OS Webview window (WebView2 / WebKit) to qxbroker.com/en/sign-in.
        Intercepts authentic cookies and live stream when user reaches /trade.
        """
        try:
            import webview
        except ImportError:
            logger.error("[AUTH] pywebview not installed. Cannot launch embedded login window.")
            return False

        logger.info("[AUTH] Launching embedded native Webview for Quotex login...")

        def on_loaded(window):
            url = window.get_current_url() or ""
            logger.debug(f"[AUTH WEBVIEW] Loaded URL: {url}")

            # Autofill credentials if on sign-in page
            if ("sign-in" in url or "login" in url) and email and password:
                js_email = json.dumps(email)
                js_pass = json.dumps(password)
                js_fill = f"""
                try {{
                    const emailInput = document.querySelector('input[type="email"], input[name="email"]');
                    const passInput = document.querySelector('input[type="password"], input[name="password"]');
                    if (emailInput && !emailInput.value) {{
                        emailInput.value = {js_email};
                        emailInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }}
                    if (passInput && !passInput.value) {{
                        passInput.value = {js_pass};
                        passInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }}
                }} catch(e) {{}}
                """
                window.evaluate_js(js_fill)

        is_gui_running = len(webview.windows) > 0

        login_win = webview.create_window(
            title="TradePulse — Connect Quotex Broker Account",
            url=QUOTEX_SIGNIN_URL,
            width=680,
            height=780,
            resizable=True,
            js_api=js_api
        )
        login_win.events.loaded += on_loaded

        # Launch active SPA polling thread
        t = threading.Thread(
            target=self._monitor_auth_window,
            args=(login_win, email, on_success_callback),
            daemon=True
        )
        t.start()

        # Only call webview.start() if the GUI event loop isn't already active
        if not is_gui_running:
            webview.start()

        return True


auth_manager = AuthManager()
