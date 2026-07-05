import { useState } from 'react';
import { recentSignals } from './data';

// Mock candlestick data for the chart
const candleData = [
  { o: 2852, h: 2861, l: 2848, c: 2858 },
  { o: 2858, h: 2865, l: 2855, c: 2862 },
  { o: 2862, h: 2870, l: 2860, c: 2868 },
  { o: 2868, h: 2875, l: 2865, c: 2872 },
  { o: 2872, h: 2878, l: 2869, c: 2875 },
  { o: 2875, h: 2882, l: 2873, c: 2880 },
  { o: 2880, h: 2886, l: 2878, c: 2884 },
  { o: 2884, h: 2890, l: 2882, c: 2888 },
  { o: 2888, h: 2893, l: 2886, c: 2891 },
  { o: 2891, h: 2895, l: 2889, c: 2893 },
  { o: 2893, h: 2898, l: 2891, c: 2896 },
  { o: 2896, h: 2900, l: 2894, c: 2898 },
  { o: 2898, h: 2902, l: 2896, c: 2900 },
  { o: 2900, h: 2905, l: 2898, c: 2903 },
  { o: 2903, h: 2908, l: 2901, c: 2906 },
  { o: 2906, h: 2910, l: 2904, c: 2908 },
  { o: 2908, h: 2912, l: 2906, c: 2910 },
  { o: 2910, h: 2915, l: 2908, c: 2913 },
  { o: 2913, h: 2918, l: 2911, c: 2916 },
  { o: 2916, h: 2920, l: 2914, c: 2918 },
];

function CandlestickChart() {
  const width = 600;
  const height = 220;
  const padding = { top: 10, right: 10, bottom: 20, left: 50 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  const allPrices = candleData.flatMap(d => [d.h, d.l]);
  const minPrice = Math.min(...allPrices) - 5;
  const maxPrice = Math.max(...allPrices) + 5;
  const priceRange = maxPrice - minPrice;

  const xScale = (i: number) => padding.left + (i / (candleData.length - 1)) * chartW;
  const yScale = (p: number) => padding.top + chartH - ((p - minPrice) / priceRange) * chartH;

  const candleWidth = Math.max(4, (chartW / candleData.length) * 0.6);

  // Signal positions (indices)
  const buySignals = [3, 7, 12, 16];
  const sellSignals = [5, 9, 14, 18];

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full" preserveAspectRatio="none">
      {/* Grid lines */}
      {[0, 0.25, 0.5, 0.75, 1].map(t => {
        const y = padding.top + t * chartH;
        const price = Math.round(maxPrice - t * priceRange);
        return (
          <g key={t}>
            <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} stroke="rgba(255,255,255,0.04)" strokeWidth="0.5" />
            <text x={padding.left - 5} y={y + 3} textAnchor="end" fill="#475569" fontSize="8" fontFamily="JetBrains Mono">{price}</text>
          </g>
        );
      })}

      {/* Candlesticks */}
      {candleData.map((d, i) => {
        const x = xScale(i);
        const yOpen = yScale(d.o);
        const yHigh = yScale(d.h);
        const yLow = yScale(d.l);
        const yClose = yScale(d.c);
        const isGreen = d.c >= d.o;
        const color = isGreen ? '#10B981' : '#EF4444';
        const bodyTop = Math.min(yOpen, yClose);
        const bodyHeight = Math.max(Math.abs(yOpen - yClose), 1);

        return (
          <g key={i}>
            <line x1={x} y1={yHigh} x2={x} y2={yLow} stroke={color} strokeWidth="0.8" />
            <rect
              x={x - candleWidth / 2}
              y={bodyTop}
              width={candleWidth}
              height={bodyHeight}
              fill={isGreen ? color : color}
              opacity={0.85}
              rx="0.5"
            />
          </g>
        );
      })}

      {/* Signal markers - Buy triangles */}
      {buySignals.map(idx => {
        const x = xScale(idx);
        const y = yScale(candleData[idx].l) + 8;
        return (
          <g key={`buy-${idx}`}>
            <polygon
              points={`${x},${y - 6} ${x - 4},${y + 2} ${x + 4},${y + 2}`}
              fill="#10B981"
              opacity="0.9"
            />
          </g>
        );
      })}

      {/* Signal markers - Sell triangles */}
      {sellSignals.map(idx => {
        const x = xScale(idx);
        const y = yScale(candleData[idx].h) - 8;
        return (
          <g key={`sell-${idx}`}>
            <polygon
              points={`${x},${y + 6} ${x - 4},${y - 2} ${x + 4},${y - 2}`}
              fill="#EF4444"
              opacity="0.9"
            />
          </g>
        );
      })}
    </svg>
  );
}

