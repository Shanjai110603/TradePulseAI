export interface User {
  id: string;
  email: string;
  full_name?: string;
  timezone: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
  is_telegram_linked: boolean;
  preferences?: UserPreferences;
}

export interface UserPreferences {
  default_market_id?: string;
  min_ai_score: number;
  min_confidence: string;
  allowed_risk_levels: string[];
  notify_on_all_signals: boolean;
  notify_on_status_change: boolean;
  notify_on_outcome: boolean;
  quiet_hours_enabled: boolean;
  quiet_hours_start?: string;
  quiet_hours_end?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Market {
  id: string;
  name: string;
  description?: string;
  market_type: string;
  is_active: boolean;
  icon?: string;
  features: Record<string, any>;
}

export interface Asset {
  id: string;
  symbol: string;
  base_asset: string;
  quote_asset: string;
  name: string;
  market_id: string;
  data_source_id: string;
  is_active: boolean;
  price_precision: number;
  min_movement: number;
}

export interface Candle {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface PatternImage {
  id: string;
  pattern_id: string;
  file_path: string;
  filename: string;
  mime_type: string;
  file_size_bytes: number;
  is_primary: boolean;
  created_at: string;
}

export interface Pattern {
  id: string;
  user_id: string;
  name: string;
  description?: string;
  market_id: string;
  direction: string;
  timeframe: string;
  is_active: boolean;
  current_version: number;
  assets_config: string[];
  timeframes_config: Record<string, string>;
  trend_config: Record<string, any>;
  momentum_config: Record<string, any>;
  volume_config: Record<string, any>;
  indicators_config: any[];
  rules_config: Record<string, any>;
  entry_config: Record<string, any>;
  target_config: Record<string, any>;
  ai_config: Record<string, any>;
  notification_config: Record<string, any>;
  images?: PatternImage[];
  created_at: string;
  updated_at: string;
  total_signals?: number;
  win_rate?: number;
}

export interface Signal {
  id: string;
  user_id: string;
  pattern_id?: string;
  pattern_version: number;
  pattern_name: string;
  market_id: string;
  asset_symbol: string;
  direction: string;
  timeframe: string;
  reference_price: number;
  entry_time: string;
  expiry_time?: string;
  duration_minutes?: number;
  stop_loss?: number;
  tp1?: number;
  tp2?: number;
  tp3?: number;
  risk_reward_ratio?: number;
  signal_strength: string;
  ai_score?: number;
  ai_confidence?: string;
  status: string;
  created_at: string;
  technical_snapshot?: Record<string, any>;
  ai_analysis?: Record<string, any>;
  result?: {
    outcome: string;
    exit_price: number;
    exit_time: string;
    pnl_percentage?: number;
    post_analysis_notes?: string;
  };
  events?: any[];
  raw_trigger_candles?: Candle[];
}

export interface BacktestResult {
  id: string;
  user_id: string;
  pattern_id: string;
  pattern_version: number;
  market_id: string;
  asset_symbol: string;
  timeframe: string;
  start_date: string;
  end_date: string;
  candle_count: number;
  status: string;
  total_signals: number;
  winning_signals: number;
  losing_signals: number;
  tie_signals: number;
  win_rate_percentage: number;
  profit_factor?: number;
  max_drawdown_percentage?: number;
  average_duration_seconds?: number;
  signals_log: any[];
  equity_curve: { timestamp: string; equity: number; trade_number: number }[];
  metrics: Record<string, any>;
  created_at: string;
}

export interface TelegramStatus {
  is_linked: boolean;
  telegram_username?: string;
  telegram_chat_id?: number;
  is_active: boolean;
  is_muted: boolean;
  bot_username: string;
  test_mode: boolean;
}

export interface PerformanceOverview {
  total_signals_all_time: number;
  active_signals_count: number;
  overall_win_rate: number;
  digital_options_win_rate: number;
  standard_markets_win_rate: number;
  total_active_patterns: number;
  pattern_stats: any[];
  top_assets: any[];
  ai_correlation: any[];
}
