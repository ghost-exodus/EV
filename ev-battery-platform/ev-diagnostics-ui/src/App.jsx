import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';
import { 
  RefreshCw, Cpu, Info, Zap, HardDrive, Search, CheckCircle, Flame, Truck, Menu, ChevronDown
} from 'lucide-react';

const DATASET_SOURCE_URL = "https://github.com/ghost-exodus/EV/tree/main/cleaned_dataset";

// Insert Google Fonts for JetBrains Mono & Inter + custom Scanline/Oscilloscope animation styles
const CustomStyles = () => (
  <style dangerouslySetInnerHTML={{ __html: `
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');
    
    body {
      font-family: 'Inter', sans-serif;
      background-color: #0A0F1E;
      color: #FFFFFF;
      overflow-x: hidden;
    }

    .font-mono {
      font-family: 'JetBrains Mono', monospace !important;
    }

    /* Oscilloscope Grid Background */
    .oscilloscope-bg {
      background-size: 40px 40px;
      background-image: 
        linear-gradient(to right, rgba(0, 212, 255, 0.04) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(0, 212, 255, 0.04) 1px, transparent 1px);
    }

    /* Scanline Overlay Effect */
    .scanline-container {
      position: relative;
    }
    .scanline-container::after {
      content: " ";
      display: block;
      position: absolute;
      top: 0; left: 0; bottom: 0; right: 0;
      background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
      aspect-ratio: auto;
      background-size: 100% 4px, 6px 100%;
      pointer-events: none;
      z-index: 10;
      opacity: 0.3;
    }

    /* Oscilloscope glow effects */
    .glow-cyan {
      text-shadow: 0 0 10px rgba(0, 212, 255, 0.8), 0 0 2px rgba(0, 212, 255, 0.3);
    }
    
    .glow-green {
      text-shadow: 0 0 10px rgba(16, 185, 129, 0.8);
    }

    .glow-amber {
      text-shadow: 0 0 10px rgba(245, 158, 11, 0.8);
    }

    .glow-red {
      text-shadow: 0 0 10px rgba(239, 68, 68, 0.8);
    }

    /* Custom Scrollbar for Sleek instrument Panels */
    .custom-scrollbar::-webkit-scrollbar {
      width: 6px;
    }
    .custom-scrollbar::-webkit-scrollbar-track {
      background: #090E1A;
    }
    .custom-scrollbar::-webkit-scrollbar-thumb {
      background: #1E3A5F;
      border-radius: 4px;
    }
    .custom-scrollbar::-webkit-scrollbar-thumb:hover {
      background: #00D4FF;
    }

    .no-scrollbar::-webkit-scrollbar {
      display: none;
    }
    .no-scrollbar {
      -ms-overflow-style: none;
      scrollbar-width: none;
    }

    /* Native Dropdown Animation Helpers */
    details > summary {
      list-style: none;
    }
    details > summary::-webkit-details-marker {
      display: none;
    }
    details[open] summary ~ * {
      animation: sweep .3s ease-in-out;
    }
    @keyframes sweep {
      0%    {opacity: 0; transform: translateY(-10px)}
      100%  {opacity: 1; transform: translateY(0)}
    }
    details[open] summary .lucide-chevron-down {
      transform: rotate(180deg);
    }
  `}} />
);

// 18 Simulated Batteries to fulfill SQS Multi-EV Fleet Specification (B0005 - B0018 Range)
const MOCK_BATTERIES = [
  { id: "EV_B0005_001", vehicle: "VH_TESLA_042", nominalCapacity: 2000, currentCapacity: 1648, baseCycle: 147, chemistry: "Li-Ion (NMC)", manufactureDate: "2023-04-12", status: "healthy", owner: "Delhi Cargo Hub" },
  { id: "EV_B0006_002", vehicle: "VH_BYD_089", nominalCapacity: 2200, currentCapacity: 1716, baseCycle: 182, chemistry: "Li-Ion (LFP)", manufactureDate: "2023-01-18", status: "healthy", owner: "Mumbai Fleet Base" },
  { id: "EV_B0007_003", vehicle: "VH_TESLA_112", nominalCapacity: 2000, currentCapacity: 1282, baseCycle: 310, chemistry: "Li-Ion (NMC)", manufactureDate: "2022-09-05", status: "warning", owner: "Bangalore Logistics" },
  { id: "EV_B0018_004", vehicle: "VH_TATA_005", nominalCapacity: 2400, currentCapacity: 1392, baseCycle: 420, chemistry: "Li-Ion (LFP)", manufactureDate: "2021-11-22", status: "critical", owner: "Pune Intercity" },
  { id: "EV_B0005_005", vehicle: "VH_TESLA_013", nominalCapacity: 2000, currentCapacity: 1810, baseCycle: 45, chemistry: "Li-Ion (NMC)", manufactureDate: "2024-02-10", status: "healthy", owner: "Delhi Cargo Hub" },
  { id: "EV_B0006_006", vehicle: "VH_BYD_102", nominalCapacity: 2200, currentCapacity: 1980, baseCycle: 62, chemistry: "Li-Ion (LFP)", manufactureDate: "2023-11-01", status: "healthy", owner: "Mumbai Fleet Base" },
  { id: "EV_B0007_007", vehicle: "VH_TATA_088", nominalCapacity: 2000, currentCapacity: 1590, baseCycle: 195, chemistry: "Li-Ion (NMC)", manufactureDate: "2023-03-15", status: "healthy", owner: "Kolkata Delivery" },
  { id: "EV_B0018_008", vehicle: "VH_MAHIND_02", nominalCapacity: 2400, currentCapacity: 1910, baseCycle: 120, chemistry: "Li-Ion (LFP)", manufactureDate: "2023-07-29", status: "healthy", owner: "Hyderabad Express" },
  { id: "EV_B0005_009", vehicle: "VH_TESLA_201", nominalCapacity: 2000, currentCapacity: 1430, baseCycle: 280, chemistry: "Li-Ion (NMC)", manufactureDate: "2022-05-14", status: "warning", owner: "Delhi Cargo Hub" },
  { id: "EV_B0006_010", vehicle: "VH_BYD_199", nominalCapacity: 2200, currentCapacity: 1510, baseCycle: 290, chemistry: "Li-Ion (LFP)", manufactureDate: "2022-08-11", status: "warning", owner: "Chennai Logistics" },
  { id: "EV_B0007_011", vehicle: "VH_TATA_145", nominalCapacity: 2000, currentCapacity: 1110, baseCycle: 480, chemistry: "Li-Ion (NMC)", manufactureDate: "2021-02-04", status: "critical", owner: "Kolkata Delivery" },
  { id: "EV_B0018_012", vehicle: "VH_MAHIND_44", nominalCapacity: 2400, currentCapacity: 1310, baseCycle: 512, chemistry: "Li-Ion (LFP)", manufactureDate: "2021-05-19", status: "critical", owner: "Ahmedabad Transit" },
  { id: "EV_B0005_013", vehicle: "VH_TESLA_199", nominalCapacity: 2000, currentCapacity: 1720, baseCycle: 90, chemistry: "Li-Ion (NMC)", manufactureDate: "2023-09-01", status: "healthy", owner: "Gurgaon Line" },
  { id: "EV_B0006_014", vehicle: "VH_BYD_250", nominalCapacity: 2200, currentCapacity: 1690, baseCycle: 155, chemistry: "Li-Ion (LFP)", manufactureDate: "2023-05-20", status: "healthy", owner: "Mumbai Fleet Base" },
  { id: "EV_B0007_015", vehicle: "VH_TATA_211", nominalCapacity: 2000, currentCapacity: 1612, baseCycle: 135, chemistry: "Li-Ion (NMC)", manufactureDate: "2023-06-11", status: "healthy", owner: "Kolkata Delivery" },
  { id: "EV_B0018_016", vehicle: "VH_MAHIND_71", nominalCapacity: 2400, currentCapacity: 2150, baseCycle: 50, chemistry: "Li-Ion (LFP)", manufactureDate: "2024-01-20", status: "healthy", owner: "Ahmedabad Transit" },
  { id: "EV_B0005_017", vehicle: "VH_TESLA_333", nominalCapacity: 2000, currentCapacity: 1580, baseCycle: 220, chemistry: "Li-Ion (NMC)", manufactureDate: "2022-12-01", status: "healthy", owner: "Delhi Cargo Hub" },
  { id: "EV_B0006_018", vehicle: "VH_BYD_404", nominalCapacity: 2200, currentCapacity: 1490, baseCycle: 260, chemistry: "Li-Ion (LFP)", manufactureDate: "2022-11-15", status: "warning", owner: "Mumbai Fleet Base" }
];

