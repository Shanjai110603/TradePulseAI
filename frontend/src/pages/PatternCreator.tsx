import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { patternsApi, marketsApi } from '../services/api';
import { Market, Asset } from '../types';
import { 
  Plus, 
  ArrowLeft, 
  ArrowRight, 
  Upload, 
  CheckCircle, 
  Layers, 
  Sparkles, 
  Eye, 
  ShieldAlert, 
  Zap, 
  FileText 
} from 'lucide-react';

export const PatternCreator: React.FC = () => {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(1);
  const totalSteps = 16;

  // Form State
  const [name, setName] = useState('SMC Liquidity Sweep Strategy');
  const [description, setDescription] = useState('Smart Money Concepts: Detects stop-hunt liquidity grabs past key highs/lows with instant shadow rejection.');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);

  const [marketId, setMarketId] = useState('digital_options');
  const [markets, setMarkets] = useState<Market[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [selectedAssets, setSelectedAssets] = useState<string[]>(['EUR/USD', 'GBP/USD']);
  const [direction, setDirection] = useState('DOWN');
  const [timeframe, setTimeframe] = useState('1M');

  // Trend Settings
  const [trendReq, setTrendReq] = useState('Bearish');
  const [mtf5mTrend, setMtf5mTrend] = useState('Bearish');

  // Momentum Settings
  const [rsiMin, setRsiMin] = useState(0);
  const [rsiMax, setRsiMax] = useState(50);
  const [adxMin, setAdxMin] = useState(20);
  const [macdBias, setMacdBias] = useState('Bearish');

  // Volume Settings
  const [volumeType, setVolumeType] = useState('above_average');
  const [minVolumePct, setMinVolumePct] = useState(120);

  // Pattern Condition Settings (Pattern Type 14 primitive)
  const [bullishCount, setBullishCount] = useState(2);
  const [confirmationType, setConfirmationType] = useState('close_below');
  const [supportSource, setSupportSource] = useState('swing_low');

  // Entry & Target Settings
  const [entryType, setEntryType] = useState('immediate');
  const [durationMinutes, setDurationMinutes] = useState(5);
  const [rrRatio, setRrRatio] = useState(2.0);

  // AI Requirements
  const [aiEnabled, setAiEnabled] = useState(true);
  const [minAiScore, setMinAiScore] = useState(80);
  const [minAiConfidence, setMinAiConfidence] = useState('HIGH');
  const [requiredAiBias, setRequiredAiBias] = useState('BEARISH');

  // Notifications
  const [telegramAlerts, setTelegramAlerts] = useState(true);

  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    marketsApi.getMarkets().then(setMarkets).catch(console.error);
  }, []);

  useEffect(() => {
    if (marketId) {
      marketsApi.getAssets(marketId).then(setAssets).catch(console.error);
    }
  }, [marketId]);

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      setImagePreview(URL.createObjectURL(file));
    }
  };

  const handleSavePattern = async (andBacktest: boolean = false) => {
    setSubmitting(true);
    try {
      const payload = {
        name,
        description,
        market_id: marketId,
        direction,
        timeframe,
        assets_config: selectedAssets,
        timeframes_config: { [timeframe]: 'Any', '5M': mtf5mTrend },
        trend_config: { required: trendReq, mtf: { '5M': mtf5mTrend } },
        momentum_config: { strength: 'Strong', rsi_min: rsiMin, rsi_max: rsiMax, adx_min: adxMin, macd_bias: macdBias },
        volume_config: { type: volumeType, min_pct_of_ma: minVolumePct },
        indicators_config: [
          { indicator: 'RSI', condition: 'BELOW', value: rsiMax, period: 14 }
        ],
        rules_config: {
          operator: 'AND',
          conditions: [
            {
              type: direction === 'DOWN' ? 'pattern_type_14' : 'pattern_type_14_inverted',
              params: {
                bullish_count: bullishCount,
                bearish_count: bullishCount,
                confirmation: confirmationType,
                support_source: supportSource,
                resistance_source: supportSource
              }
            }
          ]
        },
        entry_config: { type: entryType },
        target_config: { duration_type: 'time', duration_minutes: durationMinutes, duration_candles: durationMinutes, risk_reward_ratio: rrRatio },
        ai_config: { enabled: aiEnabled, min_score: minAiScore, min_confidence: minAiConfidence, required_bias: requiredAiBias },
        notification_config: { telegram: telegramAlerts, notify_on_entry: true, notify_on_outcome: true },
        is_active: true
      };

      const created = await patternsApi.createPattern(payload);

      // If an image was selected, upload it
      if (selectedFile && created.id) {
        try {
          await patternsApi.uploadImage(created.id, selectedFile);
        } catch (imgErr) {
          console.error('Failed to upload pattern image', imgErr);
        }
      }

      if (andBacktest) {
        navigate(`/patterns/${created.id}/backtest`);
      } else {
        navigate('/patterns');
      }
    } catch (e) {
      console.error('Failed to create pattern', e);
      alert('Error creating pattern. Please verify settings.');
    } finally {
      setSubmitting(false);
    }
  };

  const loadPresetPattern14 = () => {
    setName('Pattern Type 14 (Standard Bearish Breakdown)');
    setDescription('Bearish starting candle -> 2 Bullish base candles creating support -> Support close breakdown -> DOWN Signal');
    setDirection('DOWN');
    setTimeframe('1M');
    setTrendReq('Bearish');
    setMtf5mTrend('Bearish');
    setRsiMin(0);
    setRsiMax(50);
    setAdxMin(20);
    setMacdBias('Bearish');
    setVolumeType('above_average');
    setMinVolumePct(120);
    setBullishCount(2);
    setConfirmationType('close_below');
    setSupportSource('swing_low');
    setDurationMinutes(5);
    setMinAiScore(80);
    setRequiredAiBias('BEARISH');
  };

  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto">
      {/* Step Header */}
      <div className="flex items-center justify-between border-b border-surface-border pb-4">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-xl font-bold text-white tracking-wide">Pattern Strategy Builder</h1>
            <span className="text-xs px-2.5 py-1 rounded bg-primary/20 text-primary font-mono font-semibold border border-primary/30">
              Step {currentStep} of {totalSteps}
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            Configure machine-readable parameters and visual reference.
          </p>
        </div>

        <button
          onClick={loadPresetPattern14}
          className="px-3 py-1.5 rounded-lg bg-indigo-950/60 hover:bg-indigo-900/80 text-indigo-300 border border-indigo-700/60 text-xs font-mono transition-colors flex items-center gap-1.5"
        >
          <Sparkles className="w-3.5 h-3.5 text-primary" />
          Load Pattern 14 Preset
        </button>
      </div>

      {/* Main Step Form Container */}
      <div className="glass-panel p-6 space-y-6 min-h-[400px]">
        {/* STEP 1: Basic Info */}
        {currentStep === 1 && (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-white">Step 1: Pattern Identification</h2>
            <div className="space-y-2">
              <label className="text-xs font-mono text-gray-300">Pattern Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-surface-raised border border-surface-border rounded-lg px-4 py-2.5 text-sm text-white focus:border-primary outline-none font-mono"
                placeholder="e.g. Pattern Type 14"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-mono text-gray-300">Description & Rationale</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                className="w-full bg-surface-raised border border-surface-border rounded-lg px-4 py-2.5 text-sm text-white focus:border-primary outline-none font-mono"
                placeholder="Explain the setup mechanics..."
              />
            </div>
          </div>
        )}

        {/* STEP 2: Pattern Image Upload */}
        {currentStep === 2 && (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-white">Step 2: Upload Pattern Image (Visual Reference)</h2>
            <p className="text-xs text-gray-400">
              The image serves as your visual guide. The executable strategy is evaluated via the rules configured in the next steps.
            </p>

            <div className="border-2 border-dashed border-surface-border hover:border-primary/60 rounded-xl p-6 text-center space-y-3 cursor-pointer transition-colors bg-surface-raised/40">
              <input
                type="file"
                id="pattern-img"
                accept="image/png,image/jpeg,image/webp"
                onChange={handleImageChange}
                className="hidden"
              />
              <label htmlFor="pattern-img" className="cursor-pointer block space-y-2">
                <Upload className="w-10 h-10 text-primary mx-auto" />
                <span className="text-sm font-semibold text-white block">
                  {selectedFile ? selectedFile.name : 'Click to select Pattern Image'}
                </span>
                <span className="text-xs text-gray-500 block">PNG, JPG, WebP up to 5MB</span>
              </label>
            </div>

            {imagePreview && (
              <div className="mt-4 p-3 glass-card rounded-xl">
                <p className="text-xs font-mono text-gray-400 mb-2">Image Preview:</p>
                <img src={imagePreview} alt="Preview" className="max-h-60 rounded-lg mx-auto object-contain" />
              </div>
            )}
          </div>
        )}

        {/* STEP 3 & 4: Market & Assets */}
        {currentStep === 3 && (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-white">Step 3: Market & Asset Selection</h2>
            <div className="space-y-2">
              <label className="text-xs font-mono text-gray-300">Market Category</label>
              <select
                value={marketId}
                onChange={(e) => setMarketId(e.target.value)}
                className="w-full bg-surface-raised border border-surface-border rounded-lg px-4 py-2.5 text-sm text-white focus:border-primary outline-none font-mono"
              >
                <option value="digital_options">Digital Options Style (Fixed Time Expiry)</option>
                <option value="crypto">Cryptocurrency (Spot & Futures)</option>
                <option value="forex">Forex (Currencies)</option>
                <option value="stocks">Stocks & Equities</option>
              </select>
            </div>

            <div className="space-y-2 pt-2">
              <label className="text-xs font-mono text-gray-300">Active Assets</label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {assets.map((a) => (
                  <button
                    key={a.symbol}
                    type="button"
                    onClick={() => {
                      if (selectedAssets.includes(a.symbol)) {
                        setSelectedAssets(selectedAssets.filter((s) => s !== a.symbol));
                      } else {
                        setSelectedAssets([...selectedAssets, a.symbol]);
                      }
                    }}
                    className={`px-3 py-2 rounded-lg text-xs font-mono text-center border transition-all ${
                      selectedAssets.includes(a.symbol)
                        ? 'bg-primary/20 text-primary border-primary font-semibold shadow-glow-cyan'
                        : 'bg-surface-raised text-gray-400 border-surface-border'
                    }`}
                  >
                    {a.symbol}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* STEP 5 & 6: Direction & Timeframe */}
        {currentStep === 4 && (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-white">Step 4: Direction & Primary Timeframe</h2>
            <div className="space-y-2">
              <label className="text-xs font-mono text-gray-300">Signal Direction</label>
              <div className="grid grid-cols-2 gap-4">
                <button
                  type="button"
                  onClick={() => setDirection('DOWN')}
                  className={`p-4 rounded-xl border font-bold text-sm transition-all text-center ${
                    direction === 'DOWN'
                      ? 'bg-rose-950/60 text-trade-down border-rose-600 shadow-glow-red'
                      : 'bg-surface-raised text-gray-400 border-surface-border'
                  }`}
                >
                  🔴 DOWN (SHORT / PUT)
                </button>
                <button
                  type="button"
                  onClick={() => setDirection('UP')}
                  className={`p-4 rounded-xl border font-bold text-sm transition-all text-center ${
                    direction === 'UP'
                      ? 'bg-emerald-950/60 text-trade-up border-emerald-600 shadow-glow-green'
                      : 'bg-surface-raised text-gray-400 border-surface-border'
                  }`}
                >
                  🟢 UP (LONG / CALL)
                </button>
              </div>
            </div>

            <div className="space-y-2 pt-2">
              <label className="text-xs font-mono text-gray-300">Primary Candle Timeframe</label>
              <div className="grid grid-cols-4 gap-2">
                {['1M', '5M', '15M', '1H'].map((tf) => (
                  <button
                    key={tf}
                    type="button"
                    onClick={() => setTimeframe(tf)}
                    className={`py-2 rounded-lg text-xs font-mono font-semibold border transition-all ${
                      timeframe === tf
                        ? 'bg-primary text-black border-primary'
                        : 'bg-surface-raised text-gray-400 border-surface-border'
                    }`}
                  >
                    {tf}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* STEP 7: Trend Configuration */}
        {currentStep === 5 && (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-white">Step 5: Multi-Timeframe Trend Requirements</h2>
            <div className="space-y-2">
              <label className="text-xs font-mono text-gray-300">Base Timeframe Trend</label>
              <select
                value={trendReq}
                onChange={(e) => setTrendReq(e.target.value)}
                className="w-full bg-surface-raised border border-surface-border rounded-lg px-4 py-2.5 text-sm text-white focus:border-primary outline-none font-mono"
              >
                <option value="Any">Any Trend</option>
                <option value="Bearish">Bearish</option>
                <option value="Strong Bearish">Strong Bearish</option>
                <option value="Bullish">Bullish</option>
                <option value="Strong Bullish">Strong Bullish</option>
              </select>
            </div>

            <div className="space-y-2 pt-2">
              <label className="text-xs font-mono text-gray-300">Higher Timeframe (5M) Trend Alignment</label>
              <select
                value={mtf5mTrend}
                onChange={(e) => setMtf5mTrend(e.target.value)}
                className="w-full bg-surface-raised border border-surface-border rounded-lg px-4 py-2.5 text-sm text-white focus:border-primary outline-none font-mono"
              >
                <option value="Any">Any</option>
                <option value="Bearish">5M Must Be Bearish</option>
                <option value="Bullish">5M Must Be Bullish</option>
              </select>
            </div>
          </div>
        )}

        {/* STEP 8: Momentum & Indicators */}
        {currentStep === 6 && (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-white">Step 6: Momentum & Oscillator Rules</h2>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-xs font-mono text-gray-300">RSI Max Threshold (0-100)</label>
                <input
                  type="number"
                  value={rsiMax}
                  onChange={(e) => setRsiMax(Number(e.target.value))}
                  className="w-full bg-surface-raised border border-surface-border rounded-lg px-4 py-2 text-sm text-white font-mono"
                />
              </div>
              <div className="space-y-2">
                <label className="text-xs font-mono text-gray-300">ADX Minimum Strength</label>
                <input
                  type="number"
                  value={adxMin}
                  onChange={(e) => setAdxMin(Number(e.target.value))}
                  className="w-full bg-surface-raised border border-surface-border rounded-lg px-4 py-2 text-sm text-white font-mono"
                />
              </div>
            </div>

            <div className="space-y-2 pt-2">
              <label className="text-xs font-mono text-gray-300">MACD Histogram Alignment</label>
              <select
                value={macdBias}
                onChange={(e) => setMacdBias(e.target.value)}
                className="w-full bg-surface-raised border border-surface-border rounded-lg px-4 py-2.5 text-sm text-white font-mono"
              >
                <option value="Any">Any</option>
                <option value="Bearish">Histogram Below 0 (Bearish)</option>
                <option value="Bullish">Histogram Above 0 (Bullish)</option>
              </select>
            </div>
          </div>
        )}

        {/* STEP 9: Volume Rules */}
        {currentStep === 7 && (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-white">Step 7: Volume Confirmation</h2>
            <div className="space-y-2">
              <label className="text-xs font-mono text-gray-300">Volume Condition</label>
              <select
                value={volumeType}
                onChange={(e) => setVolumeType(e.target.value)}
                className="w-full bg-surface-raised border border-surface-border rounded-lg px-4 py-2.5 text-sm text-white font-mono"
              >
                <option value="Any">Any Volume</option>
                <option value="above_average">Above 20-Period Moving Average</option>
                <option value="strong">Strong Volume Surge (&gt;= 150%)</option>
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-mono text-gray-300">Minimum Volume % of MA</label>
              <input
                type="number"
                value={minVolumePct}
                onChange={(e) => setMinVolumePct(Number(e.target.value))}
                className="w-full bg-surface-raised border border-surface-border rounded-lg px-4 py-2 text-sm text-white font-mono"
              />
              <span className="text-[11px] text-gray-500 font-mono">120 = At least 120% of 20 SMA</span>
            </div>
          </div>
        )}

        {/* STEP 10: Pattern Condition Parameters */}
        {currentStep === 8 && (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-white">Step 8: Candlestick & Breakout Logic</h2>
            <div className="space-y-2">
              <label className="text-xs font-mono text-gray-300">Number of Base Candles</label>
              <input
                type="number"
                value={bullishCount}
                onChange={(e) => setBullishCount(Number(e.target.value))}
                className="w-full bg-surface-raised border border-surface-border rounded-lg px-4 py-2 text-sm text-white font-mono"
              />
              <span className="text-[11px] text-gray-500 font-mono">Pattern Type 14 requires exactly 2 base candles</span>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-mono text-gray-300">Support / Resistance Break Confirmation</label>
              <select
                value={confirmationType}
                onChange={(e) => setConfirmationType(e.target.value)}
                className="w-full bg-surface-raised border border-surface-border rounded-lg px-4 py-2.5 text-sm text-white font-mono"
              >
                <option value="close_below">Candle Close Strictly Below Support</option>
                <option value="wick_below">Candle Wick Pierces Below Support</option>
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-mono text-gray-300">Support Level Baseline Calculation</label>
              <select
                value={supportSource}
                onChange={(e) => setSupportSource(e.target.value)}
                className="w-full bg-surface-raised border border-surface-border rounded-lg px-4 py-2.5 text-sm text-white font-mono"
              >
                <option value="swing_low">Swing Low (Lowest wick of base)</option>
                <option value="body_low">Body Low (Lowest open/close of base)</option>
              </select>
            </div>
          </div>
        )}

        {/* STEP 11: Expiry & Targets */}
        {currentStep === 9 && (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-white">Step 9: Expiry / Target Configuration</h2>
            <div className="space-y-2">
              <label className="text-xs font-mono text-gray-300">Expiry Duration (Minutes / Candles)</label>
              <input
                type="number"
                value={durationMinutes}
                onChange={(e) => setDurationMinutes(Number(e.target.value))}
                className="w-full bg-surface-raised border border-surface-border rounded-lg px-4 py-2 text-sm text-white font-mono"
              />
              <span className="text-[11px] text-gray-500 font-mono">e.g. 5 minutes for 1M candles</span>
            </div>
          </div>
        )}

        {/* STEP 12: AI Filter Requirements */}
        {currentStep === 10 && (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-white">Step 10: AI Quantitative Filter Settings</h2>
            <p className="text-xs text-gray-400">
              Only candidate signals that pass the AI confidence threshold will be generated and dispatched.
            </p>

            <div className="flex items-center space-x-3 p-3 glass-card rounded-lg">
              <input
                type="checkbox"
                id="ai-toggle"
                checked={aiEnabled}
                onChange={(e) => setAiEnabled(e.target.checked)}
                className="w-4 h-4 rounded text-primary"
              />
              <label htmlFor="ai-toggle" className="text-xs font-semibold text-white">
                Enable AI Analysis Layer Verification
              </label>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-mono text-gray-300">Minimum AI Score (0 - 100)</label>
              <input
                type="number"
                value={minAiScore}
                onChange={(e) => setMinAiScore(Number(e.target.value))}
                className="w-full bg-surface-raised border border-surface-border rounded-lg px-4 py-2 text-sm text-white font-mono"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs font-mono text-gray-300">Minimum Required AI Confidence</label>
              <select
                value={minAiConfidence}
                onChange={(e) => setMinAiConfidence(e.target.value)}
                className="w-full bg-surface-raised border border-surface-border rounded-lg px-4 py-2.5 text-sm text-white font-mono"
              >
                <option value="HIGH">HIGH Confidence Only (&gt;= 85)</option>
                <option value="MODERATE">MODERATE or Higher (&gt;= 70)</option>
                <option value="LOW">Allow LOW Confidence</option>
              </select>
            </div>
          </div>
        )}

        {/* REVIEW & SAVE */}
        {currentStep >= 11 && (
          <div className="space-y-5">
            <h2 className="text-base font-semibold text-white flex items-center gap-2">
              <CheckCircle className="w-5 h-5 text-emerald-400" />
              Final Review & Activation
            </h2>

            <div className="grid grid-cols-2 gap-4 text-xs font-mono">
              <div className="glass-card p-3 space-y-1">
                <span className="text-gray-500 block">STRATEGY</span>
                <span className="text-white font-bold text-sm">{name}</span>
                <p className="text-[11px] text-gray-400">{description}</p>
              </div>

              <div className="glass-card p-3 space-y-1">
                <span className="text-gray-500 block">MARKET & DIRECTION</span>
                <span className="text-white font-bold">{marketId.toUpperCase()}</span>
                <span className="text-trade-down font-bold block">{direction} ({timeframe})</span>
              </div>

              <div className="glass-card p-3 space-y-1">
                <span className="text-gray-500 block">RULES PRIMITIVE</span>
                <span className="text-cyan-300 font-semibold block">Pattern Type 14 Breakdown</span>
                <span className="text-gray-400 text-[11px] block">{bullishCount} Base Candles | {confirmationType}</span>
              </div>

              <div className="glass-card p-3 space-y-1">
                <span className="text-gray-500 block">AI FILTER</span>
                <span className="text-primary font-bold block">Min Score: {minAiScore}/100</span>
                <span className="text-gray-400 text-[11px] block">{minAiConfidence} Confidence</span>
              </div>
            </div>

            <div className="flex items-center space-x-4 pt-4 border-t border-surface-border">
              <button
                type="button"
                disabled={submitting}
                onClick={() => handleSavePattern(false)}
                className="flex-1 py-3 rounded-xl bg-surface-raised hover:bg-surface-border text-white text-xs font-mono font-semibold border border-surface-border transition-colors"
              >
                Save & Return to Library
              </button>
              <button
                type="button"
                disabled={submitting}
                onClick={() => handleSavePattern(true)}
                className="flex-1 py-3 rounded-xl bg-primary hover:bg-primary-hover text-black text-xs font-mono font-bold transition-all shadow-glow-cyan flex items-center justify-center gap-2"
              >
                <Sparkles className="w-4 h-4" />
                Save & Run Instant Backtest
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Step Navigation Controls */}
      <div className="flex items-center justify-between pt-2">
        <button
          type="button"
          disabled={currentStep === 1}
          onClick={() => setCurrentStep((prev) => Math.max(prev - 1, 1))}
          className="flex items-center space-x-2 px-4 py-2 rounded-lg bg-surface-raised text-gray-300 hover:text-white text-xs font-mono disabled:opacity-30"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Previous Step</span>
        </button>

        {currentStep < 11 && (
          <button
            type="button"
            onClick={() => setCurrentStep((prev) => Math.min(prev + 1, 11))}
            className="flex items-center space-x-2 px-5 py-2 rounded-lg bg-primary hover:bg-primary-hover text-black text-xs font-mono font-semibold shadow-glow-cyan"
          >
            <span>Next Step</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    </div>
  );
};
