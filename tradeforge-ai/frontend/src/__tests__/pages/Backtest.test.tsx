import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router';
import Backtest from '@/pages/Backtest';
import * as api from '@/lib/api';

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="recharts-container">{children}</div>,
  AreaChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Area: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
}));
import type { BacktestRun, Strategy, StrategyListResponse } from '@/types/api';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    fetchStrategies: vi.fn(),
    fetchStrategy: vi.fn(),
    runBacktest: vi.fn(),
    fetchBacktest: vi.fn(),
  };
});

const mockStrategy: Strategy = {
  id: 's1',
  name: 'Test Strategy',
  instrument: 'RELIANCE',
  segment: 'equity',
  timeframe: '1d',
  status: 'draft',
  is_ai_generated: false,
  definition: {},
};

const completedRun: BacktestRun = {
  id: 'bt1',
  strategy_id: 's1',
  strategy_name: 'Test Strategy',
  start_date: '2024-06-01',
  end_date: '2024-06-30',
  initial_capital: 100000,
  status: 'completed',
  total_trades: 5,
  winning_trades: 3,
  losing_trades: 2,
  win_rate: 60,
  net_pnl: 5000,
  net_pnl_pct: 5,
  gross_profit: 7000,
  gross_loss: 2000,
  profit_factor: 3.5,
  max_drawdown: 1000,
  max_drawdown_pct: 1,
  sharpe_ratio: 1.2,
  avg_profit_per_trade: 1000,
  avg_loss_per_trade: 500,
  avg_holding_period: 2,
  equity_curve: [{ timestamp: '2024-06-01', equity: 100000 }],
  drawdown_curve: [{ timestamp: '2024-06-01', drawdown_pct: 0 }],
  monthly_returns: { monthly: [{ month: 'Jun 2024', trades: 5, wins: 3, losses: 2, win_rate: 60, gross_pnl: 7000, charges: 200, net_pnl: 6800 }] },
  trade_log: [],
};

function renderBacktest(initialEntry = '/app/backtest') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/app/backtest" element={<Backtest />} />
        <Route path="/app/paper" element={<div data-testid="paper-page">Paper Trading</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('Backtest page', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    Object.defineProperty(globalThis, 'location', {
      configurable: true,
      value: { ...window.location, reload: vi.fn() },
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('loads strategies and shows the strategy selection step', async () => {
    vi.mocked(api.fetchStrategies).mockResolvedValue({ strategies: [mockStrategy], total: 1 } as StrategyListResponse);

    renderBacktest();
    await waitFor(() => expect(screen.getByText('Test Strategy')).toBeInTheDocument());
  });

  it('pre-selects a strategy from the query parameter and advances to configuration', async () => {
    vi.mocked(api.fetchStrategies).mockResolvedValue({ strategies: [mockStrategy], total: 1 } as StrategyListResponse);
    vi.mocked(api.fetchStrategy).mockResolvedValue(mockStrategy);

    renderBacktest('/app/backtest?strategyId=s1');
    await waitFor(() => expect(screen.getByText('Backtest Configuration')).toBeInTheDocument());
  });

  it('starts a backtest run from the configuration step', async () => {
    vi.mocked(api.fetchStrategies).mockResolvedValue({ strategies: [mockStrategy], total: 1 } as StrategyListResponse);
    vi.mocked(api.runBacktest).mockResolvedValue({ id: 'bt1', status: 'running', initial_capital: 100000 } as BacktestRun);

    renderBacktest('/app/backtest?strategyId=s1');
    await waitFor(() => expect(screen.getByText('Backtest Configuration')).toBeInTheDocument());

    await userEvent.click(screen.getByRole('button', { name: /Run Backtest/i }));
    await waitFor(() => expect(api.runBacktest).toHaveBeenCalledWith(expect.objectContaining({ strategy_id: 's1' })));
    expect(screen.getByText('Running Backtest...')).toBeInTheDocument();
  });
});
