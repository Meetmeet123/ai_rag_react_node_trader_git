import { useEffect, useState } from 'react';
import { Loader } from 'lucide-react';
import { fetchBacktest } from '@/lib/api';
import { apiBacktestRunToResult } from './adapter';
import type { BacktestResult } from './types';

const STATUS_MESSAGES = [
  'Fetching historical data...',
  'Loading data points...',
  'Running strategy simulation...',
  'Calculating performance metrics...',
  'Generating report...',
];

interface Step3Props {
  backtestId: string;
  onComplete: (result: BacktestResult) => void;
  onError: (message: string) => void;
  symbol: string;
  startDate: string;
  endDate: string;
}

export default function Step3_Running({ backtestId, onComplete, onError, symbol, startDate, endDate }: Step3Props) {
  const [progress, setProgress] = useState(10);
  const [messageIndex, setMessageIndex] = useState(0);
  const [status, setStatus] = useState<string>('running');

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        const run = await fetchBacktest(backtestId);
        if (cancelled) return;
        setStatus(run.status);

        if (run.status === 'completed') {
          setProgress(100);
          onComplete(apiBacktestRunToResult(run));
          return;
        }

        if (run.status === 'failed') {
          onError(run.error_message || 'Backtest failed');
          return;
        }

        // Simulate progress while running
        setProgress((prev) => Math.min(prev + Math.random() * 8 + 2, 90));
      } catch (err) {
        if (cancelled) return;
        const message = err && typeof err === 'object' && 'detail' in err
          ? String((err as { detail: string }).detail)
          : 'Failed to check backtest status';
        onError(message);
      }
    };

    poll();
    const interval = setInterval(poll, 1500);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [backtestId, onComplete, onError]);

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
      <p className="text-[13px] text-[#64748B] mb-2 min-h-[20px] transition-opacity duration-200">
        {STATUS_MESSAGES[messageIndex]}
      </p>
      <p className="text-[11px] text-[#475569]">Status: {status}</p>

      {/* Cancel */}
      <button
        onClick={() => window.location.reload()}
        className="mt-6 px-4 py-2 text-[12px] text-[#64748B] hover:text-[#F1F5F9] transition-colors"
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
