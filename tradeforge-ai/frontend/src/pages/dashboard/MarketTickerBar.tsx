import { useEffect, useRef, useState } from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { INDICES } from './data';

export default function MarketTickerBar() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [isPaused, setIsPaused] = useState(false);
  const animationRef = useRef<number>(0);
  const scrollPosRef = useRef(0);

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
        {[...INDICES, ...INDICES].map((idx, i) => (
          <div key={`${idx.name}-${i}`} className="flex items-center gap-3 shrink-0">
            <span className="text-[12px] font-medium text-[#64748B]">{idx.name}</span>
            <span className="text-[13px] font-mono font-medium text-[#F1F5F9]">
              {idx.value.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
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
              {idx.change}%
            </span>
            {i < INDICES.length * 2 - 1 && (
              <div className="w-px h-4 bg-[rgba(255,255,255,0.06)] ml-3" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
