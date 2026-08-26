import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Activity, Lock, Mail, User, ArrowRight } from 'lucide-react';

export const Register: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register(email, password, fullName);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Registration failed');
    } finally {
      setSubmitting(false);
    }
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
          <p className="text-xs text-gray-400">Initialize Your Strategy Research Terminal</p>
        </div>

        {/* Register Box */}
        <div className="glass-panel p-8 space-y-6">
          <h2 className="text-base font-semibold text-white border-b border-surface-border/80 pb-4">
            Create Trader Account
          </h2>

          {error && (
            <div className="p-3 rounded-lg bg-rose-950/60 border border-rose-800 text-rose-300 text-xs font-mono">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-mono text-gray-300">Full Name</label>
              <div className="relative">
                <User className="w-4 h-4 text-gray-500 absolute left-3 top-3" />
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full bg-surface-raised border border-surface-border rounded-lg pl-10 pr-4 py-2.5 text-sm text-white font-mono focus:border-primary outline-none"
                  placeholder="Alex Mercer"
                />
              </div>
            </div>

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
                  minLength={6}
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
              <span>{submitting ? 'Creating Session...' : 'Launch Station'}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          <div className="text-center pt-2 border-t border-surface-border/60">
            <span className="text-xs text-gray-400">Already registered? </span>
            <Link to="/login" className="text-xs text-primary hover:underline font-semibold font-mono">
              Sign In
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
