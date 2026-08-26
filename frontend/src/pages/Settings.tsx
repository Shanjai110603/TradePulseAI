import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { authApi } from '../services/api';
import { Settings as SettingsIcon, Shield, Sliders, Check } from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const { user, refreshUser } = useAuth();
  const [minAiScore, setMinAiScore] = useState(70);
  const [minConfidence, setMinConfidence] = useState('MODERATE');
  const [notifyAll, setNotifyAll] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (user?.preferences) {
      setMinAiScore(user.preferences.min_ai_score);
      setMinConfidence(user.preferences.min_confidence);
      setNotifyAll(user.preferences.notify_on_all_signals);
    }
  }, [user]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await authApi.updatePreferences({
        min_ai_score: minAiScore,
        min_confidence: minConfidence,
        allowed_risk_levels: ['LOW', 'MODERATE', 'HIGH'],
        notify_on_all_signals: notifyAll,
        notify_on_status_change: true,
        notify_on_outcome: true,
        quiet_hours_enabled: false
      });
      await refreshUser();
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      console.error('Failed to save preferences', err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div>
        <div className="flex items-center space-x-2">
          <SettingsIcon className="w-5 h-5 text-primary" />
          <h1 className="text-xl font-bold text-white tracking-wide">Workstation Preferences</h1>
        </div>
        <p className="text-xs text-gray-400 mt-1">
          Global filter defaults and notification thresholds across all active patterns.
        </p>
      </div>

      <form onSubmit={handleSave} className="glass-panel p-6 space-y-6">
        <h2 className="text-sm font-semibold text-white font-mono border-b border-surface-border/80 pb-3">
          Global Research Filters
        </h2>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-mono text-gray-300">Global Minimum AI Score Threshold</label>
            <input
              type="number"
              min={0}
              max={100}
              value={minAiScore}
              onChange={(e) => setMinAiScore(Number(e.target.value))}
              className="w-full bg-surface-raised border border-surface-border rounded-lg px-4 py-2 text-sm text-white font-mono"
            />
            <span className="text-[11px] text-gray-500 font-mono">
              Signals below this score will be blocked unless pattern overrides with a specific threshold.
            </span>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-mono text-gray-300">Minimum AI Confidence Level</label>
            <select
              value={minConfidence}
              onChange={(e) => setMinConfidence(e.target.value)}
              className="w-full bg-surface-raised border border-surface-border rounded-lg px-4 py-2.5 text-sm text-white font-mono"
            >
              <option value="LOW">LOW</option>
              <option value="MODERATE">MODERATE (Default)</option>
              <option value="HIGH">HIGH Only</option>
            </select>
          </div>

          <div className="flex items-center space-x-3 p-3 glass-card rounded-lg">
            <input
              type="checkbox"
              id="notify-all"
              checked={notifyAll}
              onChange={(e) => setNotifyAll(e.target.checked)}
              className="w-4 h-4 rounded text-primary"
            />
            <label htmlFor="notify-all" className="text-xs font-semibold text-white">
              Dispatch instant notifications for all passing research signals
            </label>
          </div>
        </div>

        <div className="flex items-center space-x-4 pt-4 border-t border-surface-border/60">
          <button
            type="submit"
            disabled={saving}
            className="px-6 py-2.5 bg-primary hover:bg-primary-hover text-black rounded-xl font-bold text-xs font-mono transition-all shadow-glow-cyan flex items-center gap-2"
          >
            {saved ? <Check className="w-4 h-4" /> : null}
            <span>{saving ? 'Saving...' : saved ? 'Preferences Saved!' : 'Save Preferences'}</span>
          </button>
        </div>
      </form>
    </div>
  );
};
