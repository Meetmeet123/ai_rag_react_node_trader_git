import { useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { strategies as initialStrategies, sparklineData } from './data';
import type { Strategy } from './data';

function MiniSparkline({ data, positive }: { data: number[]; positive: boolean }) {
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * 80;
    const y = 20 - ((v - min) / range) * 20;
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg width="80" height="24" viewBox="0 0 80 24" className="shrink-0">
      <polyline
        points={points}
        fill="none"
        stroke={positive ? '#10B981' : '#EF4444'}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function StrategyDeploymentPanel() {
  const [strats, setStrats] = useState<Strategy[]>(initialStrategies);
  const [showDeploy, setShowDeploy] = useState(false);

  const toggleStatus = (id: string) => {
    setStrats(prev =>
      prev.map(s =>
        s.id === id
          ? { ...s, status: s.status === 'Running' ? 'Paused' : 'Running' as 'Running' | 'Paused' }
          : s
      )
    );
  };

  const deleteStrategy = (id: string) => {
    setStrats(prev => prev.filter(s => s.id !== id));
  };

  return (
    <div className="w-full h-full bg-[#12121A] border-r border-[rgba(255,255,255,0.06)] flex flex-col">
      {/* Header */}
      <div className="h-10 flex items-center justify-between px-3 border-b border-[rgba(255,255,255,0.06)]">
        <div className="flex items-center gap-2">
          <span className="text-[15px] font-semibold text-[#F1F5F9]">Active Strategies</span>
          <span className="px-1.5 py-0.5 bg-[rgba(34,211,238,0.12)] text-[#22D3EE] text-[11px] font-semibold rounded-full">
            {strats.filter(s => s.status === 'Running').length}
          </span>
        </div>
        <button
          onClick={() => setShowDeploy(!showDeploy)}
          className="flex items-center gap-1 px-2 py-1 bg-[#22D3EE] text-[#030305] text-[11px] font-semibold rounded-[4px] hover:brightness-110 transition-all"
        >
          <Plus size={12} />
          Deploy
        </button>
      </div>

      {/* Strategy Cards */}
      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        {strats.map((strat, idx) => (
          <div
            key={strat.id}
            className="bg-[#0A0A0F] border border-[rgba(255,255,255,0.06)] rounded-[6px] p-3 transition-all hover:border-[rgba(255,255,255,0.10)]"
            style={{ borderLeft: '3px solid #F59E0B', animationDelay: `${idx * 40}ms` }}
          >
            {/* Name & Symbol */}
            <div className="flex items-center justify-between mb-1">
              <span className="text-[13px] font-semibold text-[#F1F5F9]">{strat.name}</span>
              <button
                onClick={() => deleteStrategy(strat.id)}
                className="text-[#64748B] hover:text-[#EF4444] transition-colors"
              >
                <Trash2 size={13} />
              </button>
            </div>

            <div className="flex items-center gap-2 mb-2">
              <span className="text-[11px] text-[#64748B]">{strat.symbol}</span>
              <span className="px-1.5 py-0.5 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-full text-[10px] text-[#94A3B8]">
                {strat.segment}
              </span>
            </div>

            {/* Status */}
            <div className="flex items-center gap-1.5 mb-2">
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  strat.status === 'Running' ? 'bg-[#10B981]' : 'bg-[#F59E0B]'
                }`}
              />
              <span
                className={`text-[11px] font-medium ${
                  strat.status === 'Running' ? 'text-[#10B981]' : 'text-[#F59E0B]'
                }`}
              >
                {strat.status}
              </span>
            </div>

            {/* P&L + Sparkline */}
            <div className="flex items-center justify-between mb-2">
              <span
                className={`text-[13px] font-mono font-medium ${
                  strat.pnl >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
                }`}
              >
                {strat.pnl >= 0 ? '+' : ''}₹{strat.pnl.toLocaleString('en-IN')}
              </span>
              <MiniSparkline data={sparklineData[Number(strat.id) - 1] || sparklineData[0]} positive={strat.pnl >= 0} />
            </div>

            {/* Allocation */}
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] text-[#64748B]">Allocated</span>
              <span className="text-[11px] font-mono text-[#94A3B8]">₹{strat.allocation.toLocaleString('en-IN')}</span>
            </div>

            {/* Meta */}
            <div className="flex items-center justify-between text-[10px] text-[#475569] mb-2">
              <span>Since {strat.activeSince.split(' ')[0]}</span>
              <span>{strat.signalCount} signals</span>
            </div>

            {/* Toggle */}
            <button
              onClick={() => toggleStatus(strat.id)}
              className={`w-full py-1 text-[11px] font-medium rounded-[4px] transition-all ${
                strat.status === 'Running'
                  ? 'bg-[rgba(16,185,129,0.15)] text-[#10B981] hover:bg-[rgba(16,185,129,0.25)]'
                  : 'bg-[rgba(245,158,11,0.15)] text-[#F59E0B] hover:bg-[rgba(245,158,11,0.25)]'
              }`}
            >
              {strat.status === 'Running' ? 'Active' : 'Stopped'}
            </button>
          </div>
        ))}

        {/* Deploy Strategy Button */}
        <button className="w-full flex items-center justify-center gap-1.5 py-2.5 border border-dashed border-[rgba(255,255,255,0.10)] rounded-[6px] text-[13px] text-[#64748B] hover:border-[#22D3EE] hover:text-[#22D3EE] transition-all">
          <Plus size={14} />
          Deploy Strategy
        </button>
      </div>
    </div>
  );
}
