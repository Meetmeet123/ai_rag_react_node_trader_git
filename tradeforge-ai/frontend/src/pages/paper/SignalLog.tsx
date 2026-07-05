import { useState } from 'react';
import { Filter } from 'lucide-react';
import { signals } from './data';

export default function SignalLog() {
  const [filterStrategy, setFilterStrategy] = useState('All');

  const strategies = ['All', ...Array.from(new Set(signals.map(s => s.strategy)))];
  const filtered = filterStrategy === 'All' ? signals : signals.filter(s => s.strategy === filterStrategy);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'Executed': return 'text-[#10B981] bg-[rgba(16,185,129,0.15)]';
      case 'Pending': return 'text-[#F59E0B] bg-[rgba(245,158,11,0.15)]';
      case 'Failed': return 'text-[#EF4444] bg-[rgba(239,68,68,0.15)]';
      default: return 'text-[#64748B] bg-[#06060A]';
    }
  };

  const getSignalBadge = (type: string, signal: string) => {
    const isBuy = type === 'LONG';
    return (
      <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-[4px] text-[11px] font-semibold ${
        isBuy ? 'text-[#10B981] bg-[rgba(16,185,129,0.15)]' : 'text-[#EF4444] bg-[rgba(239,68,68,0.15)]'
      }`}>
        <span className={isBuy ? 'text-[#10B981]' : 'text-[#EF4444]'}>
          {isBuy ? (signal === 'ENTRY' ? '▲' : '▼') : (signal === 'ENTRY' ? '▼' : '▲')}
        </span>
        {signal === 'ENTRY' ? (isBuy ? 'BUY' : 'SELL') : 'EXIT'}
      </span>
    );
  };

  return (
    <div className="w-full h-[240px] bg-[#0A0A0F] border-t border-[rgba(255,255,255,0.06)] flex flex-col">
      {/* Header */}
      <div className="h-9 flex items-center justify-between px-4 border-b border-[rgba(255,255,255,0.06)]">
        <div className="flex items-center gap-3">
          <span className="text-[15px] font-semibold text-[#F1F5F9]">Signal Log</span>
          <span className="text-[11px] text-[#64748B]">{filtered.length} signals</span>
        </div>
        <div className="flex items-center gap-2">
          <Filter size={12} className="text-[#64748B]" />
          <select
            value={filterStrategy}
            onChange={(e) => setFilterStrategy(e.target.value)}
            className="h-6 px-2 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[11px] text-[#94A3B8] focus:outline-none focus:border-[#22D3EE]"
          >
            {strategies.map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full">
          <thead className="sticky top-0 bg-[#06060A]">
            <tr>
              <th className="text-left px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Time</th>
              <th className="text-left px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Strategy</th>
              <th className="text-left px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Symbol</th>
              <th className="text-left px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Type</th>
              <th className="text-left px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Signal</th>
              <th className="text-right px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Price</th>
              <th className="text-right px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Exec Price</th>
              <th className="text-right px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Slippage</th>
              <th className="text-right px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">P&L</th>
              <th className="text-center px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((sig) => (
              <tr
                key={sig.id}
                className="border-b border-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.02)] transition-colors"
              >
                <td className="px-4 py-1.5 text-[12px] font-mono text-[#94A3B8] whitespace-nowrap">{sig.time}</td>
                <td className="px-4 py-1.5 text-[12px] text-[#F1F5F9] whitespace-nowrap">{sig.strategy}</td>
                <td className="px-4 py-1.5 text-[12px] font-mono text-[#F1F5F9] whitespace-nowrap">{sig.symbol}</td>
                <td className="px-4 py-1.5 whitespace-nowrap">
                  <span className={`inline-flex px-1.5 py-0.5 rounded-[4px] text-[11px] font-medium ${
                    sig.type === 'LONG' ? 'text-[#10B981] bg-[rgba(16,185,129,0.15)]' : 'text-[#EF4444] bg-[rgba(239,68,68,0.15)]'
                  }`}>
                    {sig.type}
                  </span>
                </td>
                <td className="px-4 py-1.5 whitespace-nowrap">{getSignalBadge(sig.type, sig.signal)}</td>
                <td className="px-4 py-1.5 text-[12px] font-mono text-right text-[#F1F5F9] whitespace-nowrap">{sig.price.toFixed(2)}</td>
                <td className="px-4 py-1.5 text-[12px] font-mono text-right text-[#94A3B8] whitespace-nowrap">{sig.executedPrice.toFixed(2)}</td>
                <td className={`px-4 py-1.5 text-[12px] font-mono text-right whitespace-nowrap ${
                  sig.slippage >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
                }`}>
                  {sig.slippage >= 0 ? '+' : ''}{sig.slippage.toFixed(2)}
                </td>
                <td className={`px-4 py-1.5 text-[12px] font-mono text-right font-medium whitespace-nowrap ${
                  sig.pnl === null ? 'text-[#64748B]' : sig.pnl >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
                }`}>
                  {sig.pnl === null ? '—' : `${sig.pnl >= 0 ? '+' : ''}₹${sig.pnl.toLocaleString('en-IN')}`}
                </td>
                <td className="px-4 py-1.5 text-center whitespace-nowrap">
                  <span className={`inline-flex px-1.5 py-0.5 rounded-full text-[10px] font-semibold ${getStatusColor(sig.status)}`}>
                    {sig.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
