import { useEffect, useState } from 'react';
import { Circle, Wifi } from 'lucide-react';

export default function AppBottomBar() {
  const [time, setTime] = useState('');

  useEffect(() => {
    const update = () => {
      const now = new Date();
      setTime(
        now.toLocaleTimeString('en-IN', {
          timeZone: 'Asia/Kolkata',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: true,
        })
      );
    };
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <footer
      className="h-8 shrink-0 bg-[#0A0A0F] border-t border-[rgba(255,255,255,0.06)] flex items-center px-4 z-40"
    >
      <div className="flex items-center justify-between w-full">
        {/* Left: Broker Status */}
        <div className="flex items-center gap-2">
          <Wifi size={12} className="text-[#10B981]" />
          <Circle size={6} className="text-[#10B981] fill-[#10B981]" />
          <span className="text-[11px] text-[#94A3B8]">Angel One</span>
          <span className="text-[11px] text-[#475569]">|</span>
          <span className="text-[11px] text-[#10B981]">Connected</span>
        </div>

        {/* Center: Market Countdown */}
        <div className="hidden md:block">
          <span className="text-[11px] text-[#94A3B8]">
            NSE closes in 2h 14m
          </span>
        </div>

        {/* Right: Time & Version */}
        <div className="flex items-center gap-3">
          <span className="text-[11px] font-mono text-[#64748B]">{time} IST</span>
          <span className="text-[11px] text-[#475569]">v1.0.0</span>
        </div>
      </div>
    </footer>
  );
}
