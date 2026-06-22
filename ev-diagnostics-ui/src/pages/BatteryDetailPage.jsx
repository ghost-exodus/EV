import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { getTelemetry, getSoH, getRUL, getDegradation } from '../api/client';
import {
  ArrowLeft, Loader2, AlertTriangle, RefreshCw,
  Cpu, Activity, Zap, Thermometer, Battery as BatteryIcon,
} from 'lucide-react';

const POLL_INTERVAL = 30_000;

export default function BatteryDetailPage() {
  const { batteryId } = useParams();
  const navigate = useNavigate();

  const [telemetry, setTelemetry] = useState(null);
  const [soh, setSoH] = useState(null);
  const [rul, setRul] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchAll = useCallback(async (isRefresh = false) => {
    try {
      if (isRefresh) setRefreshing(true);
      else setLoading(true);
      setError(null);

      const [telData, sohData, rulData] = await Promise.all([
        getTelemetry(batteryId, 50).catch(e => ({ error: true, message: e.message })),
        getSoH(batteryId).catch(e => ({ error: true, message: e.message })),
        getRUL(batteryId).catch(e => ({ error: true, message: e.message, status: e.status })),
      ]);

      if (!telData.error) setTelemetry(telData);
      if (!sohData.error) setSoH(sohData);
      if (!rulData.error) setRul(rulData);
      else if (rulData.status === 404) setRul({ status: 'pending', message: 'Battery not found' });
      else setRul({ status: 'pending', message: rulData.message });

    } catch (err) {
      setError(err.message || 'Failed to load battery data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [batteryId]);

  useEffect(() => {
    fetchAll();
    const timer = setInterval(() => fetchAll(true), POLL_INTERVAL);
    return () => clearInterval(timer);
  }, [fetchAll]);

  // Prepare chart data from telemetry readings (reverse so oldest first)
  const chartData = telemetry?.readings
    ? [...telemetry.readings].reverse().map(r => ({
        cycle: r.cycle_number,
        voltage_v: r.voltage_v,
        temperature_c: r.temperature_c,
        current_a: r.current_a,
        capacity_mah: r.capacity_mah,
      }))
    : [];

  // SoH trend data for the second chart
  const sohChartData = soh?.trend?.history?.map(h => ({
    cycle: h.cycle,
    soh_percent: h.soh_percent,
  })) || [];

  const sohVal = soh?.current_soh_percent;
  const sohStatus = soh?.status || 'unknown';

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy': return 'text-emerald-400';
      case 'warning': return 'text-amber-400';
      case 'critical': return 'text-rose-400';
      default: return 'text-slate-400';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="text-center space-y-4">
          <Loader2 className="w-10 h-10 text-cyan-400 animate-spin mx-auto" />
          <p className="text-sm text-slate-400 font-mono">Loading battery {batteryId}...</p>
        </div>
      </div>
    );
  }

  if (error && !telemetry && !soh) {
    return (
      <div className="flex items-center justify-center h-[60vh] px-6">
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-8 max-w-md text-center">
          <AlertTriangle className="w-10 h-10 text-rose-400 mx-auto mb-4" />
          <p className="text-rose-300 font-mono text-sm mb-4">{error}</p>
          <div className="flex gap-3 justify-center">
            <button onClick={() => navigate(-1)} className="px-4 py-2 bg-slate-800 border border-slate-700 rounded-md text-sm font-mono text-slate-300 hover:bg-slate-700 transition-colors">
              Go Back
            </button>
            <button onClick={() => fetchAll()} className="px-4 py-2 bg-rose-500/20 border border-rose-500/40 rounded-md text-sm font-mono text-rose-300 hover:bg-rose-500/30 transition-colors">
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  const latestReading = telemetry?.readings?.[0];

  return (
    <div className="p-6 md:p-10 lg:p-12 space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/dashboard')}
            className="p-2 rounded-md border border-slate-700 text-slate-400 hover:text-cyan-400 hover:border-cyan-500/40 transition-all"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h2 className="text-xl font-bold text-slate-100 font-mono tracking-wider">{batteryId}</h2>
            {soh && (
              <p className="text-sm text-slate-500 font-mono mt-1">
                Vehicle: {telemetry?.battery_id || batteryId} · Status: <span className={getStatusColor(sohStatus)}>{sohStatus.toUpperCase()}</span>
              </p>
            )}
          </div>
        </div>
        <button
          onClick={() => fetchAll(true)}
          disabled={refreshing}
          className="flex items-center gap-2 px-4 py-2 bg-slate-800/50 border border-slate-700 rounded-md text-sm font-mono text-slate-300 hover:border-cyan-500/40 hover:text-cyan-400 transition-all disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          {refreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {/* ── Telemetry Readout Grid ──────────────────────────────────────── */}
      {latestReading && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            label="Cell Voltage" tag="V_SENS" icon={<Zap className="w-4 h-4" />}
            value={latestReading.voltage_v} unit="V"
            color="text-cyan-400" tagColor="text-cyan-400 bg-cyan-950/40 border-cyan-900"
            barValue={(latestReading.voltage_v - 2.5) / 1.7 * 100} barColor="bg-cyan-400"
          />
          <MetricCard
            label="Temperature" tag="TEMP_C" icon={<Thermometer className="w-4 h-4" />}
            value={latestReading.temperature_c?.toFixed(1)} unit="°C"
            color={latestReading.temperature_c > 42 ? 'text-amber-400' : 'text-slate-100'}
            tagColor="text-rose-400 bg-rose-950/40 border-rose-900"
            barValue={Math.min(100, latestReading.temperature_c / 80 * 100)}
            barColor={latestReading.temperature_c > 42 ? 'bg-amber-500' : 'bg-emerald-500'}
          />
          <MetricCard
            label="Capacity" tag="CAP_MAH" icon={<BatteryIcon className="w-4 h-4" />}
            value={latestReading.capacity_mah?.toFixed(1) || 'N/A'} unit="mAh"
            color="text-emerald-400" tagColor="text-emerald-400 bg-emerald-950/40 border-emerald-900"
            barValue={latestReading.capacity_mah ? latestReading.capacity_mah / 2200 * 100 : 0}
            barColor="bg-emerald-400"
          />
          <MetricCard
            label="SoH" tag="HEALTH" icon={<Activity className="w-4 h-4" />}
            value={sohVal != null ? sohVal.toFixed(1) : 'N/A'} unit="%"
            color={sohVal > 80 ? 'text-emerald-400' : sohVal > 60 ? 'text-amber-400' : 'text-rose-400'}
            tagColor={`${getStatusColor(sohStatus)} bg-slate-800/40 border-slate-700`}
            barValue={sohVal || 0} barColor={sohVal > 80 ? 'bg-emerald-400' : sohVal > 60 ? 'bg-amber-500' : 'bg-rose-500'}
          />
        </div>
      )}

      {/* ── Charts Row ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Telemetry Chart */}
        <div className="bg-[#111827] border border-slate-800 rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-3 h-3 rounded-full bg-cyan-400 animate-pulse" />
            <h3 className="text-sm font-bold font-mono tracking-wider uppercase text-slate-200">
              Telemetry Stream
            </h3>
          </div>
          <div className="h-72 bg-[#050914] rounded-md border border-slate-800/80 pt-2">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 5, right: 15, left: -20, bottom: 5 }}>
                  <CartesianGrid stroke="rgba(0,212,255,0.08)" strokeDasharray="3 3" />
                  <XAxis dataKey="cycle" stroke="#475569" tick={{ fill: '#94A3B8', fontSize: 10, fontFamily: 'monospace' }} />
                  <YAxis yAxisId="left" domain={[2.5, 4.5]} stroke="#475569" tick={{ fill: '#00D4FF', fontSize: 10, fontFamily: 'monospace' }} />
                  <YAxis yAxisId="right" orientation="right" domain={[15, 60]} stroke="#475569" tick={{ fill: '#F59E0B', fontSize: 10, fontFamily: 'monospace' }} />
                  <Tooltip contentStyle={{ backgroundColor: '#0F172A', borderColor: '#1E3A5F', borderRadius: '6px', fontFamily: 'monospace', fontSize: '11px' }} />
                  <Line yAxisId="left" type="monotone" dataKey="voltage_v" stroke="#00D4FF" strokeWidth={2} dot={false} name="Voltage (V)" />
                  <Line yAxisId="right" type="monotone" dataKey="temperature_c" stroke="#F59E0B" strokeWidth={2} dot={false} name="Temp (°C)" />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-slate-600 font-mono text-sm">
                No telemetry data available
              </div>
            )}
          </div>
        </div>

        {/* SoH Trend Chart */}
        <div className="bg-[#111827] border border-slate-800 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-emerald-400" />
              <h3 className="text-sm font-bold font-mono tracking-wider uppercase text-slate-200">
                SoH Trend
              </h3>
            </div>
            {soh?.trend && (
              <span className={`text-[11px] font-mono font-bold px-2 py-1 rounded border ${
                soh.trend.direction === 'degrading' ? 'text-rose-400 bg-rose-500/10 border-rose-500/30'
                : soh.trend.direction === 'improving' ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30'
                : 'text-slate-400 bg-slate-500/10 border-slate-500/30'
              }`}>
                {soh.trend.direction.toUpperCase()} ({soh.trend.delta_last_10_cycles > 0 ? '+' : ''}{soh.trend.delta_last_10_cycles}%)
              </span>
            )}
          </div>
          <div className="h-72 bg-[#050914] rounded-md border border-slate-800/80 pt-2">
            {sohChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={sohChartData} margin={{ top: 5, right: 15, left: -20, bottom: 5 }}>
                  <CartesianGrid stroke="rgba(16,185,129,0.08)" strokeDasharray="3 3" />
                  <XAxis dataKey="cycle" stroke="#475569" tick={{ fill: '#94A3B8', fontSize: 10, fontFamily: 'monospace' }} />
                  <YAxis domain={[50, 100]} stroke="#475569" tick={{ fill: '#10B981', fontSize: 10, fontFamily: 'monospace' }} />
                  <Tooltip contentStyle={{ backgroundColor: '#0F172A', borderColor: '#1E3A5F', borderRadius: '6px', fontFamily: 'monospace', fontSize: '11px' }} />
                  <Line type="monotone" dataKey="soh_percent" stroke="#10B981" strokeWidth={2.5} dot={{ r: 3 }} name="SoH (%)" />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-slate-600 font-mono text-sm">
                {soh?.message || 'No SoH data available'}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── RUL Prediction Panel ───────────────────────────────────────── */}
      <div className="bg-[#111827] border border-slate-800 rounded-xl p-6">
        <div className="flex items-center gap-2 mb-5">
          <Cpu className="w-5 h-5 text-cyan-400" />
          <h3 className="text-sm font-bold font-mono tracking-wider uppercase text-slate-200">
            LSTM RUL Prediction
          </h3>
        </div>

        {rul?.status === 'pending' ? (
          <div className="bg-amber-500/5 border border-amber-500/20 rounded-lg p-6 text-center">
            <Loader2 className="w-8 h-8 text-amber-400 animate-spin mx-auto mb-3" />
            <p className="text-sm font-mono text-amber-300 font-bold">Calculating...</p>
            <p className="text-xs font-mono text-slate-500 mt-2">
              {rul?.message || 'Insufficient telemetry data for RUL prediction. Continue ingesting data.'}
            </p>
          </div>
        ) : rul?.status === 'ready' ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-[#0A0F1E] border border-slate-800 rounded-lg p-5 text-center">
              <p className="text-xs text-slate-500 font-mono uppercase mb-2">Predicted Cycles Remaining</p>
              <p className="text-4xl font-extrabold font-mono text-amber-500">{rul.predicted_rul_cycles}</p>
              <p className="text-xs text-slate-500 font-mono mt-2">until EOL ({rul.eol_threshold_soh}% SoH)</p>
            </div>
            <div className="bg-[#0A0F1E] border border-slate-800 rounded-lg p-5 space-y-3">
              <p className="text-xs text-slate-500 font-mono uppercase mb-2">Confidence Interval</p>
              <div className="flex justify-between text-sm font-mono">
                <span className="text-slate-500">Lower Bound</span>
                <span className="text-slate-300 font-bold">{rul.confidence_interval.lower_bound} cycles</span>
              </div>
              <div className="flex justify-between text-sm font-mono">
                <span className="text-slate-500">Upper Bound</span>
                <span className="text-slate-300 font-bold">{rul.confidence_interval.upper_bound} cycles</span>
              </div>
              <div className="flex justify-between text-sm font-mono">
                <span className="text-slate-500">Confidence</span>
                <span className="text-cyan-400 font-bold">{rul.confidence_interval.confidence_percent}%</span>
              </div>
            </div>
            <div className="bg-[#0A0F1E] border border-slate-800 rounded-lg p-5 space-y-3">
              <p className="text-xs text-slate-500 font-mono uppercase mb-2">Model Info</p>
              <div className="flex justify-between text-sm font-mono">
                <span className="text-slate-500">Model</span>
                <span className="text-emerald-400 font-bold">{rul.model_version}</span>
              </div>
              <div className="flex justify-between text-sm font-mono">
                <span className="text-slate-500">Input SoH</span>
                <span className="text-slate-300 font-bold">{rul.current_soh_percent?.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between text-sm font-mono">
                <span className="text-slate-500">Alert</span>
                <span className={`font-bold ${
                  rul.alert_level === 'none' ? 'text-emerald-400' : rul.alert_level === 'warning' ? 'text-amber-400' : 'text-rose-400'
                }`}>{rul.alert_level?.toUpperCase()}</span>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center text-slate-500 font-mono text-sm py-6">
            RUL data not available
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Reusable Metric Card ──────────────────────────────────────────────────── */
function MetricCard({ label, tag, icon, value, unit, color, tagColor, barValue, barColor }) {
  return (
    <div className="bg-[#111827] border border-slate-800 rounded-xl p-5">
      <div className="flex justify-between items-center text-slate-500 mb-3">
        <span className="text-xs font-bold font-mono tracking-wider uppercase flex items-center gap-2">
          {icon} {label}
        </span>
        <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${tagColor}`}>{tag}</span>
      </div>
      <div className="flex items-baseline gap-2">
        <span className={`text-3xl font-bold font-mono ${color}`}>{value}</span>
        <span className="text-sm text-slate-500 font-mono">{unit}</span>
      </div>
      <div className="h-1.5 bg-slate-900 rounded-full mt-4 overflow-hidden">
        <div className={`h-full ${barColor} transition-all duration-500`} style={{ width: `${Math.min(100, Math.max(0, barValue))}%` }} />
      </div>
    </div>
  );
}
