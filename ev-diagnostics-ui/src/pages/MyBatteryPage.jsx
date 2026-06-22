import React, { useState, useCallback } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { getTelemetry, getSoH, getRUL } from '../api/client';
import {
  Loader2, AlertTriangle, RefreshCw, Battery, Zap,
  CheckCircle, AlertCircle, Clock, Activity, Thermometer,
  Search, X
} from 'lucide-react';

export default function MyBatteryPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeBatteryId, setActiveBatteryId] = useState(null);
  
  const [soh, setSoH] = useState(null);
  const [rul, setRul] = useState(null);
  const [telemetry, setTelemetry] = useState(null);
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async (batteryId, isRefresh = false) => {
    if (!batteryId) return;
    
    try {
      if (isRefresh) setRefreshing(true);
      else {
        setLoading(true);
        setError(null);
        setTelemetry(null);
        setSoH(null);
        setRul(null);
        setActiveBatteryId(null);
      }

      // Fetch all three endpoints in parallel.
      // We don't catch telemetry because if it fails, we want the overall try/catch to handle it.
      // We DO catch SoH and RUL because missing predictions/snapshots are handled gracefully in UI.
      const telPromise = getTelemetry(batteryId, 20);
      const sohPromise = getSoH(batteryId).catch(e => ({ error: true, message: e.message, status: e.status }));
      const rulPromise = getRUL(batteryId).catch(e => ({ error: true, message: e.message, status: e.status }));

      const [telData, sohData, rulData] = await Promise.all([telPromise, sohPromise, rulPromise]);

      setTelemetry(telData);
      
      if (!sohData.error) setSoH(sohData);
      else setSoH(null);
      
      if (!rulData.error) setRul(rulData);
      else setRul({ status: 'pending', message: rulData.message });

      setActiveBatteryId(batteryId);
      
    } catch (err) {
      if (!isRefresh) {
        if (err.status === 404) {
          setError("No EV found with this ID. Please check and try again.");
        } else {
          setError("Something went wrong. Please try again.");
        }
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    const query = searchQuery.trim();
    if (!query) return;
    fetchData(query, false);
  };

  const handleClear = () => {
    setSearchQuery('');
    setActiveBatteryId(null);
    setTelemetry(null);
    setSoH(null);
    setRul(null);
    setError(null);
  };

  // Chart data
  const chartData = telemetry?.readings
    ? [...telemetry.readings].reverse().map(r => ({
        cycle: r.cycle_number,
        voltage: r.voltage_v,
        temp: r.temperature_c,
      }))
    : [];

  const sohVal = soh?.current_soh_percent;

  const getHealthLabel = (status) => {
    switch (status) {
      case 'healthy': return { text: 'Healthy', color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', icon: CheckCircle };
      case 'warning': return { text: 'Needs Attention', color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/30', icon: AlertCircle };
      case 'critical': return { text: 'Service Required', color: 'text-rose-400', bg: 'bg-rose-500/10', border: 'border-rose-500/30', icon: AlertTriangle };
      default: return { text: 'Unknown', color: 'text-slate-400', bg: 'bg-slate-500/10', border: 'border-slate-500/30', icon: Clock };
    }
  };

  return (
    <div className="p-6 md:p-10 lg:p-16 max-w-3xl mx-auto space-y-8">
      {/* ── Search Header ─────────────────────────────────────────────── */}
      <div className="text-center space-y-6">
        <div className="flex items-center justify-center gap-3">
          <Battery className="w-8 h-8 text-emerald-400" />
          <h1 className="text-2xl font-bold text-slate-100 tracking-wide">Lookup Your EV Battery</h1>
        </div>

        {!activeBatteryId && !loading && (
          <form onSubmit={handleSearch} className="max-w-md mx-auto">
            <div className="relative flex items-center">
              <Search className="absolute left-4 text-slate-400 w-5 h-5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Enter your EV ID (e.g. 00001)"
                disabled={loading}
                className="w-full bg-[#111827] border-2 border-slate-700 text-slate-200 text-base rounded-full pl-12 pr-32 py-3 focus:outline-none focus:border-emerald-500/50 transition-colors placeholder:text-slate-500"
              />
              <button
                type="submit"
                disabled={loading || !searchQuery.trim()}
                className="absolute right-2 bg-emerald-500 hover:bg-emerald-400 text-[#0A0F1E] font-semibold text-sm rounded-full px-5 py-2 transition-colors disabled:opacity-50"
              >
                Look Up
              </button>
            </div>
          </form>
        )}

        {error && (
          <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 max-w-md mx-auto flex items-start gap-3 text-left animate-fadeIn">
            <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <p className="text-rose-300 text-sm">{error}</p>
          </div>
        )}
      </div>

      {/* ── Loading State ─────────────────────────────────────────────── */}
      {loading && (
        <div className="flex items-center justify-center py-20 animate-fadeIn">
          <div className="text-center space-y-4">
            <Loader2 className="w-10 h-10 text-emerald-400 animate-spin mx-auto" />
            <p className="text-sm text-slate-400 font-mono">Fetching your battery data...</p>
          </div>
        </div>
      )}

      {/* ── Results State ─────────────────────────────────────────────── */}
      {activeBatteryId && !loading && (
        <div className="space-y-8 animate-fadeIn">
          {/* Results Header */}
          <div className="flex items-center justify-between bg-[#111827] border border-slate-800 rounded-xl px-5 py-3">
            <p className="text-sm text-slate-300">
              Showing results for EV <span className="font-mono text-emerald-400 font-bold ml-1">{activeBatteryId}</span>
            </p>
            <div className="flex items-center gap-3">
              <button
                onClick={() => fetchData(activeBatteryId, true)}
                disabled={refreshing}
                className="inline-flex items-center gap-2 text-xs text-slate-400 hover:text-emerald-400 transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
                {refreshing ? 'Updating...' : 'Refresh'}
              </button>
              <span className="w-px h-4 bg-slate-700" />
              <button
                onClick={handleClear}
                className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-rose-400 transition-colors"
              >
                <X className="w-3.5 h-3.5" />
                Clear search
              </button>
            </div>
          </div>

          {/* Health Status — Big Prominent Card */}
          <div className={`rounded-2xl border-2 ${getHealthLabel(soh?.status).border} ${getHealthLabel(soh?.status).bg} p-8 text-center transition-all`}>
            {(() => {
              const hl = getHealthLabel(soh?.status);
              const HIcon = hl.icon;
              return (
                <>
                  <HIcon className={`w-12 h-12 ${hl.color} mx-auto mb-4`} />
                  <h2 className={`text-3xl font-bold ${hl.color} mb-2`}>{hl.text}</h2>
                </>
              );
            })()}
            
            {sohVal != null ? (
              <>
                <p className="text-5xl font-extrabold text-white font-mono my-4">
                  {sohVal.toFixed(1)}
                  <span className="text-2xl text-slate-400">%</span>
                </p>
                <p className="text-slate-400 text-sm">Battery Health Level</p>

                <div className="mt-6 mx-auto max-w-xs">
                  <div className="h-4 bg-[#0A0F1E] rounded-full overflow-hidden border border-slate-700">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${
                        sohVal > 80 ? 'bg-gradient-to-r from-emerald-600 to-emerald-400'
                        : sohVal > 60 ? 'bg-gradient-to-r from-amber-600 to-amber-400'
                        : 'bg-gradient-to-r from-rose-600 to-rose-400'
                      }`}
                      style={{ width: `${sohVal}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-[10px] text-slate-600 mt-1.5 font-mono">
                    <span>0%</span>
                    <span>End of Life (70%)</span>
                    <span>100%</span>
                  </div>
                </div>
              </>
            ) : (
              <p className="text-slate-400 text-sm mt-2">Health data not yet available</p>
            )}
          </div>

          {/* Remaining Life */}
          <div className="bg-[#111827] border border-slate-800 rounded-2xl p-6">
            <div className="flex items-center gap-2 mb-4">
              <Clock className="w-5 h-5 text-amber-400" />
              <h3 className="text-base font-bold text-slate-200">Battery Life Estimate</h3>
            </div>

            {rul?.status === 'pending' ? (
              <div className="bg-amber-500/5 border border-amber-500/20 rounded-xl p-6 text-center">
                <Loader2 className="w-8 h-8 text-amber-400 animate-spin mx-auto mb-3" />
                <p className="text-amber-300 font-medium">Calculating your battery's remaining life...</p>
                <p className="text-xs text-slate-500 mt-2">
                  This requires more usage data. Check back after a few charge cycles.
                </p>
              </div>
            ) : rul?.status === 'ready' ? (
              <div className="text-center space-y-3">
                <p className="text-sm text-slate-400">Your battery has approximately</p>
                <p className="text-4xl font-extrabold font-mono text-amber-400">
                  {rul.predicted_rul_cycles}
                  <span className="text-lg text-slate-400 ml-2">charge cycles</span>
                </p>
                <p className="text-sm text-slate-500">remaining before service is recommended</p>
                {rul.confidence_interval && (
                  <p className="text-xs text-slate-600 mt-3">
                    Estimated range: {rul.confidence_interval.lower_bound} – {rul.confidence_interval.upper_bound} cycles
                    (at {rul.confidence_interval.confidence_percent}% confidence)
                  </p>
                )}
              </div>
            ) : (
              <p className="text-center text-slate-500 text-sm py-4">
                Life estimate is not yet available
              </p>
            )}
          </div>

          {/* Recent Activity Chart */}
          <div className="bg-[#111827] border border-slate-800 rounded-2xl p-6">
            <div className="flex items-center gap-2 mb-4">
              <Activity className="w-5 h-5 text-cyan-400" />
              <h3 className="text-base font-bold text-slate-200">Recent Activity</h3>
            </div>
            <p className="text-xs text-slate-500 mb-4">
              Voltage and temperature readings from your last {chartData.length} charge cycles
            </p>

            <div className="h-56 bg-[#0A0F1E] rounded-xl border border-slate-800 pt-2">
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 10, right: 15, left: -15, bottom: 5 }}>
                    <CartesianGrid stroke="rgba(255,255,255,0.04)" strokeDasharray="3 3" />
                    <XAxis dataKey="cycle" stroke="#475569" tick={{ fill: '#94A3B8', fontSize: 10 }} label={{ value: 'Cycle', fill: '#64748B', fontSize: 10, dy: 12 }} />
                    <YAxis yAxisId="v" domain={[2.5, 4.5]} stroke="#475569" tick={{ fill: '#00D4FF', fontSize: 10 }} />
                    <YAxis yAxisId="t" orientation="right" domain={[15, 55]} stroke="#475569" tick={{ fill: '#F59E0B', fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#1E293B', borderColor: '#334155', borderRadius: '8px', fontSize: '12px' }}
                      labelFormatter={(v) => `Cycle ${v}`}
                    />
                    <Line yAxisId="v" type="monotone" dataKey="voltage" stroke="#00D4FF" strokeWidth={2} dot={false} name="Voltage (V)" />
                    <Line yAxisId="t" type="monotone" dataKey="temp" stroke="#F59E0B" strokeWidth={2} dot={false} name="Temperature (°C)" />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-slate-600 text-sm">
                  No recent activity to display
                </div>
              )}
            </div>

            <div className="flex items-center justify-center gap-6 mt-4">
              <div className="flex items-center gap-2">
                <Zap className="w-3.5 h-3.5 text-cyan-400" />
                <span className="text-xs text-slate-400">Voltage</span>
              </div>
              <div className="flex items-center gap-2">
                <Thermometer className="w-3.5 h-3.5 text-amber-400" />
                <span className="text-xs text-slate-400">Temperature</span>
              </div>
            </div>
          </div>

          {/* Footer Tip */}
          <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-xl p-4 text-center">
            <p className="text-xs text-emerald-300">
              💡 <strong>Tip:</strong> Avoid extreme temperatures and deep discharges to maximize your battery's lifespan.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
