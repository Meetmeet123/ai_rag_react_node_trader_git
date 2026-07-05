import { useState } from 'react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  ReferenceLine,
} from 'recharts';
import { dailyPnl } from './data';
import { WIN_RATE, TOTAL_TRADES, AVG_WIN, AVG_LOSS } from './data';

function formatDate(dateStr: string) {
  const d = new Date(dateStr);
  return `${d.getDate()}/${d.getMonth() + 1}`;
}

const chartData = dailyPnl.map(d => ({
  date: formatDate(d.date),
  fullDate: d.date,
  pnl: d.pnl,
  cumulative: d.cumulative,
}));

const winLossData = [
  { name: 'Wins', value: Math.round(TOTAL_TRADES * WIN_RATE / 100), color: '#10B981' },
  { name: 'Losses', value: Math.round(TOTAL_TRADES * (100 - WIN_RATE) / 100), color: '#EF4444' },
];

interface TooltipPayloadItem {
  value: number;
  dataKey: string;
  color: string;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const item = payload[0];
  const isCumulative = item.dataKey === 'cumulative';
  return (
    <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[6px] px-3 py-2 shadow-lg">
      <p className="text-[11px] text-[#64748B] mb-1">{label}</p>
      <p className="text-[13px] font-mono font-semibold" style={{ color: item.color }}>
        {isCumulative ? 'Cumulative: ' : 'P&L: '}
        {item.value >= 0 ? '+' : ''}₹{item.value.toLocaleString('en-IN')}
      </p>
    </div>
  );
}

export default function PnLChart() {
  const [view, setView] = useState<'cumulative' | 'daily'>('cumulative');

  return (
    <div className="flex gap-4">
      {/* Left: P&L Chart - 65% */}
      <div className="w-[65%] bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-[15px] font-semibold text-[#F1F5F9]">P&L Chart</h3>
          <div className="flex items-center gap-0 bg-[#06060A] rounded-[6px] p-0.5">
            <button
              onClick={() => setView('cumulative')}
              className={`px-3 py-1 rounded-[4px] text-[11px] font-medium transition-all ${
                view === 'cumulative'
                  ? 'bg-[#12121A] text-[#F1F5F9] shadow-sm'
                  : 'text-[#64748B] hover:text-[#94A3B8]'
              }`}
            >
              Cumulative
            </button>
            <button
              onClick={() => setView('daily')}
              className={`px-3 py-1 rounded-[4px] text-[11px] font-medium transition-all ${
                view === 'daily'
                  ? 'bg-[#12121A] text-[#F1F5F9] shadow-sm'
                  : 'text-[#64748B] hover:text-[#94A3B8]'
              }`}
            >
              Daily
            </button>
          </div>
        </div>

        <ResponsiveContainer width="100%" height={280}>
          {view === 'cumulative' ? (
            <AreaChart data={chartData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
              <defs>
                <linearGradient id="cumulativeGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22D3EE" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#22D3EE" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10, fill: '#475569', fontFamily: 'JetBrains Mono' }}
                tickLine={false}
                axisLine={{ stroke: 'rgba(255,255,255,0.06)' }}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={{ fontSize: 10, fill: '#475569', fontFamily: 'JetBrains Mono' }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) => `₹${(v / 1000).toFixed(0)}K`}
              />
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine y={0} stroke="#64748B" strokeDasharray="3 3" strokeOpacity={0.5} />
              <Area
                type="monotone"
                dataKey="cumulative"
                stroke="#22D3EE"
                strokeWidth={2}
                fill="url(#cumulativeGrad)"
                dot={false}
                activeDot={{ r: 4, fill: '#22D3EE', stroke: '#0A0A0F', strokeWidth: 2 }}
              />
            </AreaChart>
          ) : (
            <BarChart data={chartData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10, fill: '#475569', fontFamily: 'JetBrains Mono' }}
                tickLine={false}
                axisLine={{ stroke: 'rgba(255,255,255,0.06)' }}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={{ fontSize: 10, fill: '#475569', fontFamily: 'JetBrains Mono' }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) => `₹${(v / 1000).toFixed(0)}K`}
              />
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine y={0} stroke="#64748B" strokeDasharray="3 3" strokeOpacity={0.5} />
              <Bar
                dataKey="pnl"
                fill="#22D3EE"
                radius={[2, 2, 0, 0]}
                maxBarSize={6}
              >
                {chartData.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={entry.pnl >= 0 ? '#10B981' : '#EF4444'}
                    fillOpacity={0.8}
                  />
                ))}
              </Bar>
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>

      {/* Right: Win/Loss Donut - 35% */}
      <div className="w-[35%] bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-4">
        <h3 className="text-[15px] font-semibold text-[#F1F5F9] mb-4">Win/Loss Distribution</h3>
        <ResponsiveContainer width="100%" height={180}>
          <PieChart>
            <Pie
              data={winLossData}
              cx="50%"
              cy="50%"
              innerRadius={50}
              outerRadius={70}
              paddingAngle={3}
              dataKey="value"
              stroke="#12121A"
              strokeWidth={3}
            >
              {winLossData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <text x="50%" y="45%" textAnchor="middle" dominantBaseline="central" fill="#64748B" fontSize="11" fontFamily="Inter">
              Win Rate
            </text>
            <text x="50%" y="58%" textAnchor="middle" dominantBaseline="central" fill="#F1F5F9" fontSize="18" fontWeight="600" fontFamily="JetBrains Mono">
              {WIN_RATE}%
            </text>
          </PieChart>
        </ResponsiveContainer>

        <div className="flex items-center justify-center gap-6 mt-2">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[#10B981]" />
            <span className="text-[12px] text-[#94A3B8]">Wins: {winLossData[0].value}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[#EF4444]" />
            <span className="text-[12px] text-[#94A3B8]">Losses: {winLossData[1].value}</span>
          </div>
        </div>

        <div className="mt-4 space-y-2 pt-3 border-t border-[rgba(255,255,255,0.06)]">
          <div className="flex justify-between">
            <span className="text-[12px] text-[#94A3B8]">Avg Win</span>
            <span className="text-[12px] font-mono font-medium text-[#10B981]">+₹{AVG_WIN.toLocaleString('en-IN')}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[12px] text-[#94A3B8]">Avg Loss</span>
            <span className="text-[12px] font-mono font-medium text-[#EF4444]">-₹{Math.abs(AVG_LOSS).toLocaleString('en-IN')}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[12px] text-[#94A3B8]">Payoff Ratio</span>
            <span className="text-[12px] font-mono font-medium text-[#F1F5F9]">{(AVG_WIN / Math.abs(AVG_LOSS)).toFixed(2)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