export default function ChartSignalsArea() {
  const [hoveredSignal, setHoveredSignal] = useState<string | null>(null);

  return (
    <div className="flex-1 flex flex-col bg-[#030305] min-h-0">
      {/* Chart Area */}
      <div className="flex-1 min-h-0 relative p-3">
        <div className="absolute top-3 left-3 flex items-center gap-2 z-10">
          <span className="text-[11px] font-mono text-[#F1F5F9] font-semibold">RELIANCE</span>
          <span className="text-[10px] text-[#64748B]">NSE</span>
          <span className="text-[11px] font-mono text-[#10B981]">2,891.75</span>
          <span className="text-[10px] font-mono text-[#10B981]">+0.44%</span>
        </div>
        <div className="w-full h-full">
          <CandlestickChart />
        </div>
      </div>

      {/* Recent Signals */}
      <div className="h-[140px] bg-[#12121A] border-t border-[rgba(255,255,255,0.06)] flex flex-col">
        <div className="h-8 flex items-center justify-between px-4 border-b border-[rgba(255,255,255,0.06)]">
          <span className="text-[13px] font-semibold text-[#F1F5F9]">Recent Signals</span>
          <button className="text-[11px] text-[#22D3EE] hover:brightness-110 transition-all">View All</button>
        </div>
        <div className="flex-1 overflow-auto">
          <table className="w-full">
            <thead className="sticky top-0 bg-[#06060A]">
              <tr>
                <th className="text-left px-3 py-1.5 text-[10px] font-medium text-[#64748B]">Time</th>
                <th className="text-left px-3 py-1.5 text-[10px] font-medium text-[#64748B]">Strategy</th>
                <th className="text-left px-3 py-1.5 text-[10px] font-medium text-[#64748B]">Symbol</th>
                <th className="text-center px-3 py-1.5 text-[10px] font-medium text-[#64748B]">Signal</th>
                <th className="text-right px-3 py-1.5 text-[10px] font-medium text-[#64748B]">Price</th>
                <th className="text-right px-3 py-1.5 text-[10px] font-medium text-[#64748B]">P&L</th>
              </tr>
            </thead>
            <tbody>
              {recentSignals.map((sig) => (
                <tr
                  key={sig.id}
                  className="border-b border-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.02)] transition-colors"
                  onMouseEnter={() => setHoveredSignal(sig.id)}
                  onMouseLeave={() => setHoveredSignal(null)}
                  style={{
                    backgroundColor: hoveredSignal === sig.id ? 'rgba(255,255,255,0.02)' : undefined,
                  }}
                >
                  <td className="px-3 py-1 text-[11px] font-mono text-[#94A3B8] whitespace-nowrap">{sig.time}</td>
                  <td className="px-3 py-1 text-[11px] text-[#F1F5F9] whitespace-nowrap">{sig.strategy}</td>
                  <td className="px-3 py-1 text-[11px] font-mono text-[#F1F5F9] whitespace-nowrap">{sig.symbol}</td>
                  <td className="px-3 py-1 text-center whitespace-nowrap">
                    <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-[4px] text-[10px] font-semibold ${
                      (sig.type === 'LONG' && sig.signal === 'ENTRY') || (sig.type === 'SHORT' && sig.signal === 'EXIT')
                        ? 'text-[#10B981] bg-[rgba(16,185,129,0.15)]'
                        : 'text-[#EF4444] bg-[rgba(239,68,68,0.15)]'
                    }`}>
                      {(sig.type === 'LONG' && sig.signal === 'ENTRY') || (sig.type === 'SHORT' && sig.signal === 'EXIT') ? '▲' : '▼'}
                      {(sig.type === 'LONG' && sig.signal === 'ENTRY') || (sig.type === 'SHORT' && sig.signal === 'EXIT') ? 'BUY' : 'SELL'}
                    </span>
                  </td>
                  <td className="px-3 py-1 text-[11px] font-mono text-right text-[#F1F5F9] whitespace-nowrap">{sig.price.toFixed(2)}</td>
                  <td className={`px-3 py-1 text-[11px] font-mono text-right font-medium whitespace-nowrap ${
                    sig.pnl === null ? 'text-[#64748B]' : sig.pnl >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
                  }`}>
                    {sig.pnl === null ? '—' : `${sig.pnl >= 0 ? '+' : ''}₹${sig.pnl.toLocaleString('en-IN')}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
