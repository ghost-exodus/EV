import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { getFleetSummary, getTelemetry, getSoH, getRUL } from '../api/client';
import {
  Battery, Activity, AlertTriangle, CheckCircle, XCircle,
  Search, RefreshCw, Loader2, ChevronRight, Cpu,
} from 'lucide-react';

/**
 * DashboardPage — fleet overview for admin/operator.
 *
 * - admin: sees fleet summary panel + full battery list
 * - operator: sees battery list only (no fleet summary)
 */

// Poll interval for fleet data (30 seconds)
const POLL_INTERVAL = 30_000;

export default function DashboardPage() {
  const { viewMode } = useAuth();
  const navigate = useNavigate();
  const isAdmin = viewMode === 'admin';

  const [fleetData, setFleetData] = useState(null);
  const [batteries, setBatteries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async (isRefresh = false) => {
    try {
      if (isRefresh) setRefreshing(true);
      else setLoading(true);
      setError(null);

      if (isAdmin) {
        const data = await getFleetSummary();
        setFleetData(data);
        setBatteries(data.batteries || []);
      } else {
        // Operators can't access fleet summary. We don't have a list-all-batteries endpoint,
        // so for now show fleet summary with operator JWT (it will 403 — fall back gracefully)
        try {
          const data = await getFleetSummary();
          setBatteries(data.batteries || []);
        } catch (err) {
          if (err.status === 403) {
            // Expected for operator — fleet summary is admin-only
            // For demo, show a message
            setBatteries([]);
          } else {
            throw err;
          }
        }
      }
    } catch (err) {
      setError(err.message || 'Failed to load data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [isAdmin]);

  useEffect(() => {
    fetchData();
    const timer = setInterval(() => fetchData(true), POLL_INTERVAL);
    return () => clearInterval(timer);
  }, [fetchData]);

  const filteredBatteries = batteries.filter(b =>
    b.battery_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
    b.vehicle_id.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getStatusStyle = (status) => {
    switch (status) {
      case 'healthy':
        return { color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', led: 'bg-emerald-500 shadow-[0_0_8px_#10B981]' };
      case 'warning':
        return { color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/30', led: 'bg-amber-500 shadow-[0_0_8px_#F59E0B]' };
      case 'critical':
        return { color: 'text-rose-400', bg: 'bg-rose-500/10', border: 'border-rose-500/30', led: 'bg-rose-500 shadow-[0_0_8px_#EF4444]' };
      default:
        return { color: 'text-slate-400', bg: 'bg-slate-500/10', border: 'border-slate-500/30', led: 'bg-slate-500' };
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="text-center space-y-4">
          <Loader2 className="w-10 h-10 text-cyan-400 animate-spin mx-auto" />
          <p className="text-sm text-slate-400 font-mono">Loading fleet data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-[60vh] px-6">
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-8 max-w-md text-center">
          <AlertTriangle className="w-10 h-10 text-rose-400 mx-auto mb-4" />
          <p className="text-rose-300 font-mono text-sm mb-4">{error}</p>
          <button
            onClick={() => fetchData()}
            className="px-4 py-2 bg-rose-500/20 border border-rose-500/40 rounded-md text-sm font-mono text-rose-300 hover:bg-rose-500/30 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-10 lg:p-12 space-y-8 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-100 font-mono tracking-wider uppercase">
            {isAdmin ? 'Fleet Dashboard' : 'Battery Overview'}
          </h2>
          <p className="text-sm text-slate-500 mt-1 font-mono">
            {isAdmin ? 'Real-time fleet diagnostics and health monitoring' : 'Battery telemetry and health monitoring'}
          </p>
        </div>
        <button
          onClick={() => fetchData(true)}
          disabled={refreshing}
          className="flex items-center gap-2 px-4 py-2 bg-slate-800/50 border border-slate-700 rounded-md text-sm font-mono text-slate-300 hover:border-cyan-500/40 hover:text-cyan-400 transition-all disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          {refreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {/* ── Fleet Summary Cards (Admin Only) ───────────────────────────── */}
      {isAdmin && fleetData && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Total Batteries */}
          <div className="bg-[#111827] border border-slate-800 rounded-xl p-5">
            <div className="flex items-center gap-2 text-slate-500 mb-3">
              <Battery className="w-4 h-4" />
              <span className="text-xs font-mono font-bold uppercase tracking-wider">Total Fleet</span>
            </div>
            <p className="text-3xl font-bold font-mono text-cyan-400">{fleetData.total_batteries}</p>
            <p className="text-[11px] text-slate-500 font-mono mt-1">Registered batteries</p>
          </div>

          {/* Fleet Average SoH */}
          <div className="bg-[#111827] border border-slate-800 rounded-xl p-5">
            <div className="flex items-center gap-2 text-slate-500 mb-3">
              <Activity className="w-4 h-4" />
              <span className="text-xs font-mono font-bold uppercase tracking-wider">Fleet Avg SoH</span>
            </div>
            <p className="text-3xl font-bold font-mono text-emerald-400">
              {fleetData.fleet_avg_soh_percent != null
                ? `${fleetData.fleet_avg_soh_percent}%`
                : 'N/A'}
            </p>
            <p className="text-[11px] text-slate-500 font-mono mt-1">Average health</p>
          </div>

          {/* Healthy */}
          <div className="bg-[#111827] border border-slate-800 rounded-xl p-5">
            <div className="flex items-center gap-2 text-emerald-400 mb-3">
              <CheckCircle className="w-4 h-4" />
              <span className="text-xs font-mono font-bold uppercase tracking-wider">Healthy</span>
            </div>
            <p className="text-3xl font-bold font-mono text-emerald-400">
              {fleetData.status_summary.healthy}
            </p>
            <div className="flex gap-2 mt-2">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
                {fleetData.status_summary.warning} warn
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/30">
                {fleetData.status_summary.critical} crit
              </span>
            </div>
          </div>

          {/* LSTM Engine Status */}
          <div className="bg-[#111827] border border-slate-800 rounded-xl p-5">
            <div className="flex items-center gap-2 text-slate-500 mb-3">
              <Cpu className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-mono font-bold uppercase tracking-wider">LSTM Engine</span>
            </div>
            <p className="text-sm font-bold font-mono text-emerald-400 mb-1">Online</p>
            <p className="text-[11px] text-slate-500 font-mono">Real-time predictions active</p>
          </div>
        </div>
      )}

      {/* ── Battery List ───────────────────────────────────────────────── */}
      <div className="bg-[#111827] border border-slate-800 rounded-xl overflow-hidden">
        {/* Search Bar */}
        <div className="p-4 border-b border-slate-800 flex items-center gap-3">
          <Search className="w-4 h-4 text-slate-500" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search by battery ID or vehicle ID..."
            className="flex-1 bg-transparent text-sm text-slate-200 placeholder-slate-600 font-mono outline-none"
          />
          <span className="text-[11px] font-mono text-slate-500">
            {filteredBatteries.length} batteries
          </span>
        </div>

        {/* Battery rows */}
        {filteredBatteries.length === 0 ? (
          <div className="p-12 text-center">
            <Battery className="w-10 h-10 text-slate-700 mx-auto mb-3" />
            <p className="text-sm text-slate-500 font-mono">
              {batteries.length === 0
                ? (viewMode === 'operator'
                  ? 'Fleet summary requires admin access. Navigate to a specific battery by ID.'
                  : 'No batteries found. Ingest telemetry data to populate the fleet.')
                : 'No batteries match your search.'}
            </p>
          </div>
        ) : (
          <div className="divide-y divide-slate-800/60">
            {filteredBatteries.map((bat) => {
              const style = getStatusStyle(bat.status);
              return (
                <button
                  key={bat.battery_id}
                  onClick={() => navigate(`/battery/${bat.battery_id}`)}
                  className="w-full flex items-center gap-4 p-4 hover:bg-slate-800/30 transition-colors text-left group"
                >
                  {/* Status LED */}
                  <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${style.led}`} />

                  {/* Battery info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1">
                      <span className="text-sm font-bold font-mono text-slate-200 group-hover:text-cyan-400 transition-colors">
                        {bat.battery_id}
                      </span>
                      <span className={`text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded border ${style.color} ${style.bg} ${style.border}`}>
                        {bat.status}
                      </span>
                    </div>
                    <span className="text-xs font-mono text-slate-500">{bat.vehicle_id}</span>
                  </div>

                  {/* SoH */}
                  <div className="hidden sm:block text-right">
                    <p className="text-xs font-mono text-slate-500">SoH</p>
                    <p className={`text-sm font-bold font-mono ${
                      bat.current_soh_percent != null
                        ? (bat.current_soh_percent > 80 ? 'text-emerald-400' : bat.current_soh_percent > 60 ? 'text-amber-400' : 'text-rose-400')
                        : 'text-slate-500'
                    }`}>
                      {bat.current_soh_percent != null ? `${bat.current_soh_percent.toFixed(1)}%` : 'N/A'}
                    </p>
                  </div>

                  {/* RUL */}
                  <div className="hidden md:block text-right">
                    <p className="text-xs font-mono text-slate-500">RUL</p>
                    <p className="text-sm font-bold font-mono text-slate-300">
                      {bat.predicted_rul_cycles != null ? `${bat.predicted_rul_cycles} cycles` : 'Pending'}
                    </p>
                  </div>

                  {/* Last seen */}
                  <div className="hidden lg:block text-right">
                    <p className="text-xs font-mono text-slate-500">Last Seen</p>
                    <p className="text-xs font-mono text-slate-400">
                      {bat.last_seen ? new Date(bat.last_seen).toLocaleString() : 'Never'}
                    </p>
                  </div>

                  <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-cyan-400 transition-colors shrink-0" />
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
