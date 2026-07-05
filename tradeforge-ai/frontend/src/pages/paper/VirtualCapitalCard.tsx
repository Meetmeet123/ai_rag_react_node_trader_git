import { useState } from 'react';
import { Pause, Download, RotateCcw } from 'lucide-react';
import {
  STARTING_CAPITAL,
  USED_MARGIN,
  AVAILABLE_BALANCE,
  TODAY_PNL,
  positions,
} from './data';

export default function VirtualCapitalCard() {
  const [hoveredReset, setHoveredReset] = useState(false);

  const todayPnLPercent = ((TODAY_PNL / STARTING_CAPITAL) * 100).toFixed(2);

  // Mini area chart data for today's P&L
  const areaPoints = [
    [0, 40], [10, 35], [20, 38], [30, 30], [40, 32], [50, 25], [60, 28],
    [70, 20], [80, 22], [90, 15], [100, 18], [110, 10], [120, 12],
    [130, 8], [140, 5], [150, 0],
  ];
  const miniAreaPath = areaPoints.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0]},${p[1]}`).join(' ') +
    ' L150,60 L0,60 Z';

  return (
    <div className="w-full flex flex-col gap-3 p-3">
      {/* Virtual Capital Card */}
      <div className="bg-[#0A0A0F] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-4">
        <span className="text-[12px] text-[#64748B] font-medium">Virtual Capital</span>
        <div className="text-[28px] font-mono font-semibold text-[#F1F5F9] mt-1">
          ₹{STARTING_CAPITAL.toLocaleString('en-IN')}
        </div>
        <div className="w-full h-px bg-[rgba(255,255,255,0.06)] my-3" />
        <div className="flex justify-between mb-1">
          <span className="text-[13px] text-[#94A3B8]">Used</span>
          <span className="text-[13px] font-mono text-[#94A3B8]">₹{USED_MARGIN.toLocaleString('en-IN')}</span>
        </div>
        <div className="flex justify-between mb-3">
          <span className="text-[13px] text-[#94A3B8]">Available</span>
          <span className="text-[13px] font-mono text-[#10B981]">₹{AVAILABLE_BALANCE.toLocaleString('en-IN')}</span>
        </div>
        <div className="w-full h-1 bg-[#06060A] rounded-full overflow-hidden">
          <div
            className="h-full bg-[#22D3EE] rounded-full transition-all"
            style={{ width: `${(USED_MARGIN / STARTING_CAPITAL) * 100}%` }}
          />
        </div>
        <span className="text-[10px] text-[#64748B] mt-1 block">
          {(USED_MARGIN / STARTING_CAPITAL * 100).toFixed(1)}% utilized
        </span>
      </div>

      {/* P&L Summary Card */}
      <div className="bg-[#0A0A0F] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-4">
        <span className="text-[12px] text-[#64748B] font-medium">Today&apos;s P&amp;L</span>
        <div className="text-[28px] font-mono font-semibold text-[#10B981] mt-1">
          +₹{TODAY_PNL.toLocaleString('en-IN')}
        </div>
        <div className="flex items-center gap-1.5 mt-1">
          <span className="text-[13px] text-[#10B981]">+{todayPnLPercent}%</span>
          <span className="text-[11px] text-[#64748B]">on deployed capital</span>
        </div>
        <svg viewBox="0 0 150 60" className="w-full h-[60px] mt-2" preserveAspectRatio="none">
          <defs>
            <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgba(16,185,129,0.3)" />
              <stop offset="100%" stopColor="rgba(16,185,129,0)" />
            </linearGradient>
          </defs>
          <path d={miniAreaPath} fill="url(#pnlGrad)" />
          <polyline
            points={areaPoints.map(p => `${p[0]},${p[1]}`).join(' ')}
            fill="none"
            stroke="#10B981"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>

      {/* Active Positions Card */}
      <div className="bg-[#0A0A0F] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-4">
        <span className="text-[12px] text-[#64748B] font-medium">Active Positions</span>
        <div className="text-[28px] font-semibold text-[#F1F5F9] mt-1">
          {positions.length}
        </div>
        <div className="mt-2 space-y-1.5">
          {positions.slice(0, 3).map(pos => (
            <div key={pos.id} className="flex items-center justify-between">
              <span className="text-[11px] font-mono text-[#94A3B8]">{pos.symbol} ×{Math.abs(pos.qty)}</span>
              <span className={`text-[11px] font-mono font-medium ${pos.pnl >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                {pos.pnl >= 0 ? '+' : ''}₹{pos.pnl.toLocaleString('en-IN')}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-col gap-2 p-1">
        <button
          onMouseEnter={() => setHoveredReset(true)}
          onMouseLeave={() => setHoveredReset(false)}
          className="w-full flex items-center justify-center gap-1.5 py-2 border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] font-medium text-[#F1F5F9] hover:bg-[#1A1A25] hover:border-[rgba(255,255,255,0.10)] transition-all"
        >
          <RotateCcw size={13} className={hoveredReset ? 'rotate-[-180deg]' : ''} style={{ transition: 'transform 300ms' }} />
          Reset Capital
        </button>
        <button className="w-full flex items-center justify-center gap-1.5 py-2 border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] font-medium text-[#F1F5F9] hover:bg-[#1A1A25] hover:border-[rgba(255,255,255,0.10)] transition-all">
          <Pause size={13} />
          Pause All
        </button>
        <button className="w-full flex items-center justify-center gap-1.5 py-2 text-[12px] font-medium text-[#64748B] hover:text-[#F1F5F9] hover:bg-[#12121A] rounded-[4px] transition-all">
          <Download size={13} />
          Export Log
        </button>
      </div>
    </div>
  );
}
