import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Zap, Shield, Wrench, User, Loader2, AlertCircle } from 'lucide-react';

/**
 * LoginPage — 3-button preset login (Admin / Operator / Customer).
 * No typing required — each button uses preset demo credentials.
 */
export default function LoginPage() {
  const { login, isLoading, error } = useAuth();
  const navigate = useNavigate();
  const [loadingRole, setLoadingRole] = useState(null);

  const handleLogin = async (presetRole) => {
    setLoadingRole(presetRole);
    const success = await login(presetRole);
    if (success) {
      const destination = presetRole === 'customer' ? '/my-battery' : '/dashboard';
      navigate(destination, { replace: true });
    }
    setLoadingRole(null);
  };

  const roles = [
    {
      key: 'admin',
      label: 'Login as Admin',
      description: 'Fleet-wide diagnostics, analytics, and full battery management',
      icon: Shield,
      gradient: 'from-cyan-600 to-blue-700',
      hoverGradient: 'from-cyan-500 to-blue-600',
      border: 'border-cyan-500/30',
      glow: 'shadow-cyan-500/20',
      badge: 'Fleet Admin',
      badgeColor: 'bg-cyan-500/20 text-cyan-400',
    },
    {
      key: 'operator',
      label: 'Login as Operator',
      description: 'Battery telemetry monitoring and health status access',
      icon: Wrench,
      gradient: 'from-amber-600 to-orange-700',
      hoverGradient: 'from-amber-500 to-orange-600',
      border: 'border-amber-500/30',
      glow: 'shadow-amber-500/20',
      badge: 'Operator',
      badgeColor: 'bg-amber-500/20 text-amber-400',
    },
    {
      key: 'customer',
      label: 'Login as Customer',
      description: 'View your battery health, remaining life, and recent activity',
      icon: User,
      gradient: 'from-emerald-600 to-teal-700',
      hoverGradient: 'from-emerald-500 to-teal-600',
      border: 'border-emerald-500/30',
      glow: 'shadow-emerald-500/20',
      badge: 'Customer',
      badgeColor: 'bg-emerald-500/20 text-emerald-400',
    },
  ];

  return (
    <div className="min-h-screen bg-[#0A0F1E] flex items-center justify-center p-6 relative overflow-hidden">
      {/* Background grid effect */}
      <div
        className="absolute inset-0 opacity-30"
        style={{
          backgroundSize: '40px 40px',
          backgroundImage:
            'linear-gradient(to right, rgba(0,212,255,0.04) 1px, transparent 1px), linear-gradient(to bottom, rgba(0,212,255,0.04) 1px, transparent 1px)',
        }}
      />

      {/* Radial glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-cyan-500/5 rounded-full blur-3xl pointer-events-none" />

      <div className="relative z-10 w-full max-w-lg">
        {/* Header */}
        <div className="text-center mb-10">
          <div className="flex items-center justify-center gap-3 mb-4">
            <div className="p-3 bg-cyan-500/10 border border-cyan-500/30 rounded-xl">
              <Zap className="w-8 h-8 text-cyan-400" />
            </div>
          </div>
          <h1 className="text-2xl font-bold text-slate-100 tracking-wider font-mono uppercase">
            EV Battery Diagnostics
          </h1>
          <p className="text-sm text-slate-500 mt-2 font-mono">
            Select your access level to continue
          </p>
        </div>

        {/* Login buttons */}
        <div className="space-y-4">
          {roles.map(({ key, label, description, icon: Icon, gradient, hoverGradient, border, glow, badge, badgeColor }) => {
            const isThisLoading = isLoading && loadingRole === key;
            const isDisabled = isLoading;

            return (
              <button
                key={key}
                onClick={() => handleLogin(key)}
                disabled={isDisabled}
                className={`
                  w-full group relative overflow-hidden rounded-xl border ${border}
                  bg-gradient-to-r ${gradient} hover:${hoverGradient}
                  p-5 text-left transition-all duration-300
                  hover:shadow-lg hover:${glow} hover:scale-[1.01]
                  disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:scale-100
                  active:scale-[0.99]
                `}
              >
                {/* Shimmer effect */}
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-700" />

                <div className="relative flex items-center gap-4">
                  <div className="p-2.5 bg-white/10 rounded-lg backdrop-blur-sm shrink-0">
                    {isThisLoading ? (
                      <Loader2 className="w-6 h-6 text-white animate-spin" />
                    ) : (
                      <Icon className="w-6 h-6 text-white" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1">
                      <span className="text-base font-bold text-white font-mono tracking-wide">
                        {isThisLoading ? 'Authenticating...' : label}
                      </span>
                      <span className={`text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded ${badgeColor}`}>
                        {badge}
                      </span>
                    </div>
                    <p className="text-xs text-white/70 font-mono leading-relaxed">
                      {description}
                    </p>
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        {/* Error display */}
        {error && (
          <div className="mt-6 flex items-center gap-3 bg-rose-500/10 border border-rose-500/30 rounded-lg px-4 py-3">
            <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
            <p className="text-sm text-rose-300 font-mono">{error}</p>
          </div>
        )}

        {/* Footer */}
        <p className="text-center text-[11px] text-slate-600 mt-8 font-mono">
          Demo credentials are preset · No password entry required
        </p>
      </div>
    </div>
  );
}
