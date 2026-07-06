import { useEffect, useMemo, useState } from 'react';
import { Search, Plus, TrendingUp, TrendingDown } from 'lucide-react';
import { fetchNifty50, fetchQuote } from '@/lib/api';
import { generateSparklineData, type Stock } from './data';

interface WatchlistPanelProps {
  selectedSymbol: string;
  onSelectSymbol: (symbol: string) => void;
}

const TABS = ['Nifty 50', 'BankNifty', 'F&O', 'Custom'];

const FALLBACK_STOCKS: Stock[] = [
  { symbol: 'RELIANCE', name: 'Reliance Industries', exchange: 'NSE', ltp: 2891.45, change: 23.7, changePercent: 0.82, volume: 4523100, high: 2901.0, low: 2870.2, open: 2875.0, close: 2867.75 },
  { symbol: 'TCS', name: 'Tata Consultancy', exchange: 'NSE', ltp: 4234.6, change: -14.5, changePercent: -0.34, volume: 1234500, high: 4260.0, low: 4210.5, open: 4250.0, close: 4249.1 },
  { symbol: 'HDFCBANK', name: 'HDFC Bank', exchange: 'NSE', ltp: 1678.9, change: 18.6, changePercent: 1.12, volume: 6789000, high: 1685.0, low: 1662.3, open: 1665.0, close: 1660.3 },
  { symbol: 'INFY', name: 'Infosys Ltd', exchange: 'NSE', ltp: 1892.3, change: -10.65, changePercent: -0.56, volume: 3456700, high: 1910.0, low: 1885.5, open: 1903.0, close: 1902.95 },
  { symbol: 'ICICIBANK', name: 'ICICI Bank', exchange: 'NSE', ltp: 1123.45, change: 7.45, changePercent: 0.67, volume: 5678900, high: 1129.0, low: 1115.2, open: 1117.0, close: 1116.0 },
];

function MiniSparkline({ data, positive }: { data: number[]; positive: boolean }) {
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const w = 60;
  const h = 20;
  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * w;
      const y = h - ((v - min) / range) * h;
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <svg width={w} height={h} className="shrink-0">
      <polyline
        points={points}
        fill="none"
        stroke={positive ? '#10B981' : '#EF4444'}
        strokeWidth={1.5}
      />
    </svg>
  );
}

export default function WatchlistPanel({ selectedSymbol, onSelectSymbol }: WatchlistPanelProps) {
  const [activeTab, setActiveTab] = useState('Nifty 50');
  const [searchQuery, setSearchQuery] = useState('');
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadNifty50 = async () => {
      setLoading(true);
      setError(null);

      try {
        const { constituents } = await fetchNifty50();
        const results = await Promise.allSettled(
          constituents.map(async (symbol) => {
            const quote = await fetchQuote(symbol, '1d');
            return {
              symbol,
              name: symbol,
              exchange: 'NSE',
              ltp: quote.price_data.close,
              change: quote.price_data.change,
              changePercent: quote.price_data.change_pct,
              open: quote.price_data.open,
              high: quote.price_data.high,
              low: quote.price_data.low,
              close: quote.price_data.close,
              volume: quote.price_data.volume,
            };
          }),
        );

        const fetched = results
          .filter((r): r is PromiseFulfilledResult<Stock> => r.status === 'fulfilled')
          .map((r) => r.value);

        if (cancelled) return;

        if (fetched.length === 0) {
          setError('Could not load any Nifty 50 quotes.');
        }
        setStocks(fetched);
      } catch (err) {
        if (!cancelled) {
          setError('Failed to load Nifty 50 constituents.');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    if (activeTab === 'Nifty 50') {
      loadNifty50();
    } else {
      setStocks(FALLBACK_STOCKS);
      setLoading(false);
      setError(null);
    }

    return () => {
      cancelled = true;
    };
  }, [activeTab]);

  const filteredStocks = useMemo(() => {
    if (!searchQuery.trim()) return stocks;
    const q = searchQuery.toLowerCase();
    return stocks.filter(
      (s) => s.symbol.toLowerCase().includes(q) || s.name.toLowerCase().includes(q)
    );
  }, [searchQuery, stocks]);

  return (
    <div className="w-full h-full bg-[#12121A] border-r border-[rgba(255,255,255,0.06)] flex flex-col">
      {/* Header */}
      <div className="h-10 flex items-center justify-between px-3 border-b border-[rgba(255,255,255,0.06)] shrink-0">
        <span className="text-[15px] font-semibold text-[#F1F5F9]">Watchlist</span>
        <div className="flex items-center gap-1">
          <div className="relative">
            <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-[#64748B]" />
            <input
              type="text"
              placeholder="Search..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-[100px] h-6 pl-6 pr-2 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[11px] text-[#F1F5F9] placeholder:text-[#475569] focus:outline-none focus:border-[#22D3EE]"
            />
          </div>
          <button className="w-6 h-6 flex items-center justify-center rounded-[4px] text-[#64748B] hover:text-[#F1F5F9] hover:bg-[#1A1A25] transition-all">
            <Plus size={14} />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-0.5 p-1 bg-[#06060A] shrink-0">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 h-7 text-[11px] font-medium rounded-[4px] transition-all ${
              activeTab === tab
                ? 'bg-[#12121A] text-[#F1F5F9] shadow'
                : 'text-[#64748B] hover:text-[#94A3B8]'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Stock List */}
      <div className="flex-1 overflow-y-auto">
        {loading && (
          <div className="flex items-center justify-center h-20">
            <span className="text-[12px] text-[#64748B]">Loading watchlist…</span>
          </div>
        )}

        {!loading && error && (
          <div className="px-3 py-4 text-center">
            <span className="text-[12px] text-[#EF4444]">{error}</span>
          </div>
        )}

        {!loading && !error && filteredStocks.length === 0 && (
          <div className="px-3 py-4 text-center">
            <span className="text-[12px] text-[#64748B]">No symbols found.</span>
          </div>
        )}

        {!loading && filteredStocks.map((stock) => {
          const isPositive = stock.changePercent >= 0;
          const isSelected = stock.symbol === selectedSymbol;
          const sparkData = generateSparklineData(20);

          return (
            <button
              key={stock.symbol}
              onClick={() => onSelectSymbol(stock.symbol)}
              className={`w-full text-left px-3 py-2.5 border-b border-[rgba(255,255,255,0.06)] transition-all hover:bg-[rgba(255,255,255,0.02)] ${
                isSelected
                  ? 'bg-[rgba(34,211,238,0.12)] border-l-2 border-l-[#22D3EE]'
                  : ''
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-[13px] font-semibold text-[#F1F5F9]">
                    {stock.symbol}
                  </span>
                  <span className="text-[10px] text-[#64748B] bg-[#06060A] px-1 py-0.5 rounded-[3px]">
                    {stock.exchange}
                  </span>
                </div>
                <MiniSparkline data={sparkData} positive={isPositive} />
              </div>
              <div className="flex items-center justify-between mt-1">
                <span className="text-[13px] font-mono font-medium text-[#F1F5F9]">
                  ₹{stock.ltp.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </span>
                <span
                  className={`text-[11px] font-medium flex items-center gap-0.5 ${
                    isPositive ? 'text-[#10B981]' : 'text-[#EF4444]'
                  }`}
                >
                  {isPositive ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                  {isPositive ? '+' : ''}
                  {stock.changePercent}%
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
