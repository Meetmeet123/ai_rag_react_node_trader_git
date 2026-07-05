import { useState, useEffect } from 'react';
import { Loader } from 'lucide-react';

const STATUS_MESSAGES = [
  'Fetching historical data...',
  'Loading data points...',
  'Running strategy simulation...',
  'Calculating performance metrics...',
  'Generating report...',
];

interface Step3Props {
  onComplete: () => void;
  symbol: string;
  startDate: string;
  endDate: string;
}

export default function Step3_Running({ onComplete, symbol, startDate, endDate }: Step3Props) {
  const [progress, setProgress] = useState(0);
  const [messageIndex, setMessageIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval);
          setTimeout(onComplete, 600);
          return 100;
        }
        return prev + Math.random() * 4 + 1;
      });
    }, 150);

    return () => clearInterval(interval);
  }, [onComplete]);

  useEffect(() => {
    const msgInterval = setInterval(() => {
      setMessageIndex((prev) => (prev + 1) % STATUS_MESSAGES.length);
    }, 2000);
    return () => clearInterval(msgInterval);
  }, []);

  const clampedProgress = Math.min(progress, 100);

  return (
    <div className="flex-1 flex flex-col items-center justify-center max-w-[500px] mx-auto px-6">
      <Loader size={40} className="text-[#22D3EE] animate-spin mb-6" />

      <h2 className="font-display text-[24px] font-semibold text-[#F1F5F9] mb-2">
        Running Backtest...
      </h2>

      <p className="text-[14px] text-[#94A3B8] mb-8">
        {symbol} | {formatDate(startDate)} - {formatDate(endDate)} | Daily
      </p>

      {/* Progress bar */}
      <div className="w-full mb-4">
        <div className="w-full h-1.5 bg-[#12121A] rounded-full overflow-hidden">
          <div
            className="h-full bg-[#22D3EE] rounded-full transition-all duration-100 ease-out"
            style={{ width: `${clampedProgress}%` }}
          />
        </div>
      </div>

      {/* Percentage */}
      <p className="font-mono text-[24px] font-semibold text-[#22D3EE] mb-4">
        {Math.round(clampedProgress)}%
      </p>

      {/* Status message */}
      <p className="text-[13px] text-[#64748B] mb-6 min-h-[20px] transition-opacity duration-200">
        {STATUS_MESSAGES[messageIndex]}
      </p>

      {/* Cancel */}
      <button
        onClick={() => window.location.reload()}
        className="px-4 py-2 text-[12px] text-[#64748B] hover:text-[#F1F5F9] transition-colors"
      >
        Cancel
      </button>
    </div>
  );
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-IN', { month: 'short', year: 'numeric' });
}
