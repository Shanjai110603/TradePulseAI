"""
TradePulse Telegram Manager — Centralized Bot & Message Configuration Suite
============================================================================
Manages multi-channel Telegram destinations, event dispatch filters,
custom message templates with dynamic token interpolation, and live state persistence.
"""
import json
import logging
import os
import re
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("TradePulse.TelegramManager")

DEFAULT_TEMPLATES = {
    "signal": (
        "🚀 <b>SIGNAL ALERT: {strategy}</b>\n"
        "────────────────────────\n"
        "📊 <b>Asset:</b> <code>{asset}</code>\n"
        "💰 <b>OTC Payout:</b> <b>{payout}%</b>\n"
        "{arrow} <b>Direction:</b> <b>{direction}</b>\n"
        "⏱ <b>Timeframe:</b> <b>{timeframe}</b>\n"
        "⌛ <b>Expiry Duration:</b> <b>{expiry} Mins</b>\n"
        "🕒 <b>Entry Time:</b> <b>Next Candle Open (00s) | {entry_time} IST</b>\n"
        "💵 <b>Entry Price:</b> <code>{entry_price}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "{confluence_section}"
        "🎯 <b>Setup Quality Score:</b> <b>{confidence}% ({tier})</b>\n"
        "{stake_line}"
        "{ev_line}"
        "⏰ <b>Expiry Target:</b> <b>{expiry_time} IST</b>\n"
        "🔒 <i>TradePulse VIP Institutional Signal</i>"
    ),
    "pre_signal": (
        "⚡ <b>PRE-SIGNAL RADAR: PREPARE ENTRY</b>\n"
        "────────────────────────\n"
        "📊 <b>Asset:</b> <code>{asset}</code>\n"
        "🎯 <b>Direction:</b> <b>{dir_badge}</b>\n"
        "⏱ <b>Timeframe:</b> <b>{timeframe}</b> (Expiry: {expiry}m)\n"
        "💰 <b>Payout:</b> <b>{payout}%</b>\n"
        "⏳ <b>Candle Close In:</b> <b>~{remaining_seconds}s</b>\n"
        "🧠 <b>Forming Pattern:</b> {strategy}\n"
        "{stake_line}"
        "────────────────────────\n"
        "<i>Prepare pair & stake in Quotex. Official entry fires on candle close.</i>"
    ),
    "outcome": (
        "{header}\n"
        "────────────────────────\n"
        "📊 <b>Asset:</b> <code>{asset}</code>\n"
        "🎯 <b>Strategy:</b> <code>{strategy}</code>\n"
        "📌 <b>Direction:</b> <b>{direction}</b>\n"
        "🏁 <b>Result:</b> <b>{outcome_badge}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💵 <b>Entry Strike:</b> <code>{entry_price}</code>\n"
        "🏁 <b>Exit Price:</b>   <code>{exit_price}</code>\n"
        "{pnl_text}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔒 <i>TradePulse 24/7 Real-Time Outcome Verification</i>"
    ),
    "circuit_breaker": (
        "🛑 <b>TRADEPULSE CIRCUIT BREAKER ACTIVATED</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ <b>Signal Scanner Auto-Paused</b>\n"
        "• <b>Trigger Reason:</b> <b>{cb_reason}</b>\n"
        "• <b>Session Net PnL:</b> <b>{net_pnl}</b>\n"
        "• <b>Total Trades:</b> <b>{total_trades}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔒 <i>Scanner halted to safeguard capital. Manage in TradePulse Terminal.</i>"
    )
}


