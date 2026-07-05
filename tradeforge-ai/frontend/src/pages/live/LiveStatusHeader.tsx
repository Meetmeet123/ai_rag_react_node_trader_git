import { useState, useEffect } from 'react';
import { Octagon, Wifi } from 'lucide-react';

interface LiveStatusHeaderProps {
  onKillSwitch: () => void;
}

export default function LiveStatusHeader({ onKillSwitch }: LiveStatusHeaderProps) {
  const [latency, setLatency] = useState(34);
  const [dotOpacity, setDotOpacity] = useState(1);
  const [isLive, setIsLive] = useState(true);

  // Pulse animation for LIVE dot
  useEffect(() => {
    let direction = -1;
    const interval = setInterval(() => {
      setDotOpacity((prev) => {
        const next = prev + direction * 0.1;
        if (next <= 0.3) {
          direction = 1;
          return 0.3;
        }
        if (next >= 1) {
          direction = -1;
          return 1;
        }
        return next;
      });
    }, 100);
    return () => clearInterval(interval);
  }, []);

  // Simulate latency changes
  useEffect(() => {
    const interval = setInterval(() => {
      setLatency(20 + Math.floor(Math.random() * 60));
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const latencyColor = latency < 100 ? 'text-[#10B981]' : latency < 300 ? 'text-[#F59E0B]' : 'text-[#EF4444]';
  const orderCount = 12;

  return (
    <div
      className="h-11 flex items-center justify-between px-4 border-b shrink-0"
      style={{
        background: 'rgba(16,185,129,0.08)',
        borderColor: 'rgba(16,185,129,0.15)',
      }}
    >
      {/* Left: LIVE badge + Broker */}
      <div className="flex items-center gap-3">
        {/* LIVE badge */}
        <div
          className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border"
          style={{
            background: 'rgba(16,185,129,0.15)',
            borderColor: 'rgba(16,185,129,0.30)',
          }}
        >
          <div
            className="w-2 h-2 rounded-full bg-[#10B981]"
            style={{ opacity: dotOpacity }}
          />
          <span className="text-[11px] font-bold text-[#10B981]">LIVE</span>
        </div>

        {/* Broker status */}
        <div className="flex items-center gap-1.5">
          <Wifi size={14} className="text-[#10B981]" />
          <span className="text-[11px] text-[#94A3B8]">Angel One</span>
          <div className="w-1.5 h-1.5 rounded-full bg-[#10B981]" />
          <span className="text-[11px] text-[#10B981]">Connected</span>
        </div>
      </div>

      {/* Center: Latency + Orders */}
      <div className="flex items-center gap-3">
        <span className="text-[12px] font-mono font-medium text-[#94A3B8]">
          Latency:{" "}
          <span className={latencyColor}>{latency}ms</span>
        </span>
        <span className="text-[11px] text-[#475569]">|</span>
        <span className="text-[11px] text-[#64748B]">
          Orders: {orderCount} today
        </span>
      </div>

      {/* Right: Market status + Mode toggle + Kill */}
      <div className="flex items-center gap-3">
        {/* Paper/Live toggle */}
        <button
          onClick={() => setIsLive(!isLive)}
          className="flex items-center gap-1.5 text-[11px] font-medium transition-colors"
        >
          <span className={isLive ? 'text-[#64748B]' : 'text-[#10B981]'}>Paper</span>
          <div
            className="w-8 h-[18px] rounded-full relative transition-colors"
            style={{
              background: isLive ? 'rgba(16,185,129,0.30)' : 'rgba(100,116,139,0.30)',
            }}
          >
            <div
              className="absolute top-[2px] w-3.5 h-3.5 rounded-full bg-white transition-all"
              style={{ left: isLive ? 'calc(100% - 16px)' : '2px' }}
            />
          </div>
          <span className={isLive ? 'text-[#10B981]' : 'text-[#64748B]'}>Live</span>
        </button>

        {/* Market status */}
        <span className="text-[11px] font-medium text-[#10B981] bg-[rgba(16,185,129,0.15)] px-2 py-0.5 rounded-full">
          Market: OPEN
        </span>

        {/* STOP ALL button */}
        <button
          onClick={onKillSwitch}
          className="flex items-center gap-1 px-2.5 py-1 bg-[#EF4444] text-white text-[11px] font-semibold rounded-[4px] hover:brightness-110 transition-all active:scale-[0.98]"
        >
          <Octagon size={12} />
          STOP ALL
        </button>
      </div>
    </div>
  );
}
