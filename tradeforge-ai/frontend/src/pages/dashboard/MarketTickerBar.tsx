import { useEffect, useRef, useState } from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { fetchQuote } from '@/lib/api';

interface TickerItem {
  name: string;
  symbol: string;
  close: number;
  change: number;
  changePercent: number;
}

const DEFAULT_INDICES = [
  { name: 'NIFTY 50', symbol: 'NIFTY50' },
  { name: 'BANKNIFTY', symbol: 'BANKNIFTY' },
  { name: 'SENSEX', symbol: 'SENSEX' },
  { name: 'NIFTY IT', symbol: 'NIFTYIT' },
  { name: 'USDINR', symbol: 'USDINR' },
];

export default function MarketTickerBar() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [isPaused, setIsPaused] = useState(false);
  const [items, setItems] = useState<TickerItem[]>([]);
  const [loading, setLoading] = useState(true);
  const animationRef = useRef<number>(0);
  const scrollPosRef = useRef(0);

  const loadQuotes = async () => {
    const results = await Promise.allSettled(
      DEFAULT_INDICES.map(async (idx) => {
        const quote = await fetchQuote(idx.symbol, '1d');
        return {
          name: idx.name,
          symbol: idx.symbol,
          close: quote.price_data.close,
          change: quote.price_data.change,
          changePercent: quote.price_data.change_pct,
        };
      }),
    );

    const next = results
      .filter((r): r is PromiseFulfilledResult<TickerItem> => r.status === 'fulfilled')
      .map((r) => r.value);

    setItems(next);
    setLoading(false);
  };

  useEffect(() => {
    loadQuotes();
    const interval = setInterval(loadQuotes, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    let lastTime = performance.now();
    const speed = 40; // px/s

    const animate = (time: number) => {
      if (!isPaused) {
        const dt = (time - lastTime) / 1000;
        scrollPosRef.current += speed * dt;

        // Reset when first item scrolls out
        const firstChild = el.firstElementChild as HTMLElement;
        if (firstChild && scrollPosRef.current >= firstChild.offsetWidth + 24) {
          scrollPosRef.current = 0;
        }

        el.style.transform = `translateX(-${scrollPosRef.current}px)`;
      }
      lastTime = time;
      animationRef.current = requestAnimationFrame(animate);
    };

    animationRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationRef.current);
  }, [isPaused]);

  if (loading && items.length === 0) {
    return (
      <div className="h-10 bg-[#06060A] border-b border-[rgba(255,255,255,0.06)] flex items-center px-4">
        <span className="text-[12px] text-[#64748B]">Loading market data…</span>
      </div>
    );
  }

  const displayItems = items.length > 0 ? items : DEFAULT_INDICES.map((i) => ({
    name: i.name,
    symbol: i.symbol,
    close: 0,
    change: 0,
    changePercent: 0,
  }));

  return (
    <div
      className="h-10 bg-[#06060A] border-b border-[rgba(255,255,255,0.06)] overflow-hidden flex items-center"
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
    >
      <div
        ref={scrollRef}
        className="flex items-center gap-6 whitespace-nowrap will-change-transform"
      >
        {/* Duplicate items for seamless loop */}
        {[...displayItems, ...displayItems].map((idx, i) => (
          <div key={`${idx.symbol}-${i}`} className="flex items-center gap-3 shrink-0">
            <span className="text-[12px] font-medium text-[#64748B]">{idx.name}</span>
            <span className="text-[13px] font-mono font-medium text-[#F1F5F9]">
              {idx.close.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </span>
            <span
              className={`text-[11px] font-medium flex items-center gap-0.5 ${
                idx.change >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
              }`}
            >
              {idx.change >= 0 ? (
                <TrendingUp size={10} />
              ) : (
                <TrendingDown size={10} />
              )}
              {idx.change >= 0 ? '+' : ''}
              {idx.changePercent}%
            </span>
            {i < displayItems.length * 2 - 1 && (
              <div className="w-px h-4 bg-[rgba(255,255,255,0.06)] ml-3" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
