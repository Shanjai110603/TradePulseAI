import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Layers, 
  PlusCircle, 
  Radio, 
  TrendingUp, 
  BarChart3, 
  Send, 
  Globe, 
  Settings, 
  ShieldCheck 
} from 'lucide-react';

export const Sidebar: React.FC = () => {
  const navItems = [
    { to: '/dashboard', label: 'Command Center', icon: LayoutDashboard },
    { to: '/markets', label: 'Market Explorer', icon: Globe },
    { to: '/patterns', label: 'Pattern Library', icon: Layers },
    { to: '/patterns/new', label: 'Build New Strategy', icon: PlusCircle, highlight: true },
    { to: '/signals', label: 'Live Signal Stream', icon: Radio },
    { to: '/performance', label: 'Analytics & Alpha', icon: BarChart3 },
    { to: '/settings/telegram', label: 'Telegram Station', icon: Send },
    { to: '/settings', label: 'Preferences', icon: Settings },
    { to: '/admin', label: 'Health & Audit', icon: ShieldCheck },
  ];

  return (
    <aside className="w-64 border-r border-surface-border bg-surface/80 flex flex-col justify-between p-4 hidden md:flex min-h-[calc(100vh-4rem)]">
      <div className="space-y-6">
        <div>
          <p className="text-[10px] font-mono uppercase tracking-wider text-gray-500 font-semibold px-3 mb-2">
            Workstation
          </p>
          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/patterns'}
                  className={({ isActive }) =>
                    `flex items-center space-x-3 px-3 py-2.5 rounded-xl text-xs font-medium transition-all ${
                      isActive
                        ? 'bg-primary/15 text-primary border border-primary/30 shadow-glow-cyan/50 font-semibold'
                        : item.highlight
                        ? 'bg-primary/10 text-cyan-300 hover:bg-primary/20 hover:text-white border border-primary/20'
                        : 'text-gray-400 hover:text-gray-200 hover:bg-surface-raised/80'
                    }`
                  }
                >
                  <Icon className={`w-4 h-4 ${item.highlight ? 'text-primary' : ''}`} />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </nav>
        </div>

        {/* Quick System Badge */}
        <div className="glass-card bg-surface/50 border-surface-border/60 p-3 rounded-xl">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-semibold text-gray-300 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              Engine Status
            </span>
            <span className="text-[10px] font-mono text-emerald-400 font-semibold">ONLINE</span>
          </div>
          <p className="text-[11px] text-gray-400 leading-relaxed">
            Deterministic rule engine scanning 1M/5M feeds with AI enrichment layer active.
          </p>
        </div>
      </div>

      {/* Scope Disclaimer */}
      <div className="pt-4 border-t border-surface-border/60 text-[10px] text-gray-400 font-mono">
        <p className="font-semibold text-gray-400 uppercase tracking-wider mb-1">Scope Restriction</p>
        <p>Market Research & Signal Station Only. Zero automated trade execution.</p>
      </div>
    </aside>
  );
};
