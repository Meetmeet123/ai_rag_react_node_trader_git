import { useState, useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { monthlyData } from './data';

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[6px] px-3 py-2 shadow-lg">
      <p className="text-[11px] text-[#64748B] mb-1">{label}</p>
      <p className={`text-[13px] font-mono font-semibold ${payload[0].value >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
        {payload[0].value >= 0 ? '+' : ''}₹{payload[0].value.toLocaleString('en-IN')}
      </p>
    </div>
  );
}

export default function MonthlyReportCard() {
  const [selectedMonth, setSelectedMonth] = useState(monthlyData[monthlyData.length - 1].month);

  const month = useMemo(
    () => monthlyData.find(m => m.month === selectedMonth) || monthlyData[monthlyData.length - 1],
    [selectedMonth]
  );

  const chartData = monthlyData.map(m => ({
    month: m.month.split(' ')[0].substring(0, 3),
    netPnl: m.netPnl,
  }));

  return (
    <div className="space-y-4">
      {/* Monthly P&L Bar Chart */}
      <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-[15px] font-semibold text-[#F1F5F9]">Monthly P&L</h3>
        </div>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={chartData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis
              dataKey="month"
              tick={{ fontSize: 11, fill: '#475569', fontFamily: 'Inter' }}
              tickLine={false}
              axisLine={{ stroke: 'rgba(255,255,255,0.06)' }}
            />
            <YAxis
              tick={{ fontSize: 10, fill: '#475569', fontFamily: 'JetBrains Mono' }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: number) => `₹${(v / 1000).toFixed(0)}K`}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="netPnl" radius={[3, 3, 0, 0]} maxBarSize={32}>
              {chartData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.netPnl >= 0 ? '#10B981' : '#EF4444'}
                  fillOpacity={0.8}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Month Selector + Details */}
      <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-[15px] font-semibold text-[#F1F5F9]">Monthly Summary</h3>
          <select
            value={selectedMonth}
            onChange={e => setSelectedMonth(e.target.value)}
            className="h-8 px-3 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[6px] text-[13px] text-[#F1F5F9] focus:outline-none focus:border-[#22D3EE]"
          >
            {monthlyData.map(m => (
              <option key={m.month} value={m.month}>{m.month}</option>
            ))}
          </select>
        </div>

        {/* Month KPI Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
          <div className="bg-[#0A0A0F] rounded-[6px] p-3">
            <span className="text-[10px] text-[#64748B] font-medium">Gross P&L</span>
            <div className={`text-[16px] font-mono font-semibold mt-1 ${month.grossPnl >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
              {month.grossPnl >= 0 ? '+' : ''}₹{month.grossPnl.toLocaleString('en-IN')}
            </div>
          </div>
          <div className="bg-[#0A0A0F] rounded-[6px] p-3">
            <span className="text-[10px] text-[#64748B] font-medium">Brokerage</span>
            <div className="text-[16px] font-mono font-semibold text-[#EF4444] mt-1">
              -₹{month.brokerage.toLocaleString('en-IN')}
            </div>
          </div>
          <div className="bg-[#0A0A0F] rounded-[6px] p-3">
            <span className="text-[10px] text-[#64748B] font-medium">Net P&L</span>
            <div className={`text-[16px] font-mono font-semibold mt-1 ${month.netPnl >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
              {month.netPnl >= 0 ? '+' : ''}₹{month.netPnl.toLocaleString('en-IN')}
            </div>
          </div>
          <div className="bg-[#0A0A0F] rounded-[6px] p-3">
            <span className="text-[10px] text-[#64748B] font-medium">Cumulative</span>
            <div className="text-[16px] font-mono font-semibold text-[#22D3EE] mt-1">
              ₹{month.cumulative.toLocaleString('en-IN')}
            </div>
          </div>
        </div>

        {/* Month Details Table */}
        <div className="overflow-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[rgba(255,255,255,0.06)]">
                <th className="text-left px-3 py-2 text-[11px] font-medium text-[#64748B]">Month</th>
                <th className="text-right px-3 py-2 text-[11px] font-medium text-[#64748B]">Trades</th>
                <th className="text-right px-3 py-2 text-[11px] font-medium text-[#64748B]">Wins</th>
                <th className="text-right px-3 py-2 text-[11px] font-medium text-[#64748B]">Losses</th>
                <th className="text-right px-3 py-2 text-[11px] font-medium text-[#64748B]">Win Rate</th>
                <th className="text-right px-3 py-2 text-[11px] font-medium text-[#64748B]">Net P&L</th>
                <th className="text-right px-3 py-2 text-[11px] font-medium text-[#64748B]">Best Trade</th>
                <th className="text-right px-3 py-2 text-[11px] font-medium text-[#64748B]">Worst Trade</th>
              </tr>
            </thead>
            <tbody>
              {monthlyData.map(m => (
                <tr
                  key={m.month}
                  className={`border-b border-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.02)] transition-colors ${
                    m.month === selectedMonth ? 'bg-[rgba(34,211,238,0.04)]' : ''
                  }`}
                  onClick={() => setSelectedMonth(m.month)}
                >
                  <td className="px-3 py-2 text-[12px] font-medium text-[#F1F5F9] whitespace-nowrap cursor-pointer">{m.month}</td>
                  <td className="px-3 py-2 text-[12px] font-mono text-right text-[#94A3B8] whitespace-nowrap">{m.trades}</td>
                  <td className="px-3 py-2 text-[12px] font-mono text-right text-[#10B981] whitespace-nowrap">{m.wins}</td>
                  <td className="px-3 py-2 text-[12px] font-mono text-right text-[#EF4444] whitespace-nowrap">{m.losses}</td>
                  <td className="px-3 py-2 text-[12px] font-mono text-right text-[#A78BFA] whitespace-nowrap">{m.winRate.toFixed(1)}%</td>
                  <td className={`px-3 py-2 text-[12px] font-mono text-right font-semibold whitespace-nowrap ${
                    m.netPnl >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
                  }`}>
                    {m.netPnl >= 0 ? '+' : ''}₹{m.netPnl.toLocaleString('en-IN')}
                  </td>
                  <td className="px-3 py-2 text-[12px] font-mono text-right text-[#10B981] whitespace-nowrap">+₹{m.bestTrade.toLocaleString('en-IN')}</td>
                  <td className="px-3 py-2 text-[12px] font-mono text-right text-[#EF4444] whitespace-nowrap">-₹{Math.abs(m.worstTrade).toLocaleString('en-IN')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
