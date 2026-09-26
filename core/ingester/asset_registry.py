"""
TradePulse Asset Registry & Dynamic Payout Tracker
Maintains bidirectional mappings between user-friendly display symbols (e.g. "USD/INR (OTC)")
and Quotex internal WebSocket codes ("USDINR_otc"), along with real-time payout tracking.
Zero fake data: all payouts and quotes stream directly from genuine broker feeds.
"""
import logging
import threading
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Quotex authentic payout validation bounds
MIN_VALID_PAYOUT = 70.0          # Quotex OTC binary option payouts are 70-98%
MIN_VALID_REGULAR_PAYOUT = 20.0  # Quotex regular market pairs range 20-70% during off-peak

# Registered Asset definitions with ws mappings, display precision, authentic payouts and categories.
REGISTERED_ASSETS = [
    # Forex OTC Pairs (Real Quotex active tradable pairs)
    {"symbol": "USD/INR (OTC)", "ws_asset": "USDINR_otc", "precision": 4, "category": "currencies", "is_otc": True},
    {"symbol": "USD/BRL (OTC)", "ws_asset": "BRLUSD_otc", "precision": 4, "category": "currencies", "is_otc": True},
    {"symbol": "USD/PKR (OTC)", "ws_asset": "USDPKR_otc", "precision": 4, "category": "currencies", "is_otc": True},
    {"symbol": "USD/BDT (OTC)", "ws_asset": "USDBDT_otc", "precision": 4, "category": "currencies", "is_otc": True},
    {"symbol": "USD/MXN (OTC)", "ws_asset": "USDMXN_otc", "precision": 4, "category": "currencies", "is_otc": True},
    {"symbol": "USD/ZAR (OTC)", "ws_asset": "USDZAR_otc", "precision": 4, "category": "currencies", "is_otc": True},
    {"symbol": "USD/IDR (OTC)", "ws_asset": "USDIDR_otc", "precision": 4, "category": "currencies", "is_otc": True},
    {"symbol": "USD/DZD (OTC)", "ws_asset": "USDDZD_otc", "precision": 4, "category": "currencies", "is_otc": True},
    {"symbol": "USD/NGN (OTC)", "ws_asset": "USDNGN_otc", "precision": 4, "category": "currencies", "is_otc": True},
    {"symbol": "USD/EGP (OTC)", "ws_asset": "USDEGP_otc", "precision": 4, "category": "currencies", "is_otc": True},
    {"symbol": "USD/ARS (OTC)", "ws_asset": "USDARS_otc", "precision": 4, "category": "currencies", "is_otc": True},
    {"symbol": "USD/COP (OTC)", "ws_asset": "USDCOP_otc", "precision": 4, "category": "currencies", "is_otc": True},
    {"symbol": "USD/PHP (OTC)", "ws_asset": "USDPHP_otc", "precision": 4, "category": "currencies", "is_otc": True},
    {"symbol": "EUR/USD (OTC)", "ws_asset": "EURUSD_otc", "precision": 5, "category": "currencies", "is_otc": True},
    {"symbol": "GBP/USD (OTC)", "ws_asset": "GBPUSD_otc", "precision": 5, "category": "currencies", "is_otc": True},
    {"symbol": "USD/JPY (OTC)", "ws_asset": "USDJPY_otc", "precision": 3, "category": "currencies", "is_otc": True},
    {"symbol": "USD/CHF (OTC)", "ws_asset": "USDCHF_otc", "precision": 5, "category": "currencies", "is_otc": True},
    {"symbol": "USD/CAD (OTC)", "ws_asset": "USDCAD_otc", "precision": 5, "category": "currencies", "is_otc": True},
    {"symbol": "AUD/USD (OTC)", "ws_asset": "AUDUSD_otc", "precision": 5, "category": "currencies", "is_otc": True},
    {"symbol": "NZD/USD (OTC)", "ws_asset": "NZDUSD_otc", "precision": 5, "category": "currencies", "is_otc": True},
    {"symbol": "EUR/GBP (OTC)", "ws_asset": "EURGBP_otc", "precision": 5, "category": "currencies", "is_otc": True},
    {"symbol": "EUR/JPY (OTC)", "ws_asset": "EURJPY_otc", "precision": 3, "category": "currencies", "is_otc": True},
    {"symbol": "EUR/NZD (OTC)", "ws_asset": "EURNZD_otc", "precision": 5, "category": "currencies", "is_otc": True},
    {"symbol": "EUR/AUD (OTC)", "ws_asset": "EURAUD_otc", "precision": 5, "category": "currencies", "is_otc": True},
    {"symbol": "EUR/CAD (OTC)", "ws_asset": "EURCAD_otc", "precision": 5, "category": "currencies", "is_otc": True},
    {"symbol": "EUR/CHF (OTC)", "ws_asset": "EURCHF_otc", "precision": 5, "category": "currencies", "is_otc": True},
    {"symbol": "GBP/JPY (OTC)", "ws_asset": "GBPJPY_otc", "precision": 3, "category": "currencies", "is_otc": True},
    {"symbol": "GBP/NZD (OTC)", "ws_asset": "GBPNZD_otc", "precision": 5, "category": "currencies", "is_otc": True},
    {"symbol": "GBP/AUD (OTC)", "ws_asset": "GBPAUD_otc", "precision": 5, "category": "currencies", "is_otc": True},
    {"symbol": "GBP/CAD (OTC)", "ws_asset": "GBPCAD_otc", "precision": 5, "category": "currencies", "is_otc": True},
    {"symbol": "GBP/CHF (OTC)", "ws_asset": "GBPCHF_otc", "precision": 5, "category": "currencies", "is_otc": True},
    {"symbol": "AUD/CAD (OTC)", "ws_asset": "AUDCAD_otc", "precision": 5, "category": "currencies", "is_otc": True},
    {"symbol": "AUD/CHF (OTC)", "ws_asset": "AUDCHF_otc", "precision": 5, "category": "currencies", "is_otc": True},
    {"symbol": "AUD/JPY (OTC)", "ws_asset": "AUDJPY_otc", "precision": 3, "category": "currencies", "is_otc": True},
    {"symbol": "AUD/NZD (OTC)", "ws_asset": "AUDNZD_otc", "precision": 5, "category": "currencies", "is_otc": True},
    {"symbol": "CAD/CHF (OTC)", "ws_asset": "CADCHF_otc", "precision": 5, "category": "currencies", "is_otc": True},
    {"symbol": "CAD/JPY (OTC)", "ws_asset": "CADJPY_otc", "precision": 3, "category": "currencies", "is_otc": True},
    {"symbol": "CHF/JPY (OTC)", "ws_asset": "CHFJPY_otc", "precision": 3, "category": "currencies", "is_otc": True},
    {"symbol": "NZD/JPY (OTC)", "ws_asset": "NZDJPY_otc", "precision": 3, "category": "currencies", "is_otc": True},
    {"symbol": "NZD/CAD (OTC)", "ws_asset": "NZDCAD_otc", "precision": 5, "category": "currencies", "is_otc": True},
    {"symbol": "NZD/CHF (OTC)", "ws_asset": "NZDCHF_otc", "precision": 5, "category": "currencies", "is_otc": True},

    # Regular Market Forex Pairs (Quotex standard currency pairs)
    {"symbol": "EUR/USD", "ws_asset": "EURUSD", "precision": 5, "category": "currencies", "is_otc": False},
    {"symbol": "GBP/USD", "ws_asset": "GBPUSD", "precision": 5, "category": "currencies", "is_otc": False},
    {"symbol": "USD/JPY", "ws_asset": "USDJPY", "precision": 3, "category": "currencies", "is_otc": False},
    {"symbol": "USD/CAD", "ws_asset": "USDCAD", "precision": 5, "category": "currencies", "is_otc": False},
    {"symbol": "USD/CHF", "ws_asset": "USDCHF", "precision": 5, "category": "currencies", "is_otc": False},
    {"symbol": "AUD/USD", "ws_asset": "AUDUSD", "precision": 5, "category": "currencies", "is_otc": False},
    {"symbol": "NZD/USD", "ws_asset": "NZDUSD", "precision": 5, "category": "currencies", "is_otc": False},
    {"symbol": "CAD/JPY", "ws_asset": "CADJPY", "precision": 3, "category": "currencies", "is_otc": False},
    {"symbol": "GBP/JPY", "ws_asset": "GBPJPY", "precision": 3, "category": "currencies", "is_otc": False},
    {"symbol": "EUR/JPY", "ws_asset": "EURJPY", "precision": 3, "category": "currencies", "is_otc": False},
    {"symbol": "AUD/JPY", "ws_asset": "AUDJPY", "precision": 3, "category": "currencies", "is_otc": False},
    {"symbol": "CHF/JPY", "ws_asset": "CHFJPY", "precision": 3, "category": "currencies", "is_otc": False},
    {"symbol": "EUR/CHF", "ws_asset": "EURCHF", "precision": 5, "category": "currencies", "is_otc": False},
    {"symbol": "EUR/GBP", "ws_asset": "EURGBP", "precision": 5, "category": "currencies", "is_otc": False},
    {"symbol": "EUR/AUD", "ws_asset": "EURAUD", "precision": 5, "category": "currencies", "is_otc": False},
    {"symbol": "EUR/CAD", "ws_asset": "EURCAD", "precision": 5, "category": "currencies", "is_otc": False},
    {"symbol": "EUR/NZD", "ws_asset": "EURNZD", "precision": 5, "category": "currencies", "is_otc": False},
    {"symbol": "GBP/AUD", "ws_asset": "GBPAUD", "precision": 5, "category": "currencies", "is_otc": False},
    {"symbol": "GBP/CAD", "ws_asset": "GBPCAD", "precision": 5, "category": "currencies", "is_otc": False},
    {"symbol": "GBP/CHF", "ws_asset": "GBPCHF", "precision": 5, "category": "currencies", "is_otc": False},
    {"symbol": "GBP/NZD", "ws_asset": "GBPNZD", "precision": 5, "category": "currencies", "is_otc": False},
    {"symbol": "AUD/CAD", "ws_asset": "AUDCAD", "precision": 5, "category": "currencies", "is_otc": False},
    {"symbol": "AUD/CHF", "ws_asset": "AUDCHF", "precision": 5, "category": "currencies", "is_otc": False},
    {"symbol": "AUD/NZD", "ws_asset": "AUDNZD", "precision": 5, "category": "currencies", "is_otc": False},
    {"symbol": "CAD/CHF", "ws_asset": "CADCHF", "precision": 5, "category": "currencies", "is_otc": False},
    {"symbol": "NZD/CAD", "ws_asset": "NZDCAD", "precision": 5, "category": "currencies", "is_otc": False},
    {"symbol": "NZD/CHF", "ws_asset": "NZDCHF", "precision": 5, "category": "currencies", "is_otc": False},
    {"symbol": "NZD/JPY", "ws_asset": "NZDJPY", "precision": 3, "category": "currencies", "is_otc": False},

    # Crypto & Commodities OTC and Real Market (Authentic Quotex display labels)
    {"symbol": "GOLD (OTC)", "ws_asset": "XAUUSD_otc", "precision": 2, "category": "commodities", "is_otc": True},
    {"symbol": "SILVER (OTC)", "ws_asset": "XAGUSD_otc", "precision": 3, "category": "commodities", "is_otc": True},
    {"symbol": "Gold", "ws_asset": "XAUUSD", "precision": 2, "category": "commodities", "is_otc": False},
    {"symbol": "Silver", "ws_asset": "XAGUSD", "precision": 3, "category": "commodities", "is_otc": False},
    {"symbol": "UK BRENT (OTC)", "ws_asset": "UKBrent_otc", "precision": 2, "category": "commodities", "is_otc": True},
    {"symbol": "US CRUDE (OTC)", "ws_asset": "USCrude_otc", "precision": 2, "category": "commodities", "is_otc": True},
    {"symbol": "Natural Gas (OTC)", "ws_asset": "XNGUSD_otc", "precision": 3, "category": "commodities", "is_otc": True},
    {"symbol": "Bitcoin (OTC)", "ws_asset": "BTCUSD_otc", "precision": 2, "category": "crypto", "is_otc": True},
    {"symbol": "Ethereum (OTC)", "ws_asset": "ETHUSD_otc", "precision": 2, "category": "crypto", "is_otc": True},
    {"symbol": "Chainlink (OTC)", "ws_asset": "LINKUSD_otc", "precision": 3, "category": "crypto", "is_otc": True},
    {"symbol": "Avalanche (OTC)", "ws_asset": "AVAXUSD_otc", "precision": 3, "category": "crypto", "is_otc": True},
    {"symbol": "Ethereum Classic (OTC)", "ws_asset": "ETCUSD_otc", "precision": 3, "category": "crypto", "is_otc": True},
    {"symbol": "Toncoin (OTC)", "ws_asset": "TONUSD_otc", "precision": 3, "category": "crypto", "is_otc": True},
    {"symbol": "Trump (OTC)", "ws_asset": "TRUMPUSD_otc", "precision": 3, "category": "crypto", "is_otc": True},
    {"symbol": "Ripple (OTC)", "ws_asset": "XRPUSD_otc", "precision": 4, "category": "crypto", "is_otc": True},
    {"symbol": "Zcash (OTC)", "ws_asset": "ZECUSD_otc", "precision": 3, "category": "crypto", "is_otc": True},
    {"symbol": "Litecoin (OTC)", "ws_asset": "LTCUSD_otc", "precision": 2, "category": "crypto", "is_otc": True},
    {"symbol": "Bitcoin Cash (OTC)", "ws_asset": "BCHUSD_otc", "precision": 2, "category": "crypto", "is_otc": True},
    {"symbol": "Binance Coin (OTC)", "ws_asset": "BNBUSD_otc", "precision": 2, "category": "crypto", "is_otc": True},
    {"symbol": "Polkadot (OTC)", "ws_asset": "DOTUSD_otc", "precision": 3, "category": "crypto", "is_otc": True},
    {"symbol": "Axie Infinity (OTC)", "ws_asset": "AXSUSD_otc", "precision": 3, "category": "crypto", "is_otc": True},
    {"symbol": "Dash (OTC)", "ws_asset": "DASHUSD_otc", "precision": 2, "category": "crypto", "is_otc": True},
    {"symbol": "Cosmos (OTC)", "ws_asset": "ATOUSD_otc", "precision": 4, "category": "crypto", "is_otc": True},
    {"symbol": "Solana (OTC)", "ws_asset": "SOLUSD_otc", "precision": 2, "category": "crypto", "is_otc": True},

    # Indices & Stocks (Authentic Quotex display labels)
    {"symbol": "S&P/ASX 200", "ws_asset": "ASX200", "precision": 1, "category": "stocks", "is_otc": False},
    {"symbol": "FTSE 100", "ws_asset": "FTSE100", "precision": 1, "category": "stocks", "is_otc": False},
    {"symbol": "IBEX 35", "ws_asset": "IBEX35", "precision": 1, "category": "stocks", "is_otc": False},
    {"symbol": "Nikkei 225", "ws_asset": "Nikkei225", "precision": 1, "category": "stocks", "is_otc": False},
    {"symbol": "EURO STOXX 50", "ws_asset": "STOXX50", "precision": 1, "category": "stocks", "is_otc": False},
    {"symbol": "CAC 40", "ws_asset": "CAC40", "precision": 1, "category": "stocks", "is_otc": False},
    {"symbol": "Hong Kong 50", "ws_asset": "HongKong50", "precision": 1, "category": "stocks", "is_otc": False},
    {"symbol": "FTSE China A50 Index", "ws_asset": "FTSEChinaA50", "precision": 1, "category": "stocks", "is_otc": False},
]

