import { useState } from 'react';
import { Search, Plus, GitBranch } from 'lucide-react';
import type { SavedStrategy, StrategyStatus } from './types';

const statusColors: Record<StrategyStatus, string> = {
  active: 'bg-[#22D3EE] text-[#030305]',
  paper: 'bg-[#F59E0B] text-[#030305]',
  backtesting: 'bg-[#A78BFA] text-[#030305]',
  draft: 'bg-[#1A1A25] text-[#64748B] border border-[rgba(255,255,255,0.06)]',
};

const statusLabels: Record<StrategyStatus, string> = {
  active: 'Active',
  paper: 'Paper',
  backtesting: 'Testing',
  draft: 'Draft',
};

const accentColors: Record<StrategyStatus, string> = {
  active: 'border-l-[#22D3EE]',
  paper: 'border-l-[#F59E0B]',
  backtesting: 'border-l-[#A78BFA]',
  draft: 'border-l-[#475569]',
};

interface StrategyListPanelProps {
  strategies: SavedStrategy[];
  selectedId: string | null;
  onSelect: (strategy: SavedStrategy) => void;
  onNew: () => void;
}

export default function StrategyListPanel({ strategies, selectedId, onSelect, onNew }: StrategyListPanelProps) {
  const [search, setSearch] = useState('');

  const filtered = strategies.filter((s) =>
    s.name.toLowerCase().includes(search.toLowerCase()) ||
    s.instrument.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="w-[280px] shrink-0 bg-[#12121A] border-r border-[rgba(255,255,255,0.06)] flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-[rgba(255,255,255,0.06)]">
        <button
          onClick={onNew}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-[#22D3EE] text-[#030305] text-[13px] font-semibold rounded-[4px] hover:brightness-110 transition-all duration-200 hover:shadow-[0_0_20px_rgba(34,211,238,0.15)] active:scale-[0.98]"
        >
          <Plus size={14} />
          New Strategy
        </button>
      </div>

      {/* Search */}
      <div className="px-3 py-2 border-b border-[rgba(255,255,255,0.06)]">
        <div className="relative">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#64748B]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search strategies..."
            className="w-full h-8 pl-8 pr-3 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[6px] text-[12px] text-[#F1F5F9] placeholder:text-[#475569] focus:outline-none focus:border-[#22D3EE] transition-all"
          />
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto py-1">
        {filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center py-10 text-center">
            <GitBranch size={20} className="text-[#475569] mb-2" />
            <p className="text-[11px] text-[#64748B]">No strategies found</p>
          </div>
        )}
        {filtered.map((strategy) => (
          <button
            key={strategy.id}
            onClick={() => onSelect(strategy)}
            className={`w-full text-left px-4 py-3 border-l-[3px] transition-all duration-150 group ${
              selectedId === strategy.id
                ? 'bg-[rgba(34,211,238,0.08)] border-l-[#22D3EE]'
                : `${accentColors[strategy.status]} hover:bg-[#1A1A25]`
            }`}
          >
            <div className="flex items-center justify-between mb-1">
              <span className={`text-[13px] font-medium truncate ${
                selectedId === strategy.id ? 'text-[#22D3EE]' : 'text-[#F1F5F9]'
              }`}>
                {strategy.name}
              </span>
            </div>
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${statusColors[strategy.status]}`}>
                {statusLabels[strategy.status]}
              </span>
              <span className="text-[11px] text-[#64748B]">{strategy.instrument}</span>
            </div>
            <p className="text-[11px] text-[#475569] truncate">{strategy.lastModified}</p>
          </button>
        ))}
      </div>
    </div>
  );
}
