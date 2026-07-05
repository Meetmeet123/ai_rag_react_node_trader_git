import { useState } from 'react';
import { paperOrders } from './data';

export default function PaperOrderBook() {
  const [tab, setTab] = useState<'orders' | 'bids'>('orders');

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'Filled': return 'text-[#10B981] bg-[rgba(16,185,129,0.15)]';
      case 'Partial': return 'text-[#F59E0B] bg-[rgba(245,158,11,0.15)]';
      case 'Pending': return 'text-[#60A5FA] bg-[rgba(96,165,250,0.15)]';
      case 'Rejected': return 'text-[#EF4444] bg-[rgba(239,68,68,0.15)]';
      case 'Cancelled': return 'text-[#64748B] bg-[#06060A]';
      default: return 'text-[#64748B] bg-[#06060A]';
    }
  };

  return (
    <div className="w-full bg-[#0A0A0F] border-t border-[rgba(255,255,255,0.06)]">
      {/* Tabs */}
      <div className="h-9 flex items-center px-4 border-b border-[rgba(255,255,255,0.06)]">
        <div className="flex items-center gap-0 bg-[#06060A] rounded-[6px] p-0.5">
          <button
            onClick={() => setTab('orders')}
            className={`px-3 py-1 rounded-[4px] text-[11px] font-medium transition-all ${
              tab === 'orders'
                ? 'bg-[#12121A] text-[#F1F5F9] shadow-sm'
                : 'text-[#64748B] hover:text-[#94A3B8]'
            }`}
          >
            Order History
          </button>
          <button
            onClick={() => setTab('bids')}
            className={`px-3 py-1 rounded-[4px] text-[11px] font-medium transition-all ${
              tab === 'bids'
                ? 'bg-[#12121A] text-[#F1F5F9] shadow-sm'
                : 'text-[#64748B] hover:text-[#94A3B8]'
            }`}
          >
            Order Book
          </button>
        </div>
        <span className="ml-auto text-[11px] text-[#64748B]">{paperOrders.length} orders</span>
      </div>

      {tab === 'orders' ? (
        <div className="h-[200px] overflow-auto">
          <table className="w-full">
            <thead className="sticky top-0 bg-[#06060A]">
              <tr>
                <th className="text-left px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Order ID</th>
                <th className="text-left px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Time</th>
                <th className="text-left px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Symbol</th>
                <th className="text-left px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Type</th>
                <th className="text-right px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Qty</th>
                <th className="text-right px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Price</th>
                <th className="text-center px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Status</th>
                <th className="text-left px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Strategy</th>
              </tr>
            </thead>
            <tbody>
              {paperOrders.map((order) => (
                <tr
                  key={order.id}
                  className="border-b border-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.02)] transition-colors"
                >
                  <td className="px-4 py-1.5 text-[11px] font-mono text-[#64748B] whitespace-nowrap">{order.id}</td>
                  <td className="px-4 py-1.5 text-[12px] font-mono text-[#94A3B8] whitespace-nowrap">{order.time}</td>
                  <td className="px-4 py-1.5 text-[12px] font-mono text-[#F1F5F9] whitespace-nowrap">{order.symbol}</td>
                  <td className="px-4 py-1.5 whitespace-nowrap">
                    <span className={`text-[11px] font-semibold ${
                      order.type === 'BUY' ? 'text-[#10B981]' : 'text-[#EF4444]'
                    }`}>
                      {order.type}
                    </span>
                  </td>
                  <td className="px-4 py-1.5 text-[12px] font-mono text-right text-[#F1F5F9] whitespace-nowrap">{order.qty}</td>
                  <td className="px-4 py-1.5 text-[12px] font-mono text-right text-[#F1F5F9] whitespace-nowrap">₹{order.price.toFixed(2)}</td>
                  <td className="px-4 py-1.5 text-center whitespace-nowrap">
                    <span className={`inline-flex px-1.5 py-0.5 rounded-full text-[10px] font-semibold ${getStatusColor(order.status)}`}>
                      {order.status}
                    </span>
                  </td>
                  <td className="px-4 py-1.5 text-[11px] text-[#94A3B8] whitespace-nowrap">{order.strategy}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="h-[200px] flex">
          {/* Bids */}
          <div className="flex-1 border-r border-[rgba(255,255,255,0.06)]">
            <div className="h-7 flex items-center px-4 bg-[rgba(16,185,129,0.08)]">
              <span className="text-[11px] font-semibold text-[#10B981]">BIDS</span>
            </div>
            <div className="overflow-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="text-left px-3 py-1.5 text-[10px] font-medium text-[#64748B]">Price</th>
                    <th className="text-right px-3 py-1.5 text-[10px] font-medium text-[#64748B]">Qty</th>
                    <th className="text-right px-3 py-1.5 text-[10px] font-medium text-[#64748B]">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { price: 2891.50, qty: 45, total: 130117 },
                    { price: 2891.45, qty: 120, total: 346974 },
                    { price: 2891.40, qty: 75, total: 216855 },
                    { price: 2891.35, qty: 200, total: 578270 },
                    { price: 2891.30, qty: 30, total: 86739 },
                  ].map((bid, i) => (
                    <tr key={i} className="hover:bg-[rgba(16,185,129,0.04)] transition-colors">
                      <td className="px-3 py-1 text-[11px] font-mono text-[#10B981]">{bid.price.toFixed(2)}</td>
                      <td className="px-3 py-1 text-[11px] font-mono text-right text-[#94A3B8]">{bid.qty}</td>
                      <td className="px-3 py-1 text-[11px] font-mono text-right text-[#64748B]">{(bid.total / 1000).toFixed(1)}K</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Center Spread */}
          <div className="w-[100px] flex flex-col items-center justify-center border-r border-[rgba(255,255,255,0.06)] bg-[#06060A]">
            <span className="text-[10px] text-[#64748B]">Spread</span>
            <span className="text-[11px] font-mono text-[#94A3B8]">0.05</span>
            <span className="text-[15px] font-mono font-semibold text-[#F1F5F9] mt-1">2891.48</span>
            <span className="text-[9px] text-[#64748B]">LTP</span>
          </div>

          {/* Asks */}
          <div className="flex-1">
            <div className="h-7 flex items-center px-4 bg-[rgba(239,68,68,0.08)]">
              <span className="text-[11px] font-semibold text-[#EF4444]">ASKS</span>
            </div>
            <div className="overflow-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="text-left px-3 py-1.5 text-[10px] font-medium text-[#64748B]">Price</th>
                    <th className="text-right px-3 py-1.5 text-[10px] font-medium text-[#64748B]">Qty</th>
                    <th className="text-right px-3 py-1.5 text-[10px] font-medium text-[#64748B]">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { price: 2891.55, qty: 60, total: 173493 },
                    { price: 2891.60, qty: 90, total: 260244 },
                    { price: 2891.65, qty: 150, total: 433747 },
                    { price: 2891.70, qty: 40, total: 115668 },
                    { price: 2891.75, qty: 85, total: 245798 },
                  ].map((ask, i) => (
                    <tr key={i} className="hover:bg-[rgba(239,68,68,0.04)] transition-colors">
                      <td className="px-3 py-1 text-[11px] font-mono text-[#EF4444]">{ask.price.toFixed(2)}</td>
                      <td className="px-3 py-1 text-[11px] font-mono text-right text-[#94A3B8]">{ask.qty}</td>
                      <td className="px-3 py-1 text-[11px] font-mono text-right text-[#64748B]">{(ask.total / 1000).toFixed(1)}K</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
