from typing import Dict, Any, List
from fastapi import APIRouter

router = APIRouter(prefix="/pattern-rules", tags=["Pattern Rule Engine"])


@router.get("/templates")
async def get_rule_templates() -> List[Dict[str, Any]]:
    """Returns pre-built strategy templates including Pattern Type 14"""
    return [
        {
            "id": "pattern_type_14",
            "name": "Pattern Type 14 (Breakdown Confirmation)",
            "description": "Bearish initial candle followed by 2 bullish candles establishing a support base, followed by a bearish breakdown closing below support.",
            "market_id": "digital_options",
            "direction": "DOWN",
            "timeframe": "1M",
            "trend_config": {"required": "Bearish", "mtf": {"5M": "Bearish"}},
            "momentum_config": {"strength": "Strong", "rsi_min": 0, "rsi_max": 50, "adx_min": 20, "macd_bias": "Bearish"},
            "volume_config": {"type": "above_average", "min_pct_of_ma": 120},
            "rules_config": {
                "operator": "AND",
                "conditions": [
                    {
                        "type": "pattern_type_14",
                        "params": {
                            "bullish_count": 2,
                            "confirmation": "close_below",
                            "support_source": "swing_low"
                        }
                    }
                ]
            },
            "entry_config": {"type": "immediate"},
            "target_config": {"duration_type": "time", "duration_minutes": 5, "duration_candles": 5},
            "ai_config": {"enabled": True, "min_score": 80, "min_confidence": "HIGH", "required_bias": "BEARISH"}
        },
        {
            "id": "pattern_type_14_inverted",
            "name": "Inverted Pattern Type 14 (Breakout Confirmation)",
            "description": "Bullish initial candle followed by 2 bearish candles establishing resistance, followed by a bullish breakout closing above resistance.",
            "market_id": "digital_options",
            "direction": "UP",
            "timeframe": "1M",
            "trend_config": {"required": "Bullish", "mtf": {"5M": "Bullish"}},
            "momentum_config": {"strength": "Strong", "rsi_min": 50, "rsi_max": 100, "adx_min": 20, "macd_bias": "Bullish"},
            "volume_config": {"type": "above_average", "min_pct_of_ma": 120},
            "rules_config": {
                "operator": "AND",
                "conditions": [
                    {
                        "type": "pattern_type_14_inverted",
                        "params": {
                            "bearish_count": 2,
                            "confirmation": "close_above",
                            "resistance_source": "swing_high"
                        }
                    }
                ]
            },
            "entry_config": {"type": "immediate"},
            "target_config": {"duration_type": "time", "duration_minutes": 5, "duration_candles": 5},
            "ai_config": {"enabled": True, "min_score": 80, "min_confidence": "HIGH", "required_bias": "BULLISH"}
        },
        {
            "id": "ema_momentum_breakout",
            "name": "EMA Momentum Crossover",
            "description": "Fast EMA (9) cross above Slow EMA (21) with RSI above 55 and expanding volume.",
            "market_id": "crypto",
            "direction": "BUY",
            "timeframe": "5M",
            "trend_config": {"required": "Bullish"},
            "momentum_config": {"rsi_min": 55, "rsi_max": 80, "macd_bias": "Bullish"},
            "volume_config": {"type": "above_average", "min_pct_of_ma": 115},
            "rules_config": {
                "operator": "AND",
                "conditions": [
                    {
                        "type": "candle_color",
                        "params": {"index": -1, "color": "bullish"}
                    }
                ]
            },
            "entry_config": {"type": "immediate"},
            "target_config": {"risk_reward_ratio": 2.5},
            "ai_config": {"enabled": True, "min_score": 75}
        }
    ]


@router.get("/primitives")
async def get_rule_primitives() -> Dict[str, Any]:
    """Returns all supported rule primitives, indicators, and logical operators"""
    return {
        "operators": ["AND", "OR", "NOT"],
        "primitives": [
            {
                "type": "pattern_type_14",
                "label": "Pattern Type 14 (Bearish Breakdown)",
                "params": [
                    {"name": "bullish_count", "type": "int", "default": 2, "label": "Bullish Base Candles"},
                    {"name": "confirmation", "type": "select", "options": ["close_below", "wick_below"], "default": "close_below"},
                    {"name": "support_source", "type": "select", "options": ["swing_low", "body_low"], "default": "swing_low"}
                ]
            },
            {
                "type": "pattern_type_14_inverted",
                "label": "Inverted Pattern Type 14 (Bullish Breakout)",
                "params": [
                    {"name": "bearish_count", "type": "int", "default": 2, "label": "Bearish Base Candles"},
                    {"name": "confirmation", "type": "select", "options": ["close_above", "wick_above"], "default": "close_above"},
                    {"name": "resistance_source", "type": "select", "options": ["swing_high", "body_high"], "default": "swing_high"}
                ]
            },
            {
                "type": "candle_color",
                "label": "Candle Color",
                "params": [
                    {"name": "index", "type": "int", "default": -1, "label": "Candle Offset (-1 is current)"},
                    {"name": "color", "type": "select", "options": ["bullish", "bearish", "doji"], "default": "bearish"}
                ]
            },
            {
                "type": "candle_sequence",
                "label": "Candle Sequence Match",
                "params": [
                    {"name": "colors", "type": "tags", "default": ["bearish", "bullish", "bullish"]}
                ]
            },
            {
                "type": "support_break",
                "label": "Support Breakdown",
                "params": [
                    {"name": "lookback", "type": "int", "default": 5},
                    {"name": "break_type", "type": "select", "options": ["close_below", "wick_below"], "default": "close_below"}
                ]
            },
            {
                "type": "resistance_break",
                "label": "Resistance Breakout",
                "params": [
                    {"name": "lookback", "type": "int", "default": 5},
                    {"name": "break_type", "type": "select", "options": ["close_above", "wick_above"], "default": "close_above"}
                ]
            }
        ],
        "indicators": ["RSI", "MACD", "EMA_FAST", "EMA_SLOW", "SMA_200", "BOLLINGER", "VWAP", "ATR", "ADX", "STOCHASTIC"]
    }
