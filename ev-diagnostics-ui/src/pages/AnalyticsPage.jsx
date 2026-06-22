import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { getDegradation, getFleetSummary } from '../api/client';
import {
  Loader2, AlertTriangle, RefreshCw, BarChart3, Search,
} from 'lucide-react';

/**
 * AnalyticsPage — degradation time series for a selected battery.
 * Available to both admin and operator roles.
 */
export default function AnalyticsPage() {
  const { viewMode } = useAuth();
  const isAdmin = viewMode === 'admin';

  const [batteries, setBatteries] = useState([]);
  const [selectedBattery, setSelectedBattery] = useState('');
  const [degradation, setDegradation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [fleetLoading, setFleetLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load battery list for the selector
  useEffect(() => {
    async function loadBatteries() {
      try {
        setFleetLoading(true);
        const data = await getFleetSummary();
        setBatteries(data.batteries || []);
        if (data.batteries?.length > 0) {
          setSelectedBattery(data.batteries[0].battery_id);
        }
      } catch (err) {
        // If operator can't access fleet summary, show manual input
        setBatteries([]);
      } finally {
        setFleetLoading(false);
      }
    }
    loadBatteries();
  }, []);

  // Fetch degradation data when battery changes
  const fetchDegradation = useCallback(async () => {
    if (!selectedBattery) return;
    try {
      setLoading(true);
      setError(null);
      const data = await getDegradation(selectedBattery);
      setDegradation(data);
    } catch (err) {
      setError(err.message || 'Failed to load degradation data');
    } finally {
      setLoading(false);
    }
  }, [selectedBattery]);

  useEffect(() => {
    fetchDegradation();
  }, [fetchDegradation]);

  const chartData = degradation?.data?.map(d => ({
    date: d.date,
    avg_soh: d.avg_soh_percent,
    min_soh: d.min_soh_percent,
  })) || [];

  return (
    <div className="p-6 md:p-10 lg:p-12 space-y-8 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-100 font-mono tracking-wider uppercase flex items-center gap-3">
            <BarChart3 className="w-6 h-6 text-cyan-400" />
            Degradation Analytics
          </h2>
          <p className="text-sm text-slate-500 mt-1 font-mono">
            Daily SoH degradation time series
          </p>
        </div>
      </div>

      {/* Battery selector */}
      <div className="bg-[#111827] border border-slate-800 rounded-xl p-5">
        <label className="block text-xs font-mono text-slate-500 uppercase tracking-wider mb-2">
          Select Battery
        </label>
        {batteries.length > 0 ? (
          <select
            value={selectedBattery}
            onChange={(e) => setSelectedBattery(e.target.value)}
            className="w-full md:w-auto bg-[#0A0F1E] border border-slate-700 text-slate-200 text-sm font-mono rounded-md px-4 py-2.5 focus:outline-none focus:border-cyan-500/50 cursor-pointer"
          >
            {batteries.map(b => (
              <option key={b.battery_id} value={b.battery_id}>
                {b.battery_id} — {b.vehicle_id} ({b.status})
              </option>
            ))}
          </select>
        ) : (
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={selectedBattery}
              onChange={(e) => setSelectedBattery(e.target.value)}
              placeholder="Enter battery ID (e.g. B0005)"
              className="bg-[#0A0F1E] border border-slate-700 text-slate-200 text-sm font-mono rounded-md px-4 py-2.5 focus:outline-none focus:border-cyan-500/50 w-full md:w-64"
            />
            <button
              onClick={fetchDegradation}
              className="px-4 py-2.5 bg-cyan-500/20 border border-cyan-500/40 rounded-md text-sm font-mono text-cyan-400 hover:bg-cyan-500/30 transition-colors"
            >
              Load
            </button>
          </div>
        )}
      </div>

      {/* Chart */}
      <div className="bg-[#111827] border border-slate-800 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold font-mono text-slate-200 tracking-wider uppercase">
            SoH Over Time
          </h3>
          {degradation && (
            <span className="text-[11px] font-mono text-slate-500">
              {chartData.length} data points
            </span>
          )}
        </div>

        <div className="h-80 bg-[#050914] rounded-md border border-slate-800/80 pt-2">
          {loading ? (
            <div className="h-full flex items-center justify-center">
              <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
            </div>
          ) : error ? (
            <div className="h-full flex items-center justify-center text-rose-400 text-sm font-mono">
              {error}
            </div>
          ) : chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 20, left: -10, bottom: 5 }}>
                <CartesianGrid stroke="rgba(0,212,255,0.06)" strokeDasharray="3 3" />
                <XAxis dataKey="date" stroke="#475569" tick={{ fill: '#94A3B8', fontSize: 10, fontFamily: 'monospace' }} angle={-45} textAnchor="end" height={60} />
                <YAxis domain={[50, 100]} stroke="#475569" tick={{ fill: '#10B981', fontSize: 10, fontFamily: 'monospace' }} />
                <Tooltip contentStyle={{ backgroundColor: '#0F172A', borderColor: '#1E3A5F', borderRadius: '6px', fontFamily: 'monospace', fontSize: '11px' }} />
                <Line type="monotone" dataKey="avg_soh" stroke="#10B981" strokeWidth={2.5} dot={{ r: 2 }} name="Avg SoH (%)" />
                <Line type="monotone" dataKey="min_soh" stroke="#F59E0B" strokeWidth={1.5} dot={false} strokeDasharray="5 5" name="Min SoH (%)" />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-slate-600 font-mono text-sm">
              {selectedBattery ? 'No degradation data available for this battery' : 'Select a battery to view analytics'}
            </div>
          )}
        </div>

        <div className="flex items-center justify-center gap-6 mt-4">
          <div className="flex items-center gap-2">
            <span className="w-3 h-0.5 bg-emerald-400 rounded" />
            <span className="text-xs text-slate-400 font-mono">Average SoH</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-0.5 bg-amber-400 rounded border-dashed" style={{ borderBottom: '1px dashed #F59E0B' }} />
            <span className="text-xs text-slate-400 font-mono">Minimum SoH</span>
          </div>
        </div>
      </div>
    </div>
  );
}
