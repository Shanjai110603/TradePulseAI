import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { telegramApi } from '../../services/api';
import { TelegramStatus } from '../../types';
import { Activity, Bell, Send, Shield, User as UserIcon, LogOut, ChevronDown, CheckCircle2, AlertCircle } from 'lucide-react';

export const Navbar: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [tgStatus, setTgStatus] = useState<TelegramStatus | null>(null);
  const [showDropdown, setShowDropdown] = useState(false);

  useEffect(() => {
    if (user) {
      telegramApi.getStatus().then(setTgStatus).catch(console.error);
    }
  }, [user]);

  return (
    <header className="h-16 border-b border-surface-border bg-surface/90 backdrop-blur-md sticky top-0 z-40 px-6 flex items-center justify-between">
      {/* Brand & Market Ticker */}
      <div className="flex items-center space-x-6">
        <Link to="/dashboard" className="flex items-center space-x-3 group">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-primary to-emerald-400 p-[2px] shadow-glow-cyan transition-transform group-hover:scale-105">
            <div className="w-full h-full bg-background rounded-[10px] flex items-center justify-center">
              <Activity className="w-5 h-5 text-primary" />
            </div>
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-lg tracking-wider bg-clip-text text-transparent bg-gradient-to-r from-white via-gray-200 to-primary">
                TRADEPULSE
              </span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary/20 text-primary font-mono font-semibold border border-primary/30">
                AI PRO
              </span>
            </div>
            <p className="text-[10px] text-gray-400 tracking-tight">Market Research & Signal Station</p>
          </div>
        </Link>

        {/* Live Mini Market Bar */}
        <div className="hidden lg:flex items-center space-x-4 pl-6 border-l border-surface-border/60 text-xs font-mono">
          <div className="flex items-center space-x-2 bg-surface-raised/60 px-3 py-1.5 rounded-lg border border-surface-border/40">
            <span className="text-gray-400">EUR/USD</span>
            <span className="text-trade-up font-semibold">1.08542</span>
            <span className="text-[10px] text-trade-up font-medium">+0.18%</span>
          </div>
          <div className="flex items-center space-x-2 bg-surface-raised/60 px-3 py-1.5 rounded-lg border border-surface-border/40">
            <span className="text-gray-400">BTC/USDT</span>
            <span className="text-trade-up font-semibold">67,520.40</span>
            <span className="text-[10px] text-trade-up font-medium">+2.45%</span>
          </div>
          <div className="flex items-center space-x-2 bg-surface-raised/60 px-3 py-1.5 rounded-lg border border-surface-border/40">
            <span className="text-gray-400">GBP/USD</span>
            <span className="text-trade-down font-semibold">1.27180</span>
            <span className="text-[10px] text-trade-down font-medium">-0.05%</span>
          </div>
        </div>
      </div>

      {/* Right Controls */}
      <div className="flex items-center space-x-4">
        {/* Telegram Status Badge */}
        <Link
          to="/settings/telegram"
          className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
            tgStatus?.is_linked
              ? 'bg-emerald-950/40 text-emerald-300 border-emerald-800/60 hover:bg-emerald-900/50'
              : 'bg-surface-raised text-primary border-primary/30 hover:border-primary/60 hover:shadow-glow-cyan'
          }`}
        >
          <Send className="w-3.5 h-3.5" />
          <span>{tgStatus?.is_linked ? 'Telegram Linked' : 'Connect Telegram'}</span>
          {tgStatus?.is_linked ? (
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          ) : (
            <span className="w-2 h-2 rounded-full bg-primary animate-ping" />
          )}
        </Link>

        {/* User Profile Menu */}
        {user ? (
          <div className="relative">
            <button
              onClick={() => setShowDropdown(!showDropdown)}
              className="flex items-center space-x-3 px-3 py-1.5 rounded-lg bg-surface-raised hover:bg-surface-border/80 border border-surface-border text-sm transition-colors"
            >
              <div className="w-7 h-7 rounded-full bg-primary/20 text-primary flex items-center justify-center font-bold text-xs border border-primary/30">
                {user.full_name ? user.full_name.charAt(0).toUpperCase() : user.email.charAt(0).toUpperCase()}
              </div>
              <span className="text-xs font-medium text-gray-200 hidden sm:inline-block max-w-[120px] truncate">
                {user.full_name || user.email}
              </span>
              <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
            </button>

            {showDropdown && (
              <div className="absolute right-0 mt-2 w-56 glass-panel p-2 shadow-2xl z-50 animate-in fade-in slide-in-from-top-2 duration-150">
                <div className="px-3 py-2 border-b border-surface-border/60 mb-1">
                  <p className="text-xs font-semibold text-white">{user.full_name || 'Trader'}</p>
                  <p className="text-[11px] text-gray-400 truncate">{user.email}</p>
                </div>
                <Link
                  to="/settings"
                  onClick={() => setShowDropdown(false)}
                  className="flex items-center space-x-2 px-3 py-2 rounded-md text-xs text-gray-300 hover:text-white hover:bg-surface-raised transition-colors"
                >
                  <UserIcon className="w-4 h-4 text-primary" />
                  <span>Account & Preferences</span>
                </Link>
                <Link
                  to="/settings/telegram"
                  onClick={() => setShowDropdown(false)}
                  className="flex items-center space-x-2 px-3 py-2 rounded-md text-xs text-gray-300 hover:text-white hover:bg-surface-raised transition-colors"
                >
                  <Send className="w-4 h-4 text-cyan-400" />
                  <span>Telegram Bot Controls</span>
                </Link>
                <Link
                  to="/admin"
                  onClick={() => setShowDropdown(false)}
                  className="flex items-center space-x-2 px-3 py-2 rounded-md text-xs text-gray-300 hover:text-white hover:bg-surface-raised transition-colors"
                >
                  <Shield className="w-4 h-4 text-emerald-400" />
                  <span>System Health Monitor</span>
                </Link>
                <div className="border-t border-surface-border/60 mt-1 pt-1">
                  <button
                    onClick={() => {
                      logout();
                      navigate('/login');
                    }}
                    className="w-full flex items-center space-x-2 px-3 py-2 rounded-md text-xs text-rose-400 hover:bg-rose-950/40 transition-colors text-left"
                  >
                    <LogOut className="w-4 h-4" />
                    <span>Sign Out</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center space-x-3">
            <Link
              to="/login"
              className="px-4 py-2 text-xs font-semibold text-gray-300 hover:text-white transition-colors"
            >
              Sign In
            </Link>
            <Link
              to="/register"
              className="px-4 py-2 text-xs font-semibold bg-primary hover:bg-primary-hover text-black rounded-lg transition-all shadow-glow-cyan"
            >
              Get Started
            </Link>
          </div>
        )}
      </div>
    </header>
  );
};
