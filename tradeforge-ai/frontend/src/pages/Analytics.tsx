import { useMemo, useState } from 'react';
import { Download, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';
import KPICardsRow from './analytics/KPICardsRow';
import PnLChart from './analytics/PnLChart';
import StrategyPerformanceTable from './analytics/StrategyPerformanceTable';
import TradeJournal from './analytics/TradeJournal';
import DrawdownAnalysis from './analytics/DrawdownAnalysis';
import MonthlyReportCard from './analytics/MonthlyReportCard';
import ExportReport from './analytics/ExportReport';
import { Spinner } from '@/components/ui/spinner';
import { useQuery } from '@/hooks/useApi';
import { fetchAnalyticsDashboard, exportAnalyticsReport } from '@/lib/api';

type TabKey = 'performance' | 'journal' | 'drawdown' | 'monthly' | 'export';

const tabs: { key: TabKey; label: string }[] = [
  { key: 'performance', label: 'Performance' },
  { key: 'journal', label: 'Trade Journal' },
  { key: 'drawdown', label: 'Drawdown' },
  { key: 'monthly', label: 'Monthly' },
  { key: 'export', label: 'Export' },
];

function getDateRange(range: string): { from_date?: string; to_date?: string } {
  const today = new Date();
  const to_date = today.toISOString().split('T')[0];
  const from = new Date(today);

  switch (range) {
    case 'Today':
      break;
    case '1W':
      from.setDate(from.getDate() - 7);
      break;
    case '1M':
      from.setDate(from.getDate() - 30);
      break;
    case '3M':
      from.setDate(from.getDate() - 90);
      break;
    case '1Y':
      from.setDate(from.getDate() - 365);
      break;
    default:
      from.setDate(from.getDate() - 30);
  }

  const from_date = from.toISOString().split('T')[0];
  return range === 'Today' ? { from_date: to_date, to_date } : { from_date, to_date };
}

export default function Analytics() {
  const [activeTab, setActiveTab] = useState<TabKey>('performance');
  const [dateRange, setDateRange] = useState('1M');
  const [exporting, setExporting] = useState(false);

  const dateRanges = ['Today', '1W', '1M', '3M', '1Y'];

  const { from_date, to_date } = useMemo(() => getDateRange(dateRange), [dateRange]);

  const { data: dashboard, isLoading, error } = useQuery(
    () => fetchAnalyticsDashboard({ from_date, to_date }),
    [dateRange],
  );

  const kpis = dashboard?.kpis;
  const dailyPnl = dashboard?.daily_pnl?.length ? dashboard.daily_pnl : undefined;
  const strategyPerformance = dashboard?.strategy_performance?.length
    ? dashboard.strategy_performance
    : undefined;
  const recentTrades = dashboard?.recent_trades?.length ? dashboard.recent_trades : undefined;

  const handleExport = async () => {
    try {
      setExporting(true);
      const csv = await exportAnalyticsReport();
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `analytics-report-${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success('Report downloaded');
    } catch (err) {
      const message = err && typeof err === 'object' && 'detail' in err
        ? String(err.detail)
        : 'Failed to export report';
      toast.error(message);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="flex flex-col gap-5 relative">
      {isLoading && (
        <div className="absolute inset-0 z-10 bg-[#030305]/60 backdrop-blur-[2px] rounded-[8px] flex items-center justify-center">
          <div className="flex items-center gap-2 text-[#94A3B8] text-[13px]">
            <Spinner className="text-[#22D3EE]" />
            Loading analytics…
          </div>
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 px-4 py-3 bg-[rgba(239,68,68,0.08)] border border-[rgba(239,68,68,0.15)] rounded-[8px] text-[12px] text-[#EF4444]">
          <AlertCircle size={14} />
          Could not load live analytics. Showing fallback data.
        </div>
      )}

      {/* Filter Bar */}
      <div className="w-full h-12 flex items-center gap-3 px-4 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[8px]">
        {/* Date Range Selector */}
        <div className="flex items-center gap-0 bg-[#12121A] rounded-[6px] p-0.5">
          {dateRanges.map(range => (
            <button
              key={range}
              onClick={() => setDateRange(range)}
              className={`px-3 py-1 rounded-[4px] text-[11px] font-medium transition-all ${
                dateRange === range
                  ? 'bg-[#1A1A25] text-[#F1F5F9] shadow-sm'
                  : 'text-[#64748B] hover:text-[#94A3B8]'
              }`}
            >
              {range}
            </button>
          ))}
        </div>

        <div className="w-px h-5 bg-[rgba(255,255,255,0.06)]" />

        {/* Strategy Filter */}
        <select className="h-7 px-2 bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[6px] text-[11px] text-[#94A3B8] focus:outline-none focus:border-[#22D3EE]">
          <option>All Strategies</option>
          <option>Momentum Crossover</option>
          <option>RSI Reversal</option>
          <option>Bollinger Bounce</option>
          <option>Breakout Scout</option>
          <option>Mean Reversion</option>
        </select>

        {/* Segment Filter */}
        <select className="h-7 px-2 bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[6px] text-[11px] text-[#94A3B8] focus:outline-none focus:border-[#22D3EE]">
          <option>All Segments</option>
          <option>Stocks</option>
          <option>Futures</option>
          <option>Options</option>
        </select>

        <div className="ml-auto">
          <button
            onClick={handleExport}
            disabled={exporting}
            className="h-7 px-3 flex items-center gap-1.5 bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[6px] text-[11px] text-[#94A3B8] hover:text-[#F1F5F9] hover:bg-[#1A1A25] transition-all disabled:opacity-50"
          >
            {exporting ? (
              <Spinner className="text-[#22D3EE]" />
            ) : (
              <Download size={12} />
            )}
            Export Report
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <KPICardsRow kpis={kpis} />

      {/* Charts Row */}
      <PnLChart dailyPnl={dailyPnl} kpis={kpis} />

      {/* Tabs */}
      <div className="flex items-center gap-0 border-b border-[rgba(255,255,255,0.06)]">
        {tabs.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2.5 text-[13px] font-medium transition-all relative ${
              activeTab === tab.key
                ? 'text-[#F1F5F9]'
                : 'text-[#64748B] hover:text-[#94A3B8]'
            }`}
          >
            {tab.label}
            {activeTab === tab.key && (
              <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-[#22D3EE] rounded-t-full" />
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="pb-4">
        {activeTab === 'performance' && <StrategyPerformanceTable strategyPerformance={strategyPerformance} />}
        {activeTab === 'journal' && <TradeJournal trades={recentTrades} />}
        {activeTab === 'drawdown' && <DrawdownAnalysis />}
        {activeTab === 'monthly' && <MonthlyReportCard />}
        {activeTab === 'export' && <ExportReport />}
      </div>
    </div>
  );
}
