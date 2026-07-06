import { useEffect, useMemo, useState } from 'react';
import { Plus, Trash2, Play, Square } from 'lucide-react';
import { toast } from 'sonner';
import { fetchStrategies, deployStrategy, stopStrategy, deleteStrategy } from '@/lib/api';
import type { Strategy } from '@/types/api';

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

const sparklineData = [
  [4200, 4500, 4100, 4800, 5200, 4900, 5600, 5800, 6200, 6800],
  [3200, 3100, 2800, 2600, 2400, 2200, 2000, 1800, 1600, 1400],
  [1500, 1800, 2200, 2600, 2400, 2800, 3200, 3500, 3800, 4200],
];

function formatStatus(status: string): 'Running' | 'Paused' | 'Stopped' {
  if (status === 'paper' || status === 'active' || status === 'backtesting') return 'Running';
  if (status === 'draft') return 'Paused';
  return 'Stopped';
}

export default function StrategyDeploymentPanel() {
  const [strats, setStrats] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  const loadStrategies = async () => {
    try {
      setLoading(true);
      const response = await fetchStrategies('paper');
      setStrats(response.strategies ?? []);
      setError(null);
    } catch (err) {
      const message = err && typeof err === 'object' && 'detail' in err ? String(err.detail) : 'Failed to load strategies';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStrategies();
    const interval = setInterval(loadStrategies, 10000);
    return () => clearInterval(interval);
  }, []);

  const runningCount = useMemo(
    () => strats.filter(s => formatStatus(s.status) === 'Running').length,
    [strats],
  );

  const handleToggle = async (id: string, currentStatus: string) => {
    setTogglingId(id);
    try {
      if (formatStatus(currentStatus) === 'Running') {
        const result = await stopStrategy(id);
        toast.success(result.message || 'Strategy stopped');
      } else {
        const result = await deployStrategy(id, 'paper');
        toast.success(result.message || 'Strategy deployed');
      }
      await loadStrategies();
    } catch (err) {
      const message = err && typeof err === 'object' && 'detail' in err ? String(err.detail) : 'Strategy action failed';
      toast.error(message);
    } finally {
      setTogglingId(null);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      const result = await deleteStrategy(id);
      toast.success(result.message || 'Strategy deleted');
      await loadStrategies();
    } catch (err) {
      const message = err && typeof err === 'object' && 'detail' in err ? String(err.detail) : 'Delete failed';
      toast.error(message);
    }
  };

  return (
    <div className="w-full h-full bg-[#12121A] border-r border-[rgba(255,255,255,0.06)] flex flex-col">
      {/* Header */}
      <div className="h-10 flex items-center justify-between px-3 border-b border-[rgba(255,255,255,0.06)]">
        <div className="flex items-center gap-2">
          <span className="text-[15px] font-semibold text-[#F1F5F9]">Active Strategies</span>
          <span className="px-1.5 py-0.5 bg-[rgba(34,211,238,0.12)] text-[#22D3EE] text-[11px] font-semibold rounded-full">
            {runningCount}
          </span>
        </div>
        <button
          onClick={() => loadStrategies()}
          className="flex items-center gap-1 px-2 py-1 bg-[#22D3EE] text-[#030305] text-[11px] font-semibold rounded-[4px] hover:brightness-110 transition-all"
        >
          <Plus size={12} />
          Deploy
        </button>
      </div>

      {/* Strategy Cards */}
      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        {error && (
          <div className="p-2 text-[11px] text-[#EF4444] bg-[rgba(239,68,68,0.12)] rounded-[4px]">
            {error}
          </div>
        )}

        {loading && strats.length === 0 ? (
          <div className="p-3 text-[12px] text-[#64748B]">Loading strategies…</div>
        ) : strats.length === 0 ? (
          <div className="p-3 text-[12px] text-[#64748B]">No paper strategies deployed.</div>
        ) : (
          strats.map((strat, idx) => {
            const status = formatStatus(strat.status);
            const isRunning = status === 'Running';
            const pnl = 0; // Realised strategy P&L not available from Strategy model
            const positive = pnl >= 0;
            const sparkData = sparklineData[idx % sparklineData.length] ?? sparklineData[0];

            return (
              <div
                key={strat.id}
                className="bg-[#0A0A0F] border border-[rgba(255,255,255,0.06)] rounded-[6px] p-3 transition-all hover:border-[rgba(255,255,255,0.10)]"
                style={{ borderLeft: '3px solid #F59E0B', animationDelay: `${idx * 40}ms` }}
              >
                {/* Name & Symbol */}
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[13px] font-semibold text-[#F1F5F9]">{strat.name}</span>
                  <button
                    onClick={() => handleDelete(strat.id)}
                    className="text-[#64748B] hover:text-[#EF4444] transition-colors"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>

                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[11px] text-[#64748B]">{strat.instrument}</span>
                  <span className="px-1.5 py-0.5 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-full text-[10px] text-[#94A3B8]">
                    {strat.segment || 'NSE'}
                  </span>
                </div>

                {/* Status */}
                <div className="flex items-center gap-1.5 mb-2">
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      isRunning ? 'bg-[#10B981]' : 'bg-[#F59E0B]'
                    }`}
                  />
                  <span
                    className={`text-[11px] font-medium ${
                      isRunning ? 'text-[#10B981]' : 'text-[#F59E0B]'
                    }`}
                  >
                    {status}
                  </span>
                </div>

                {/* P&L + Sparkline */}
                <div className="flex items-center justify-between mb-2">
                  <span
                    className={`text-[13px] font-mono font-medium ${
                      positive ? 'text-[#10B981]' : 'text-[#EF4444]'
                    }`}
                  >
                    {positive ? '+' : ''}₹{pnl.toLocaleString('en-IN')}
                  </span>
                  <MiniSparkline data={sparkData} positive={positive} />
                </div>

                {/* Allocation */}
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[11px] text-[#64748B]">Timeframe</span>
                  <span className="text-[11px] font-mono text-[#94A3B8]">{strat.timeframe}</span>
                </div>

                {/* Meta */}
                <div className="flex items-center justify-between text-[10px] text-[#475569] mb-2">
                  <span>{strat.status}</span>
                  <span>AI: {strat.is_ai_generated ? 'Yes' : 'No'}</span>
                </div>

                {/* Toggle */}
                <button
                  onClick={() => handleToggle(strat.id, strat.status)}
                  disabled={togglingId === strat.id}
                  className={`w-full py-1 text-[11px] font-medium rounded-[4px] transition-all flex items-center justify-center gap-1 ${
                    isRunning
                      ? 'bg-[rgba(16,185,129,0.15)] text-[#10B981] hover:bg-[rgba(16,185,129,0.25)]'
                      : 'bg-[rgba(245,158,11,0.15)] text-[#F59E0B] hover:bg-[rgba(245,158,11,0.25)]'
                  } ${togglingId === strat.id ? 'opacity-60 cursor-not-allowed' : ''}`}
                >
                  {togglingId === strat.id ? (
                    <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                  ) : isRunning ? (
                    <Square size={11} />
                  ) : (
                    <Play size={11} />
                  )}
                  {isRunning ? 'Active' : 'Stopped'}
                </button>
              </div>
            );
          })
        )}

        {/* Deploy Strategy Button */}
        <button className="w-full flex items-center justify-center gap-1.5 py-2.5 border border-dashed border-[rgba(255,255,255,0.10)] rounded-[6px] text-[13px] text-[#64748B] hover:border-[#22D3EE] hover:text-[#22D3EE] transition-all">
          <Plus size={14} />
          Deploy Strategy
        </button>
      </div>
    </div>
  );
}
