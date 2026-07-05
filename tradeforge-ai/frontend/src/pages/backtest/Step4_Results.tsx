import { useState, useMemo } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { Download, ChevronLeft, ChevronRight, Shield, Zap } from 'lucide-react';
import type { BacktestResult } from './types';

interface Step4Props {
  result: BacktestResult;
  onBack: () => void;
  onPaperTrade: () => void;
}

type ResultTab = 'trades' | 'monthly' | 'stats';

export default function Step4_Results({ result, onBack, onPaperTrade }: Step4Props) {
  const [activeTab, setActiveTab] = useState<ResultTab>('trades');
  const [tradePage, setTradePage] = useState(0);
  const TRADES_PER_PAGE = 15;

  const paginatedTrades = useMemo(() => {
    const start = tradePage * TRADES_PER_PAGE;
    return result.trades.slice(start, start + TRADES_PER_PAGE);
  }, [result.trades, tradePage]);

  const totalPages = Math.ceil(result.trades.length / TRADES_PER_PAGE);

  return (
    <div className="flex flex-col -mx-4 md:-mx-6 -mt-4 md:-mt-6">
      {/* Metrics Summary Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 border-b border-[rgba(255,255,255,0.06)]">
        <MetricCard label="Net P&L" value={formatCurrency(result.netPnl)} color={result.netPnl >= 0 ? 'green' : 'red'} />
        <MetricCard label="Total Trades" value={String(result.totalTrades)} color="neutral" />
        <MetricCard label="Win Rate" value={`${result.winRate}%`} color={result.winRate > 50 ? 'green' : 'neutral'} />
        <MetricCard label="Profit Factor" value={String(result.profitFactor)} color={result.profitFactor > 1 ? 'green' : 'neutral'} />
        <MetricCard label="Max Drawdown" value={formatCurrency(result.maxDrawdown)} color="red" />
        <MetricCard label="Sharpe Ratio" value={String(result.sharpeRatio)} color={result.sharpeRatio > 1 ? 'green' : 'neutral'} />
        <MetricCard label="Avg Profit" value={formatCurrency(result.avgProfitPerTrade)} color="green" />
        <MetricCard label="Avg Loss" value={`${formatCurrency(result.avgLossPerTrade)}`} color="red" last />
      </div>

      {/* Equity Curve Chart */}
      <div className="h-[340px] bg-[#12121A] border-b border-[rgba(255,255,255,0.06)] p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[13px] font-semibold text-[#F1F5F9]">Equity Curve</h3>
          <div className="flex items-center gap-1">
            {['1M', '3M', '6M', '1Y', 'ALL'].map((range) => (
              <button key={range} className="px-2 py-0.5 text-[10px] text-[#475569] hover:text-[#94A3B8] transition-colors">
                {range}
              </button>
            ))}
            <button className="w-6 h-6 flex items-center justify-center rounded-[4px] text-[#475569] hover:text-[#F1F5F9] hover:bg-[#1A1A25] ml-1">
              <Download size={11} />
            </button>
          </div>
        </div>
        <ResponsiveContainer width="100%" height="88%">
          <AreaChart data={result.equityCurve} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgba(16,185,129,0.15)" />
                <stop offset="100%" stopColor="rgba(16,185,129,0)" />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: '#475569' }}
              tickLine={false}
              axisLine={{ stroke: 'rgba(255,255,255,0.06)' }}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fontSize: 10, fill: '#475569', fontFamily: 'JetBrains Mono' }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: number) => `Rs.${(v / 1000).toFixed(0)}K`}
              domain={['auto', 'auto']}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#12121A',
                border: '1px solid rgba(255,255,255,0.06)',
                borderRadius: '6px',
                fontSize: '12px',
              }}
              labelStyle={{ color: '#94A3B8' }}
              formatter={(value: number) => [`Rs. ${value.toLocaleString('en-IN')}`, 'Portfolio']}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke="#10B981"
              strokeWidth={1.5}
              fill="url(#equityGradient)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Drawdown Chart */}
      <div className="h-[180px] bg-[#0A0A0F] border-b border-[rgba(255,255,255,0.06)] p-4">
        <h3 className="text-[13px] font-semibold text-[#F1F5F9] mb-3">Drawdown</h3>
        <ResponsiveContainer width="100%" height="80%">
          <AreaChart data={result.drawdownCurve} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="ddGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgba(239,68,68,0.12)" />
                <stop offset="100%" stopColor="rgba(239,68,68,0)" />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: '#475569' }}
              tickLine={false}
              axisLine={{ stroke: 'rgba(255,255,255,0.06)' }}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fontSize: 10, fill: '#475569', fontFamily: 'JetBrains Mono' }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: number) => `${v.toFixed(1)}%`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#12121A',
                border: '1px solid rgba(255,255,255,0.06)',
                borderRadius: '6px',
                fontSize: '12px',
              }}
              formatter={(value: number) => [`${value.toFixed(2)}%`, 'Drawdown']}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke="#EF4444"
              strokeWidth={1}
              fill="url(#ddGradient)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 px-4 py-2 border-b border-[rgba(255,255,255,0.06)] bg-[#06060A]">
        {[
          { key: 'trades' as const, label: 'Trades' },
          { key: 'monthly' as const, label: 'Monthly' },
          { key: 'stats' as const, label: 'Statistics' },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => { setActiveTab(tab.key); setTradePage(0); }}
            className={`px-3 py-1.5 rounded-[6px] text-[12px] font-medium transition-all ${
              activeTab === tab.key
                ? 'bg-[#12121A] text-[#F1F5F9]'
                : 'text-[#64748B] hover:text-[#94A3B8]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto p-4 min-h-[300px]">
        {activeTab === 'trades' && (
          <div>
            <table className="w-full">
              <thead>
                <tr className="bg-[#06060A]">
                  <Th>#</Th>
                  <Th>Entry Date</Th>
                  <Th>Exit Date</Th>
                  <Th>Symbol</Th>
                  <Th>Side</Th>
                  <Th className="text-right">Entry</Th>
                  <Th className="text-right">Exit</Th>
                  <Th className="text-right">P&L</Th>
                  <Th className="text-right">P&L %</Th>
                  <Th>Status</Th>
                </tr>
              </thead>
              <tbody>
                {paginatedTrades.map((trade) => (
                  <tr
                    key={trade.id}
                    className="border-b border-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.02)] transition-colors"
                  >
                    <Td>{trade.id}</Td>
                    <Td>{trade.entryDate}</Td>
                    <Td>{trade.exitDate}</Td>
                    <Td mono>{trade.symbol}</Td>
                    <Td>
                      <span className={`text-[11px] font-medium ${trade.side === 'Long' ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                        {trade.side}
                      </span>
                    </Td>
                    <Td mono className="text-right">{trade.entryPrice.toLocaleString('en-IN')}</Td>
                    <Td mono className="text-right">{trade.exitPrice.toLocaleString('en-IN')}</Td>
                    <Td mono className={`text-right ${trade.pnl >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                      {trade.pnl >= 0 ? '+' : ''}{trade.pnl.toLocaleString('en-IN')}
                    </Td>
                    <Td mono className={`text-right ${trade.pnlPercent >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                      {trade.pnlPercent >= 0 ? '+' : ''}{trade.pnlPercent}%
                    </Td>
                    <Td>
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                        trade.status === 'WIN'
                          ? 'bg-[rgba(16,185,129,0.15)] text-[#10B981]'
                          : 'bg-[rgba(239,68,68,0.15)] text-[#EF4444]'
                      }`}>
                        {trade.status}
                      </span>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Pagination */}
            <div className="flex items-center justify-end gap-2 mt-3">
              <button
                onClick={() => setTradePage((p) => Math.max(0, p - 1))}
                disabled={tradePage === 0}
                className="w-7 h-7 flex items-center justify-center rounded-[4px] text-[#475569] hover:text-[#F1F5F9] hover:bg-[#12121A] disabled:opacity-30 transition-all"
              >
                <ChevronLeft size={14} />
              </button>
              <span className="text-[11px] text-[#64748B] font-mono">
                {tradePage + 1} / {totalPages}
              </span>
              <button
                onClick={() => setTradePage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={tradePage >= totalPages - 1}
                className="w-7 h-7 flex items-center justify-center rounded-[4px] text-[#475569] hover:text-[#F1F5F9] hover:bg-[#12121A] disabled:opacity-30 transition-all"
              >
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}

        {activeTab === 'monthly' && (
          <div>
            <table className="w-full">
              <thead>
                <tr className="bg-[#06060A]">
                  <Th>Month</Th>
                  <Th className="text-right">Trades</Th>
                  <Th className="text-right">Wins</Th>
                  <Th className="text-right">Losses</Th>
                  <Th className="text-right">Win Rate</Th>
                  <Th className="text-right">Gross P&L</Th>
                  <Th className="text-right">Charges</Th>
                  <Th className="text-right">Net P&L</Th>
                </tr>
              </thead>
              <tbody>
                {result.monthlyReturns.map((m) => (
                  <tr key={m.month} className="border-b border-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.02)]">
                    <Td>{m.month}</Td>
                    <Td mono className="text-right">{m.trades}</Td>
                    <Td mono className="text-right text-[#10B981]">{m.wins}</Td>
                    <Td mono className="text-right text-[#EF4444]">{m.losses}</Td>
                    <Td mono className="text-right">{m.winRate}%</Td>
                    <Td mono className={`text-right ${m.grossPnl >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                      {m.grossPnl >= 0 ? '+' : ''}{m.grossPnl.toLocaleString('en-IN')}
                    </Td>
                    <Td mono className="text-right text-[#475569]">{m.charges.toLocaleString('en-IN')}</Td>
                    <Td mono className={`text-right ${m.netPnl >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                      {m.netPnl >= 0 ? '+' : ''}{m.netPnl.toLocaleString('en-IN')}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'stats' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-3 max-w-[800px]">
            <StatRow label="Expectancy" value={`Rs. ${result.expectancy.toLocaleString('en-IN')}`} />
            <StatRow label="Calmar Ratio" value={String(result.calmarRatio)} />
            <StatRow label="Sortino Ratio" value={String(result.sortinoRatio)} />
            <StatRow label="Avg Holding Period" value={`${result.avgHoldingPeriod} days`} />
            <StatRow label="Largest Win" value={`Rs. ${result.largestWin.toLocaleString('en-IN')}`} color="green" />
            <StatRow label="Largest Loss" value={`Rs. ${result.largestLoss.toLocaleString('en-IN')}`} color="red" />
            <StatRow label="Consecutive Wins (Max)" value={String(result.consecutiveWins)} color="green" />
            <StatRow label="Consecutive Losses (Max)" value={String(result.consecutiveLosses)} color="red" />
            <StatRow label="Recovery Factor" value={String(result.recoveryFactor)} />
            <StatRow label="Payoff Ratio" value={String(result.payoffRatio)} />
            <StatRow label="Average Win" value={`Rs. ${result.avgWin.toLocaleString('en-IN')}`} color="green" />
            <StatRow label="Average Loss" value={`Rs. ${Math.abs(result.avgLoss).toLocaleString('en-IN')}`} color="red" />
            <StatRow label="Best Month" value={result.bestMonth} color="green" />
            <StatRow label="Worst Month" value={result.worstMonth} color="red" />
            <StatRow label="Win Streak (Current)" value={String(result.currentWinStreak)} color="green" />
          </div>
        )}
      </div>

      {/* Bottom Action Bar */}
      <div className="h-12 shrink-0 bg-[#12121A] border-t border-[rgba(255,255,255,0.06)] flex items-center justify-between px-4">
        <button
          onClick={onBack}
          className="flex items-center gap-1 px-3 py-1.5 text-[12px] text-[#64748B] hover:text-[#F1F5F9] transition-colors"
        >
          <ChevronLeft size={14} />
          Back to Config
        </button>

        <div className="flex items-center gap-2">
          <button className="flex items-center gap-1.5 px-3 py-1.5 border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] text-[#94A3B8] hover:text-[#F1F5F9] hover:bg-[#1A1A25] transition-all">
            <Download size={12} />
            Save Report
          </button>
          <button
            onClick={onPaperTrade}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-[rgba(245,158,11,0.30)] rounded-[4px] text-[12px] text-[#F59E0B] hover:bg-[rgba(245,158,11,0.08)] transition-all"
          >
            <Shield size={12} />
            Paper Trade
          </button>
          <button className="flex items-center gap-1.5 px-3 py-1.5 bg-[#22D3EE] text-[#030305] rounded-[4px] text-[12px] font-semibold hover:brightness-110 transition-all">
            <Zap size={12} />
            Deploy Live
          </button>
        </div>
      </div>
    </div>
  );
}

/* ─── Sub-components ─── */

function MetricCard({ label, value, color, last = false }: { label: string; value: string; color: 'green' | 'red' | 'neutral'; last?: boolean }) {
  const colorMap = {
    green: 'text-[#10B981]',
    red: 'text-[#EF4444]',
    neutral: 'text-[#F1F5F9]',
  };

  return (
    <div className={`bg-[#12121A] p-3 ${last ? '' : 'border-r border-[rgba(255,255,255,0.06)]'}`}>
      <p className="text-[10px] text-[#64748B] mb-1">{label}</p>
      <p className={`font-mono text-[16px] font-medium ${colorMap[color]}`}>{value}</p>
    </div>
  );
}

function Th({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <th className={`text-left px-3 py-2 text-[11px] font-medium text-[#64748B] ${className}`}>
      {children}
    </th>
  );
}

function Td({ children, mono = false, className = '' }: { children: React.ReactNode; mono?: boolean; className?: string }) {
  return (
    <td className={`px-3 py-2 text-[12px] text-[#F1F5F9] ${mono ? 'font-mono' : ''} ${className}`}>
      {children}
    </td>
  );
}

function StatRow({ label, value, color }: { label: string; value: string; color?: 'green' | 'red' }) {
  const colorClass = color === 'green' ? 'text-[#10B981]' : color === 'red' ? 'text-[#EF4444]' : 'text-[#F1F5F9]';
  return (
    <div className="flex items-center justify-between py-2 border-b border-[rgba(255,255,255,0.04)]">
      <span className="text-[12px] text-[#64748B]">{label}</span>
      <span className={`text-[13px] font-semibold font-mono ${colorClass}`}>{value}</span>
    </div>
  );
}

function formatCurrency(value: number): string {
  const absVal = Math.abs(value);
  if (absVal >= 100000) {
    return `${value >= 0 ? '+' : '-'}Rs.${(absVal / 100000).toFixed(2)}L`;
  }
  return `${value >= 0 ? '+' : '-'}Rs.${absVal.toLocaleString('en-IN')}`;
}
