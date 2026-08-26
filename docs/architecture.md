# TradePulse AI - System Architecture

## Overview

TradePulse AI is a personalized, AI-powered quantitative market research and trade-signal notification platform. It operates under a strict **Zero-Trade-Execution** scope: it detects patterns, runs multi-timeframe indicator calculations, enriches setups with AI scoring, and dispatches research notifications to Telegram.

## High-Level Architecture Diagram

```mermaid
flowchart TD
    subgraph MarketDataLayer ["Market Data Layer"]
        P1[Mock / Synthetic Provider]
        P2[Binance Live Provider]
        P3[Forex / Custom Adapter]
        P1 --> Norm[Market Normalizer & Candle Aggregator]
        P2 --> Norm
        P3 --> Norm
    end

    subgraph StrategyCore ["Deterministic Strategy Engine"]
        Norm --> ActivePats[Active User Patterns]
        ActivePats --> AST[AST Rule Tree Evaluator\nCandle Sequences & S/R Breakouts]
        AST --> TechInd[Technical Indicators Engine\nRSI, MACD, EMA, BB, ATR, ADX, VWAP]
        TechInd --> MTF[Multi-Timeframe Trend & Momentum Matrix]
        MTF --> CandMatch[Deterministic Signal Candidate Match]
    end

    subgraph AIEvaluation ["AI Analysis & User Filters"]
        CandMatch --> AIAbst[AI Provider Abstraction\nMock / OpenAI / Anthropic / Gemini]
        AIAbst --> AIScore[Structured JSON Scoring\nScore 0-100, Bias, Key Levels, Risks]
        AIScore --> FilterEng[User Filter Engine\nMin AI Score, Confidence, Risk Thresholds]
        FilterEng --> ValSig{Validated Signal?}
    end

    subgraph DeliveryLifecycle ["Signal Lifecycle & Delivery"]
        ValSig -->|Yes| SigStore[Signal & Audit Snapshot Store]
        SigStore --> TGBot[Telegram Bot Engine\nConcise Card + Interactive Callback Views]
        SigStore --> WebDash[Web Dashboard WebSocket / Polling]
        SigStore --> LifeTracker[Live Signal Tracker\nPending -> Active -> Expiry / TP / SL]
        LifeTracker --> OutcomeStore[Historical Results & Post-Analysis AI]
    end
```

## Key Architectural Principles

1. **Deterministic Rule Execution**: LLMs are never used as real-time candle pattern detectors. User strategy rules are executed deterministically via pure Python AST logic.
2. **AI as an Enrichment Layer**: AI acts as a quantitative analyst evaluating market context, bias, key levels, and risk factors.
3. **Pluggable Data Providers**: The system abstracts market data sources (Mock, Binance, etc.) so new asset classes can be added without rewriting strategy rules.
4. **Reproducible Signal Auditing**: Every generated signal permanently stores its triggering candle sequence, indicator values, AI reasoning, and filter evaluations.
