import React, { useState, useEffect } from 'react';
import { telegramApi } from '../services/api';
import { TelegramStatus } from '../types';
import { 
  Send, 
  KeyRound, 
  Copy, 
  Check, 
  CheckCircle2, 
  AlertCircle, 
  Bell, 
  ExternalLink, 
  ShieldCheck, 
  Radio 
} from 'lucide-react';

export const TelegramSettings: React.FC = () => {
  const [status, setStatus] = useState<TelegramStatus | null>(null);
  const [linkCode, setLinkCode] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testSent, setTestSent] = useState(false);

  const loadStatus = async () => {
    try {
      const st = await telegramApi.getStatus();
      setStatus(st);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadStatus();
  }, []);

  const handleGenerateCode = async () => {
    setGenerating(true);
    try {
      const res = await telegramApi.generateLinkCode();
      setLinkCode(res.code);
      setExpiresAt(new Date(res.expires_at).toLocaleTimeString());
    } catch (e) {
      console.error(e);
    } finally {
      setGenerating(false);
    }
  };

  const handleCopy = () => {
    if (linkCode) {
      navigator.clipboard.writeText(`/link ${linkCode}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleSendTest = async () => {
    setTesting(true);
    try {
      await telegramApi.sendTestNotification();
      setTestSent(true);
      setTimeout(() => setTestSent(false), 4000);
    } catch (e) {
      console.error(e);
      alert('Failed to send test notification. Please verify account is linked.');
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div>
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-cyan-950/80 border border-cyan-700/60 flex items-center justify-center text-primary shadow-glow-cyan">
            <Send className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-wide">Telegram Signal Station</h1>
            <p className="text-xs text-gray-400 mt-0.5">
              Securely link your Telegram account to receive real-time research signal cards with interactive buttons.
            </p>
          </div>
        </div>
      </div>

      {/* Main Connection Card */}
      <div className="glass-panel p-6 space-y-6">
        <div className="flex items-center justify-between border-b border-surface-border/80 pb-4">
          <div className="flex items-center space-x-3">
            <div
              className={`w-3 h-3 rounded-full ${
                status?.is_linked ? 'bg-emerald-400 shadow-glow-green animate-pulse' : 'bg-gray-500'
              }`}
            />
            <div>
              <h2 className="font-semibold text-sm text-white">Connection Status</h2>
              <p className="text-xs text-gray-400">
                {status?.is_linked
                  ? `Linked to chat ID: ${status.telegram_chat_id}`
                  : 'No Telegram account currently linked to your session.'}
              </p>
            </div>
          </div>

          <span
            className={`text-xs font-mono font-bold px-3 py-1 rounded-full ${
              status?.is_linked
                ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                : 'bg-surface-raised text-gray-400 border border-surface-border'
            }`}
          >
            {status?.is_linked ? 'ACTIVE & CONNECTED' : 'NOT LINKED'}
          </span>
        </div>

        {/* Step-by-Step Linking Instructions */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-4">
            <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-gray-400">
              How to Connect:
            </h3>
            <ol className="list-decimal list-inside text-xs space-y-2.5 text-gray-300 font-mono">
              <li>Click the button to generate a secure 6-character linking code.</li>
              <li>
                Open the Telegram bot:{' '}
                <a
                  href={`https://t.me/${status?.bot_username || 'TradePulseAIBot'}`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-primary hover:underline font-bold inline-flex items-center gap-1"
                >
                  @{status?.bot_username || 'TradePulseAIBot'}
                  <ExternalLink className="w-3 h-3" />
                </a>
              </li>
              <li>Send the command: <code className="text-white bg-surface-raised px-1.5 py-0.5 rounded">/link &lt;CODE&gt;</code></li>
              <li>Your workstation is instantly connected!</li>
            </ol>

            <button
              onClick={handleGenerateCode}
              disabled={generating}
              className="px-5 py-2.5 bg-primary hover:bg-primary-hover text-black rounded-xl font-bold text-xs font-mono transition-all shadow-glow-cyan flex items-center gap-2"
            >
              <KeyRound className="w-4 h-4" />
              <span>{generating ? 'Generating...' : 'Generate New Linking Code'}</span>
            </button>
          </div>

          {/* Code Display Area */}
          <div className="glass-card p-5 flex flex-col justify-between space-y-4">
            <div>
              <span className="text-[10px] font-mono text-gray-500 block">TEMPORARY LINKING CODE</span>
              {linkCode ? (
                <div className="mt-2 space-y-2">
                  <div className="flex items-center justify-between bg-surface p-3 rounded-lg border border-primary/50">
                    <span className="font-mono text-2xl font-bold tracking-widest text-primary">
                      {linkCode}
                    </span>
                    <button
                      onClick={handleCopy}
                      className="px-3 py-1.5 bg-primary/20 hover:bg-primary/30 text-primary border border-primary/30 rounded text-xs font-mono flex items-center gap-1 transition-colors"
                    >
                      {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                      <span>{copied ? 'Copied!' : 'Copy'}</span>
                    </button>
                  </div>
                  <p className="text-[11px] text-gray-400 font-mono">
                    Expires at: <span className="text-white">{expiresAt}</span> (Valid for 15 mins)
                  </p>
                </div>
              ) : (
                <div className="mt-4 py-8 text-center text-gray-500 font-mono text-xs">
                  Click "Generate New Linking Code" to begin.
                </div>
              )}
            </div>

            {/* Test Notification Dispatch Button */}
            {status?.is_linked && (
              <div className="pt-3 border-t border-surface-border/60">
                <button
                  onClick={handleSendTest}
                  disabled={testing}
                  className="w-full py-2 bg-emerald-950 hover:bg-emerald-900 text-emerald-300 border border-emerald-800 rounded-lg text-xs font-mono font-semibold transition-colors flex items-center justify-center gap-2"
                >
                  <Radio className="w-3.5 h-3.5" />
                  <span>{testSent ? 'Alert Dispatched to Telegram!' : 'Send Sample Pattern 14 Alert'}</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
