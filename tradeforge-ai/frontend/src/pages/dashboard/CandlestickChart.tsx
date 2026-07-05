import { useState, useMemo } from 'react';
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { Maximize2, Settings, Plus, Minus, RotateCcw } from 'lucide-react';
import { generateOHLCData, TIMEFRAMES } from './data';
import type { Timeframe } from './data';

interface CandlestickChartProps {
  symbol: string;
}

interface TooltipPayloadItem {
  payload: {
    time: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    sma20?: number;
    ema50?: number;
    bbUpper?: number;
    bbLower?: number;
  };
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
}) {
  if (!active || !payload || !payload.length) return null;
  const d = payload[0].payload;
  const isGreen = d.close >= d.open;

  return (
    <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[6px] p-3 shadow-[0_8px_24px_rgba(0,0,0,0.40)]">
      <div className="text-[11px] font-mono text-[#64748B] mb-1.5">{d.time}</div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
        <span className="text-[11px] text-[#94A3B8]">Open</span>
        <span className="text-[11px] font-mono text-[#F1F5F9]">₹{d.open.toFixed(2)}</span>
        <span className="text-[11px] text-[#94A3B8]">High</span>
        <span className="text-[11px] font-mono text-[#F1F5F9]">₹{d.high.toFixed(2)}</span>
        <span className="text-[11px] text-[#94A3B8]">Low</span>
        <span className="text-[11px] font-mono text-[#F1F5F9]">₹{d.low.toFixed(2)}</span>
        <span className="text-[11px] text-[#94A3B8]">Close</span>
        <span className={`text-[11px] font-mono ${isGreen ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
          ₹{d.close.toFixed(2)}
        </span>
        <span className="text-[11px] text-[#94A3B8]">Vol</span>
        <span className="text-[11px] font-mono text-[#F1F5F9]">{(d.volume / 1000).toFixed(0)}K</span>
      </div>
      {d.sma20 && (
        <div className="mt-1.5 pt-1.5 border-t border-[rgba(255,255,255,0.06)]">
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-[#22D3EE]">SMA20: ₹{d.sma20.toFixed(2)}</span>
            {d.ema50 && <span className="text-[10px] text-[#A78BFA]">EMA50: ₹{d.ema50.toFixed(2)}</span>}
          </div>
        </div>
      )}
    </div>
  );
}

// Custom candlestick shape renderer
function CandlestickShape(props: {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  payload?: { open: number; high: number; low: number; close: number };
  lowValue?: number;
  highValue?: number;
}) {
  const { x = 0, y = 0, width = 0, payload, lowValue = 0, highValue = 1 } = props;
  if (!payload) return null;

  const { open, high, low, close } = payload;
  const isGreen = close >= open;
  const color = isGreen ? '#10B981' : '#EF4444';

  // Calculate positions
  const range = highValue - lowValue || 1;
  const chartHeight = 400; // approximate chart area height
  const scale = chartHeight / range;

  const h = (props as any).height || 0;
  const yHigh = y + h / 2 - (high - lowValue) * scale;
  const yLow = y + h / 2 - (low - lowValue) * scale;
  const yOpen = y + h / 2 - (open - lowValue) * scale;
  const yClose = y + h / 2 - (close - lowValue) * scale;

  const bodyTop = Math.min(yOpen, yClose);
  const bodyBottom = Math.max(yOpen, yClose);
  const bodyHeight = Math.max(bodyBottom - bodyTop, 1);
  const centerX = x + width / 2;

  return (
    <g>
      {/* Wick */}
      <line
        x1={centerX}
        y1={yHigh}
        x2={centerX}
        y2={yLow}
        stroke={color}
        strokeWidth={1}
      />
      {/* Body */}
      <rect
        x={x + 1}
        y={bodyTop}
        width={Math.max(width - 2, 2)}
        height={bodyHeight}
        fill={isGreen ? '#10B981' : '#EF4444'}
        rx={1}
      />
    </g>
  );
}

export default function CandlestickChart({ symbol }: CandlestickChartProps) {
  const [timeframe, setTimeframe] = useState<Timeframe>('15m');
  const [showSMA, setShowSMA] = useState(true);
  const [showEMA, setShowEMA] = useState(true);
  const [showBB, setShowBB] = useState(true);

  const data = useMemo(() => generateOHLCData(100, 2500), [symbol]);

  const priceRange = useMemo(() => {
    const highs = data.map((d) => d.high);
    const lows = data.map((d) => d.low);
    const min = Math.min(...lows);
    const max = Math.max(...highs);
    const padding = (max - min) * 0.1;
    return [min - padding, max + padding];
  }, [data]);

  const volRange = useMemo(() => {
    const max = Math.max(...data.map((d) => d.volume));
    return [0, max * 3];
  }, [data]);

  return (
    <div className="flex flex-col h-full bg-[#030305]">
      {/* Chart Toolbar */}
      <div className="h-9 flex items-center justify-between px-3 bg-[#06060A] border-b border-[rgba(255,255,255,0.06)] shrink-0">
        <div className="flex items-center gap-2">
          {/* Symbol */}
          <span className="text-[13px] font-semibold text-[#F1F5F9]">{symbol}</span>
          <span className="text-[10px] text-[#64748B]">NSE</span>

          {/* Timeframe selector */}
          <div className="flex items-center gap-0.5 ml-3 bg-[#06060A] rounded-[4px]">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={`h-6 px-2 text-[11px] font-medium rounded-[4px] transition-all ${
                  timeframe === tf
                    ? 'bg-[#12121A] text-[#F1F5F9] shadow'
                    : 'text-[#64748B] hover:text-[#94A3B8]'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-1">
          {/* Indicator toggles */}
          <button
            onClick={() => setShowSMA(!showSMA)}
            className={`h-6 px-2 text-[10px] font-medium rounded-[4px] transition-all ${
              showSMA ? 'bg-[rgba(34,211,238,0.12)] text-[#22D3EE]' : 'text-[#64748B] hover:text-[#94A3B8]'
            }`}
          >
            SMA
          </button>
          <button
            onClick={() => setShowEMA(!showEMA)}
            className={`h-6 px-2 text-[10px] font-medium rounded-[4px] transition-all ${
              showEMA ? 'bg-[rgba(167,139,250,0.12)] text-[#A78BFA]' : 'text-[#64748B] hover:text-[#94A3B8]'
            }`}
          >
            EMA
          </button>
          <button
            onClick={() => setShowBB(!showBB)}
            className={`h-6 px-2 text-[10px] font-medium rounded-[4px] transition-all ${
              showBB ? 'bg-[rgba(148,163,184,0.12)] text-[#94A3B8]' : 'text-[#64748B] hover:text-[#94A3B8]'
            }`}
          >
            BB
          </button>

          <div className="w-px h-4 bg-[rgba(255,255,255,0.06)] mx-1" />

          <button className="w-6 h-6 flex items-center justify-center rounded-[4px] text-[#64748B] hover:text-[#F1F5F9] hover:bg-[#12121A] transition-all">
            <Settings size={13} />
          </button>
          <button className="w-6 h-6 flex items-center justify-center rounded-[4px] text-[#64748B] hover:text-[#F1F5F9] hover:bg-[#12121A] transition-all">
            <Maximize2 size={13} />
          </button>
        </div>
      </div>

      {/* Chart Area */}
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 10, right: 10, bottom: 10, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis
              dataKey="time"
              tick={{ fontSize: 10, fill: '#64748B', fontFamily: 'JetBrains Mono' }}
              tickLine={false}
              axisLine={{ stroke: 'rgba(255,255,255,0.06)' }}
              minTickGap={30}
            />
            <YAxis
              domain={priceRange}
              orientation="right"
              tick={{ fontSize: 10, fill: '#64748B', fontFamily: 'JetBrains Mono' }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: number) => `₹${v.toFixed(0)}`}
              width={60}
            />
            <Tooltip content={<CustomTooltip />} />

            {/* Volume bars at bottom */}
            <Bar
              dataKey="volume"
              yAxisId="vol"
              fill="rgba(255,255,255,0.1)"
              barSize={data.length > 50 ? 2 : 4}
            >
              {data.map((entry, index) => (
                <Cell
                  key={`vol-${index}`}
                  fill={entry.close >= entry.open ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}
                />
              ))}
            </Bar>

            {/* Candlesticks as bars */}
            <Bar
              dataKey="close"
              barSize={data.length > 50 ? 3 : 6}
              shape={(props: any) => (
                <CandlestickShape
                  {...props}
                  lowValue={priceRange[0]}
                  highValue={priceRange[1]}
                />
              )}
            >
              {data.map((_entry, index) => (
                <Cell key={`candle-${index}`} fill="transparent" />
              ))}
            </Bar>

            {/* SMA 20 */}
            {showSMA && (
              <Line
                type="monotone"
                dataKey="sma20"
                stroke="#22D3EE"
                strokeWidth={1.5}
                dot={false}
                connectNulls
              />
            )}

            {/* EMA 50 */}
            {showEMA && (
              <Line
                type="monotone"
                dataKey="ema50"
                stroke="#A78BFA"
                strokeWidth={1.5}
                dot={false}
                connectNulls
              />
            )}

            {/* Bollinger Bands */}
            {showBB && (
              <>
                <Line
                  type="monotone"
                  dataKey="bbUpper"
                  stroke="#64748B"
                  strokeWidth={1}
                  strokeDasharray="4 4"
                  dot={false}
                  connectNulls
                />
                <Line
                  type="monotone"
                  dataKey="bbLower"
                  stroke="#64748B"
                  strokeWidth={1}
                  strokeDasharray="4 4"
                  dot={false}
                  connectNulls
                />
              </>
            )}

            <YAxis yAxisId="vol" orientation="left" domain={volRange} hide />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="h-7 flex items-center gap-4 px-3 bg-[#06060A] border-t border-[rgba(255,255,255,0.06)] shrink-0">
        {showSMA && (
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-0.5 bg-[#22D3EE]" />
            <span className="text-[10px] text-[#94A3B8]">SMA 20</span>
          </div>
        )}
        {showEMA && (
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-0.5 bg-[#A78BFA]" />
            <span className="text-[10px] text-[#94A3B8]">EMA 50</span>
          </div>
        )}
        {showBB && (
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-0.5 bg-[#64748B] border-dashed" style={{ borderTop: '1px dashed #64748B', height: 0 }} />
            <span className="text-[10px] text-[#94A3B8]">Bollinger</span>
          </div>
        )}
        <div className="flex items-center gap-1.5 ml-auto">
          <button className="w-5 h-5 flex items-center justify-center rounded-[3px] text-[#64748B] hover:text-[#F1F5F9] hover:bg-[#12121A]">
            <Plus size={10} />
          </button>
          <button className="w-5 h-5 flex items-center justify-center rounded-[3px] text-[#64748B] hover:text-[#F1F5F9] hover:bg-[#12121A]">
            <Minus size={10} />
          </button>
          <button className="w-5 h-5 flex items-center justify-center rounded-[3px] text-[#64748B] hover:text-[#F1F5F9] hover:bg-[#12121A]">
            <RotateCcw size={10} />
          </button>
        </div>
      </div>
    </div>
  );
}