class TelegramManager:
    """Central manager for Telegram bots, distribution channels, and customizable message templates."""

    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir:
            self.config_dir = config_dir
        else:
            try:
                from core.config import settings
                self.config_dir = settings.resolved_data_dir
            except Exception:
                self.config_dir = Path.home() / ".tradepulse"

        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "telegram_config.json"
        self._lock = threading.Lock()

        # Bot Settings
        self.bot_token: str = ""
        self.bot_username: str = ""
        self.bot_first_name: str = ""
        self.is_online: bool = False
        self.polling_enabled: bool = True

        # Multi-Channel Distribution
        self.channels: List[Dict[str, Any]] = []

        # Event Dispatch Filters ("what messages to send")
        self.send_signals: bool = True
        self.send_pre_signals: bool = True
        self.send_outcomes: bool = True
        self.send_circuit_breaker: bool = True
        self.send_news_blackouts: bool = False
        self.min_signal_score: float = 80.0
        self.min_payout_pct: float = 75.0
        self.attach_chart_photo: bool = True
        self.include_inline_buttons: bool = True

        # Customizable Templates
        self.templates: Dict[str, str] = dict(DEFAULT_TEMPLATES)

        # Load persisted settings
        self.load_from_disk()

    def get_config(self) -> Dict[str, Any]:
        """Returns full manager configuration object for frontend and bridge."""
        with self._lock:
            return {
                "bot_token": self.bot_token,
                "bot_username": self.bot_username,
                "bot_first_name": self.bot_first_name,
                "is_online": self.is_online,
                "polling_enabled": self.polling_enabled,
                "channels": list(self.channels),
                "send_signals": self.send_signals,
                "send_pre_signals": self.send_pre_signals,
                "send_outcomes": self.send_outcomes,
                "send_circuit_breaker": self.send_circuit_breaker,
                "send_news_blackouts": self.send_news_blackouts,
                "min_signal_score": self.min_signal_score,
                "min_payout_pct": self.min_payout_pct,
                "attach_chart_photo": self.attach_chart_photo,
                "include_inline_buttons": self.include_inline_buttons,
                "templates": dict(self.templates),
                "rules": {
                    "signals": self.send_signals,
                    "pre_signals": self.send_pre_signals,
                    "outcomes": self.send_outcomes,
                    "circuit_breaker": self.send_circuit_breaker,
                    "news": self.send_news_blackouts,
                    "attach_charts": self.attach_chart_photo,
                    "min_score": self.min_signal_score,
                    "min_payout": self.min_payout_pct
                }
            }

    def update_config(self, new_config: Dict[str, Any]) -> Dict[str, Any]:
        """Updates Telegram configuration fields safely."""
        with self._lock:
            if "bot_token" in new_config and new_config["bot_token"] is not None:
                self.bot_token = str(new_config["bot_token"]).strip()
            if "bot_username" in new_config and new_config["bot_username"] is not None:
                self.bot_username = str(new_config["bot_username"]).strip()
            if "bot_first_name" in new_config and new_config["bot_first_name"] is not None:
                self.bot_first_name = str(new_config["bot_first_name"]).strip()
            if "polling_enabled" in new_config and new_config["polling_enabled"] is not None:
                self.polling_enabled = bool(new_config["polling_enabled"])
            if "channels" in new_config and isinstance(new_config["channels"], list):
                self.channels = [
                    {
                        "id": str(c.get("id", "")).strip(),
                        "name": str(c.get("title") or c.get("name") or "Telegram Channel").strip(),
                        "title": str(c.get("title") or c.get("name") or "Telegram Channel").strip(),
                        "enabled": bool(c.get("enabled", True))
                    }
                    for c in new_config["channels"]
                    if str(c.get("id", "")).strip()
                ]
            if "send_signals" in new_config and new_config["send_signals"] is not None:
                self.send_signals = bool(new_config["send_signals"])
            if "send_pre_signals" in new_config and new_config["send_pre_signals"] is not None:
                self.send_pre_signals = bool(new_config["send_pre_signals"])
            if "send_outcomes" in new_config and new_config["send_outcomes"] is not None:
                self.send_outcomes = bool(new_config["send_outcomes"])
            if "send_circuit_breaker" in new_config and new_config["send_circuit_breaker"] is not None:
                self.send_circuit_breaker = bool(new_config["send_circuit_breaker"])
            if "send_news_blackouts" in new_config and new_config["send_news_blackouts"] is not None:
                self.send_news_blackouts = bool(new_config["send_news_blackouts"])
            if "min_signal_score" in new_config and new_config["min_signal_score"] is not None:
                self.min_signal_score = max(50.0, min(100.0, float(new_config["min_signal_score"])))
            if "min_payout_pct" in new_config and new_config["min_payout_pct"] is not None:
                self.min_payout_pct = max(0.0, min(100.0, float(new_config["min_payout_pct"])))
            if "attach_chart_photo" in new_config and new_config["attach_chart_photo"] is not None:
                self.attach_chart_photo = bool(new_config["attach_chart_photo"])
            if "include_inline_buttons" in new_config and new_config["include_inline_buttons"] is not None:
                self.include_inline_buttons = bool(new_config["include_inline_buttons"])

            # Support nested "rules" dict
            if "rules" in new_config and isinstance(new_config["rules"], dict):
                r = new_config["rules"]
                if "signals" in r and r["signals"] is not None:
                    self.send_signals = bool(r["signals"])
                if "pre_signals" in r and r["pre_signals"] is not None:
                    self.send_pre_signals = bool(r["pre_signals"])
                if "outcomes" in r and r["outcomes"] is not None:
                    self.send_outcomes = bool(r["outcomes"])
                if "circuit_breaker" in r and r["circuit_breaker"] is not None:
                    self.send_circuit_breaker = bool(r["circuit_breaker"])
                if "news" in r and r["news"] is not None:
                    self.send_news_blackouts = bool(r["news"])
                if "attach_charts" in r and r["attach_charts"] is not None:
                    self.attach_chart_photo = bool(r["attach_charts"])
                if "min_score" in r and r["min_score"] is not None:
                    self.min_signal_score = max(50.0, min(100.0, float(r["min_score"])))
                if "min_payout" in r and r["min_payout"] is not None:
                    self.min_payout_pct = max(0.0, min(100.0, float(r["min_payout"])))

            if "templates" in new_config and isinstance(new_config["templates"], dict):
                for k, v in new_config["templates"].items():
                    k_clean = str(k).strip().lower()
                    if k_clean in DEFAULT_TEMPLATES and isinstance(v, str) and v.strip():
                        self.templates[k_clean] = v.strip()

        self.save_to_disk()
        return self.get_config()

    def set_template(self, template_key: str, template_text: str) -> bool:
        """Sets and persists an individual template string."""
        with self._lock:
            key = str(template_key).strip().lower()
            text = str(template_text or "").strip()
            if key in DEFAULT_TEMPLATES and text:
                self.templates[key] = text
                self.save_to_disk()
                return True
            return False

    def add_channel(self, channel_id: str, title: str = "", enabled: bool = True):
        """Adds or updates a destination channel."""
        with self._lock:
            cid = str(channel_id).strip()
            if not cid:
                return
            t = str(title or f"Channel {len(self.channels)+1}").strip()
            for ch in self.channels:
                if ch.get("id") == cid:
                    ch["title"] = t
                    ch["name"] = t
                    ch["enabled"] = bool(enabled)
                    self.save_to_disk()
                    return
            self.channels.append({
                "id": cid,
                "title": t,
                "name": t,
                "enabled": bool(enabled)
            })
            self.save_to_disk()

    def remove_channel(self, channel_id: str):
        """Removes a destination channel by chat ID."""
        with self._lock:
            cid = str(channel_id).strip()
            self.channels = [c for c in self.channels if c.get("id") != cid]
            self.save_to_disk()

    def get_template(self, template_key: str) -> str:
        """Gets active template string by key."""
        with self._lock:
            key = str(template_key).strip().lower()
            return self.templates.get(key, DEFAULT_TEMPLATES.get(key, ""))

    def reset_template_to_default(self, template_key: str) -> str:
        """Alias for reset_template."""
        return self.reset_template(template_key)

    def get_active_channel_ids(self) -> List[str]:
        """Returns list of active channel IDs configured to receive broadcasts."""
        with self._lock:
            active = [c["id"] for c in self.channels if c.get("enabled", True) and c.get("id")]
            if not active and self.channels:
                active = [self.channels[0]["id"]]
            return active

    def reset_template(self, template_key: str) -> str:
        """Resets a specific template back to its default formatting."""
        with self._lock:
            if template_key in DEFAULT_TEMPLATES:
                self.templates[template_key] = DEFAULT_TEMPLATES[template_key]
                self.save_to_disk()
                return self.templates[template_key]
            return ""

    def render_template(self, template_key: str, context: Dict[str, Any]) -> str:
        """Interpolates dynamic tokens into template, safely falling back on errors."""
        with self._lock:
            template = self.templates.get(template_key, DEFAULT_TEMPLATES.get(template_key, ""))

        try:
            return self.interpolate(template, context)
        except Exception as e:
            logger.warning(f"[TELEGRAM TEMPLATE ERROR] Failed to interpolate {template_key}: {e}. Falling back to default.")
            default_tmpl = DEFAULT_TEMPLATES.get(template_key, "")
            try:
                return self.interpolate(default_tmpl, context)
            except Exception:
                return str(context)

    @staticmethod
    def interpolate(template: str, context: Dict[str, Any]) -> str:
        """
        Replaces all `{token}` occurrences in `template` with matching values from `context`.
        Ignores unknown tokens cleanly without breaking.
        """
        def replace_token(match):
            key = match.group(1).strip()
            if key in context:
                val = context[key]
                return "" if val is None else str(val)
            return match.group(0)

        return re.sub(r"\{([a-zA-Z0-9_]+)\}", replace_token, template)

    def load_from_disk(self):
        """Loads configuration from telegram_config.json if present, plus environment fallbacks."""
        from core.config import settings
        if settings.TELEGRAM_BOT_TOKEN and not self.bot_token:
            self.bot_token = settings.TELEGRAM_BOT_TOKEN.strip()
        if settings.TELEGRAM_CHAT_IDS and not self.channels:
            raw_ids = [c.strip() for c in settings.TELEGRAM_CHAT_IDS.split(",") if c.strip()]
            self.channels = [{"id": cid, "name": f"Channel {i+1}", "enabled": True} for i, cid in enumerate(raw_ids)]

        if self.config_file.exists():
            try:
                data = json.loads(self.config_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    if data.get("bot_token"):
                        self.bot_token = data["bot_token"].strip()
                    if data.get("bot_username"):
                        self.bot_username = data["bot_username"].strip()
                    if data.get("bot_first_name"):
                        self.bot_first_name = data["bot_first_name"].strip()
                    if "polling_enabled" in data:
                        self.polling_enabled = bool(data["polling_enabled"])
                    if isinstance(data.get("channels"), list):
                        self.channels = data["channels"]
                    if "send_signals" in data:
                        self.send_signals = bool(data["send_signals"])
                    if "send_pre_signals" in data:
                        self.send_pre_signals = bool(data["send_pre_signals"])
                    if "send_outcomes" in data:
                        self.send_outcomes = bool(data["send_outcomes"])
                    if "send_circuit_breaker" in data:
                        self.send_circuit_breaker = bool(data["send_circuit_breaker"])
                    if "send_news_blackouts" in data:
                        self.send_news_blackouts = bool(data["send_news_blackouts"])
                    if "min_signal_score" in data:
                        self.min_signal_score = float(data["min_signal_score"])
                    if "min_payout_pct" in data:
                        self.min_payout_pct = float(data["min_payout_pct"])
                    if "attach_chart_photo" in data:
                        self.attach_chart_photo = bool(data["attach_chart_photo"])
                    if "include_inline_buttons" in data:
                        self.include_inline_buttons = bool(data["include_inline_buttons"])
                    if isinstance(data.get("templates"), dict):
                        for k, v in data["templates"].items():
                            k_clean = str(k).strip().lower()
                            if k_clean in DEFAULT_TEMPLATES and isinstance(v, str) and v.strip():
                                self.templates[k_clean] = v.strip()
                    logger.info(f"[TELEGRAM MANAGER] Config loaded from {self.config_file}")
            except Exception as e:
                logger.warning(f"[TELEGRAM MANAGER] Failed to load config from {self.config_file}: {e}")

    def save_to_disk(self):
        """Saves current configuration to telegram_config.json and synchronizes with .env."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "bot_token": self.bot_token,
                "bot_username": self.bot_username,
                "bot_first_name": self.bot_first_name,
                "polling_enabled": self.polling_enabled,
                "channels": self.channels,
                "send_signals": self.send_signals,
                "send_pre_signals": self.send_pre_signals,
                "send_outcomes": self.send_outcomes,
                "send_circuit_breaker": self.send_circuit_breaker,
                "send_news_blackouts": self.send_news_blackouts,
                "min_signal_score": self.min_signal_score,
                "min_payout_pct": self.min_payout_pct,
                "attach_chart_photo": self.attach_chart_photo,
                "include_inline_buttons": self.include_inline_buttons,
                "templates": self.templates
            }
            self.config_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"[TELEGRAM MANAGER] Failed to write {self.config_file}: {e}")

        # Synchronize core settings & .env
        try:
            from core.config import settings
            settings.TELEGRAM_BOT_TOKEN = self.bot_token
            all_cids = ",".join(c["id"] for c in self.channels if c.get("id"))
            settings.TELEGRAM_CHAT_IDS = all_cids

            env_file = self.config_dir / ".env"
            lines = []
            if env_file.exists():
                lines = env_file.read_text(encoding="utf-8").splitlines()
            new_lines = []
            token_set, chat_set = False, False
            for line in lines:
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    new_lines.append(f"TELEGRAM_BOT_TOKEN={self.bot_token}")
                    token_set = True
                elif line.startswith("TELEGRAM_CHAT_IDS="):
                    new_lines.append(f"TELEGRAM_CHAT_IDS={all_cids}")
                    chat_set = True
                else:
                    new_lines.append(line)
            if not token_set:
                new_lines.append(f"TELEGRAM_BOT_TOKEN={self.bot_token}")
            if not chat_set:
                new_lines.append(f"TELEGRAM_CHAT_IDS={all_cids}")
            env_file.write_text("\n".join(new_lines), encoding="utf-8")
        except Exception as e:
            logger.debug(f"[TELEGRAM MANAGER] .env sync note: {e}")
