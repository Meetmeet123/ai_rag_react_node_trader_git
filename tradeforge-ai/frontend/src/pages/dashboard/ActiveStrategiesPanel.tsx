import { useState } from 'react';
import { Pause, Play, Square, Settings, TrendingUp, TrendingDown } from 'lucide-react';
import { ACTIVE_STRATEGIES } from './data';

export default function ActiveStrategiesPanel() {
  const [strategies, setStrategies] = useState(ACTIVE_STRATEGIES);

  const toggleStatus = (id: string) => {
    setStrategies((prev) =>
      prev.map((s) =>
        s.id === id ? { ...s, status: s.status === 'Running' ? 'Paused' : 'Running' } : s
      )
    );
  };

  return (
    <div className="w-full bg-[#12121A] border-t border-[rgba(255,255,255,0.06)] p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[15px] font-semibold text-[#F1F5F9]">Active Strategies</span>
        <span className="text-[11px] text-[#64748B]">
          {strategies.filter((s) => s.status === 'Running').length} running
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
        {strategies.map((strategy) => {
          const isProfit = strategy.pnl >= 0;
          const isRunning = strategy.status === 'Running';

          return (
            <div
              key={strategy.id}
              className="bg-[#0A0A0F] border border-[rgba(255,255,255,0.06)] rounded-[6px] p-3 flex items-center justify-between"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-[13px] font-semibold text-[#F1F5F9] truncate">
                    {strategy.name}
                  </span>
                  <span
                    className={`shrink-0 w-1.5 h-1.5 rounded-full ${
                      isRunning ? 'bg-[#10B981]' : 'bg-[#F59E0B]'
                    }`}
                  />
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-[#64748B]">{strategy.instrument}</span>
                  <span
                    className={`text-[10px] font-medium ${
                      isRunning ? 'text-[#10B981]' : 'text-[#F59E0B]'
                    }`}
                  >
                    {strategy.status}
                  </span>
                </div>
                <div className="flex items-center gap-1 mt-1">
                  {isProfit ? (
                    <TrendingUp size={10} className="text-[#10B981]" />
                  ) : (
                    <TrendingDown size={10} className="text-[#EF4444]" />
                  )}
                  <span
                    className={`text-[12px] font-mono font-medium ${
                      isProfit ? 'text-[#10B981]' : 'text-[#EF4444]'
                    }`}
                  >
                    {isProfit ? '+' : ''}₹{strategy.pnl.toLocaleString('en-IN')}
                  </span>
                  <span
                    className={`text-[10px] ${
                      isProfit ? 'text-[#10B981]' : 'text-[#EF4444]'
                    }`}
                  >
                    ({isProfit ? '+' : ''}
                    {strategy.pnlPercent}%)
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-1 shrink-0 ml-2">
                <button
                  onClick={() => toggleStatus(strategy.id)}
                  className="w-7 h-7 flex items-center justify-center rounded-[4px] text-[#64748B] hover:text-[#F1F5F9] hover:bg-[#1A1A25] transition-all"
                  title={isRunning ? 'Pause' : 'Resume'}
                >
                  {isRunning ? <Pause size={12} /> : <Play size={12} />}
                </button>
                <button className="w-7 h-7 flex items-center justify-center rounded-[4px] text-[#64748B] hover:text-[#EF4444] hover:bg-[rgba(239,68,68,0.15)] transition-all">
                  <Square size={12} />
                </button>
                <button className="w-7 h-7 flex items-center justify-center rounded-[4px] text-[#64748B] hover:text-[#F1F5F9] hover:bg-[#1A1A25] transition-all">
                  <Settings size={12} />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
