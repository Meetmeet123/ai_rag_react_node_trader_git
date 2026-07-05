import { useState } from 'react';
import { Download } from 'lucide-react';
import KPICardsRow from './analytics/KPICardsRow';
import PnLChart from './analytics/PnLChart';
import StrategyPerformanceTable from './analytics/StrategyPerformanceTable';
import TradeJournal from './analytics/TradeJournal';
import DrawdownAnalysis from './analytics/DrawdownAnalysis';
import MonthlyReportCard from './analytics/MonthlyReportCard';
import ExportReport from './analytics/ExportReport';

type TabKey = 'performance' | 'journal' | 'drawdown' | 'monthly' | 'export';

const tabs: { key: TabKey; label: string }[] = [
  { key: 'performance', label: 'Performance' },
  { key: 'journal', label: 'Trade Journal' },
  { key: 'drawdown', label: 'Drawdown' },
  { key: 'monthly', label: 'Monthly' },
  { key: 'export', label: 'Export' },
];

export default function Analytics() {
  const [activeTab, setActiveTab] = useState<TabKey>('performance');
  const [dateRange, setDateRange] = useState('1M');

  const dateRanges = ['Today', '1W', '1M', '3M', '1Y'];

  return (
    <div className="flex flex-col gap-5">
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
          <button className="h-7 px-3 flex items-center gap-1.5 bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[6px] text-[11px] text-[#94A3B8] hover:text-[#F1F5F9] hover:bg-[#1A1A25] transition-all">
            <Download size={12} />
            Export Report
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <KPICardsRow />

      {/* Charts Row */}
      <PnLChart />

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
        {activeTab === 'performance' && <StrategyPerformanceTable />}
        {activeTab === 'journal' && <TradeJournal />}
        {activeTab === 'drawdown' && <DrawdownAnalysis />}
        {activeTab === 'monthly' && <MonthlyReportCard />}
        {activeTab === 'export' && <ExportReport />}
      </div>
    </div>
  );
}
