import { useMemo } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { drawdownData, MAX_DRAWDOWN } from './data';

function formatDate(dateStr: string) {
  const d = new Date(dateStr);
  return `${d.getDate()}/${d.getMonth() + 1}`;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[6px] px-3 py-2 shadow-lg">
      <p className="text-[11px] text-[#64748B] mb-1">{label}</p>
      <p className="text-[13px] font-mono font-semibold text-[#EF4444]">
        Drawdown: ₹{payload[0].value.toLocaleString('en-IN')}
      </p>
    </div>
  );
}

export default function DrawdownAnalysis() {
  const chartData = useMemo(() =>
    drawdownData.map(d => ({
      date: formatDate(d.date),
      drawdown: d.drawdown,
    })),
    []
  );

  const maxDrawdownValue = useMemo(() =>
    Math.min(...drawdownData.map(d => d.drawdown)),
    []
  );

  const maxDrawdownDate = useMemo(() => {
    const idx = drawdownData.findIndex(d => d.drawdown === maxDrawdownValue);
    return idx >= 0 ? formatDate(drawdownData[idx].date) : '';
  }, [maxDrawdownValue]);

  return (
    <div className="space-y-4">
      {/* Chart */}
      <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-[15px] font-semibold text-[#F1F5F9]">Drawdown Analysis</h3>
          <span className="text-[11px] text-[#64748B]">Underwater Equity</span>
        </div>
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={chartData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
            <defs>
              <linearGradient id="drawdownGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#EF4444" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#EF4444" stopOpacity={0.02} />
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
            <ReferenceLine
              y={maxDrawdownValue}
              stroke="#EF4444"
              strokeDasharray="5 5"
              strokeOpacity={0.7}
              label={{
                value: `Max DD: ₹${maxDrawdownValue.toLocaleString('en-IN')} (${maxDrawdownDate})`,
                position: 'insideBottomRight',
                fill: '#EF4444',
                fontSize: 10,
                fontFamily: 'JetBrains Mono',
              }}
            />
            <Area
              type="monotone"
              dataKey="drawdown"
              stroke="#EF4444"
              strokeWidth={1.5}
              fill="url(#drawdownGrad)"
              dot={false}
              activeDot={{ r: 4, fill: '#EF4444', stroke: '#0A0A0F', strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-4">
          <span className="text-[11px] text-[#64748B] font-medium">Max Drawdown</span>
          <div className="text-[20px] font-mono font-semibold text-[#EF4444] mt-1">
            ₹{Math.abs(MAX_DRAWDOWN).toLocaleString('en-IN')}
          </div>
        </div>
        <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-4">
          <span className="text-[11px] text-[#64748B] font-medium">Max Drawdown %</span>
          <div className="text-[20px] font-mono font-semibold text-[#EF4444] mt-1">
            -3.2%
          </div>
        </div>
        <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-4">
          <span className="text-[11px] text-[#64748B] font-medium">Recovery Days</span>
          <div className="text-[20px] font-mono font-semibold text-[#F1F5F9] mt-1">
            5
          </div>
        </div>
        <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-4">
          <span className="text-[11px] text-[#64748B] font-medium">Current Drawdown</span>
          <div className="text-[20px] font-mono font-semibold text-[#F59E0B] mt-1">
            -₹2,100
          </div>
        </div>
      </div>
    </div>
  );
}
