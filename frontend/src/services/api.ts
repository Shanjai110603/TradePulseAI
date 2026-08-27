import axios from 'axios';
import { AuthResponse, User, UserPreferences, Market, Asset, Candle, Pattern, PatternImage, Signal, BacktestResult, TelegramStatus, PerformanceOverview } from '../types';

// Dynamic API Base - uses local reverse proxy by default
const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';

const api = axios.create({
  baseURL: API_BASE,
});

// Interceptor to inject JWT token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('tradepulse_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const authApi = {
  login: async (formData: FormData): Promise<AuthResponse> => {
    const res = await api.post('/auth/login', formData);
    return res.data;
  },
  register: async (data: any): Promise<AuthResponse> => {
    const res = await api.post('/auth/register', data);
    return res.data;
  },
  getMe: async (): Promise<User> => {
    const res = await api.get('/auth/me');
    return res.data;
  },
  updatePreferences: async (prefs: UserPreferences): Promise<UserPreferences> => {
    const res = await api.put('/auth/preferences', prefs);
    return res.data;
  }
};

export const marketsApi = {
  getMarkets: async (): Promise<Market[]> => {
    const res = await api.get('/markets');
    return res.data;
  },
  getAssets: async (marketId: string): Promise<Asset[]> => {
    const res = await api.get(`/markets/${marketId}/assets`);
    return res.data;
  },
  getCandles: async (symbol: string, timeframe: string = '1M', limit: number = 100): Promise<Candle[]> => {
    const res = await api.get('/markets/candles', { params: { symbol, timeframe, limit } });
    return res.data;
  },
  getDataSources: async () => {
    const res = await api.get('/markets/data-sources');
    return res.data;
  }
};

export const patternsApi = {
  getPatterns: async (): Promise<Pattern[]> => {
    const res = await api.get('/patterns');
    return res.data;
  },
  getPattern: async (id: string): Promise<Pattern> => {
    const res = await api.get(`/patterns/${id}`);
    return res.data;
  },
  createPattern: async (data: any): Promise<Pattern> => {
    const res = await api.post('/patterns', data);
    return res.data;
  },
  updatePattern: async (id: string, data: any): Promise<Pattern> => {
    const res = await api.put(`/patterns/${id}`, data);
    return res.data;
  },
  togglePattern: async (id: string): Promise<Pattern> => {
    const res = await api.post(`/patterns/${id}/toggle`);
    return res.data;
  },
  duplicatePattern: async (id: string): Promise<Pattern> => {
    const res = await api.post(`/patterns/${id}/duplicate`);
    return res.data;
  },
  deletePattern: async (id: string): Promise<void> => {
    await api.delete(`/patterns/${id}`);
  },
  uploadImage: async (id: string, file: File): Promise<PatternImage> => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await api.post(`/patterns/${id}/image`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return res.data;
  },
  getVersions: async (id: string) => {
    const res = await api.get(`/patterns/${id}/versions`);
    return res.data;
  },
  getTemplates: async () => {
    const res = await api.get('/pattern-rules/templates');
    return res.data;
  },
  getPrimitives: async () => {
    const res = await api.get('/pattern-rules/primitives');
    return res.data;
  }
};

export const signalsApi = {
  getSignals: async (params?: { market_id?: string; status?: string; pattern_id?: string; limit?: number }): Promise<Signal[]> => {
    const res = await api.get('/signals', { params });
    return res.data;
  },
  getSignal: async (id: string): Promise<Signal> => {
    const res = await api.get(`/signals/${id}`);
    return res.data;
  },
  getSignalTechnicals: async (id: string) => {
    const res = await api.get(`/signals/${id}/technicals`);
    return res.data;
  },
  getSignalAnalysis: async (id: string) => {
    const res = await api.get(`/signals/${id}/analysis`);
    return res.data;
  }
};

export const backtestsApi = {
  runBacktest: async (data: { pattern_id: string; market_id: string; asset_symbol: string; timeframe: string; candle_count?: number }): Promise<BacktestResult> => {
    const res = await api.post('/backtests/run', data);
    return res.data;
  },
  getPatternBacktests: async (patternId: string): Promise<BacktestResult[]> => {
    const res = await api.get(`/backtests/pattern/${patternId}`);
    return res.data;
  },
  getBacktest: async (id: string): Promise<BacktestResult> => {
    const res = await api.get(`/backtests/${id}`);
    return res.data;
  }
};

export const telegramApi = {
  generateLinkCode: async () => {
    const res = await api.post('/telegram/link-code');
    return res.data;
  },
  getStatus: async (): Promise<TelegramStatus> => {
    const res = await api.get('/telegram/status');
    return res.data;
  },
  getSubscribers: async () => {
    const res = await api.get('/telegram/subscribers');
    return res.data;
  },
  clearSubscribers: async () => {
    const res = await api.delete('/telegram/subscribers');
    return res.data;
  },
  deleteSubscriber: async (id: string) => {
    const res = await api.delete(`/telegram/subscribers/${id}`);
    return res.data;
  },
  sendTestNotification: async () => {
    const res = await api.post('/telegram/test-notification');
    return res.data;
  }
};

export const performanceApi = {
  getOverview: async (): Promise<PerformanceOverview> => {
    const res = await api.get('/performance/overview');
    return res.data;
  }
};

export const adminApi = {
  getHealth: async () => {
    const res = await api.get('/admin/health');
    return res.data;
  },
  getMetrics: async () => {
    const res = await api.get('/admin/metrics');
    return res.data;
  }
};

export default api;
