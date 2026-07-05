import { useState, useMemo } from 'react';
import { X, Pencil, Briefcase } from 'lucide-react';
import { POSITIONS } from './data';

const TABS = ['Positions', 'Orders', 'Trades', 'Holdings'] as const;

export default function PositionsTable() {
  const [activeTab, setActiveTab] = useState<(typeof TABS)[number]>('Positions');

  const totalPnL = useMemo(
    () => POSITIONS.reduce((sum, p) => sum + p.pnl, 0),
    []
  );

  const usedMargin = 124500;
  const availableBalance = 875000;

  return (
    <div className="w-full h-[280px] bg-[#12121A] border-t border-[rgba(255,255,255,0.06)] flex flex-col">
      {/* Tabs */}
      <div className="h-9 flex items-center px-3 border-b border-[rgba(255,255,255,0.06)] shrink-0">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`relative h-full px-4 text-[12px] font-medium transition-colors ${
              activeTab === tab
                ? 'text-[#F1F5F9]'
                : 'text-[#64748B] hover:text-[#94A3B8]'
            }`}
          >
            {tab}
            {tab === 'Positions' && (
              <span className="ml-1 text-[10px] bg-[#06060A] px-1.5 py-0.5 rounded-full text-[#94A3B8]">
                {POSITIONS.length}
              </span>
            )}
            {activeTab === tab && (
              <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-[#22D3EE]" />
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {activeTab === 'Positions' ? (
          POSITIONS.length > 0 ? (
            <table className="w-full">
              <thead>
                <tr className="bg-[#06060A]">
                  <th className="text-left text-[11px] font-medium text-[#64748B] px-4 py-2">Symbol</th>
                  <th className="text-left text-[11px] font-medium text-[#64748B] px-4 py-2">Product</th>
                  <th className="text-right text-[11px] font-medium text-[#64748B] px-4 py-2">Qty</th>
                  <th className="text-right text-[11px] font-medium text-[#64748B] px-4 py-2">Avg Price</th>
                  <th className="text-right text-[11px] font-medium text-[#64748B] px-4 py-2">LTP</th>
                  <th className="text-right text-[11px] font-medium text-[#64748B] px-4 py-2">P&L</th>
                  <th className="text-right text-[11px] font-medium text-[#64748B] px-4 py-2">P&L %</th>
                  <th className="text-center text-[11px] font-medium text-[#64748B] px-4 py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {POSITIONS.map((pos) => {
                  const isLong = pos.qty > 0;
                  const isProfit = pos.pnl >= 0;
                  return (
                    <tr
                      key={pos.id}
                      className="border-b border-[rgba(255,255,255,0.06)] hover:bg-[rgba(255,255,255,0.02)] transition-colors"
                    >
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-1.5">
                          <span className="text-[13px] font-semibold text-[#F1F5F9]">{pos.symbol}</span>
                          <span className="text-[9px] text-[#64748B] bg-[#06060A] px-1 py-0.5 rounded-[3px]">
                            {pos.exchange}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-2.5">
                        <span className="text-[11px] text-[#64748B]">{pos.product}</span>
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <span
                          className={`text-[13px] font-mono font-medium ${
                            isLong ? 'text-[#10B981]' : 'text-[#EF4444]'
                          }`}
                        >
                          {isLong ? '+' : ''}
                          {pos.qty}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <span className="text-[13px] font-mono text-[#F1F5F9]">
                          ₹{pos.avgPrice.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <span className="text-[13px] font-mono text-[#F1F5F9]">
                          ₹{pos.ltp.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <span
                          className={`text-[13px] font-mono font-medium ${
                            isProfit ? 'text-[#10B981]' : 'text-[#EF4444]'
                          }`}
                        >
                          {isProfit ? '+' : ''}₹{pos.pnl.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <span
                          className={`text-[11px] font-medium ${
                            isProfit ? 'text-[#10B981]' : 'text-[#EF4444]'
                          }`}
                        >
                          {isProfit ? '↑' : '↓'} {isProfit ? '+' : ''}
                          {pos.pnlPercent}%
                        </span>
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="flex items-center justify-center gap-1">
                          <button className="w-6 h-6 flex items-center justify-center rounded-[4px] text-[#64748B] hover:text-[#F1F5F9] hover:bg-[#1A1A25] transition-all">
                            <Pencil size={11} />
                          </button>
                          <button className="w-6 h-6 flex items-center justify-center rounded-[4px] text-[#64748B] hover:text-[#EF4444] hover:bg-[rgba(239,68,68,0.15)] transition-all">
                            <X size={11} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <div className="flex flex-col items-center justify-center h-full gap-3">
              <Briefcase size={48} className="text-[#475569]" />
              <span className="text-[15px] font-semibold text-[#64748B]">No open positions</span>
              <span className="text-[13px] text-[#475569]">
                Place your first order to start trading
              </span>
              <button className="mt-2 px-4 py-2 bg-[#22D3EE] text-[#030305] text-[12px] font-semibold rounded-[4px] hover:brightness-110 transition-all">
                Place Order
              </button>
            </div>
          )
        ) : (
          <div className="flex flex-col items-center justify-center h-full gap-2">
            <span className="text-[14px] text-[#64748B]">No {activeTab.toLowerCase()} to display</span>
          </div>
        )}
      </div>

      {/* P&L Summary Bar */}
      <div className="h-9 flex items-center justify-between px-4 bg-[#06060A] border-t border-[rgba(255,255,255,0.06)] shrink-0">
        <div className="flex items-center gap-6">
          <span className="text-[12px] text-[#94A3B8]">
            Total P&L:{" "}
            <span
              className={`font-mono font-semibold ${
                totalPnL >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
              }`}
            >
              {totalPnL >= 0 ? '+' : ''}₹{totalPnL.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </span>
          </span>
          <span className="text-[12px] text-[#94A3B8]">
            Used Margin:{" "}
            <span className="font-mono text-[#F1F5F9]">
              ₹{usedMargin.toLocaleString('en-IN')}
            </span>
          </span>
          <span className="text-[12px] text-[#94A3B8]">
            Available:{" "}
            <span className="font-mono text-[#F1F5F9]">
              ₹{availableBalance.toLocaleString('en-IN')}
            </span>
          </span>
        </div>
      </div>
    </div>
  );
}
