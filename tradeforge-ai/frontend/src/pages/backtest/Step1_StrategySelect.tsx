import { useMemo } from 'react';
import { Plus, GitBranch, Loader2, RefreshCcw } from 'lucide-react';
import type { Strategy as ApiStrategy } from '@/types/api';

const statusColors: Record<string, string> = {
  active: 'border-l-[#22D3EE]',
  paper: 'border-l-[#F59E0B]',
  backtesting: 'border-l-[#A78BFA]',
  draft: 'border-l-[#475569]',
};

interface Step1Props {
  strategies: ApiStrategy[];
  isLoading: boolean;
  error: string | null;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRetry?: () => void;
}

export default function Step1_StrategySelect({
  strategies,
  isLoading,
  error,
  selectedId,
  onSelect,
  onNew,
  onRetry,
}: Step1Props) {
  const sortedStrategies = useMemo(
    () => [...strategies].sort((a, b) => Number(b.id) - Number(a.id)),
    [strategies]
  );

  return (
    <div className="max-w-[800px] mx-auto pt-10 pb-8 px-6">
      <div className="text-center mb-8">
        <h2 className="font-display text-[26px] font-semibold text-[#F1F5F9] mb-2">
          Select a Strategy to Backtest
        </h2>
        <p className="text-[15px] text-[#94A3B8]">
          Choose from your saved strategies or create a new one
        </p>
      </div>

      {isLoading && (
        <div className="flex flex-col items-center justify-center py-16">
          <Loader2 size={28} className="text-[#22D3EE] animate-spin mb-3" />
          <p className="text-[13px] text-[#64748B]">Loading strategies...</p>
        </div>
      )}

      {error && !isLoading && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <p className="text-[14px] text-[#EF4444] mb-3">{error}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="flex items-center gap-2 px-4 py-2 bg-[#12121A] border border-[rgba(255,255,255,0.08)] text-[#F1F5F9] text-[13px] rounded-[4px] hover:bg-[#1A1A25]"
            >
              <RefreshCcw size={13} />
              Retry
            </button>
          )}
        </div>
      )}

      {!isLoading && !error && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {sortedStrategies.map((strategy) => (
            <button
              key={strategy.id}
              onClick={() => onSelect(strategy.id)}
              className={`text-left p-5 bg-[#12121A] border rounded-[8px] transition-all duration-150 group ${
                selectedId === strategy.id
                  ? 'border-[#22D3EE] bg-[rgba(34,211,238,0.06)] shadow-[0_0_0_2px_rgba(34,211,238,0.20)]'
                  : `${statusColors[strategy.status] || 'border-l-[#475569]'} border-l-[3px] border-[rgba(255,255,255,0.06)] hover:border-[rgba(255,255,255,0.10)] hover:bg-[#1A1A25]`
              }`}
            >
              <div className="flex items-start justify-between mb-2">
                <h3 className="text-[15px] font-semibold text-[#F1F5F9]">{strategy.name}</h3>
                {selectedId === strategy.id && (
                  <div className="w-5 h-5 rounded-full bg-[#22D3EE] flex items-center justify-center shrink-0">
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M2.5 6L5 8.5L9.5 4" stroke="#030305" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </div>
                )}
              </div>
              <p className="text-[13px] text-[#94A3B8] mb-3 line-clamp-2 leading-relaxed">
                {strategy.description || 'No description'}
              </p>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-[#1A1A25] text-[#94A3B8]">
                  {strategy.segment || 'Stocks'}
                </span>
                <span className="text-[11px] text-[#475569]">Status: {strategy.status}</span>
              </div>
            </button>
          ))}

          {/* New Strategy Card */}
          <button
            onClick={onNew}
            className="flex flex-col items-center justify-center p-5 border-2 border-dashed border-[rgba(255,255,255,0.06)] rounded-[8px] text-[#475569] hover:text-[#22D3EE] hover:border-[#22D3EE] transition-all min-h-[140px]"
          >
            <Plus size={28} className="mb-2" />
            <span className="text-[13px] font-medium">Create New Strategy</span>
          </button>
        </div>
      )}

      {/* Empty state fallback */}
      {!isLoading && !error && strategies.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <GitBranch size={40} className="text-[#475569] mb-3" />
          <p className="text-[14px] font-medium text-[#475569]">No strategies yet</p>
          <p className="text-[12px] text-[#64748B] mt-1">Create your first strategy in the Strategy Builder</p>
        </div>
      )}
    </div>
  );
}