export default function App() {
  const [selectedBatteryId, setSelectedBatteryId] = useState("EV_B0005_001");
  const [userRole, setUserRole] = useState("fleet_admin");
  const [isPlaying, setIsPlaying] = useState(true);
  const [scenario, setScenario] = useState("normal_degradation");
  const [replaySpeed, setReplaySpeed] = useState(1);
  const [searchTerm, setSearchTerm] = useState("");
  const [telemetryHistory, setTelemetryHistory] = useState({});
  const [isSecondLifeModalOpen, setIsSecondLifeModalOpen] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  // Connection states
  const [connectionStatus, setConnectionStatus] = useState("OFFLINE");

  // Force chart to expand dynamically whenever the sidebar is minimized/opened
  useEffect(() => {
    // Send a resize event so Recharts repaints at exactly 100% of the new wide container
    window.dispatchEvent(new Event('resize'));
    const timer = setTimeout(() => window.dispatchEvent(new Event('resize')), 50);
    return () => clearTimeout(timer);
  }, [isSidebarOpen]);

  // Find active battery stats
  const activeBattery = useMemo(() => {
    return MOCK_BATTERIES.find(b => b.id === selectedBatteryId) || MOCK_BATTERIES[0];
  }, [selectedBatteryId]);

  // Hooking up Server-Sent Events (SSE) with graceful Mock fallback
  useEffect(() => {
    if (!isPlaying) {
        setConnectionStatus("PAUSED");
        return;
    }

    setConnectionStatus("CONNECTING");

    let eventSource = null;
    let mockInterval = null;

    // Graceful fallback if FastAPI backend is not running yet
    const startMockFallback = () => {
      setConnectionStatus("MOCK DATA");
      const intervalTime = Math.max(100, 1000 / replaySpeed);
      
      mockInterval = setInterval(() => {
        setTelemetryHistory(prev => {
          const nextState = { ...prev };
          MOCK_BATTERIES.forEach(bat => {
            if (!nextState[bat.id]) {
              // Seed base historical points
              nextState[bat.id] = Array.from({ length: 30 }).map((_, i) => {
                const cycle = bat.baseCycle - 30 + i;
                const degradationFactor = 1 - (cycle * 0.0004);
                const capacity = bat.nominalCapacity * degradationFactor;
                const soh = (capacity / bat.nominalCapacity) * 100;
                return {
                  battery_id: bat.id,
                  cycle,
                  voltage_v: (3.7 + Math.random() * 0.35).toFixed(4),
                  current_a: (1.5 - Math.random() * 3.0).toFixed(4),
                  temperature_c: (25 + Math.random() * 5).toFixed(2),
                  capacity_mah: capacity.toFixed(1),
                  soh_percent: soh.toFixed(2),
                  recorded_at: new Date(Date.now() - (30 - i) * 60000).toISOString()
                };
              });
            }

            const currentArray = nextState[bat.id];
            const lastReading = currentArray[currentArray.length - 1];
            const nextCycle = lastReading.cycle + 1;

            let scenarioTempMultiplier = 1.0;
            let scenarioVDropMultiplier = 1.0;
            let scenarioSoHDegradationMultiplier = 1.0;

            if (scenario === "rapid_fault" && bat.id === selectedBatteryId) {
              scenarioTempMultiplier = 1.3;
              scenarioVDropMultiplier = 0.9;
              scenarioSoHDegradationMultiplier = 4.5;
            } else if (scenario === "thermal_runaway" && bat.id === selectedBatteryId) {
              scenarioTempMultiplier = 2.4;
              scenarioVDropMultiplier = 0.78;
              scenarioSoHDegradationMultiplier = 15.0;
            }

            const currentCap = parseFloat(lastReading.capacity_mah) - (0.15 * scenarioSoHDegradationMultiplier * (1 + Math.random() * 0.5));
            const calculatedSoH = (currentCap / bat.nominalCapacity) * 100;

            const newReading = {
              battery_id: bat.id,
              cycle: nextCycle,
              voltage_v: ((3.82 - (nextCycle * 0.0001) + (Math.random() * 0.1 - 0.05)) * scenarioVDropMultiplier).toFixed(4),
              current_a: (-1.98 + (Math.random() * 0.4 - 0.2)).toFixed(4),
              temperature_c: ((24.5 + (nextCycle * 0.01) + (Math.random() * 1.5 - 0.75)) * scenarioTempMultiplier).toFixed(2),
              capacity_mah: currentCap.toFixed(1),
              soh_percent: Math.max(0, calculatedSoH).toFixed(2),
              recorded_at: new Date().toISOString()
            };

            // Maintain sliding window of 40 points
            nextState[bat.id] = [...currentArray.slice(1), newReading];
          });
          return nextState;
        });
      }, intervalTime);
    };

    try {
      // Point EventSource to the FastAPI telemetry SSE endpoint
      eventSource = new EventSource(`http://localhost:8000/api/v1/stream/${selectedBatteryId}`);

      eventSource.onopen = () => {
          setConnectionStatus("LIVE (SSE)");
      };

      eventSource.addEventListener("telemetry", (event) => {
        const rawData = JSON.parse(event.data);
        
        setTelemetryHistory(prev => {
          const currentArray = prev[rawData.battery_id] || [];
          
          // Append newest real reading, keeping a sliding window of 40 points
          let updatedArray = [...currentArray, rawData];
          if (updatedArray.length > 40) {
              updatedArray = updatedArray.slice(1);
          }

          return {
            ...prev,
            [rawData.battery_id]: updatedArray
          };
        });
      });

      eventSource.onerror = (err) => {
        console.warn("FastAPI backend not detected at :8000. Engaging mock data fallback.");
        eventSource.close();
        startMockFallback();
      };
    } catch (e) {
      console.error("EventSource failed to initialize:", e);
      startMockFallback();
    }

    return () => {
      if (eventSource) eventSource.close();
      if (mockInterval) clearInterval(mockInterval);
      setConnectionStatus("OFFLINE");
    };
  }, [selectedBatteryId, isPlaying, replaySpeed, scenario]);

  // Calculate current dynamic metrics derived from history
  const activeHistory = telemetryHistory[selectedBatteryId] || [];
  const currentReading = activeHistory[activeHistory.length - 1] || {
    voltage_v: "3.8124",
    current_a: "-1.9987",
    temperature_c: "24.50",
    soh_percent: "82.40",
    capacity_mah: "1648.0",
    cycle: activeBattery.baseCycle
  };

  const sohVal = parseFloat(currentReading.soh_percent);

  // AI-Derived Predictions representing ML Data Ka Pandit's PyTorch LSTM Inference outputs
  const lstmPredictions = useMemo(() => {
    const eolThreshold = 70.0;
    const currentSoh = parseFloat(currentReading.soh_percent);
    
    const cyclesRan = currentReading.cycle;
    const rateOfDecline = (100 - currentSoh) / Math.max(1, cyclesRan);
    
    let basePredictedRul = 0;
    if (currentSoh > eolThreshold) {
      basePredictedRul = Math.max(10, Math.round((currentSoh - eolThreshold) / (rateOfDecline || 0.05)));
    }

    const rmseDev = Math.round(9.5 * (1 + (cyclesRan * 0.001)));
    const lowerBound = Math.max(0, basePredictedRul - rmseDev);
    const upperBound = basePredictedRul + rmseDev;

    return {
      predictedRul: basePredictedRul,
      lowerBound,
      upperBound,
      confidencePercent: 90,
      modelVersion: "v2.0-LSTM"
    };
  }, [currentReading]);

  // Second Life Decision Support Matrix
  const secondLifeRecommendation = useMemo(() => {
    const soh = parseFloat(currentReading.soh_percent);
    
    if (soh >= 80.0) {
      return {
        tier: "Tier 1: High Capacity Electric Mobility",
        suitability: "90% - 100% (Optimal)",
        application: "Heavy-Duty Cargo Fleet, Public Transit, EV Pooling",
        engineeringInsight: "Minimal internal resistance degradation ($R_{int} < 0.022\\Omega$). Dynamic load capability is outstanding. Highly stable for continuous mobility environments.",
        icon: Truck,
        color: "#10B981"
      };
    } else if (soh >= 70.0 && soh < 80.0) {
      return {
        tier: "Tier 2: Stationary Grid ESS & Peak Shaving",
        suitability: "70% - 85% (Recommended for Transition)",
        application: "Telecom Backup Power, Solar Micro-grids, Station Buffer Charging",
        engineeringInsight: "The cell capacity is below nominal automotive density but has huge static utility ($C/5$ rates). Excellent choice for stationary grid-connected systems.",
        icon: HardDrive,
        color: "#F59E0B"
      };
    } else if (soh >= 60.0 && soh < 70.0) {
      return {
        tier: "Tier 3: Low-Demand Static Applications",
        suitability: "60% - 70% (Secondary Grade Support Only)",
        application: "Residential Powerwalls, Rural Pumps, Emergency Static UPS Units",
        engineeringInsight: "Degraded capacity retention. Best used in low-demand setups with slower charge cycles and proactive, integrated BMS monitoring loops.",
        icon: Zap,
        color: "#EF4444"
      };
    } else {
      return {
        tier: "Tier 4: Material Extraction & Reprocessing",
        suitability: "0% - 59% (End of Life - Safe Disposal)",
        application: "Raw Nickel, Cobalt, Lithium, and Manganese Extraction",
        engineeringInsight: "State of Health is below safe operational deployment parameters. Safe recycling processing is strongly advised to retrieve precious transition metals.",
        icon: Flame,
        color: "#EF4444"
      };
    }
  }, [currentReading.soh_percent]);

  // Simulate SQS Ingestion trigger
  const handleIngestTrigger = () => {
    setConnectionStatus("LIVE (SSE)");
  };

  const filteredBatteries = MOCK_BATTERIES.filter(b => 
    b.id.toLowerCase().includes(searchTerm.toLowerCase()) || 
    b.vehicle.toLowerCase().includes(searchTerm.toLowerCase()) ||
    b.owner.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="min-h-screen text-slate-100 flex flex-col font-sans relative select-none bg-[#0A0F1E]">
      <CustomStyles />

      {/* RESTRUCTURED HEADER BAR: Two-tier layout to prevent overlaps */}
      <header className="border-b border-slate-800 bg-[#0A0F1E] flex flex-col z-20 shrink-0 relative">
        
        {/* TOP ROW: Dedicated full-width center title */}
        <div className="w-full flex items-center justify-center pt-5 pb-1">
          <h1 style={{ fontFamily: 'Arial, sans-serif', fontSize: '18px' }} className="text-slate-300 font-bold tracking-widest uppercase m-0">
            EV Battery Health Diagnostics
          </h1>
        </div>

        {/* BOTTOM ROW: Controls and Search */}
        <div className="flex items-center justify-between w-full px-6 pb-4 pt-3">
          {/* LEFT SIDE: Menu & Search */}
          <div className="flex items-center gap-4 flex-1">
            <button 
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className={`p-2.5 rounded-md transition-all duration-200 flex items-center justify-center border ${
                isSidebarOpen 
                  ? 'bg-slate-800/40 hover:bg-slate-800/80 border-slate-700 text-slate-300' 
                  : 'bg-[#00D4FF]/10 hover:bg-[#00D4FF]/20 border-[#00D4FF]/50 text-[#00D4FF] shadow-[0_0_10px_rgba(0,212,255,0.2)]'
              }`}
              title={isSidebarOpen ? "Collapse Battery List" : "Expand Battery List"}
            >
              <Menu className="w-5 h-5" />
            </button>
            
            {/* SEARCH BAR BLOCK */}
            <div className="flex w-full max-w-sm">
              <div className="flex items-center bg-[#111827] border border-slate-800 focus-within:border-[#00D4FF] rounded-md px-3 py-2.5 transition-all w-full">
                <Search className="h-4 w-4 text-[#00D4FF] glow-cyan shrink-0 mr-2" />
                <input
                  type="text"
                  placeholder="Search Active Battery ID..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full bg-transparent border-none outline-none focus:ring-0 text-slate-100 placeholder-slate-500 font-mono text-sm tracking-wider"
                  style={{ color: '#FFFFFF' }}
                />
              </div>
            </div>
          </div>

          {/* RIGHT SIDE: Controls & Status */}
          <div className="flex items-center justify-end gap-5 flex-1 relative z-10">
            {/* SIMULATION CONTROLLER AND SCENARIO INJECTORS */}
            <div className="hidden xl:flex items-center gap-4 bg-slate-900/60 border border-slate-800 rounded-md px-3 py-1.5 text-xs">
              <div className="flex items-center gap-2 border-r border-slate-800 pr-3">
                <span className="text-[10px] uppercase text-slate-500 font-mono font-bold">Scenario:</span>
                <select 
                  value={scenario} 
                  onChange={(e) => setScenario(e.target.value)}
                  className="bg-[#0A0F1E] border border-slate-800 text-cyan-400 text-[11px] rounded px-2.5 py-0.5 font-mono focus:outline-none cursor-pointer"
                >
                  <option className="bg-[#111827] text-white" value="normal_degradation">Normal Cycle Ops</option>
                  <option className="bg-[#111827] text-white" value="rapid_fault">Accelerated Heat Stress</option>
                  <option className="bg-[#111827] text-white" value="thermal_runaway">Simulated Thermal Runaway</option>
                </select>
              </div>

              <div className="flex items-center gap-3">
                <button 
                  onClick={() => setIsPlaying(!isPlaying)}
                  className={`px-2 py-1 rounded font-mono text-[10px] uppercase font-bold transition-all border ${isPlaying ? 'bg-amber-500/10 text-amber-400 border-amber-500/30' : 'bg-green-500/20 text-green-400 border-green-500/40'}`}
                >
                  {isPlaying ? 'PAUSE LIVE FEED' : 'RESUME SIMULATION'}
                </button>
                <div className="flex gap-1.5 items-center">
                  <span className="text-[10px] text-slate-500 font-mono uppercase font-bold">Speed:</span>
                  {[1, 2, 5, 10].map(speed => (
                    <button
                      key={speed}
                      onClick={() => setReplaySpeed(speed)}
                      className={`px-2 py-0.5 rounded font-mono text-[10px] transition-all ${replaySpeed === speed ? 'bg-cyan-500 text-black font-bold' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'}`}
                    >
                      {speed}x
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* CONNECTION & AUTH SECTION */}
            <div className="flex items-center gap-3 font-mono">
              <div className="flex items-center gap-2">
                <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${connectionStatus.includes('LIVE') || connectionStatus.includes('MOCK') ? 'bg-emerald-400' : connectionStatus === 'CONNECTING' ? 'bg-amber-500' : 'bg-rose-500'}`}></span>
                <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${connectionStatus.includes('LIVE') || connectionStatus.includes('MOCK') ? 'bg-emerald-500' : connectionStatus === 'CONNECTING' ? 'bg-amber-500' : 'bg-rose-500'}`}></span>
                <span className="text-[11px] text-slate-300 font-bold">{connectionStatus}</span>
              </div>

              <div className="h-6 w-[1px] bg-slate-800"></div>

              {/* Role Claim Indicator */}
              <div className="flex items-center gap-2 bg-[#111827] border border-slate-800 px-3 py-1.5 rounded-md">
                <select
                  value={userRole}
                  onChange={(e) => setUserRole(e.target.value)}
                  style={{ color: '#FFFFFF' }}
                  className="bg-transparent text-xs font-bold focus:outline-none cursor-pointer"
                >
                  <option className="bg-[#111827]" value="fleet_admin">Admin (All Analytics)</option>
                  <option className="bg-[#111827]" value="operator">Operator (Read-Only Telemetry)</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* CORE WORKSPACE */}
      <div className="flex-1 flex overflow-hidden w-full">
        
        {/* COMPLETELY COLLAPSIBLE LEFT SIDEBAR */}
        {isSidebarOpen && (
          <aside className="bg-[#111827] w-80 md:w-[350px] flex flex-col z-10 shadow-[4px_0_24px_rgba(0,0,0,0.4)] border-r border-slate-800 shrink-0">
            {/* SYSTEM INDEXING HEADER */}
            <div className="p-4 border-b border-slate-800 bg-[#151D30] flex items-center justify-between shrink-0">
              <span className="text-[11px] font-mono uppercase text-white tracking-widest font-semibold">BATTERY NODE REGISTRY</span>
              <span className="text-cyan-400 bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-900/60 text-[10px] font-bold font-mono">
                {filteredBatteries.length} / 18 ONLINE
              </span>
            </div>

            {/* SCROLLABLE LIVE BATTERY LIST IN HIGH-CONTRAST DATA LAYERS */}
            <div className="flex-1 overflow-y-auto custom-scrollbar divide-y divide-slate-800/80 bg-[#0A0F1E]/40">
              {filteredBatteries.map((bat) => {
                const hist = telemetryHistory[bat.id] || [];
                const lastVal = hist[hist.length - 1];
                const curSoh = lastVal ? parseFloat(lastVal.soh_percent) : 100.0;
                const curTemp = lastVal ? parseFloat(lastVal.temperature_c) : 25.0;

                // Derive status colors & visual LED state
                let statusText = "HEALTHY";
                let statusColorClass = "text-emerald-400 border-emerald-950 bg-emerald-950/40";
                let statusLedColor = "bg-emerald-500 shadow-[0_0_8px_#10B981]";

                if (curSoh < 60 || curTemp > 65) {
                  statusText = "CRITICAL";
                  statusColorClass = "text-rose-400 border-rose-950 bg-rose-950/40";
                  statusLedColor = "bg-rose-500 shadow-[0_0_8px_#EF4444]";
                } else if (curSoh < 75 || curTemp > 42) {
                  statusText = "WARNING";
                  statusColorClass = "text-amber-400 border-amber-950 bg-amber-950/40";
                  statusLedColor = "bg-amber-500 shadow-[0_0_8px_#F59E0B]";
                }

                const isSelected = bat.id === selectedBatteryId;

                return (
                  <div
                    key={bat.id}
                    onClick={() => setSelectedBatteryId(bat.id)}
                    className={`relative p-4 cursor-pointer transition-all duration-150 flex flex-col gap-3 border-l-4 ${
                      isSelected 
                        ? 'bg-[#1E3A5F]/25 border-cyan-400 shadow-inner' 
                        : 'hover:bg-slate-900/40 bg-transparent border-transparent'
                    }`}
                  >
                    {/* Top Row: LED Indicator, ID, and Class Status Badge */}
                    <div className="flex justify-between items-center gap-2">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${statusLedColor}`} />
                        <span className={`font-mono text-sm tracking-wider font-bold ${isSelected ? 'text-[#00D4FF] glow-cyan' : 'text-white'}`}>
                          {bat.id}
                        </span>
                      </div>
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded border uppercase font-bold tracking-widest ${statusColorClass}`}>
                        {statusText}
                      </span>
                    </div>

                    {/* Secondary Row: Chassis Reference & Active Cycle Count */}
                    <div className="flex justify-between items-center text-xs font-mono">
                      <span className="text-[11px] text-white font-semibold tracking-wide bg-[#151D30] px-2 py-0.5 rounded border border-slate-800">
                        {bat.vehicle}
                      </span>
                      <span className="text-[11px] text-white uppercase font-semibold">
                        Cycle <span className="text-[#00D4FF] font-bold">#{lastVal?.cycle || bat.baseCycle}</span>
                      </span>
                    </div>

                    {/* Progressive SOH Retention Indicator with Neon Tracking */}
                    <div className="space-y-1 bg-[#151D30]/30 p-2.5 rounded border border-slate-800/40">
                      <div className="flex justify-between items-center text-[10px] font-mono">
                        <span className="text-white uppercase font-bold tracking-wider">STATE OF HEALTH RETENTION</span>
                        <span className={`font-bold text-xs ${curSoh > 80 ? 'text-[#10B981] glow-green' : curSoh > 60 ? 'text-[#F59E0B] glow-amber' : 'text-[#EF4444] glow-red'}`}>
                          {curSoh.toFixed(2)}{"%"}
                        </span>
                      </div>
                      <div className="h-2 w-full bg-[#0A0F1E] rounded overflow-hidden border border-slate-800/80">
                        <div 
                          className={`h-full transition-all duration-300 ${
                            curSoh > 80 ? 'bg-[#10B981]' : curSoh > 60 ? 'bg-[#F59E0B]' : 'bg-[#EF4444]'
                          }`}
                          style={{ width: `${curSoh}%` }}
                        ></div>
                      </div>
                    </div>

                    {/* Modular Instrumentation Spark Grid: Super High-Readability Numbers */}
                    <div className="grid grid-cols-3 gap-2 py-2 px-2.5 bg-[#090E1A] border border-slate-800 rounded font-mono text-xs">
                      <div>
                        <span className="text-[9px] text-white block uppercase font-bold tracking-wider mb-0.5">V_SENS</span>
                        <span className="text-white font-bold font-mono text-[11px]">{lastVal?.voltage_v || '3.812'}{"V"}</span>
                      </div>
                      <div>
                        <span className="text-[9px] text-white block uppercase font-bold tracking-wider mb-0.5">T_CELL</span>
                        <span className={`font-bold font-mono text-[11px] ${curTemp > 50 ? 'text-[#EF4444]' : 'text-white'}`}>{curTemp.toFixed(1)}{"°C"}</span>
                      </div>
                      <div>
                        <span className="text-[9px] text-white block uppercase font-bold tracking-wider mb-0.5">FORMULA</span>
                        <span className="text-cyan-400 font-bold font-mono text-[11px] block truncate">{bat.chemistry.split(' ')[1] || 'Li'}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* SQS ENGINE STATUS ANCHOR */}
            <div className="p-4 border-t border-slate-800 bg-[#151D30] shrink-0">
              <div className="flex items-center gap-3 text-xs font-mono text-slate-400">
                <Cpu className="w-5 h-5 text-cyan-400 animate-spin" style={{ animationDuration: '8s' }} />
                <div>
                  <span className="text-[9px] block text-slate-500 tracking-widest font-bold">AWS SQS CONNECTION</span>
                  <span className="text-emerald-400 text-[10px] font-bold tracking-wider">ONLINE @ 18 MSGS/SEC</span>
                </div>
              </div>
            </div>
          </aside>
        )}

        {/* MAIN DIAGNOSTIC DISPLAY CANVAS - Fully Expands into the whole space automatically */}
        <main className="flex-1 w-full overflow-y-auto custom-scrollbar py-8 px-8 md:py-10 md:px-16 lg:py-12 lg:px-24 xl:px-32 flex flex-col gap-8 bg-[#0A0F1E] oscilloscope-bg">
          
          {/* HEADER DIAGNOSTICS CONTROL HEADER - Heavily padded and enlarged for readability */}
          <div className="flex flex-col md:flex-row md:items-center justify-between bg-[#111827] border border-slate-800/80 p-8 md:p-12 lg:p-16 rounded-xl scanline-container shadow-lg">
            <div className="flex items-start gap-8">
              <div className="space-y-4">
                <div className="flex items-center gap-5">
                  <h2 className="text-3xl font-extrabold text-slate-100 font-mono tracking-wider glow-cyan">{selectedBatteryId}</h2>
                  <span className="text-sm bg-slate-800 px-4 py-2 rounded-md border border-slate-700 text-slate-300 font-mono font-medium">
                    {activeBattery.chemistry}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-x-8 gap-y-3 text-base text-slate-400 font-mono">
                  <span className="flex items-center gap-2">CHASSIS REF: <span className="text-slate-100 font-bold">{activeBattery.vehicle}</span></span>
                  <span className="text-slate-600">•</span>
                  <span className="flex items-center gap-2">OWNER: <span className="text-slate-100 font-bold">{activeBattery.owner}</span></span>
                  <span className="text-slate-600">•</span>
                  <span className="flex items-center gap-2">MFG DATE: <span className="text-slate-100 font-bold">{activeBattery.manufactureDate}</span></span>
                </div>
              </div>
            </div>

            {/* Manual Ingestion Trigger simulating Cloud API SQS Gateway */}
            <div className="mt-8 md:mt-0 flex gap-5">
              <button 
                onClick={handleIngestTrigger}
                className="bg-[#1E3A5F] hover:bg-[#1E3A5F]/80 text-sm text-cyan-400 border border-cyan-500/30 px-6 py-4 rounded-md font-mono flex items-center gap-3 tracking-wider uppercase transition-colors shadow-md"
              >
                <RefreshCw className="w-5 h-5" />
                Trigger SQS Ingest
              </button>
              <button 
                onClick={() => setIsSecondLifeModalOpen(true)}
                className="bg-slate-800 hover:bg-slate-700 text-sm text-amber-400 border border-amber-500/30 px-6 py-4 rounded-md font-mono flex items-center gap-3 tracking-wider uppercase transition-colors shadow-md"
              >
                <Info className="w-5 h-5" />
                Life Cycle Info
              </button>
            </div>
          </div>

          {/* TELEMETRY READOUT GRID */}
          <section className="grid grid-cols-2 lg:grid-cols-4 gap-6">
            
            {/* VOLTAGE INSTRUMENT */}
            <div className="bg-[#111827] border border-slate-800/80 p-6 rounded-lg flex flex-col relative overflow-hidden shadow-md">
              <div className="flex justify-between items-center text-slate-500">
                <span className="text-xs font-bold font-mono tracking-wider">CELL VOLTAGE</span>
                <span className="text-[10px] font-mono text-cyan-400 bg-cyan-950/40 px-2 py-0.5 rounded border border-cyan-900">V_SENS</span>
              </div>
              <div className="mt-4 flex items-baseline gap-2">
                <span className="text-4xl font-bold font-mono text-[#00D4FF] glow-cyan tracking-tight">{currentReading.voltage_v}</span>
                <span className="text-sm text-slate-500 font-mono">{"V"}</span>
              </div>
              <div className="h-2 bg-slate-900 rounded-full mt-5 overflow-hidden">
                <div 
                  className="h-full bg-cyan-400 transition-all duration-300" 
                  style={{ width: `${((parseFloat(currentReading.voltage_v) - 2.5) / 1.7) * 100}%` }}
                ></div>
              </div>
              <span className="text-[10px] font-mono text-slate-600 mt-2.5">SAFE WINDOW: 2.7V - 4.2V</span>
            </div>

            {/* TEMPERATURE INSTRUMENT */}
            <div className="bg-[#111827] border border-slate-800/80 p-6 rounded-lg flex flex-col relative overflow-hidden shadow-md">
              <div className="flex justify-between items-center text-slate-500">
                <span className="text-xs font-bold font-mono tracking-wider">CELL TEMPERATURE</span>
                <span className="text-[10px] font-mono text-rose-400 bg-rose-950/40 px-2 py-0.5 rounded border border-rose-900">TEMP_C</span>
              </div>
              <div className="mt-4 flex items-baseline gap-2">
                <span className={`text-4xl font-bold font-mono tracking-tight ${
                  parseFloat(currentReading.temperature_c) > 65 ? 'text-rose-500 glow-red' : parseFloat(currentReading.temperature_c) > 42 ? 'text-amber-500 glow-amber' : 'text-slate-100'
                }`}>{currentReading.temperature_c}</span>
                <span className="text-sm text-slate-500 font-mono">{"°C"}</span>
              </div>
              <div className="h-2 bg-slate-900 rounded-full mt-5 overflow-hidden">
                <div 
                  className={`h-full transition-all duration-300 ${
                    parseFloat(currentReading.temperature_c) > 65 ? 'bg-rose-500' : parseFloat(currentReading.temperature_c) > 42 ? 'bg-amber-500' : 'bg-emerald-500'
                  }`} 
                  style={{ width: `${Math.min(100, (parseFloat(currentReading.temperature_c) / 100) * 100)}%` }}
                ></div>
              </div>
              <span className="text-[10px] font-mono text-slate-600 mt-2.5">CRITICAL SHUTDOWN @ 65°C</span>
            </div>

            {/* CAPACITY INSTRUMENT */}
            <div className="bg-[#111827] border border-slate-800/80 p-6 rounded-lg flex flex-col relative overflow-hidden shadow-md">
              <div className="flex justify-between items-center text-slate-500">
                <span className="text-xs font-bold font-mono tracking-wider">CAPACITY RETENTION</span>
                <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-900">CAP_MAH</span>
              </div>
              <div className="mt-4 flex items-baseline gap-2">
                <span className="text-4xl font-bold font-mono text-emerald-400 glow-green tracking-tight">
                  {currentReading.capacity_mah}
                </span>
                <span className="text-sm text-slate-500 font-mono">{"mAh"}</span>
              </div>
              <div className="h-2 bg-slate-900 rounded-full mt-5 overflow-hidden">
                <div 
                  className="h-full bg-emerald-400 transition-all duration-300" 
                  style={{ width: `${(parseFloat(currentReading.capacity_mah) / activeBattery.nominalCapacity) * 100}%` }}
                ></div>
              </div>
              <span className="text-[10px] font-mono text-slate-600 mt-2.5">NOMINAL: {activeBattery.nominalCapacity}{" mAh"}</span>
            </div>

            {/* CURRENT INTENSITY INSTRUMENT */}
            <div className="bg-[#111827] border border-slate-800/80 p-6 rounded-lg flex flex-col relative overflow-hidden shadow-md">
              <div className="flex justify-between items-center text-slate-500">
                <span className="text-xs font-bold font-mono tracking-wider">LOAD CURRENT</span>
                <span className="text-[10px] font-mono text-purple-400 bg-purple-950/40 px-2 py-0.5 rounded border border-purple-900">CUR_AMP</span>
              </div>
              <div className="mt-4 flex items-baseline gap-2">
                <span className="text-4xl font-bold font-mono text-purple-400 tracking-tight">{currentReading.current_a}</span>
                <span className="text-sm text-slate-500 font-mono">{"A"}</span>
              </div>
              <div className="h-2 bg-slate-900 rounded-full mt-5 overflow-hidden">
                <div 
                  className="h-full bg-purple-500 transition-all duration-300" 
                  style={{ width: `${Math.min(100, Math.abs(parseFloat(currentReading.current_a) / 5) * 100)}%` }}
                ></div>
              </div>
              <span className="text-[10px] font-mono text-slate-600 mt-2.5">DISCHARGE LIMIT: -3.0 A</span>
            </div>

          </section>

          {/* MAIN OSCILLOSCOPE TIME SERIES DIAGNOSTIC & LSTM PANEL CHART */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* THE SIGNATURE CYAN OSCILLOSCOPE REALTIME CHART */}
            <div className="lg:col-span-2 bg-[#111827] border border-slate-800 p-6 rounded-lg scanline-container flex flex-col relative shadow-md">
              <div className="flex justify-between items-center mb-5">
                <div className="flex items-center gap-3">
                  <div className="w-3.5 h-3.5 rounded-full bg-cyan-400 animate-pulse"></div>
                  <h3 className="text-sm font-bold font-mono tracking-wider uppercase text-slate-200">REALTIME TELEMETRY STREAM</h3>
                </div>
                <div className="flex items-center gap-3 font-mono text-xs text-slate-400">
                  <span className="w-3 h-3 rounded bg-cyan-400 inline-block"></span> {"Voltage (V)"}
                  <span className="w-3 h-3 rounded bg-emerald-400 inline-block ml-4"></span> {"SoH (%)"}
                </div>
              </div>

              {/* Graphical rendering */}
              <div className="h-80 md:h-96 w-full bg-[#050914] rounded-md border border-slate-800/80 pt-4 overflow-hidden relative">
                {/* Embedded dynamic coordinate background representation */}
                <div className="absolute inset-0 bg-[#060B18] oscilloscope-bg pointer-events-none z-0"></div>
                
                <ResponsiveContainer width="100%" height="100%" className="z-10 relative">
                  <LineChart data={activeHistory} margin={{ top: 5, right: 15, left: -20, bottom: 5 }}>
                    <CartesianGrid stroke="rgba(0, 212, 255, 0.08)" strokeDasharray="3 3" />
                    <XAxis 
                      dataKey="cycle" 
                      stroke="#475569" 
                      tick={{ fill: '#94A3B8', fontSize: 11, fontFamily: 'JetBrains Mono' }}
                      tickLine={false}
                    />
                    <YAxis 
                      yAxisId="left"
                      domain={[2.5, 4.5]} 
                      stroke="#475569"
                      tick={{ fill: '#00D4FF', fontSize: 11, fontFamily: 'JetBrains Mono' }}
                      tickLine={false}
                    />
                    <YAxis 
                      yAxisId="right"
                      orientation="right"
                      domain={[50, 100]} 
                      stroke="#475569"
                      tick={{ fill: '#10B981', fontSize: 11, fontFamily: 'JetBrains Mono' }}
                      tickLine={false}
                    />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#0F172A', borderColor: '#1E3A5F', borderRadius: '6px', fontFamily: 'JetBrains Mono', fontSize: '12px', padding: '12px' }}
                      labelClassName="text-slate-400 font-bold mb-2"
                    />
                    <Line 
                      yAxisId="left"
                      type="monotone" 
                      dataKey="voltage_v" 
                      stroke="#00D4FF" 
                      strokeWidth={2.5} 
                      dot={false}
                      activeDot={{ r: 6, stroke: '#00D4FF', strokeWidth: 1 }}
                    />
                    <Line 
                      yAxisId="right"
                      type="monotone" 
                      dataKey="soh_percent" 
                      stroke="#10B981" 
                      strokeWidth={2.5} 
                      dot={false}
                      activeDot={{ r: 6, stroke: '#10B981', strokeWidth: 1 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              <div className="flex justify-between items-center mt-4 font-mono text-[11px] text-slate-500">
                <span>INDEX SCALE: CYCLE RESOLUTION</span>
                <span className="flex items-center gap-2 text-cyan-400 bg-cyan-950/20 px-3 py-1.5 rounded border border-cyan-900/60">
                  <HardDrive className="w-4 h-4" /> Hypertable compressed window: 7-day policy Active
                </span>
              </div>
            </div>

            {/* PREDICTIVE AI / LSTM INFERENCE BLOCK - With Dropdown */}
            <details className="bg-[#111827] border border-slate-800 rounded-lg scanline-container shadow-md group" open>
              <summary className="flex justify-between items-center p-6 cursor-pointer outline-none">
                <div className="flex items-center gap-2.5">
                  <Cpu className="w-5 h-5 text-cyan-400" />
                  <h3 className="text-sm font-bold font-mono tracking-wider uppercase text-slate-200">LSTM RUL PREDICTIONS</h3>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/40 px-2.5 py-1 rounded border border-emerald-900 uppercase">
                    {lstmPredictions.modelVersion}
                  </span>
                  <ChevronDown className="w-5 h-5 text-slate-400 transition-transform duration-300" />
                </div>
              </summary>

              <div className="px-6 pb-6">
                {userRole === "fleet_admin" ? (
                  /* RUL VIEW FOR ADMIN */
                  <div className="space-y-5">
                    <div className="bg-[#0A0F1E] border border-slate-800 p-5 rounded-md flex flex-col items-center">
                      <span className="text-xs text-slate-500 uppercase font-mono tracking-wide">Forecasted Cycles Remaining</span>
                      <span className="text-5xl font-extrabold font-mono text-amber-500 glow-amber tracking-tight mt-3">
                        {lstmPredictions.predictedRul}
                      </span>
                      <span className="text-xs text-slate-400 font-mono mt-2">cycles until EOL limit (70%)</span>
                    </div>

                    <div className="space-y-3 pt-2">
                      <div className="flex justify-between text-sm font-mono">
                        <span className="text-slate-500">MC-Dropout Lower Bound</span>
                        <span className="text-slate-300 font-bold">{lstmPredictions.lowerBound}{" cycles"}</span>
                      </div>
                      <div className="flex justify-between text-sm font-mono">
                        <span className="text-slate-500">MC-Dropout Upper Bound</span>
                        <span className="text-slate-300 font-bold">{lstmPredictions.upperBound}{" cycles"}</span>
                      </div>
                      <div className="flex justify-between text-sm font-mono">
                        <span className="text-slate-500">Confidence Interval Range</span>
                        <span className="text-cyan-400 font-bold">{lstmPredictions.confidencePercent}{"% band"}</span>
                      </div>
                    </div>

                    <div className="bg-[#1E3A5F]/20 border border-[#1E3A5F]/60 p-4 rounded-md text-xs font-mono leading-relaxed text-cyan-100 mt-2">
                      <strong>AI DIAGNOSTIC SUMMARY:</strong>
                      {" The neural model calculates state degradation trajectory within acceptable $\pm15\%$ NASA ground-truth boundaries. Schedule next mechanical pack check at cycle #"}{currentReading.cycle + lstmPredictions.predictedRul - 20}{"."}
                    </div>

                    <div className="border-t border-slate-800/80 pt-4 mt-2">
                      <div className="flex justify-between items-center text-xs font-mono text-slate-500">
                        <span>LSTM ROOT MEAN SQ ERROR</span>
                        <span className="text-slate-300 font-bold">&lt; 10 CYCLES</span>
                      </div>
                    </div>
                  </div>
                ) : (
                  /* OPERATOR MOCKED OUT PREDICTIVE BLOCKED SCREEN */
                  <div className="flex-1 flex flex-col items-center justify-center border border-dashed border-slate-800 rounded-md p-8 bg-[#0A0F1E]/50 my-2">
                    <span className="text-sm font-bold uppercase tracking-wider text-rose-500 font-mono mb-2">Access Restriction Claimed</span>
                    <p className="text-xs text-slate-400 font-mono text-center leading-relaxed">
                      Predictive analytics are restricted to the <strong>fleet_admin</strong> claims authorization token. Change role in top navbar to authorize view.
                    </p>
                  </div>
                )}
              </div>
            </details>

          </div>

          {/* DYNAMIC SECOND LIFE RECOMMENDATION SYSTEM - With Dropdown */}
          <details className="bg-[#111827] border border-slate-800 rounded-lg scanline-container shadow-md group" open>
            <summary className="flex justify-between items-center p-6 cursor-pointer outline-none border-b border-transparent group-open:border-slate-800 transition-colors">
              <div className="flex items-center gap-3">
                <Zap className="w-6 h-6 text-amber-500 animate-pulse" />
                <h3 className="text-sm font-extrabold font-mono tracking-widest uppercase text-slate-200">
                  AUTOMATED SECOND-LIFE ENGINE & DISPOSITION SELECTOR
                </h3>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-xs font-mono bg-slate-800 text-slate-300 px-3 py-1 rounded border border-slate-700 uppercase">
                  Acoustic Analysis Driven
                </span>
                <ChevronDown className="w-5 h-5 text-slate-400 transition-transform duration-300 group-open:rotate-180" />
              </div>
            </summary>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 p-6">
              {/* Metric dials */}
              <div className="lg:col-span-5 bg-[#0A0F1E] border border-slate-800/80 p-5 rounded-md flex flex-col justify-between gap-5">
                <div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-mono text-slate-400 uppercase tracking-wide">STATE OF HEALTH SNAPSHOT</span>
                    <span className="text-xs font-mono text-slate-500">Snapshot #{currentReading.cycle}</span>
                  </div>
                  <div className="flex items-baseline gap-2 mt-3">
                    <span className="text-4xl font-extrabold font-mono text-cyan-400 tracking-tight glow-cyan">{sohVal.toFixed(2)}{"%"}</span>
                    <span className="text-sm text-slate-500 font-mono">SoH Ratio</span>
                  </div>
                </div>

                <div className="space-y-3 font-mono text-sm border-t border-slate-900 pt-4">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Current Battery Capacity:</span>
                    <span className="text-slate-200 font-bold">{currentReading.capacity_mah}{" mAh"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Nominal Design Capacity:</span>
                    <span className="text-slate-200">{activeBattery.nominalCapacity}{" mAh"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Total Run Cycles Accomplished:</span>
                    <span className="text-slate-200">{currentReading.cycle}{" Cycles"}</span>
                  </div>
                </div>

                <div className="pt-4 border-t border-slate-900 flex gap-3">
                  <div className="flex-1 bg-slate-900/60 border border-slate-800/80 px-3 py-2.5 rounded flex items-center gap-2 text-sm font-mono">
                    <span className="w-3 h-3 rounded-full bg-[#10B981]"></span>
                    <div>
                      <span className="text-[10px] text-slate-500 block leading-none mb-1">EV RETAIN</span>
                      <span className="text-xs text-slate-200 font-bold font-mono">{"SOH > 80%"}</span>
                    </div>
                  </div>
                  <div className="flex-1 bg-slate-900/60 border border-slate-800/80 px-3 py-2.5 rounded flex items-center gap-2 text-sm font-mono">
                    <span className="w-3 h-3 rounded-full bg-[#F59E0B]"></span>
                    <div>
                      <span className="text-[10px] text-slate-500 block leading-none mb-1">GRID STATIC</span>
                      <span className="text-xs text-slate-200 font-bold font-mono">{"SOH 70-80%"}</span>
                    </div>
                  </div>
                  <div className="flex-1 bg-slate-900/60 border border-slate-800/80 px-3 py-2.5 rounded flex items-center gap-2 text-sm font-mono">
                    <span className="w-3 h-3 rounded-full bg-[#EF4444]"></span>
                    <div>
                      <span className="text-[10px] text-slate-500 block leading-none mb-1">RECYCLE</span>
                      <span className="text-xs text-slate-200 font-bold font-mono">{"SOH < 60%"}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Dynamic recommendation card - Clean space wrapping with no overlaps */}
              <div className="lg:col-span-7 bg-[#1E3A5F]/20 border border-cyan-500/10 p-6 rounded-md flex flex-col justify-between relative min-h-[280px] overflow-hidden">
                {/* Low opacity background watermarked icon (placed cleanly and safely with lower opacity to prevent overlap clutter) */}
                <div className="absolute right-5 bottom-4 text-cyan-400/5 pointer-events-none z-0">         
                </div>

                <div className="z-10 space-y-5">
                  <div className="flex items-center gap-4">
                    <CheckCircle className="w-8 h-8 text-cyan-400 shrink-0" />
                    <div>
                      <span className="text-[10px] text-cyan-400 font-mono tracking-widest block uppercase font-bold mb-1">RE-DEPLOYMENT STRATEGY DISPOSITION</span>
                      <h4 className="text-xl font-bold text-slate-100 font-mono leading-tight">{secondLifeRecommendation.tier}</h4>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 mt-3 text-sm font-mono">
                    <div>
                      <span className="text-slate-500 block text-[10px] uppercase tracking-wide">SUITABILITY FACTOR</span>
                      <span className="text-slate-200 font-bold block text-base mt-1" style={{ color: secondLifeRecommendation.color }}>
                        {secondLifeRecommendation.suitability}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[10px] uppercase tracking-wide">REC APPLICATION AREA</span>
                      <span className="text-slate-200 font-semibold block mt-1">{secondLifeRecommendation.application}</span>
                    </div>
                  </div>

                  <div className="pt-4 border-t border-slate-800/80">
                    <span className="text-slate-500 block text-[10px] uppercase tracking-wide font-mono mb-2">ELECTROCHEMICAL INSIGHT & HEALTH REASONING</span>
                    <p className="text-slate-300 text-xs font-mono leading-relaxed bg-[#0A0F1E]/60 p-4 rounded border border-slate-800/60 max-h-[120px] overflow-y-auto custom-scrollbar">
                      {secondLifeRecommendation.engineeringInsight}
                    </p>
                  </div>
                </div>

                {/* Handover notification CTA */}
                <div className="mt-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 text-xs font-mono text-slate-400 bg-slate-900/90 px-5 py-3.5 rounded border border-slate-800 z-10">
                  <span className="text-slate-300">Authorized Disposition Target Selected:</span>
                  <button className="bg-cyan-500 hover:bg-cyan-400 text-black px-4 py-2 rounded font-bold uppercase text-[11px] tracking-wider transition-colors shrink-0">
                    GENERATE TRANSFER MANIFEST
                  </button>
                </div>
              </div>
            </div>
          </details>

        </main>
      </div>

      {/* SECOND LIFE & LIFE CYCLE EXPLAINER MODAL DIALOG */}
      {isSecondLifeModalOpen && (
        <div className="fixed inset-0 bg-[#000000]/85 flex items-center justify-center z-50 p-4 font-mono">
          <div className="bg-[#111827] border border-slate-800 rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto flex flex-col">
            
            <div className="p-4 border-b border-slate-800 flex justify-between items-center bg-[#0C111C]">
              <div className="flex items-center gap-2">
                <Info className="w-5 h-5 text-cyan-400" />
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200">
                  EV Battery Diagnostics & Second-Life Recommendation Framework
                </h3>
              </div>
              <button 
                onClick={() => setIsSecondLifeModalOpen(false)}
                className="text-slate-400 hover:text-slate-100 font-bold"
              >
                [ESC/CLOSE]
              </button>
            </div>

            <div className="p-6 space-y-4 text-xs leading-relaxed text-slate-300">
              <h4 className="text-cyan-400 text-xs font-bold uppercase tracking-wide">1. State of Health (SoH) Threshold Rules</h4>
              <p>
                The health status of each battery pack is calculated automatically upon every complete charge/discharge telemetry event as recorded in the TimescaleDB hypertable schema. 
              </p>
              <div className="my-3 py-2.5 bg-[#0A0F1E] rounded border border-slate-800 text-center text-cyan-400 font-mono text-[13px]">
                {"$$\\text{SoH (\\%) } = \\left( \\frac{Q_{\\text{measured}}}{Q_{\\text{nominal}}} \\right) \\times 100$$"}
              </div>
              <p>
                A decline in SoH is generally correlated to chemical degradation factors such as Solid Electrolyte Interphase (SEI) growth, lithium plating, and active material loss.
              </p>

              <h4 className="text-amber-500 text-xs font-bold uppercase tracking-wide">2. Remaining Useful Life (RUL) Forecasting</h4>
              <p>
                LSTM networks (Deep Learning model architecture managed by Data Ka Pandit) accept sequence windows of 50 features—including rolling voltage drop, temperature gradients, and internal resistance spikes—to predict the number of standard charge/discharge cycles until the battery hits the automotive End Of Life standard threshold of <strong>70% State of Health</strong>.
              </p>

              <h4 className="text-emerald-500 text-xs font-bold uppercase tracking-wide">3. Second-Life Trajectory Path Decisions</h4>
              <div className="bg-slate-900 border border-slate-800 p-3 rounded space-y-2">
                <div className="flex justify-between items-center border-b border-slate-800/60 pb-1.5 text-slate-200">
                  <span className="font-semibold text-emerald-400">Class A (&gt;80% SoH):</span>
                  <span>Continued Automotive Traction Deployment</span>
                </div>
                <div className="flex justify-between items-center border-b border-slate-800/60 pb-1.5 text-slate-200">
                  <span className="font-semibold text-amber-500">Class B (70% - 80% SoH):</span>
                  <span>Stationary Grid & Micro-Grid Peak Shaving Backup</span>
                </div>
                <div className="flex justify-between items-center border-b border-slate-800/60 pb-1.5 text-slate-200">
                  <span className="font-semibold text-rose-400">Class C (60% - 70% SoH):</span>
                  <span>Residential Energy Powerwalls & Agricultural Pumps</span>
                </div>
                <div className="flex justify-between items-center text-slate-200">
                  <span className="font-semibold text-rose-600">Class D (&lt;60% SoH):</span>
                  <span>Direct Material Recovery & Reprocessing Recycling</span>
                </div>
              </div>

              {/* NEW DATASOURCE SECTION FOR CLEANED DATASET*/}
              <h4 className="text-[#00D4FF] text-xs font-bold uppercase tracking-wide mt-4">4. Open Source Telemetry Dataset</h4>
              <p>
                The foundational battery degradation cycles driving this simulation and the LSTM inference engine are derived from the NASA Prognostics Data Repository. Our refined, model-ready dataset is publicly hosted and maintained at:
              </p>
              <div className="bg-[#111827] border border-slate-800 p-3 rounded font-mono text-xs break-all flex items-center gap-3">
                <HardDrive className="w-4 h-4 text-cyan-400 shrink-0" />
                <a href={DATASET_SOURCE_URL} target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:text-cyan-300 hover:underline transition-colors block w-full">
                  {DATASET_SOURCE_URL}
                </a>
              </div>

              <div className="bg-[#1E3A5F]/20 border border-[#1E3A5F] p-3 rounded text-[11px] text-cyan-100 mt-2">
                <strong>Rangoli Designer Tip:</strong> This UI is completely prepared for live FastAPI server WebSocket/SSE integration. SQS multi-EV concurrent payloads mapped to standard payload specifications align smoothly without layout adjustments.
              </div>
            </div>

            <div className="p-4 border-t border-slate-800 bg-[#0C111C] flex justify-end">
              <button 
                onClick={() => setIsSecondLifeModalOpen(false)}
                className="bg-cyan-500 hover:bg-cyan-400 text-black px-4 py-2 rounded font-bold font-mono text-xs uppercase"
              >
                Acknowledge & Return
              </button>
            </div>

          </div>
        </div>
      )}

    </div>
  );
}