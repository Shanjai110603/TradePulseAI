# Deterministic Strategy & Pattern Engine

## Core Primitives

The strategy engine evaluates candlestick data through an Abstract Syntax Tree (AST) supporting composite logical operators (`AND`, `OR`, `NOT`) and specialized trading primitives.

### Supported Primitives

| Primitive Type | Description | Parameters |
| :--- | :--- | :--- |
| `pattern_type_14` | Bearish Start -> 2 Bullish base candles -> Support low created -> Bearish breakdown close | `bullish_count`, `confirmation` (`close_below`/`wick_below`), `support_source` |
| `pattern_type_14_inverted` | Bullish Start -> 2 Bearish base candles -> Resistance high created -> Bullish breakout close | `bearish_count`, `confirmation` (`close_above`/`wick_above`), `resistance_source` |
| `candle_color` | Checks color of candle at specific offset | `index` (-1 is trigger candle), `color` (`bullish`, `bearish`, `doji`) |
| `candle_sequence` | Matches exact chronological sequence of candle colors | `colors` (e.g. `["bearish", "bullish", "bullish"]`) |
| `support_break` | Identifies swing low support in lookback window and verifies breakdown | `lookback`, `break_type` (`close_below`, `wick_below`) |
| `resistance_break` | Identifies swing high resistance in lookback window and verifies breakout | `lookback`, `break_type` (`close_above`, `wick_above`) |

## Pattern Type 14 Specification

Pattern Type 14 is defined as:
1. **Initial Bearish Candle**: Sets preceding short-term selling baseline.
2. **First 2 Bullish Candles**: Forms a local bottom and establishes a support level at the swing low of the base.
3. **Bearish Pullback**: Price tests back down towards the established support.
4. **Breakdown Confirmation**: A bearish candle pierces and closes strictly below the support line.
5. **Action**: Generates an immediate `DOWN` research signal.

```json
{
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
}
```
