import { useState } from 'react';
import { Search, ChevronDown, TrendingUp, Zap, Activity, BarChart3 } from 'lucide-react';
import { INDICATORS } from './types';
import type { IndicatorMeta } from './types';

const categoryIcons = {
  trend: TrendingUp,
  momentum: Zap,
  volatility: Activity,
  volume: BarChart3,
};

const categoryLabels = {
  trend: 'Trend',
  momentum: 'Momentum',
  volatility: 'Volatility',
  volume: 'Volume',
};

const categoryColors: Record<string, string> = {
  trend: 'text-[#22D3EE]',
  momentum: 'text-[#A78BFA]',
  volatility: 'text-[#F59E0B]',
  volume: 'text-[#10B981]',
};

interface IndicatorPaletteProps {
  onSelect?: (indicator: IndicatorMeta) => void;
}

export default function IndicatorPalette({ onSelect }: IndicatorPaletteProps) {
  const [search, setSearch] = useState('');
  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>({
    trend: true,
    momentum: true,
    volatility: false,
    volume: false,
  });

  const toggleCategory = (cat: string) => {
    setExpandedCategories((prev) => ({ ...prev, [cat]: !prev[cat] }));
  };

  const categories = ['trend', 'momentum', 'volatility', 'volume'] as const;

  const filteredIndicators = search
    ? INDICATORS.filter((i) =>
        i.name.toLowerCase().includes(search.toLowerCase()) ||
        i.shortName.toLowerCase().includes(search.toLowerCase())
      )
    : null;

  return (
    <div className="w-[240px] shrink-0 bg-[#12121A] border-r border-[rgba(255,255,255,0.06)] flex flex-col h-full">
      {/* Header */}
      <div className="px-3 py-3 border-b border-[rgba(255,255,255,0.06)]">
        <h3 className="text-[13px] font-semibold text-[#F1F5F9] mb-2">Indicators</h3>
        <div className="relative">
          <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#64748B]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search..."
            className="w-full h-7 pl-7 pr-2 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[6px] text-[12px] text-[#F1F5F9] placeholder:text-[#475569] focus:outline-none focus:border-[#22D3EE] transition-all"
          />
        </div>
      </div>

      {/* Categories */}
      <div className="flex-1 overflow-y-auto py-1">
        {filteredIndicators ? (
          <div className="px-2 py-1">
            {filteredIndicators.map((indicator) => (
              <button
                key={indicator.shortName}
                onClick={() => onSelect?.(indicator)}
                className="w-full text-left px-3 py-2 rounded-[6px] hover:bg-[rgba(34,211,238,0.08)] transition-all group"
              >
                <div className="flex items-center gap-2">
                  <span className={`text-[12px] font-mono font-medium ${categoryColors[indicator.category]}`}>
                    {indicator.shortName}
                  </span>
                </div>
                <p className="text-[11px] text-[#475569] mt-0.5">{indicator.description}</p>
              </button>
            ))}
            {filteredIndicators.length === 0 && (
              <p className="text-[11px] text-[#475569] text-center py-4">No indicators found</p>
            )}
          </div>
        ) : (
          categories.map((cat) => {
            const Icon = categoryIcons[cat];
            const items = INDICATORS.filter((i) => i.category === cat);
            const expanded = expandedCategories[cat];

            return (
              <div key={cat} className="mb-0.5">
                <button
                  onClick={() => toggleCategory(cat)}
                  className="w-full flex items-center gap-2 px-3 py-2 hover:bg-[#1A1A25] transition-all"
                >
                  <Icon size={14} className={categoryColors[cat]} />
                  <span className="text-[12px] font-semibold text-[#F1F5F9] flex-1 text-left">
                    {categoryLabels[cat]}
                  </span>
                  <span className="text-[10px] text-[#475569]">{items.length}</span>
                  <ChevronDown
                    size={12}
                    className={`text-[#475569] transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
                  />
                </button>

                {expanded && (
                  <div className="px-1 pb-1">
                    {items.map((indicator) => (
                      <button
                        key={indicator.shortName}
                        onClick={() => onSelect?.(indicator)}
                        className="w-full text-left pl-8 pr-3 py-1.5 rounded-[4px] hover:bg-[rgba(34,211,238,0.06)] transition-all group"
                        title={indicator.description}
                      >
                        <span className="text-[12px] text-[#94A3B8] group-hover:text-[#F1F5F9] font-mono">
                          {indicator.shortName}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
