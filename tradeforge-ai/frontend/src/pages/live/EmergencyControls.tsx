import { useState } from 'react';
import { AlertTriangle, Pause, Power, X } from 'lucide-react';
import { LIVE_STRATEGIES, PNL_SUMMARY, LIVE_POSITIONS } from './data';

interface EmergencyControlsProps {
  onKillSwitch: () => void;
}

export default function EmergencyControls({ onKillSwitch }: EmergencyControlsProps) {
  const [showKillConfirm, setShowKillConfirm] = useState(false);
  const [allPaused, setAllPaused] = useState(false);
  const [maxDailyLoss, setMaxDailyLoss] = useState(50000);

  const activeStrategies = LIVE_STRATEGIES.filter((s) => s.status === 'Live').length;
  const totalPnl = PNL_SUMMARY.total;
  const isProfit = totalPnl >= 0;

  return (
    <div className="w-full bg-[#0A0A0F] border-t border-[rgba(255,255,255,0.06)] p-3">
      <div className="flex items-center gap-4 flex-wrap">
        {/* P&L Summary */}
        <div className="flex items-center gap-4 mr-auto">
          <div>
            <span className="text-[10px] text-[#64748B] block">Today's P&L</span>
            <span
              className={`text-[18px] font-mono font-semibold ${
                isProfit ? 'text-[#10B981]' : 'text-[#EF4444]'
              }`}
            >
              {isProfit ? '+' : ''}₹{totalPnl.toLocaleString('en-IN')}
            </span>
          </div>
          <div className="w-px h-8 bg-[rgba(255,255,255,0.06)]" />
          <div>
            <span className="text-[10px] text-[#64748B] block">Realized</span>
            <span className="text-[13px] font-mono text-[#10B981]">
              +₹{PNL_SUMMARY.realized.toLocaleString('en-IN')}
            </span>
          </div>
          <div>
            <span className="text-[10px] text-[#64748B] block">Unrealized</span>
            <span className="text-[13px] font-mono text-[#F59E0B]">
              +₹{PNL_SUMMARY.unrealized.toLocaleString('en-IN')}
            </span>
          </div>
          <div>
            <span className="text-[10px] text-[#64748B] block">Change</span>
            <span className={`text-[13px] font-mono ${isProfit ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
              {isProfit ? '+' : ''}
              {PNL_SUMMARY.changePercent}%
            </span>
          </div>
          <div className="w-px h-8 bg-[rgba(255,255,255,0.06)]" />
          <div>
            <span className="text-[10px] text-[#64748B] block">Active Strategies</span>
            <span className="text-[13px] font-mono text-[#22D3EE]">{activeStrategies}</span>
          </div>
          <div>
            <span className="text-[10px] text-[#64748B] block">Open Positions</span>
            <span className="text-[13px] font-mono text-[#F1F5F9]">{LIVE_POSITIONS.length}</span>
          </div>
        </div>

        {/* Max Daily Loss */}
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-[#64748B]">Max Daily Loss</span>
          <input
            type="number"
            value={maxDailyLoss}
            onChange={(e) => setMaxDailyLoss(Number(e.target.value))}
            className="w-20 h-7 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[4px] px-2 text-[12px] font-mono text-[#F1F5F9] focus:outline-none focus:border-[#22D3EE]"
          />
        </div>

        {/* Pause All */}
        <button
          onClick={() => setAllPaused(!allPaused)}
          className={`flex items-center gap-1.5 px-3 py-2 rounded-[4px] text-[12px] font-semibold transition-all active:scale-[0.98] ${
            allPaused
              ? 'bg-[rgba(16,185,129,0.15)] text-[#10B981] hover:bg-[rgba(16,185,129,0.25)]'
              : 'bg-[rgba(245,158,11,0.15)] text-[#F59E0B] hover:bg-[rgba(245,158,11,0.25)]'
          }`}
        >
          <Pause size={14} />
          {allPaused ? 'Resume All' : 'Pause All'}
        </button>

        {/* Kill Switch */}
        <button
          onClick={() => setShowKillConfirm(true)}
          className="flex items-center gap-1.5 px-4 py-2 bg-[#EF4444] text-white rounded-[4px] text-[12px] font-bold hover:brightness-110 transition-all active:scale-[0.98] shadow-[0_0_20px_rgba(239,68,68,0.20)]"
        >
          <Power size={14} />
          KILL SWITCH
        </button>
      </div>

      {/* Confirmation Dialog */}
      {showKillConfirm && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-[rgba(0,0,0,0.60)] backdrop-blur-sm"
            onClick={() => setShowKillConfirm(false)}
          />

          {/* Dialog */}
          <div className="relative bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[12px] p-6 shadow-[0_24px_48px_rgba(0,0,0,0.40)] max-w-[400px] w-full mx-4">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-[rgba(239,68,68,0.15)] flex items-center justify-center">
                <AlertTriangle size={20} className="text-[#EF4444]" />
              </div>
              <div>
                <h3 className="text-[16px] font-semibold text-[#F1F5F9]">Kill Switch</h3>
                <p className="text-[12px] text-[#94A3B8]">This action cannot be undone</p>
              </div>
            </div>

            <p className="text-[13px] text-[#94A3B8] mb-4 leading-relaxed">
              This will immediately:
            </p>
            <ul className="text-[13px] text-[#94A3B8] mb-6 space-y-1.5">
              <li className="flex items-center gap-2">
                <X size={12} className="text-[#EF4444]" />
                Close all {LIVE_POSITIONS.length} open positions at market price
              </li>
              <li className="flex items-center gap-2">
                <X size={12} className="text-[#EF4444]" />
                Stop all {activeStrategies} active strategies
              </li>
              <li className="flex items-center gap-2">
                <X size={12} className="text-[#EF4444]" />
                Cancel all pending orders
              </li>
              <li className="flex items-center gap-2">
                <X size={12} className="text-[#EF4444]" />
                Disable all trading for 1 hour
              </li>
            </ul>

            <div className="flex gap-3">
              <button
                onClick={() => setShowKillConfirm(false)}
                className="flex-1 h-10 rounded-[4px] bg-transparent border border-[rgba(255,255,255,0.06)] text-[#94A3B8] text-[13px] font-medium hover:bg-[#1A1A25] transition-all"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setShowKillConfirm(false);
                  onKillSwitch();
                }}
                className="flex-1 h-10 rounded-[4px] bg-[#EF4444] text-white text-[13px] font-bold hover:brightness-110 transition-all active:scale-[0.98]"
              >
                Confirm Kill Switch
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
