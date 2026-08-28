import React, { useState, useEffect } from 'react';
import { telegramApi } from '../services/api';
import { TelegramStatus } from '../types';
import { 
  Send, 
  Users, 
  CheckCircle2, 
  AlertCircle, 
  Radio, 
  ExternalLink, 
  Zap, 
  ShieldCheck, 
  RefreshCw,
  Clock,
  Sparkles,
  Trash2
} from 'lucide-react';

interface Subscriber {
  id: string;
  telegram_user_id: number;
  telegram_chat_id: number;
  telegram_username: string | null;
  first_name: string | null;
  is_active: boolean;
  is_muted: boolean;
  created_at: string;
}

export const TelegramSettings: React.FC = () => {
  const [status, setStatus] = useState<TelegramStatus | null>(null);
  const [subscribers, setSubscribers] = useState<Subscriber[]>([]);
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [st, subs] = await Promise.all([
        telegramApi.getStatus(),
        telegramApi.getSubscribers()
      ]);
      setStatus(st);
      setSubscribers(subs || []);
    } catch (e) {
      console.error('Failed to load Telegram broadcast data:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleSendBroadcast = async () => {
    setTesting(true);
    setFeedback(null);
    try {
      const res = await telegramApi.sendTestNotification();
      setFeedback(`✅ ${res.message || 'Signal card dispatched to all subscribers!'}`);
      setTimeout(() => setFeedback(null), 5000);
      loadData();
    } catch (err: any) {
      setFeedback(`⚠️ ${err.response?.data?.detail || 'Failed to dispatch test signal.'}`);
      setTimeout(() => setFeedback(null), 5000);
    } finally {
      setTesting(false);
    }
  };

  const handleClearAllSubscribers = async () => {
    if (!window.confirm('Clear all subscribers from the list? Any active user can re-subscribe by sending /start.')) {
      return;
    }
    setClearing(true);
    try {
      await telegramApi.clearSubscribers();
      setFeedback('✅ All old subscribers cleared! The list is fresh.');
      setTimeout(() => setFeedback(null), 4000);
      loadData();
    } catch (e) {
      console.error(e);
      setFeedback('⚠️ Failed to clear subscribers.');
    } finally {
      setClearing(false);
    }
  };

  const handleDeleteSubscriber = async (id: string) => {
    try {
      await telegramApi.deleteSubscriber(id);
      loadData();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-11 h-11 rounded-xl bg-cyan-950/80 border border-cyan-700/60 flex items-center justify-center text-primary shadow-glow-cyan">
            <Send className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold text-white tracking-wide">Telegram Broadcast Station</h1>
              <span className="px-2 py-0.5 text-[10px] font-bold bg-emerald-950/80 text-emerald-400 border border-emerald-700/60 rounded-full flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                24/7 AUTO-BROADCAST ACTIVE
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-0.5">
              Zero linking codes needed. Every trader who interacts with the bot is instantly subscribed to live Quotex AI signals.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={loadData}
            disabled={loading}
            className="px-3 py-1.5 bg-surface-dark border border-surface-border text-gray-300 hover:text-white rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          <a
            href={`https://t.me/${status?.bot_username || 'TradePulse_101_bot'}`}
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white rounded-xl text-xs font-bold flex items-center space-x-2 shadow-glow-cyan transition"
          >
            <span>Open @{status?.bot_username || 'TradePulse_101_bot'}</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>

      {/* Broadcast Summary Card */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="glass-panel p-5 space-y-2">
          <div className="flex items-center justify-between text-gray-400 text-xs font-semibold">
            <span>Broadcasting Bot</span>
            <Radio className="w-4 h-4 text-cyan-400 animate-pulse" />
          </div>
          <div className="text-xl font-bold text-white tracking-wide flex items-center space-x-2">
            <span>@{status?.bot_username || 'TradePulse_101_bot'}</span>
          </div>
          <p className="text-[11px] text-emerald-400 font-medium flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5" /> Connected & Polling 24/7
          </p>
        </div>

        <div className="glass-panel p-5 space-y-2">
          <div className="flex items-center justify-between text-gray-400 text-xs font-semibold">
            <span>Active Subscribers</span>
            <Users className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-2xl font-bold text-white tracking-wide">
            {subscribers.filter(s => s.is_active && !s.is_muted).length} <span className="text-sm font-normal text-gray-400">Traders</span>
          </div>
          <p className="text-[11px] text-gray-400">
            Auto-subscribed upon sending <code className="text-cyan-300">/start</code>
          </p>
        </div>

        <div className="glass-panel p-5 space-y-2">
          <div className="flex items-center justify-between text-gray-400 text-xs font-semibold">
            <span>Signal Dispatch Engine</span>
            <Zap className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-lg font-bold text-white">
            Quotex 1M OTC Scanner
          </div>
          <p className="text-[11px] text-gray-400">
            Multi-timeframe AI confirmation active
          </p>
        </div>
      </div>

      {/* Instant Broadcast Control */}
      <div className="glass-panel p-6 space-y-4 border border-cyan-900/40 bg-cyan-950/20">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="space-y-1">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-cyan-400" /> Instant Signal Dispatch Test
            </h3>
            <p className="text-xs text-gray-300">
              Dispatches an enriched <b>SMC Institutional</b> interactive signal card directly to all active Telegram subscribers.
            </p>
          </div>
          <button
            onClick={handleSendBroadcast}
            disabled={testing || subscribers.length === 0}
            className="px-5 py-2.5 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 disabled:opacity-50 text-white rounded-xl text-xs font-bold flex items-center justify-center space-x-2 shadow-glow-green transition whitespace-nowrap"
          >
            {testing ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            <span>{testing ? 'Broadcasting...' : 'Broadcast Test Signal Now'}</span>
          </button>
        </div>

        {feedback && (
          <div className={`p-3 rounded-lg text-xs font-medium ${
            feedback.startsWith('✅') 
              ? 'bg-emerald-950/80 border border-emerald-700/60 text-emerald-300' 
              : 'bg-amber-950/80 border border-amber-700/60 text-amber-300'
          }`}>
            {feedback}
          </div>
        )}
      </div>

      {/* Subscriber Management Table */}
      <div className="glass-panel p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-surface-border pb-3">
          <div className="flex items-center space-x-2">
            <Users className="w-4 h-4 text-primary" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">
              Subscribed Telegram Traders ({subscribers.length})
            </h2>
          </div>
          <div className="flex items-center space-x-2">
            {subscribers.length > 0 && (
              <button
                onClick={handleClearAllSubscribers}
                disabled={clearing}
                className="px-3 py-1 bg-red-950/60 hover:bg-red-900/80 border border-red-800/60 text-red-300 rounded-lg text-xs font-medium flex items-center space-x-1.5 transition"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>{clearing ? 'Clearing...' : 'Clear Old Subscribers'}</span>
              </button>
            )}
            <span className="text-xs text-gray-400 hidden sm:inline-block">
              Real-time registry
            </span>
          </div>
        </div>

        {subscribers.length === 0 ? (
          <div className="py-12 text-center space-y-3">
            <div className="w-12 h-12 rounded-full bg-surface-dark border border-surface-border flex items-center justify-center mx-auto text-gray-500">
              <Users className="w-6 h-6" />
            </div>
            <p className="text-sm text-gray-300 font-semibold">Subscriber Registry is Empty</p>
            <p className="text-xs text-gray-500 max-w-sm mx-auto">
              Open <b>@{status?.bot_username || 'TradePulse_101_bot'}</b> on Telegram and tap <b>/start</b> to immediately appear here!
            </p>
            <a
              href={`https://t.me/${status?.bot_username || 'TradePulse_101_bot'}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center space-x-2 px-4 py-2 bg-cyan-600/30 hover:bg-cyan-600/50 border border-cyan-500/50 text-cyan-300 rounded-lg text-xs font-bold transition"
            >
              <span>Open @{status?.bot_username || 'TradePulse_101_bot'}</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-surface-border text-gray-400">
                  <th className="pb-3 font-semibold">Trader / Name</th>
                  <th className="pb-3 font-semibold">Telegram ID</th>
                  <th className="pb-3 font-semibold">Chat ID</th>
                  <th className="pb-3 font-semibold">Status</th>
                  <th className="pb-3 font-semibold">Subscribed Since</th>
                  <th className="pb-3 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border/50">
                {subscribers.map((sub) => (
                  <tr key={sub.id} className="hover:bg-white/[0.02] transition">
                    <td className="py-3 font-medium text-white flex items-center space-x-2">
                      <div className="w-7 h-7 rounded-full bg-cyan-950 border border-cyan-700/60 flex items-center justify-center text-cyan-400 font-bold text-[10px]">
                        {(sub.first_name || sub.telegram_username || 'T').charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <div>{sub.first_name || 'Anonymous Trader'}</div>
                        {sub.telegram_username && (
                          <div className="text-[10px] text-gray-500">@{sub.telegram_username}</div>
                        )}
                      </div>
                    </td>
                    <td className="py-3 text-gray-300 font-mono text-[11px]">{sub.telegram_user_id}</td>
                    <td className="py-3 text-gray-300 font-mono text-[11px]">{sub.telegram_chat_id}</td>
                    <td className="py-3">
                      {sub.is_active && !sub.is_muted ? (
                        <span className="px-2 py-0.5 text-[10px] font-bold bg-emerald-950 text-emerald-400 border border-emerald-800 rounded-full">
                          ACTIVE (Receiving)
                        </span>
                      ) : sub.is_muted ? (
                        <span className="px-2 py-0.5 text-[10px] font-bold bg-amber-950 text-amber-400 border border-amber-800 rounded-full">
                          MUTED
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 text-[10px] font-bold bg-gray-800 text-gray-400 rounded-full">
                          PAUSED
                        </span>
                      )}
                    </td>
                    <td className="py-3 text-gray-400 text-[11px]">
                      {new Date(sub.created_at).toLocaleString()}
                    </td>
                    <td className="py-3 text-right">
                      <button
                        onClick={() => handleDeleteSubscriber(sub.id)}
                        className="p-1 hover:bg-red-950/60 text-gray-500 hover:text-red-400 rounded transition"
                        title="Remove subscriber"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Information Box */}
      <div className="glass-panel p-5 border border-surface-border text-xs text-gray-400 space-y-2">
        <div className="flex items-center space-x-2 text-white font-semibold">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span>How Broadcaster Works</span>
        </div>
        <p className="leading-relaxed">
          The background market scanner checks Quotex OTC 1-Minute candles on AWS continuously. When algorithmic Smart Money Concepts criteria (Fair Value Gap, Liquidity Sweep, BOS, Wick Rejection) are satisfied and validated by AI confidence score, the server automatically broadcasts rich interactive signal cards to all subscribers listed above simultaneously.
        </p>
      </div>
    </div>
  );
};
