import { useState } from 'react';
import { Shield, X, RotateCcw, Wifi, WifiOff } from 'lucide-react';

interface CapitalMetrics {
  portfolio_value: number;
  used_margin: number;
  available_balance: number;
  pnl_today: number;
  total_unrealized_pnl: number;
}

interface VirtualCapitalHeaderProps {
  metrics: CapitalMetrics;
  socketConnected?: boolean;
}

export default function VirtualCapitalHeader({ metrics, socketConnected }: VirtualCapitalHeaderProps) {
  const [visible, setVisible] = useState(true);

  const overallPnl = metrics.total_unrealized_pnl + metrics.pnl_today;

  if (!visible) return null;

  return (
    <div className="w-full">
      {/* Paper Trading Banner */}
      <div className="w-full h-10 flex items-center justify-center px-4 gap-3 border-b border-[rgba(245,158,11,0.20)] animate-[slideDown_300ms_ease-out]"
        style={{ background: 'rgba(245,158,11,0.12)' }}>
        <Shield size={16} className="text-[#F59E0B] shrink-0" />
        <span className="text-[13px] font-medium text-[#F59E0B]">
          PAPER TRADING MODE — All trades are simulated with virtual capital. No real money at risk.
        </span>
        <span className="text-[13px] font-mono font-semibold text-[#F59E0B] ml-4">
          Virtual Balance: ₹{metrics.portfolio_value.toLocaleString('en-IN')}
        </span>
        <div className="ml-auto flex items-center gap-3">
          {socketConnected !== undefined && (
            <span className="flex items-center gap-1 text-[11px] text-[#64748B]" title={socketConnected ? 'Live updates connected' : 'Live updates disconnected'}>
              {socketConnected ? <Wifi size={12} className="text-[#10B981]" /> : <WifiOff size={12} className="text-[#EF4444]" />}
              {socketConnected ? 'Live' : 'Offline'}
            </span>
          )}
          <button
            onClick={() => setVisible(false)}
            className="text-[#F59E0B] opacity-60 hover:opacity-100 transition-opacity"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Capital Summary Bar */}
      <div className="w-full flex items-center gap-6 px-5 py-3 bg-[#12121A] border-b border-[rgba(255,255,255,0.06)]">
        <div className="flex items-center gap-2">
          <span className="text-[12px] text-[#64748B] font-medium">Virtual Capital</span>
          <span className="text-[18px] font-mono font-semibold text-[#F1F5F9]">
            ₹{metrics.portfolio_value.toLocaleString('en-IN')}
          </span>
        </div>

        <div className="w-px h-6 bg-[rgba(255,255,255,0.06)]" />

        <div className="flex items-center gap-2">
          <span className="text-[12px] text-[#64748B] font-medium">Available</span>
          <span className="text-[15px] font-mono font-medium text-[#10B981]">
            ₹{metrics.available_balance.toLocaleString('en-IN')}
          </span>
        </div>

        <div className="w-px h-6 bg-[rgba(255,255,255,0.06)]" />

        <div className="flex items-center gap-2">
          <span className="text-[12px] text-[#64748B] font-medium">Used Margin</span>
          <span className="text-[15px] font-mono font-medium text-[#F1F5F9]">
            ₹{metrics.used_margin.toLocaleString('en-IN')}
          </span>
        </div>

        <div className="w-px h-6 bg-[rgba(255,255,255,0.06)]" />

        <div className="flex items-center gap-2">
          <span className="text-[12px] text-[#64748B] font-medium">Today&apos;s P&amp;L</span>
          <span className={`text-[15px] font-mono font-semibold ${metrics.pnl_today >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
            {metrics.pnl_today >= 0 ? '+' : ''}₹{metrics.pnl_today.toLocaleString('en-IN')}
          </span>
        </div>

        <div className="w-px h-6 bg-[rgba(255,255,255,0.06)]" />

        <div className="flex items-center gap-2">
          <span className="text-[12px] text-[#64748B] font-medium">Overall P&amp;L</span>
          <span className={`text-[15px] font-mono font-semibold ${overallPnl >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
            {overallPnl >= 0 ? '+' : ''}₹{overallPnl.toLocaleString('en-IN')}
          </span>
        </div>

        <div className="ml-auto">
          <button className="flex items-center gap-1.5 px-3 py-1.5 border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] font-medium text-[#94A3B8] hover:bg-[#1A1A25] hover:text-[#F1F5F9] transition-all">
            <RotateCcw size={12} />
            Reset to ₹10L
          </button>
        </div>
      </div>
    </div>
  );
}