# Aliases for backwards compatibility with previous configurations and broker variations
SYMBOL_ALIASES = {
    "UK BRENT (OTC)": "UKBrent_otc",
    "US CRUDE (OTC)": "USCrude_otc",
    "UKBrent (OTC)": "UKBrent_otc",
    "USCrude (OTC)": "USCrude_otc",
    "Gold (OTC)": "XAUUSD_otc",
    "Silver (OTC)": "XAGUSD_otc",
    "Gold": "XAUUSD",
    "Silver": "XAGUSD",
    "XAU/USD": "XAUUSD",
    "XAG/USD": "XAGUSD",
    "XAU/USD (OTC)": "XAUUSD_otc",
    "XAG/USD (OTC)": "XAGUSD_otc",
    "BTC/USD (OTC)": "BTCUSD_otc",
    "ETH/USD (OTC)": "ETHUSD_otc",
    "BTC/USDT (OTC)": "BTCUSD_otc",
    "ETH/USDT (OTC)": "ETHUSD_otc",
    "BTCUSD": "BTCUSD_otc",
    "ETHUSD": "ETHUSD_otc",
    "USD/BRL (OTC)": "BRLUSD_otc",
    "USDBRL_otc": "USD/BRL (OTC)",
    "BRLUSD_otc": "USD/BRL (OTC)",
    "AUDCHF_otc": "AUD/CHF (OTC)",
    "N225": "Nikkei225",
    "FTXIN9": "FTSEChinaA50",
    "Solana (OTC)": "SOLUSD_otc",
    "SOLUSD_otc": "Solana (OTC)",
    "SOL/USD (OTC)": "SOLUSD_otc",
    "SOL/USDT (OTC)": "SOLUSD_otc",
}


