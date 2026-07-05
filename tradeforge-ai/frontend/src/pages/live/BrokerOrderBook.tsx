import { useState } from 'react';
import { X, BookOpen } from 'lucide-react';
import { BROKER_ORDERS } from './data';

export default function BrokerOrderBook() {
  const [orders, setOrders] = useState(BROKER_ORDERS);

  const cancelPending = () => {
    setOrders((prev) =>
      prev.map((o) => (o.status === 'PENDING' ? { ...o, status: 'REJECTED' as const } : o))
    );
  };

  return (
    <div className="w-full h-full bg-[#12121A] border-t border-[rgba(255,255,255,0.06)] flex flex-col">
      {/* Header */}
      <div className="h-10 flex items-center justify-between px-3 border-b border-[rgba(255,255,255,0.06)] shrink-0">
        <div className="flex items-center gap-2">
          <BookOpen size={14} className="text-[#22D3EE]" />
          <span className="text-[15px] font-semibold text-[#F1F5F9]">Order Book</span>
          <span className="text-[11px] text-[#64748B] bg-[#06060A] px-1.5 py-0.5 rounded-full">
            {orders.length}
          </span>
        </div>
        <button
          onClick={cancelPending}
          className="px-3 py-1 bg-[rgba(239,68,68,0.15)] text-[#EF4444] text-[11px] font-semibold rounded-[4px] hover:bg-[rgba(239,68,68,0.25)] transition-all"
        >
          Cancel Pending
        </button>
      </div>

      {/* Orders table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-[#06060A]">
              <th className="text-left text-[10px] font-medium text-[#64748B] px-3 py-2">Order ID</th>
              <th className="text-left text-[10px] font-medium text-[#64748B] px-3 py-2">Time</th>
              <th className="text-left text-[10px] font-medium text-[#64748B] px-3 py-2">Symbol</th>
              <th className="text-center text-[10px] font-medium text-[#64748B] px-3 py-2">Side</th>
              <th className="text-right text-[10px] font-medium text-[#64748B] px-3 py-2">Qty</th>
              <th className="text-right text-[10px] font-medium text-[#64748B] px-3 py-2">Price</th>
              <th className="text-center text-[10px] font-medium text-[#64748B] px-3 py-2">Status</th>
              <th className="text-center text-[10px] font-medium text-[#64748B] px-3 py-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((order) => {
              const isBuy = order.side === 'BUY';
              const statusConfig = {
                FILLED: { color: 'text-[#10B981]', bg: 'bg-[rgba(16,185,129,0.15)]' },
                PARTIAL: { color: 'text-[#F59E0B]', bg: 'bg-[rgba(245,158,11,0.15)]' },
                REJECTED: { color: 'text-[#EF4444]', bg: 'bg-[rgba(239,68,68,0.15)]' },
                PENDING: { color: 'text-[#F59E0B]', bg: 'bg-[rgba(245,158,11,0.15)]' },
              };
              const sc = statusConfig[order.status];

              return (
                <tr
                  key={order.id}
                  className="border-b border-[rgba(255,255,255,0.06)] hover:bg-[rgba(255,255,255,0.02)] transition-colors"
                >
                  <td className="px-3 py-2">
                    <span className="text-[11px] font-mono text-[#64748B]">{order.id}</span>
                  </td>
                  <td className="px-3 py-2">
                    <span className="text-[11px] font-mono text-[#94A3B8]">{order.time}</span>
                  </td>
                  <td className="px-3 py-2">
                    <span className="text-[12px] font-semibold text-[#F1F5F9]">{order.symbol}</span>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex justify-center">
                      <span
                        className={`text-[10px] font-semibold px-2 py-0.5 rounded-[4px] ${
                          isBuy
                            ? 'bg-[rgba(16,185,129,0.15)] text-[#10B981]'
                            : 'bg-[rgba(239,68,68,0.15)] text-[#EF4444]'
                        }`}
                      >
                        {order.side}
                      </span>
                    </div>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <span className="text-[12px] font-mono text-[#F1F5F9]">{order.qty}</span>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <span className="text-[12px] font-mono font-medium text-[#F1F5F9]">
                      ₹{order.price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex justify-center">
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${sc.bg} ${sc.color}`}>
                        {order.status}
                      </span>
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex justify-center">
                      {order.status === 'PENDING' && (
                        <button
                          onClick={() =>
                            setOrders((prev) =>
                              prev.map((o) =>
                                o.id === order.id ? { ...o, status: 'REJECTED' as const } : o
                              )
                            )
                          }
                          className="w-6 h-6 flex items-center justify-center rounded-[4px] text-[#64748B] hover:text-[#EF4444] hover:bg-[rgba(239,68,68,0.15)] transition-all"
                        >
                          <X size={11} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
