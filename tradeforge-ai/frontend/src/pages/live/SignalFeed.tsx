import { useState } from 'react';
import { TrendingUp, TrendingDown, Activity } from 'lucide-react';
import { SIGNALS } from './data';

export default function SignalFeed() {
  const [signals] = useState(SIGNALS);

  return (
    <div className="w-full h-full bg-[#12121A] border-r border-[rgba(255,255,255,0.06)] flex flex-col">
      {/* Header */}
      <div className="h-10 flex items-center justify-between px-3 border-b border-[rgba(255,255,255,0.06)] shrink-0">
        <div className="flex items-center gap-2">
          <Activity size={14} className="text-[#22D3EE]" />
          <span className="text-[15px] font-semibold text-[#F1F5F9]">Signal Feed</span>
        </div>
        <span className="text-[11px] text-[#64748B]">{signals.length} signals</span>
      </div>

      {/* Signals list */}
      <div className="flex-1 overflow-y-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-[#06060A]">
              <th className="text-left text-[10px] font-medium text-[#64748B] px-3 py-2">Time</th>
              <th className="text-left text-[10px] font-medium text-[#64748B] px-3 py-2">Strategy</th>
              <th className="text-left text-[10px] font-medium text-[#64748B] px-3 py-2">Symbol</th>
              <th className="text-center text-[10px] font-medium text-[#64748B] px-3 py-2">Signal</th>
              <th className="text-right text-[10px] font-medium text-[#64748B] px-3 py-2">Price</th>
              <th className="text-center text-[10px] font-medium text-[#64748B] px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {signals.map((signal) => {
              const isBuy = signal.side === 'BUY';
              const statusColor =
                signal.status === 'EXECUTED'
                  ? 'text-[#10B981]'
                  : signal.status === 'PENDING'
                    ? 'text-[#F59E0B]'
                    : 'text-[#64748B]';
              const statusBg =
                signal.status === 'EXECUTED'
                  ? 'bg-[rgba(16,185,129,0.15)]'
                  : signal.status === 'PENDING'
                    ? 'bg-[rgba(245,158,11,0.15)]'
                    : 'bg-[#06060A]';

              return (
                <tr
                  key={signal.id}
                  className="border-b border-[rgba(255,255,255,0.06)] hover:bg-[rgba(255,255,255,0.02)] transition-all"
                  style={{
                    animation: 'slideInRight 300ms ease-out',
                  }}
                >
                  <td className="px-3 py-2">
                    <span className="text-[11px] font-mono text-[#64748B]">{signal.timestamp}</span>
                  </td>
                  <td className="px-3 py-2">
                    <span className="text-[12px] text-[#F1F5F9]">{signal.strategy}</span>
                  </td>
                  <td className="px-3 py-2">
                    <span className="text-[12px] font-semibold text-[#F1F5F9]">{signal.symbol}</span>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex justify-center">
                      <span
                        className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-[4px] ${
                          isBuy
                            ? 'bg-[rgba(16,185,129,0.15)] text-[#10B981]'
                            : 'bg-[rgba(239,68,68,0.15)] text-[#EF4444]'
                        }`}
                      >
                        {isBuy ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                        {signal.side}
                      </span>
                    </div>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <span className="text-[12px] font-mono font-medium text-[#F1F5F9]">
                      ₹{signal.price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex justify-center">
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${statusBg} ${statusColor}`}>
                        {signal.status}
                      </span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* CSS animation */}
      <style>{`
        @keyframes slideInRight {
          from {
            opacity: 0;
            transform: translateX(12px);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }
      `}</style>
    </div>
  );
}
