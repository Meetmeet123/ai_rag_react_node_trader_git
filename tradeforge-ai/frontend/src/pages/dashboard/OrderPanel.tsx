import { useState } from 'react';
import { STOCKS, RECENT_ORDERS } from './data';

interface OrderPanelProps {
  selectedSymbol: string;
}

type OrderSide = 'BUY' | 'SELL';
type ProductType = 'MIS' | 'CNC' | 'NRML';
type OrderType = 'Market' | 'Limit' | 'SL' | 'SL-M';

export default function OrderPanel({ selectedSymbol }: OrderPanelProps) {
  const [side, setSide] = useState<OrderSide>('BUY');
  const [product, setProduct] = useState<ProductType>('MIS');
  const [orderType, setOrderType] = useState<OrderType>('Market');
  const [qty, setQty] = useState(1);
  const [price, setPrice] = useState('');
  const [stopLoss, setStopLoss] = useState('');
  const [target, setTarget] = useState('');

  const stock = STOCKS.find((s) => s.symbol === selectedSymbol) || STOCKS[0];
  const isBuy = side === 'BUY';

  const handleQtyChange = (delta: number) => {
    setQty((prev) => Math.max(1, prev + delta));
  };

  const marginRequired = Math.floor(qty * stock.ltp * 0.2);

  return (
    <div className="w-full h-full bg-[#12121A] border-l border-[rgba(255,255,255,0.06)] flex flex-col">
      {/* Buy/Sell Toggle */}
      <div className="flex h-9 shrink-0">
        <button
          onClick={() => setSide('BUY')}
          className={`flex-1 text-[13px] font-semibold transition-all ${
            isBuy
              ? 'bg-[#10B981] text-white'
              : 'bg-[rgba(16,185,129,0.15)] text-[#10B981] hover:bg-[rgba(16,185,129,0.25)]'
          }`}
        >
          BUY
        </button>
        <button
          onClick={() => setSide('SELL')}
          className={`flex-1 text-[13px] font-semibold transition-all ${
            !isBuy
              ? 'bg-[#EF4444] text-white'
              : 'bg-[rgba(239,68,68,0.15)] text-[#EF4444] hover:bg-[rgba(239,68,68,0.25)]'
          }`}
        >
          SELL
        </button>
      </div>

      {/* Order Form */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {/* Symbol & Price */}
        <div className="flex items-center justify-between">
          <div>
            <span className="text-[13px] font-semibold text-[#F1F5F9]">{stock.symbol}</span>
            <span className="text-[10px] text-[#64748B] ml-1.5">{stock.exchange}</span>
          </div>
          <span className="text-[15px] font-mono font-semibold text-[#F1F5F9]">
            ₹{stock.ltp.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </span>
        </div>

        {/* Product Type */}
        <div>
          <label className="text-[11px] text-[#64748B] mb-1 block">Product</label>
          <div className="flex gap-0.5 bg-[#06060A] rounded-[4px] p-0.5">
            {(['MIS', 'CNC', 'NRML'] as ProductType[]).map((p) => (
              <button
                key={p}
                onClick={() => setProduct(p)}
                className={`flex-1 h-7 text-[11px] font-medium rounded-[4px] transition-all ${
                  product === p
                    ? 'bg-[#12121A] text-[#F1F5F9] shadow'
                    : 'text-[#64748B] hover:text-[#94A3B8]'
                }`}
              >
                {p}
              </button>
            ))}
          </div>
        </div>

        {/* Order Type */}
        <div>
          <label className="text-[11px] text-[#64748B] mb-1 block">Order Type</label>
          <div className="flex gap-0.5 bg-[#06060A] rounded-[4px] p-0.5">
            {(['Market', 'Limit', 'SL', 'SL-M'] as OrderType[]).map((ot) => (
              <button
                key={ot}
                onClick={() => setOrderType(ot)}
                className={`flex-1 h-7 text-[11px] font-medium rounded-[4px] transition-all ${
                  orderType === ot
                    ? 'bg-[#12121A] text-[#F1F5F9] shadow'
                    : 'text-[#64748B] hover:text-[#94A3B8]'
                }`}
              >
                {ot}
              </button>
            ))}
          </div>
        </div>

        {/* Quantity */}
        <div>
          <label className="text-[11px] text-[#64748B] mb-1 block">Quantity</label>
          <div className="flex items-center gap-2">
            <button
              onClick={() => handleQtyChange(-1)}
              className="w-8 h-8 flex items-center justify-center rounded-[4px] bg-[#06060A] border border-[rgba(255,255,255,0.06)] text-[#F1F5F9] hover:bg-[#1A1A25] transition-all text-[15px]"
            >
              −
            </button>
            <input
              type="number"
              value={qty}
              onChange={(e) => setQty(Math.max(1, parseInt(e.target.value) || 1))}
              className="flex-1 h-8 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[6px] text-center text-[13px] font-mono text-[#F1F5F9] focus:outline-none focus:border-[#22D3EE]"
            />
            <button
              onClick={() => handleQtyChange(1)}
              className="w-8 h-8 flex items-center justify-center rounded-[4px] bg-[#06060A] border border-[rgba(255,255,255,0.06)] text-[#F1F5F9] hover:bg-[#1A1A25] transition-all text-[15px]"
            >
              +
            </button>
          </div>
        </div>

        {/* Price (for Limit/SL orders) */}
        {orderType !== 'Market' && (
          <div>
            <label className="text-[11px] text-[#64748B] mb-1 block">Price</label>
            <input
              type="number"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder={stock.ltp.toFixed(2)}
              className="w-full h-8 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[6px] px-3 text-[13px] font-mono text-[#F1F5F9] placeholder:text-[#475569] focus:outline-none focus:border-[#22D3EE]"
            />
          </div>
        )}

        {/* Stop Loss */}
        {(orderType === 'SL' || orderType === 'SL-M') && (
          <div>
            <label className="text-[11px] text-[#64748B] mb-1 block">Stop Loss</label>
            <input
              type="number"
              value={stopLoss}
              onChange={(e) => setStopLoss(e.target.value)}
              placeholder="0.00"
              className="w-full h-8 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[6px] px-3 text-[13px] font-mono text-[#F1F5F9] placeholder:text-[#475569] focus:outline-none focus:border-[#22D3EE]"
            />
          </div>
        )}

        {/* Target */}
        <div>
          <label className="text-[11px] text-[#64748B] mb-1 block">Target (optional)</label>
          <input
            type="number"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            placeholder="0.00"
            className="w-full h-8 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[6px] px-3 text-[13px] font-mono text-[#F1F5F9] placeholder:text-[#475569] focus:outline-none focus:border-[#22D3EE]"
          />
        </div>

        {/* Margin Required */}
        <div className="flex items-center justify-between py-2 border-t border-[rgba(255,255,255,0.06)]">
          <span className="text-[11px] text-[#64748B]">Margin Required</span>
          <span className="text-[13px] font-mono font-medium text-[#F1F5F9]">
            ₹{marginRequired.toLocaleString('en-IN')}
          </span>
        </div>

        {/* Action Buttons */}
        <button
          className={`w-full h-11 rounded-[4px] text-[15px] font-bold transition-all active:scale-[0.98] ${
            isBuy
              ? 'bg-[#10B981] text-white hover:brightness-110'
              : 'bg-[#EF4444] text-white hover:brightness-110'
          }`}
        >
          {side} {stock.symbol}
        </button>
        <button className="w-full h-8 text-[12px] text-[#64748B] hover:text-[#94A3B8] transition-colors">
          Reset
        </button>

        {/* Recent Orders */}
        <div className="pt-2 border-t border-[rgba(255,255,255,0.06)]">
          <span className="text-[11px] text-[#64748B] mb-2 block">Recent Orders</span>
          <div className="space-y-1.5">
            {RECENT_ORDERS.map((order) => (
              <div
                key={order.id}
                className="flex items-center justify-between py-1.5 px-2 bg-[#06060A] rounded-[4px]"
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-[3px] ${
                      order.side === 'BUY'
                        ? 'bg-[rgba(16,185,129,0.15)] text-[#10B981]'
                        : 'bg-[rgba(239,68,68,0.15)] text-[#EF4444]'
                    }`}
                  >
                    {order.side}
                  </span>
                  <span className="text-[11px] text-[#94A3B8]">
                    {order.qty} @ ₹{order.price.toFixed(2)}
                  </span>
                </div>
                <span
                  className={`text-[10px] font-medium ${
                    order.status === 'COMPLETE'
                      ? 'text-[#10B981]'
                      : order.status === 'REJECTED'
                        ? 'text-[#EF4444]'
                        : 'text-[#F59E0B]'
                  }`}
                >
                  {order.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
