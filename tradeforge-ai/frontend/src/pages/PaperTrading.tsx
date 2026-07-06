import { useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { useWebSocket } from '@/hooks/useWebSocket';
import {
  fetchPortfolio,
  fetchPositions,
  fetchSignals,
  fetchOrders,
  closePosition,
  fetchSystemStatus,
} from '@/lib/api';
import type { PortfolioResponse, PositionResponse } from '@/types/api';
import VirtualCapitalHeader from './paper/VirtualCapitalHeader';
import StrategyDeploymentPanel from './paper/StrategyDeploymentPanel';
import ChartSignalsArea from './paper/ChartSignalsArea';
import VirtualCapitalCard from './paper/VirtualCapitalCard';
import VirtualPositions from './paper/VirtualPositions';
import SignalLog from './paper/SignalLog';
import PaperOrderBook from './paper/PaperOrderBook';

const POLL_INTERVAL_MS = 3000;
const SOCKET_URL = import.meta.env.VITE_SOCKET_URL || 'http://localhost:8000';

interface CapitalMetrics {
  portfolio_value: number;
  used_margin: number;
  available_balance: number;
  pnl_today: number;
  total_unrealized_pnl: number;
}

function computeCapitalMetrics(
  portfolio: PortfolioResponse | null,
  defaultCapital: number,
): CapitalMetrics {
  const positions = portfolio ? Object.values(portfolio.positions) : [];
  const usedMargin = positions.reduce((sum, p) => sum + Math.abs(p.quantity) * p.avg_price, 0);
  const totalUnrealized = portfolio?.total_unrealized_pnl ?? 0;
  const pnlToday =
    typeof portfolio?.daily_stats?.pnl_today === 'number' ? portfolio.daily_stats.pnl_today : 0;

  const availableBalance = Math.max(0, defaultCapital - usedMargin);
  const portfolioValue = availableBalance + usedMargin + totalUnrealized;

  return {
    portfolio_value: portfolioValue,
    used_margin: usedMargin,
    available_balance: availableBalance,
    pnl_today: pnlToday,
    total_unrealized_pnl: totalUnrealized,
  };
}

export default function PaperTrading() {
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [positions, setPositions] = useState<PositionResponse[]>([]);
  const [signals, setSignals] = useState<unknown[]>([]);
  const [orders, setOrders] = useState<unknown[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [defaultCapital, setDefaultCapital] = useState(1_000_000);

  const refreshData = useCallback(async () => {
    try {
      const [portfolioRes, positionsRes, signalsRes, ordersRes] = await Promise.all([
        fetchPortfolio(),
        fetchPositions(),
        fetchSignals(100),
        fetchOrders(100),
      ]);
      setPortfolio(portfolioRes);
      setPositions(Object.values(positionsRes.positions ?? {}));
      setSignals(signalsRes);
      setOrders(ordersRes.trades ?? []);
      setError(null);
    } catch (err) {
      const message = err && typeof err === 'object' && 'detail' in err ? String(err.detail) : 'Failed to load paper trading data';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Load default capital once
  useEffect(() => {
    fetchSystemStatus()
      .then((status) => {
        const config = status.config as Record<string, unknown> | undefined;
        if (config && typeof config.default_capital === 'number') {
          setDefaultCapital(config.default_capital);
        }
      })
      .catch(() => {
        // Fallback to 10L if status fails
      });
  }, []);

  // Polling
  useEffect(() => {
    refreshData();
    const interval = setInterval(refreshData, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refreshData]);

  // Socket.IO updates
  const handleSocketMessage = useCallback(
    (data: unknown) => {
      if (
        data &&
        typeof data === 'object' &&
        ('signal' in data || 'result' in data || 'mode' in data)
      ) {
        refreshData();
      }
    },
    [refreshData],
  );

  const { readyState } = useWebSocket({
    url: SOCKET_URL,
    room: 'paper',
    onMessage: handleSocketMessage,
    onError: (err) => {
      // eslint-disable-next-line no-console
      console.warn('Socket.IO error:', err.message);
    },
  });

  const handleClosePosition = useCallback(
    async (symbol: string) => {
      try {
        const result = await closePosition(symbol);
        if (result.success) {
          toast.success(`Closed position for ${symbol}`);
        } else {
          toast.error(result.message || `Failed to close ${symbol}`);
        }
        await refreshData();
      } catch (err) {
        const message = err && typeof err === 'object' && 'detail' in err ? String(err.detail) : 'Close position failed';
        toast.error(message);
      }
    },
    [refreshData],
  );

  const capitalMetrics = useMemo(
    () => computeCapitalMetrics(portfolio, defaultCapital),
    [portfolio, defaultCapital],
  );

  const isConnected = readyState === 'open';

  return (
    <div className="flex flex-col h-full -m-4 md:-m-6">
      <VirtualCapitalHeader metrics={capitalMetrics} socketConnected={isConnected} />

      {error && (
        <div className="px-5 py-2 bg-[rgba(239,68,68,0.12)] border-b border-[rgba(239,68,68,0.20)] text-[13px] text-[#EF4444]">
          {error}
        </div>
      )}

      <div className="flex flex-1 min-h-0">
        <div className="w-[20%] min-w-[180px] shrink-0 overflow-hidden">
          <StrategyDeploymentPanel />
        </div>

        <div className="w-[55%] min-w-0 shrink-0 flex flex-col overflow-hidden">
          <ChartSignalsArea signals={signals} loading={loading} />
        </div>

        <div className="w-[25%] min-w-[180px] shrink-0 overflow-y-auto flex flex-col">
          <VirtualCapitalCard
            metrics={capitalMetrics}
            positions={positions}
            loading={loading}
          />
          <div className="flex-1 min-h-[200px]">
            <VirtualPositions positions={positions} onClose={handleClosePosition} loading={loading} />
          </div>
        </div>
      </div>

      {/* Bottom: Signal Log + Order Book */}
      <div className="shrink-0">
        <SignalLog signals={signals} loading={loading} />
        <PaperOrderBook orders={orders} loading={loading} />
      </div>
    </div>
  );
}
