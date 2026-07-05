import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { strategyPerformance } from './data';

type SortKey = keyof typeof strategyPerformance[0];

interface PerformanceMetricsProps {
  label: string;
  value: string;
  valueColor?: string;
}

function PerformanceMetric({ label, value, valueColor = 'text-[#F1F5F9]' }: PerformanceMetricsProps) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-[11px] text-[#64748B] font-medium">{label}</span>
      <span className={`text-[13px] font-mono font-semibold ${valueColor}`}>{value}</span>
    </div>
  );
}

export default function StrategyPerformanceTable() {
  const [sortKey, setSortKey] = useState<SortKey>('netPnl');
  const [sortAsc, setSortAsc] = useState(false);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const sorted = [...strategyPerformance].sort((a, b) => {
    const aVal = a[sortKey];
    const bVal = b[sortKey];
    if (typeof aVal === 'number' && typeof bVal === 'number') {
      return sortAsc ? aVal - bVal : bVal - aVal;
    }
    return sortAsc
      ? String(aVal).localeCompare(String(bVal))
      : String(bVal).localeCompare(String(aVal));
  });

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  };

  const SortIcon = ({ colKey }: { colKey: SortKey }) => {
    if (sortKey !== colKey) return <span className="text-[#475569] ml-1">↕</span>;
    return sortAsc
      ? <ChevronUp size={12} className="ml-1 text-[#22D3EE]" />
      : <ChevronDown size={12} className="ml-1 text-[#22D3EE]" />;
  };

  return (
    <div className="flex gap-4">
      {/* Table - 60% */}
      <div className="w-[60%] bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-4">
        <h3 className="text-[15px] font-semibold text-[#F1F5F9] mb-3">Strategy Performance</h3>
        <div className="overflow-auto">
          <table className="w-full">
            <thead className="sticky top-0 bg-[#06060A]">
              <tr>
                {[
                  { key: 'name' as SortKey, label: 'Strategy' },
                  { key: 'trades' as SortKey, label: 'Trades' },
                  { key: 'winRate' as SortKey, label: 'Win Rate' },
                  { key: 'netPnl' as SortKey, label: 'Net P&L' },
                  { key: 'avgProfit' as SortKey, label: 'Avg Profit' },
                  { key: 'avgLoss' as SortKey, label: 'Avg Loss' },
                  { key: 'profitFactor' as SortKey, label: 'P.F.' },
                ].map(col => (
                  <th
                    key={col.key}
                    className="text-left px-3 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap cursor-pointer hover:text-[#F1F5F9] transition-colors select-none"
                    onClick={() => toggleSort(col.key)}
                  >
                    <span className="flex items-center">
                      {col.label}
                      <SortIcon colKey={col.key} />
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((strat) => (
                <>
                  <tr
                    key={strat.name}
                    className="border-b border-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.02)] transition-colors cursor-pointer"
                    onClick={() => setExpandedRow(expandedRow === strat.name ? null : strat.name)}
                  >
                    <td className="px-3 py-2 text-[12px] font-medium text-[#F1F5F9] whitespace-nowrap">{strat.name}</td>
                    <td className="px-3 py-2 text-[12px] font-mono text-[#94A3B8] whitespace-nowrap">{strat.trades}</td>
                    <td className="px-3 py-2 text-[12px] font-mono text-[#A78BFA] whitespace-nowrap">{strat.winRate.toFixed(1)}%</td>
                    <td className={`px-3 py-2 text-[12px] font-mono font-semibold whitespace-nowrap ${
                      strat.netPnl >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
                    }`}>
                      {strat.netPnl >= 0 ? '+' : ''}₹{strat.netPnl.toLocaleString('en-IN')}
                    </td>
                    <td className="px-3 py-2 text-[12px] font-mono text-[#10B981] whitespace-nowrap">+₹{strat.avgProfit.toLocaleString('en-IN')}</td>
                    <td className="px-3 py-2 text-[12px] font-mono text-[#EF4444] whitespace-nowrap">-₹{Math.abs(strat.avgLoss).toLocaleString('en-IN')}</td>
                    <td className="px-3 py-2 text-[12px] font-mono text-[#F1F5F9] whitespace-nowrap">{strat.profitFactor.toFixed(2)}</td>
                  </tr>
                  {expandedRow === strat.name && (
                    <tr>
                      <td colSpan={7} className="px-3 py-2 bg-[#06060A]">
                        <div className="grid grid-cols-3 gap-3 text-[11px]">
                          <div>
                            <span className="text-[#64748B]">Wins: </span>
                            <span className="text-[#10B981] font-mono font-medium">{strat.wins}</span>
                          </div>
                          <div>
                            <span className="text-[#64748B]">Losses: </span>
                            <span className="text-[#EF4444] font-mono font-medium">{strat.losses}</span>
                          </div>
                          <div>
                            <span className="text-[#64748B]">Sharpe: </span>
                            <span className="text-[#F1F5F9] font-mono font-medium">{strat.sharpe.toFixed(2)}</span>
                          </div>
                          <div>
                            <span className="text-[#64748B]">Max DD: </span>
                            <span className="text-[#EF4444] font-mono font-medium">₹{Math.abs(strat.maxDrawdown).toLocaleString('en-IN')}</span>
                          </div>
                          <div>
                            <span className="text-[#64748B]">P.F.: </span>
                            <span className="text-[#F1F5F9] font-mono font-medium">{strat.profitFactor.toFixed(2)}</span>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Metrics Detail - 40% */}
      <div className="w-[40%] bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-4">
        <h3 className="text-[15px] font-semibold text-[#F1F5F9] mb-3">Performance Metrics</h3>
        <div className="divide-y divide-[rgba(255,255,255,0.04)]">
          <PerformanceMetric label="Gross Profit" value={`+₹${(253500).toLocaleString('en-IN')}`} valueColor="text-[#10B981]" />
          <PerformanceMetric label="Gross Loss" value={`-₹${(128940).toLocaleString('en-IN')}`} valueColor="text-[#EF4444]" />
          <PerformanceMetric label="Net Profit" value={`+₹${(145000).toLocaleString('en-IN')}`} valueColor="text-[#10B981]" />
          <PerformanceMetric label="Profit Factor" value="1.97" />
          <PerformanceMetric label="Expectancy" value={`₹${(2595).toLocaleString('en-IN')}`} />
          <PerformanceMetric label="Average Trade" value={`₹${(1169).toLocaleString('en-IN')}`} />
          <PerformanceMetric label="Average Win" value={`+₹${(8450).toLocaleString('en-IN')}`} valueColor="text-[#10B981]" />
          <PerformanceMetric label="Average Loss" value={`-₹${(3200).toLocaleString('en-IN')}`} valueColor="text-[#EF4444]" />
          <PerformanceMetric label="Largest Win" value={`+₹${(34200).toLocaleString('en-IN')}`} valueColor="text-[#10B981]" />
          <PerformanceMetric label="Largest Loss" value={`-₹${(18500).toLocaleString('en-IN')}`} valueColor="text-[#EF4444]" />
          <PerformanceMetric label="Avg Holding Period" value="2.3 days" />
          <PerformanceMetric label="Total Commission" value={`₹${(2880).toLocaleString('en-IN')}`} valueColor="text-[#EF4444]" />
        </div>
      </div>
    </div>
  );
}
