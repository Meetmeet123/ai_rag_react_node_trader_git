import { useState, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { requestLiveApproval, closeAllPositions } from '@/lib/api';
import { toast } from 'sonner';
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from 'recharts';
import { TrendingDown } from 'lucide-react';
import LiveStatusHeader from './live/LiveStatusHeader';
import SignalFeed from './live/SignalFeed';
import BrokerOrderBook from './live/BrokerOrderBook';
import EmergencyControls from './live/EmergencyControls';
import { generateOHLCData, generateSparklineData } from './dashboard/data';
import { LIVE_STRATEGIES, LIVE_POSITIONS, PNL_SUMMARY } from './live/data';
// OHLCData type used via generateOHLCData return

// Custom candlestick shape for live chart
function LiveCandleShape(props: {
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
  const range = highValue - lowValue || 1;
  const chartHeight = 300;
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
      <line x1={centerX} y1={yHigh} x2={centerX} y2={yLow} stroke={color} strokeWidth={1} />
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

function MiniSparkline({ data, positive }: { data: number[]; positive: boolean }) {
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * 80;
      const y = 20 - ((v - min) / range) * 20;
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <svg width={80} height={20} className="shrink-0">
      <polyline points={points} fill="none" stroke={positive ? '#10B981' : '#EF4444'} strokeWidth={1.5} />
    </svg>
  );
}

export default function LiveTrading() {
  const { user } = useAuth();
  const [selectedStrategy, setSelectedStrategy] = useState(LIVE_STRATEGIES[0]);
  const [showKillConfirm, setShowKillConfirm] = useState(false);
  const [requesting, setRequesting] = useState(false);

  const handleRequestApproval = useCallback(async () => {
    setRequesting(true);
    try {
      const res = await requestLiveApproval();
      toast.success(res.message);
    } catch (err: any) {
      toast.error(err?.message || 'Failed to submit approval request');
    } finally {
      setRequesting(false);
    }
  }, []);

  const isApproved = user?.is_approved_for_live ?? false;

  const chartData = generateOHLCData(60, 22450);
  const priceRange = [Math.min(...chartData.map((d) => d.low)) * 0.999, Math.max(...chartData.map((d) => d.high)) * 1.001];
  const volRange = [0, Math.max(...chartData.map((d) => d.volume)) * 3];

  const handleKillSwitch = useCallback(async () => {
    setShowKillConfirm(false);
    try {
      const result = await closeAllPositions();
      toast.success(result.message || 'Kill switch activated');
    } catch (err: any) {
      toast.error(err?.detail || err?.message || 'Failed to activate kill switch');
    }
  }, []);

  const isProfit = PNL_SUMMARY.total >= 0;

  return (
    <div className="flex flex-col h-full">
      {!isApproved && (
        <div className="bg-amber-900/30 border-b border-amber-700/40 px-4 py-2 flex items-center justify-between">
          <span className="text-sm text-amber-200">
            Live trading requires admin approval. You can view the dashboard, but real-broker orders will be blocked.
          </span>
          <button
            data-testid="request-approval-btn"
            onClick={handleRequestApproval}
            disabled={requesting}
            className="px-3 py-1 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white text-xs font-semibold rounded transition-colors"
          >
            {requesting ? 'Submitting...' : 'Request Approval'}
          </button>
        </div>
      )}

      {/* Section 1: Live Status Bar */}
      <LiveStatusHeader onKillSwitch={() => setShowKillConfirm(true)} />

      {/* Main content area */}
      <div className="flex flex-1 min-h-0">
        {/* Left: Active Strategies (25%) */}
        <div className="w-[25%] min-w-[200px] h-full bg-[#12121A] border-r border-[rgba(255,255,255,0.06)] flex flex-col overflow-hidden">
          {/* Header */}
          <div className="h-10 flex items-center justify-between px-3 border-b border-[rgba(255,255,255,0.06)] shrink-0">
            <span className="text-[15px] font-semibold text-[#F1F5F9]">Live Strategies</span>
            <button className="px-2 py-1 bg-[#22D3EE] text-[#030305] text-[11px] font-semibold rounded-[4px] hover:brightness-110 transition-all">
              + Deploy
            </button>
          </div>

          {/* Strategy cards */}
          <div className="flex-1 overflow-y-auto p-2 space-y-2">
            {LIVE_STRATEGIES.map((strategy) => {
              const stratProfit = strategy.pnl >= 0;
              const isRunning = strategy.status === 'Live';
              const isSelected = selectedStrategy.id === strategy.id;
              const sparkData = generateSparklineData(15);

              return (
                <button
                  key={strategy.id}
                  onClick={() => setSelectedStrategy(strategy)}
                  className={`w-full text-left bg-[#0A0A0F] border rounded-[6px] p-3 transition-all hover:border-[rgba(255,255,255,0.10)] ${
                    isSelected
                      ? 'border-[rgba(34,211,238,0.30)]'
                      : 'border-[rgba(255,255,255,0.06)]'
                  }`}
                  style={{ borderLeft: isSelected ? '3px solid #10B981' : '3px solid rgba(16,185,129,0.30)' }}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[13px] font-semibold text-[#F1F5F9]">{strategy.name}</span>
                    <div className="flex items-center gap-1">
                      <div className={`w-1.5 h-1.5 rounded-full ${isRunning ? 'bg-[#10B981]' : 'bg-[#F59E0B]'}`} />
                      <span className={`text-[10px] ${isRunning ? 'text-[#10B981]' : 'text-[#F59E0B]'}`}>
                        {strategy.status}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-[10px] text-[#64748B]">
                        {strategy.symbol} | {strategy.segment}
                      </span>
                      <div className="flex items-center gap-2 mt-1">
                        <span className={`text-[12px] font-mono font-medium ${stratProfit ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                          {stratProfit ? '+' : ''}₹{strategy.pnl.toLocaleString('en-IN')}
                        </span>
                        <span className="text-[10px] text-[#64748B]">
                          {strategy.positions} positions
                        </span>
                      </div>
                    </div>
                    <MiniSparkline data={sparkData} positive={stratProfit} />
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Center: Chart + Signals (45%) */}
        <div className="w-[45%] h-full bg-[#030305] flex flex-col border-r border-[rgba(255,255,255,0.06)]">
          {/* Chart */}
          <div className="flex-1 min-h-0">
            <div className="h-8 flex items-center justify-between px-3 bg-[#06060A] border-b border-[rgba(255,255,255,0.06)]">
              <span className="text-[12px] font-semibold text-[#F1F5F9]">{selectedStrategy.symbol}</span>
              <span className="text-[10px] text-[#64748B]">{selectedStrategy.name}</span>
            </div>
            <ResponsiveContainer width="100%" height="calc(100% - 32px)">
              <ComposedChart data={chartData} margin={{ top: 10, right: 10, bottom: 10, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#64748B', fontFamily: 'JetBrains Mono' }} tickLine={false} axisLine={{ stroke: 'rgba(255,255,255,0.06)' }} minTickGap={30} />
                <YAxis domain={priceRange} orientation="right" tick={{ fontSize: 10, fill: '#64748B', fontFamily: 'JetBrains Mono' }} tickLine={false} axisLine={false} tickFormatter={(v: number) => `₹${v.toFixed(0)}`} width={60} />
                <ReferenceLine y={22456} stroke="#10B981" strokeDasharray="4 4" strokeOpacity={0.5} />
                <Bar dataKey="volume" yAxisId="vol" barSize={2}>
                  {chartData.map((entry, i) => (
                    <Cell key={`v-${i}`} fill={entry.close >= entry.open ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'} />
                  ))}
                </Bar>
                <Bar dataKey="close" barSize={3} shape={(props: any) => <LiveCandleShape {...props} lowValue={priceRange[0]} highValue={priceRange[1]} />}>
                  {chartData.map((_e, i) => (
                    <Cell key={`c-${i}`} fill="transparent" />
                  ))}
                </Bar>
                <Line type="monotone" dataKey="sma20" stroke="#22D3EE" strokeWidth={1.5} dot={false} connectNulls />
                <YAxis yAxisId="vol" orientation="left" domain={volRange} hide />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* Signal Feed */}
          <div className="h-[200px] shrink-0 border-t border-[rgba(255,255,255,0.06)]">
            <SignalFeed />
          </div>
        </div>

        {/* Right: P&L + Quick Order + Positions (30%) */}
        <div className="w-[30%] min-w-[220px] h-full bg-[#12121A] flex flex-col overflow-hidden">
          {/* Live P&L Card */}
          <div className="m-3 p-4 bg-[#0A0A0F] border border-[rgba(255,255,255,0.06)] rounded-[8px]">
            <span className="text-[11px] text-[#64748B] block mb-1">Live P&L</span>
            <span className={`text-[24px] font-mono font-semibold ${isProfit ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
              {isProfit ? '+' : ''}₹{PNL_SUMMARY.total.toLocaleString('en-IN')}
            </span>
            <div className="flex items-center gap-4 mt-2">
              <div>
                <span className="text-[10px] text-[#64748B] block">Realized</span>
                <span className="text-[12px] font-mono text-[#10B981]">+₹{PNL_SUMMARY.realized.toLocaleString('en-IN')}</span>
              </div>
              <div>
                <span className="text-[10px] text-[#64748B] block">Unrealized</span>
                <span className="text-[12px] font-mono text-[#F59E0B]">+₹{PNL_SUMMARY.unrealized.toLocaleString('en-IN')}</span>
              </div>
              <div>
                <span className="text-[10px] text-[#64748B] block">Change</span>
                <span className={`text-[12px] font-mono ${isProfit ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                  {isProfit ? '+' : ''}{PNL_SUMMARY.changePercent}%
                </span>
              </div>
            </div>
          </div>

          {/* Open Positions */}
          <div className="flex-1 overflow-y-auto px-3">
            <span className="text-[15px] font-semibold text-[#F1F5F9] block mb-2">Open Positions</span>
            <div className="space-y-2">
              {LIVE_POSITIONS.map((pos) => {
                const posProfit = pos.pnl >= 0;
                return (
                  <div key={pos.id} className="flex items-center justify-between py-2 px-2 bg-[#0A0A0F] border border-[rgba(255,255,255,0.06)] rounded-[4px]">
                    <div>
                      <span className="text-[12px] font-semibold text-[#F1F5F9]">{pos.symbol}</span>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[11px] font-mono text-[#94A3B8]">
                          {pos.qty > 0 ? '+' : ''}{pos.qty} | Avg ₹{pos.avgPrice.toLocaleString('en-IN')}
                        </span>
                      </div>
                    </div>
                    <div className="text-right">
                      <span className={`text-[12px] font-mono font-medium ${posProfit ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                        {posProfit ? '+' : ''}₹{pos.pnl.toLocaleString('en-IN')}
                      </span>
                      <span className="text-[10px] text-[#64748B] block">LTP ₹{pos.ltp.toLocaleString('en-IN')}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Quick Actions */}
          <div className="p-3 border-t border-[rgba(255,255,255,0.06)] shrink-0">
            <div className="flex gap-2">
              <button className="flex-1 h-9 bg-[#10B981] text-white text-[12px] font-bold rounded-[4px] hover:brightness-110 transition-all active:scale-[0.98]">
                BUY
              </button>
              <button className="flex-1 h-9 bg-[#EF4444] text-white text-[12px] font-bold rounded-[4px] hover:brightness-110 transition-all active:scale-[0.98]">
                SELL
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom: Order Book */}
      <div className="h-[240px] shrink-0">
        <BrokerOrderBook />
      </div>

      {/* Emergency Controls Bar */}
      <EmergencyControls onKillSwitch={handleKillSwitch} />

      {/* Kill Switch Confirmation overlay (managed by EmergencyControls) */}
      {showKillConfirm && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center">
          <div className="absolute inset-0 bg-[rgba(0,0,0,0.60)] backdrop-blur-sm" onClick={() => setShowKillConfirm(false)} />
          <div className="relative bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[12px] p-6 shadow-[0_24px_48px_rgba(0,0,0,0.40)] max-w-[400px] w-full mx-4">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-[rgba(239,68,68,0.15)] flex items-center justify-center">
                <TrendingDown size={20} className="text-[#EF4444]" />
              </div>
              <div>
                <h3 className="text-[16px] font-semibold text-[#F1F5F9]">Kill Switch</h3>
                <p className="text-[12px] text-[#94A3B8]">This action cannot be undone</p>
              </div>
            </div>
            <p className="text-[13px] text-[#94A3B8] mb-4">This will immediately close all positions, stop all strategies, and cancel all pending orders.</p>
            <div className="flex gap-3">
              <button onClick={() => setShowKillConfirm(false)} className="flex-1 h-10 rounded-[4px] border border-[rgba(255,255,255,0.06)] text-[#94A3B8] text-[13px] font-medium hover:bg-[#1A1A25]">Cancel</button>
              <button onClick={handleKillSwitch} className="flex-1 h-10 rounded-[4px] bg-[#EF4444] text-white text-[13px] font-bold hover:brightness-110 active:scale-[0.98]">Confirm</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
