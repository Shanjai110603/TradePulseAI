import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Activity, Lock, Mail, ArrowRight, Sparkles } from 'lucide-react';

export const Login: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate('/dashboard');
    } catch (err: any) {
      console.error('Login submission error:', err);
      const serverDetail = err?.response?.data?.detail;
      if (typeof serverDetail === 'string') {
        setError(serverDetail);
      } else if (Array.isArray(serverDetail) && serverDetail.length > 0) {
        setError(serverDetail[0]?.msg || 'Validation error');
      } else {
        setError(err?.message ? `Login failed (${err.message})` : 'Invalid email or password');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const fillDemo = () => {
    setEmail('demo@tradepulse.ai');
    setPassword('password123');
  };

  return (
    <div className="min-h-screen bg-background flex flex-col justify-center items-center p-4">
      <div className="w-full max-w-md space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-primary to-emerald-400 p-[2px] shadow-glow-cyan mx-auto">
            <div className="w-full h-full bg-background rounded-[14px] flex items-center justify-center">
              <Activity className="w-6 h-6 text-primary" />
            </div>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-wide">TRADEPULSE AI</h1>
          <p className="text-xs text-gray-400">Personalized Market Research & Signal Station</p>
        </div>

        {/* Login Box */}
        <div className="glass-panel p-8 space-y-6">
          <div className="flex items-center justify-between border-b border-surface-border/80 pb-4">
            <h2 className="text-base font-semibold text-white">Sign In to Workstation</h2>
            <button
              type="button"
              onClick={fillDemo}
              className="text-xs text-primary hover:underline font-mono flex items-center gap-1 font-semibold"
            >
              <Sparkles className="w-3.5 h-3.5" />
              1-Click Demo Fill
            </button>
          </div>

          {error && (
            <div className="p-3 rounded-lg bg-rose-950/60 border border-rose-800 text-rose-300 text-xs font-mono">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-mono text-gray-300">Email Address</label>
              <div className="relative">
                <Mail className="w-4 h-4 text-gray-500 absolute left-3 top-3" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-surface-raised border border-surface-border rounded-lg pl-10 pr-4 py-2.5 text-sm text-white font-mono focus:border-primary outline-none"
                  placeholder="analyst@tradepulse.ai"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-mono text-gray-300">Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-gray-500 absolute left-3 top-3" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-surface-raised border border-surface-border rounded-lg pl-10 pr-4 py-2.5 text-sm text-white font-mono focus:border-primary outline-none"
                  placeholder="••••••••"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full py-3 bg-primary hover:bg-primary-hover text-black rounded-xl font-bold text-xs font-mono transition-all shadow-glow-cyan flex items-center justify-center gap-2"
            >
              <span>{submitting ? 'Authenticating...' : 'Access Dashboard'}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          <div className="text-center pt-2 border-t border-surface-border/60">
            <span className="text-xs text-gray-400">Don't have an account? </span>
            <Link to="/register" className="text-xs text-primary hover:underline font-semibold font-mono">
              Create One
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