class AssetRegistry:
    """Manages active asset definitions, dynamic auto-registration, and real-time payout tracking. Thread-safe."""

    def __init__(self, load_cache: bool = True):
        self._lock = threading.RLock()
        self._symbol_to_ws: Dict[str, str] = {}
        self._ws_to_symbol: Dict[str, str] = {}
        self._payouts: Dict[str, float] = {}
        self._precisions: Dict[str, int] = {}
        self._categories: Dict[str, str] = {}
        self._latest_prices: Dict[str, float] = {}
        self._price_sources: Dict[str, str] = {}
        self._registered_asset_list: List[dict] = []
        self._payout_callbacks: List[Callable[[str, float], None]] = []
        self._asset_added_callbacks: List[Callable[[dict], None]] = []
        # Tracks which symbols received a live payout update in THIS session.
        # Used by get_live_payouts() to distinguish genuinely fresh data from
        # stale disk-cache entries that were loaded at construction time.
        self._live_session_payouts: set = set()

        for item in REGISTERED_ASSETS:
            sym = item["symbol"]
            ws = item["ws_asset"]
            self._symbol_to_ws[sym] = ws
            self._ws_to_symbol[ws] = sym
            self._precisions[sym] = item.get("precision", 5)
            self._categories[sym] = item.get("category", "currencies")
            self._registered_asset_list.append(dict(item))

        for alias, ws in SYMBOL_ALIASES.items():
            if ws in self._ws_to_symbol:
                self._symbol_to_ws[alias] = ws
                if alias not in self._ws_to_symbol:
                    self._ws_to_symbol[alias] = self._ws_to_symbol[ws]
            elif alias in self._symbol_to_ws:
                self._ws_to_symbol[ws] = self._symbol_to_ws[alias]

        if load_cache:
            self.load_cached_payouts()

    def add_payout_callback(self, callback: Callable[[str, float], None]):
        """Registers a listener for live payout updates."""
        with self._lock:
            if callback not in self._payout_callbacks:
                self._payout_callbacks.append(callback)

    def add_asset_added_callback(self, callback: Callable[[dict], None]):
        """Registers a listener for new dynamically registered assets."""
        with self._lock:
            if callback not in self._asset_added_callbacks:
                self._asset_added_callbacks.append(callback)

    def get_all_symbols(self) -> List[str]:
        with self._lock:
            return [item["symbol"] for item in self._registered_asset_list]

    def get_all_ws_assets(self) -> List[str]:
        with self._lock:
            return list(self._ws_to_symbol.keys())

    def get_all_asset_defs(self) -> List[dict]:
        """Returns copies of all registered assets (OTC, Forex, Crypto, Commodities)."""
        with self._lock:
            result = []
            for item in self._registered_asset_list:
                d = dict(item)
                d["data_source"] = "quotex_otc" if d.get("is_otc") else "real_market_api"
                result.append(d)
            return result

    def get_otc_symbols(self) -> List[str]:
        with self._lock:
            return [item["symbol"] for item in self._registered_asset_list if item.get("is_otc")]

    def get_real_market_symbols(self) -> List[str]:
        with self._lock:
            return [item["symbol"] for item in self._registered_asset_list if not item.get("is_otc")]

    def filter_real_currencies_only(self):
        """
        Configures the asset registry for TradePulse Personal:
        Retains ONLY authentic real Forex market currency pairs (e.g. EUR/USD, GBP/USD, USD/JPY, etc.)
        and strictly excludes all OTC, commodities, crypto, and index instruments.
        """
        with self._lock:
            self._real_currencies_only = True
            filtered_list = []
            for item in self._registered_asset_list:
                sym = item.get("symbol", "")
                is_otc = item.get("is_otc", False) or "(OTC)" in sym or "_otc" in item.get("ws_asset", "").lower()
                cat = item.get("category", "").lower()
                if not is_otc and cat == "currencies" and "/" in sym:
                    filtered_list.append(dict(item))
            self._registered_asset_list = filtered_list

            # Rebuild symbol mappings
            self._symbol_to_ws = {item["symbol"]: item["ws_asset"] for item in self._registered_asset_list}
            self._ws_to_symbol = {item["ws_asset"]: item["symbol"] for item in self._registered_asset_list}
            self._precisions = {item["symbol"]: item.get("precision", 5) for item in self._registered_asset_list}
            self._categories = {item["symbol"]: "currencies" for item in self._registered_asset_list}
            logger.info(f"[ASSET REGISTRY] Personal Edition mode active: Filtered to {len(self._registered_asset_list)} real Forex currency pairs (NO OTC).")

    def register_dynamic_asset(
        self,
        ws_code: str,
        display_name: Optional[str] = None,
        category: str = "currencies",
        precision: int = 5,
        payout: Optional[float] = None
    ) -> str:
        """
        Dynamically registers or updates an authentic asset received from broker instruments frame.
        Guarantees that any trade or currency offered by Quotex is recognized and streamed in real-time.
        """
        if not ws_code:
            return ""

        is_otc = "_otc" in ws_code.lower() or (display_name and "(OTC)" in display_name)
        if getattr(self, "_real_currencies_only", False):
            if is_otc or category != "currencies":
                return ""

        # Determine canonical display symbol (prevent raw codes like EURUSD_otc from overriding)
        sym = None
        if display_name and not display_name.endswith("_otc") and not display_name.endswith("_OTC"):
            if "/" in display_name or " " in display_name or "(" in display_name:
                sym = display_name
            else:
                sym = self.ws_to_symbol(display_name)

        if not sym:
            sym = self.ws_to_symbol(ws_code)

        is_otc = "_otc" in ws_code.lower() or (sym and "(OTC)" in sym)

        if not sym:
            # Derive canonical display name e.g. "BRLUSD_otc" -> "USD/BRL (OTC)", "CADJPY" -> "CAD/JPY"
            clean = ws_code.replace("_otc", "").replace("_OTC", "").strip()
            if clean.upper() == "BRLUSD":
                sym = "USD/BRL" + (" (OTC)" if is_otc else "")
            elif len(clean) == 6 and clean.isalpha():
                base = clean[:3].upper()
                quote = clean[3:].upper()
                sym = f"{base}/{quote}" + (" (OTC)" if is_otc else "")
            else:
                sym = clean + (" (OTC)" if is_otc else "")

        cat = (category or "currencies").lower()
        if "crypto" in cat:
            cat = "crypto"
        elif "commodit" in cat:
            cat = "commodities"
        elif "stock" in cat:
            cat = "stocks"
        else:
            cat = "currencies"

        new_entry = None
        with self._lock:
            clean_sym = sym.lower().replace(" ", "").replace("_", "")
            existing = next(
                (item for item in self._registered_asset_list 
                 if item["ws_asset"].lower() == ws_code.lower() or 
                    item["symbol"].lower().replace(" ", "").replace("_", "") == clean_sym), 
                None
            )
            if existing:
                sym = existing["symbol"]
                existing["ws_asset"] = ws_code
                existing["precision"] = precision
                existing["category"] = cat
                existing["is_otc"] = is_otc
            else:
                new_entry = {
                    "symbol": sym,
                    "ws_asset": ws_code,
                    "precision": precision,
                    "category": cat,
                    "is_otc": is_otc
                }
                self._registered_asset_list.append(new_entry)
                logger.info(f"[ASSET REGISTRY] Dynamically registered asset: {sym} ({ws_code}) [{cat}]")

            self._symbol_to_ws[sym] = ws_code
            self._ws_to_symbol[ws_code] = sym
            self._precisions[sym] = precision
            self._categories[sym] = cat
            if display_name and display_name != sym:
                self._symbol_to_ws[display_name] = ws_code

        if payout is not None:
            self.update_payout(ws_code, payout)

        if new_entry:
            for cb in list(self._asset_added_callbacks):
                try:
                    cb(new_entry)
                except Exception as e:
                    logger.debug(f"[ASSET ADDED CB ERR] {e}")

        return sym

    def symbol_to_ws(self, symbol: str) -> Optional[str]:
        """Converts display symbol (e.g. 'USD/INR (OTC)') to WS code ('USDINR_otc')."""
        if not symbol:
            return None
        with self._lock:
            if symbol in self._symbol_to_ws:
                return self._symbol_to_ws[symbol]
            is_otc = "(OTC)" in symbol.upper() or "_OTC" in symbol.upper()
            clean = symbol.upper().replace("(OTC)", "").replace("/", "").replace(" ", "").replace("_", "").strip()
            # Strict OTC matching first
            for sym, ws in self._symbol_to_ws.items():
                ws_is_otc = "_otc" in ws.lower() or "(otc)" in sym.lower()
                if is_otc != ws_is_otc:
                    continue
                sym_clean = sym.upper().replace("(OTC)", "").replace("/", "").replace(" ", "").replace("_", "").strip()
                ws_clean = ws.upper().replace("_OTC", "").replace("/", "").replace(" ", "").replace("_", "").strip()
                if clean in (sym_clean, ws_clean):
                    return ws
            # Fallback fuzzy match
            for sym, ws in self._symbol_to_ws.items():
                if clean.lower() in ws.replace("_otc", "").lower():
                    return ws
            return None

    def ws_to_symbol(self, ws_asset: str) -> Optional[str]:
        """Converts WS code ('USDINR_otc', 'BRLUSD_otc', 'CADJPY') to display symbol ('USD/INR (OTC)', 'CAD/JPY')."""
        if not ws_asset:
            return None
        with self._lock:
            if ws_asset in self._ws_to_symbol:
                return self._ws_to_symbol[ws_asset]
            if ws_asset in self._symbol_to_ws:
                return ws_asset

            # Check special case BRLUSD
            if "brlusd" in ws_asset.lower():
                return "USD/BRL (OTC)" if "_otc" in ws_asset.lower() else "USD/BRL"

            is_otc = "_otc" in ws_asset.lower() or "(otc)" in ws_asset.lower()

            # Normalize stripped name: remove _otc, (otc), underscores, slashes, spaces
            clean = (
                ws_asset.lower()
                .replace("_otc", "")
                .replace("(otc)", "")
                .replace("_", "")
                .replace("/", "")
                .replace(" ", "")
                .strip()
            )
            for ws, sym in self._ws_to_symbol.items():
                ws_is_otc = "_otc" in ws.lower() or "(otc)" in sym.lower()
                if is_otc != ws_is_otc:
                    continue
                ws_clean = ws.lower().replace("_otc", "").replace("(otc)", "").replace("_", "").replace("/", "").replace(" ", "").strip()
                sym_clean = sym.lower().replace("(otc)", "").replace("_", "").replace("/", "").replace(" ", "").strip()
                if clean in (ws_clean, sym_clean):
                    return sym
                if "brent" in clean and "brent" in ws_clean:
                    return sym
                if "crude" in clean and "crude" in ws_clean:
                    return sym

            # Check standard 6-character forex pairs like CADJPY or EURUSD
            if len(clean) == 6 and clean.isalpha():
                base = clean[:3].upper()
                quote = clean[3:].upper()
                return f"{base}/{quote}" + (" (OTC)" if is_otc else "")

            return None

    def normalize_ws_symbol(self, ws_asset: str) -> Optional[str]:
        """Alias for ws_to_symbol."""
        return self.ws_to_symbol(ws_asset)

    def load_cached_payouts(self):
        """
        Restores confirmed broker payouts from local disk cache.

        IMPORTANT: These cached payouts are NOT tagged as live-session data.
        They are available via get_all_payouts() for offline use cases like
        backtesting and strategy testing where staleness is acceptable, but
        must NOT be surfaced in the Live Monitor UI as if they were current.
        Use get_live_payouts() for anything shown to the user as "live".
        """
        try:
            import json
            from core.config import settings
            cache_file = settings.resolved_data_dir / "payouts_cache.json"
            if cache_file.exists():
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    loaded = 0
                    with self._lock:
                        for k, v in data.items():
                            sym = self.ws_to_symbol(k) or k
                            if isinstance(v, (int, float)) and 20.0 <= float(v) <= 100.0:
                                self._payouts[sym] = round(float(v), 1)
                                # NOTE: Deliberately NOT adding to _live_session_payouts.
                                # Cached values must not appear as live until confirmed
                                # by a real broker update in this session.
                                loaded += 1
                    logger.info(f"[ASSET REGISTRY] Restored {loaded} cached payouts (offline use only, not shown as live).")
        except Exception as e:
            logger.debug(f"[ASSET REGISTRY] Could not load payouts cache: {e}")

    def save_payouts_cache(self):
        """Persists confirmed live payouts to disk."""
        try:
            import json
            from core.config import settings
            cache_file = settings.resolved_data_dir / "payouts_cache.json"
            with self._lock:
                data = dict(self._payouts)
            if data:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
        except Exception as e:
            logger.debug(f"[ASSET REGISTRY] Could not save payouts cache: {e}")

    def get_payout(self, symbol: str) -> Optional[float]:
        """Returns current live payout percentage for a symbol or ws code, or None if not yet received."""
        if not symbol:
            return None
        with self._lock:
            if symbol in self._payouts:
                return self._payouts[symbol]
            sym = self.ws_to_symbol(symbol)
            if sym and sym in self._payouts:
                return self._payouts[sym]
            ws = self.symbol_to_ws(symbol)
            if ws and ws in self._payouts:
                return self._payouts[ws]
            return None

    def get_all_payouts(self) -> Dict[str, float]:
        """
        Returns ALL payouts (including stale disk-cached ones) mapped to display symbols.
        Suitable for offline use cases like backtesting where staleness is acceptable.
        For live UI display, use get_live_payouts() instead.
        """
        with self._lock:
            res = {}
            for k, v in self._payouts.items():
                display_sym = self.ws_to_symbol(k) or k
                res[display_sym] = v
            return res

    def get_live_payouts(self) -> Dict[str, float]:
        """
        Returns ONLY payouts that were confirmed by a real broker update in this session.
        This is the correct source for anything shown in the Live Monitor UI.
        Excludes stale disk-cached values that haven't been re-confirmed this session.
        """
        with self._lock:
            res = {}
            for k, v in self._payouts.items():
                display_sym = self.ws_to_symbol(k) or k
                if display_sym in self._live_session_payouts or k in self._live_session_payouts:
                    res[display_sym] = v
            return res

    def update_payout(self, ws_asset: str, payout_pct: float):
        """Updates live payout percentage dynamically from WebSocket stream or DOM."""
        sym = self.ws_to_symbol(ws_asset) or ws_asset
        callbacks = []
        val = 0.0

        is_otc = "(OTC)" in sym or "_otc" in ws_asset.lower()
        min_payout = MIN_VALID_PAYOUT if is_otc else MIN_VALID_REGULAR_PAYOUT

        with self._lock:
            if payout_pct and payout_pct >= min_payout and payout_pct <= 100.0:
                val = round(float(payout_pct), 1)
                self._payouts[sym] = val
                self._live_session_payouts.add(sym)  # Mark as confirmed-live this session
                callbacks = list(self._payout_callbacks)
                logger.info(f"[PAYOUT UPDATE] {sym} -> {val}%")

        if val > 0:
            self.save_payouts_cache()

        for cb in callbacks:
            try:
                cb(sym, val)
            except Exception as e:
                logger.warning(f"[PAYOUT CALLBACK ERR] {e}", exc_info=True)

    def get_latest_price(self, symbol: str) -> Optional[float]:
        if not symbol:
            return None
        with self._lock:
            if symbol in self._latest_prices:
                return self._latest_prices[symbol]
            sym = self.ws_to_symbol(symbol)
            if sym and sym in self._latest_prices:
                return self._latest_prices[sym]
            ws = self.symbol_to_ws(symbol)
            if ws and ws in self._latest_prices:
                return self._latest_prices[ws]
            return None

    def get_all_prices(self) -> Dict[str, float]:
        """Returns all prices mapped to display symbols."""
        with self._lock:
            res = {}
            for k, v in self._latest_prices.items():
                display_sym = self.ws_to_symbol(k) or k
                res[display_sym] = v
            return res

    def update_latest_price(self, symbol: str, price: float, source: str = "unknown"):
        """Records the latest confirmed price tick for an asset along with its origin source."""
        if not symbol:
            return
        display_sym = self.ws_to_symbol(symbol) or symbol
        with self._lock:
            self._latest_prices[display_sym] = float(price)
            self._price_sources[display_sym] = str(source)
            if display_sym != symbol:
                self._latest_prices[symbol] = float(price)
                self._price_sources[symbol] = str(source)

    def get_price_source(self, symbol: str) -> str:
        """Returns the origin source of the latest price for an asset."""
        if not symbol:
            return "unknown"
        with self._lock:
            if symbol in self._price_sources:
                return self._price_sources[symbol]
            sym = self.ws_to_symbol(symbol)
            if sym and sym in self._price_sources:
                return self._price_sources[sym]
            return "unknown"

    def get_all_price_sources(self) -> Dict[str, str]:
        """Returns all price origin sources mapped to display symbols."""
        with self._lock:
            res = {}
            for k, v in self._price_sources.items():
                display_sym = self.ws_to_symbol(k) or k
                res[display_sym] = v
            return res

    def get_precision(self, symbol: str) -> int:
        """Returns institutional precision for that currency."""
        with self._lock:
            if symbol in self._precisions:
                return self._precisions[symbol]
            ws_code = self._symbol_to_ws.get(symbol)
            if ws_code and ws_code in self._precisions:
                return self._precisions[ws_code]
            sym_u = (symbol or "").upper()
            if "JPY" in sym_u:
                return 3
            if any(em in sym_u for em in ["INR", "BRL", "PKR", "BDT", "EGP", "PHP", "TRY", "IDR", "ZAR", "MXN"]):
                return 4
            return 5

    def format_price(self, symbol: str, price: float) -> str:
        """Formats price with exact institutional precision for that currency."""
        prec = self.get_precision(symbol)
        return f"{price:.{prec}f}"


asset_registry = AssetRegistry()
