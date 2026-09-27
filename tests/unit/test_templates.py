import re
from pathlib import Path
import pytest
from core.telegram.manager import DEFAULT_TEMPLATES, TelegramManager


def test_telegram_manager_default_templates_keys():
    """Verify core TelegramManager defines all essential templates."""
    required_keys = {"signal", "pre_signal", "outcome", "circuit_breaker"}
    assert required_keys.issubset(set(DEFAULT_TEMPLATES.keys()))
    for key in required_keys:
        assert isinstance(DEFAULT_TEMPLATES[key], str)
        assert len(DEFAULT_TEMPLATES[key]) > 0


def test_ui_personal_defines_default_templates():
    """Verify ui_personal/app.js defines DEFAULT_TEMPLATES with all required template keys."""
    app_js_path = Path(__file__).resolve().parent.parent.parent / "ui_personal" / "app.js"
    assert app_js_path.exists(), f"Could not find {app_js_path}"
    content = app_js_path.read_text(encoding="utf-8")

    assert "const DEFAULT_TEMPLATES = {" in content
    assert "signal:" in content
    assert "pre_signal:" in content
    assert "outcome:" in content
    assert "circuit_breaker:" in content
    assert "initTemplateEditor();" in content
    assert "updateCardPreview();" in content


def test_telegram_template_rendering_interpolation():
    """Verify Telegram template token interpolation renders expected tags and content."""
    sample_signal_tmpl = DEFAULT_TEMPLATES["signal"]
    tokens = {
        "{strategy}": "Dual Bollinger Protrusion",
        "{asset}": "EUR/USD",
        "{payout}": "85",
        "{arrow}": "🟢",
        "{dir_badge}": "CALL",
        "{chart_timeframe}": "1M",
        "{timeframe}": "1M",
        "{expiry}": "1",
        "{entry_time}": "14:35:00",
    }
    rendered = sample_signal_tmpl
    for token, val in tokens.items():
        rendered = rendered.replace(token, val)

    assert "EUR/USD" in rendered
    assert "Dual Bollinger Protrusion" in rendered
    assert "85%" in rendered
    assert "CALL" in rendered
