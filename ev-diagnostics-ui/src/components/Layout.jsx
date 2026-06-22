import React, { useState } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  Menu, LogOut, LayoutDashboard, Battery, BarChart3, User, Zap, X,
} from 'lucide-react';

/**
 * Layout — top nav + optional sidebar, adapts by viewMode.
 *
 * - "admin":    full nav (Dashboard, Analytics, all batteries)
 * - "operator": nav without Fleet Summary, but battery access
 * - "customer": minimal nav — just "My Battery" + Logout, no sidebar
 */
export default function Layout() {
  const { viewMode, logout } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  const isCustomer = viewMode === 'customer';

  const navLinks = [];
  if (!isCustomer) {
    navLinks.push({ to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard });
    navLinks.push({ to: '/analytics', label: 'Analytics', icon: BarChart3 });
  }
  if (isCustomer) {
    navLinks.push({ to: '/my-battery', label: 'My Battery', icon: Battery });
  }

  const viewModeLabel = {
    admin: 'Fleet Admin',
    operator: 'Operator',
    customer: 'Customer',
  }[viewMode] || '';

  const viewModeColor = {
    admin: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/40',
    operator: 'bg-amber-500/20 text-amber-400 border-amber-500/40',
    customer: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
  }[viewMode] || '';

  return (
    <div className="min-h-screen flex flex-col bg-[#0A0F1E] text-slate-100">
      {/* ── Top Navigation Bar ─────────────────────────────────────────── */}
      <header className="border-b border-slate-800 bg-[#0C111C] shrink-0 z-30">
        <div className="flex items-center justify-between px-6 h-16">
          {/* Left: menu toggle + brand */}
          <div className="flex items-center gap-4">
            {!isCustomer && (
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="p-2 rounded-md border border-slate-700 text-slate-400 hover:text-cyan-400 hover:border-cyan-500/40 transition-all md:hidden"
                aria-label="Toggle sidebar"
              >
                {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
            )}
            <div className="flex items-center gap-3">
              <Zap className="w-6 h-6 text-cyan-400" />
              <h1 className="text-base font-bold tracking-widest uppercase text-slate-200 font-mono hidden sm:block">
                EV Battery Diagnostics
              </h1>
            </div>
          </div>

          {/* Center: navigation links */}
          <nav className="hidden md:flex items-center gap-1">
            {navLinks.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `flex items-center gap-2 px-4 py-2 rounded-md text-sm font-mono font-medium tracking-wider transition-all ${
                    isActive
                      ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 border border-transparent'
                  }`
                }
              >
                <Icon className="w-4 h-4" />
                {label}
              </NavLink>
            ))}
          </nav>

          {/* Right: role badge + logout */}
          <div className="flex items-center gap-3">
            <span className={`text-[11px] font-mono font-bold uppercase tracking-wider px-3 py-1.5 rounded-md border ${viewModeColor}`}>
              {viewModeLabel}
            </span>
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 px-3 py-2 rounded-md text-sm font-mono text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 border border-transparent hover:border-rose-500/30 transition-all"
              title="Logout"
            >
              <LogOut className="w-4 h-4" />
              <span className="hidden sm:inline">Logout</span>
            </button>
          </div>
        </div>

        {/* Mobile nav */}
        <div className="md:hidden border-t border-slate-800">
          <div className="flex items-center gap-1 px-4 py-2 overflow-x-auto">
            {navLinks.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `flex items-center gap-2 px-3 py-1.5 rounded text-xs font-mono whitespace-nowrap transition-all ${
                    isActive
                      ? 'bg-cyan-500/10 text-cyan-400'
                      : 'text-slate-400 hover:text-slate-200'
                  }`
                }
              >
                <Icon className="w-3.5 h-3.5" />
                {label}
              </NavLink>
            ))}
          </div>
        </div>
      </header>

      {/* ── Main Content ───────────────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
