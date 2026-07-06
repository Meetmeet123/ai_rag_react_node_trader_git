import { X } from 'lucide-react';
import type { PositionResponse } from '@/types/api';

interface VirtualPositionsProps {
  positions: PositionResponse[];
  onClose?: (symbol: string) => void;
  loading?: boolean;
}

export default function VirtualPositions({ positions, onClose, loading }: VirtualPositionsProps) {
  return (
    <div className="w-full h-full bg-[#12121A] border-l border-[rgba(255,255,255,0.06)] flex flex-col">
      {/* Header */}
      <div className="h-10 flex items-center justify-between px-3 border-b border-[rgba(255,255,255,0.06)]">
        <div className="flex items-center gap-2">
          <span className="text-[15px] font-semibold text-[#F1F5F9]">Virtual Positions</span>
          <span className="px-1.5 py-0.5 bg-[rgba(245,158,11,0.15)] text-[#F59E0B] text-[10px] font-bold rounded-full">
            PAPER
          </span>
        </div>
        <span className="text-[11px] text-[#64748B]">{positions.length} open</span>
      </div>

      {/* Positions List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        {loading && positions.length === 0 ? (
          <div className="p-3 text-[12px] text-[#64748B]">Loading positions…</div>
        ) : positions.length === 0 ? (
          <div className="p-3 text-[12px] text-[#64748B]">No open positions.</div>
        ) : (
          positions.map(pos => {
            const pnlPercent = pos.avg_price > 0
              ? ((pos.current_price - pos.avg_price) / pos.avg_price) * 100 * (pos.quantity >= 0 ? 1 : -1)
              : 0;
            const type = pos.quantity >= 0 ? 'LONG' : 'SHORT';

            return (
              <div
                key={pos.symbol}
                className="bg-[#0A0A0F] border border-[rgba(255,255,255,0.06)] rounded-[6px] p-3 transition-all hover:border-[rgba(255,255,255,0.10)]"
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className="text-[13px] font-semibold text-[#F1F5F9]">{pos.symbol}</span>
                    <span className={`text-[10px] font-medium px-1 py-0.5 rounded-[4px] ${
                      type === 'LONG' ? 'text-[#10B981] bg-[rgba(16,185,129,0.15)]' : 'text-[#EF4444] bg-[rgba(239,68,68,0.15)]'
                    }`}>
                      {type}
                    </span>
                  </div>
                  <button
                    onClick={() => onClose?.(pos.symbol)}
                    className="text-[#64748B] hover:text-[#EF4444] transition-colors"
                    title="Close position"
                  >
                    <X size={13} />
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-x-3 gap-y-1 mb-2">
                  <div>
                    <span className="text-[10px] text-[#64748B]">Qty</span>
                    <div className="text-[12px] font-mono text-[#F1F5F9]">{Math.abs(pos.quantity)}</div>
                  </div>
                  <div>
                    <span className="text-[10px] text-[#64748B]">Avg Price</span>
                    <div className="text-[12px] font-mono text-[#94A3B8]">₹{pos.avg_price.toFixed(2)}</div>
                  </div>
                  <div>
                    <span className="text-[10px] text-[#64748B]">LTP</span>
                    <div className="text-[12px] font-mono text-[#F1F5F9]">₹{pos.current_price.toFixed(2)}</div>
                  </div>
                  <div>
                    <span className="text-[10px] text-[#64748B]">Strategy</span>
                    <div className="text-[11px] text-[#94A3B8] truncate">{String(pos.strategy_id)}</div>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-1.5 border-t border-[rgba(255,255,255,0.04)]">
                  <span className="text-[10px] text-[#64748B]">P&amp;L</span>
                  <div className="flex items-center gap-1.5">
                    <span className={`text-[13px] font-mono font-semibold ${
                      pos.unrealized_pnl >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
                    }`}>
                      {pos.unrealized_pnl >= 0 ? '+' : ''}₹{pos.unrealized_pnl.toLocaleString('en-IN')}
                    </span>
                    <span className={`text-[10px] font-mono ${
                      pnlPercent >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
                    }`}>
                      ({pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%)
                    </span>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
