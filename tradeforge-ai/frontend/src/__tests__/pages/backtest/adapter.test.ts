import { describe, it, expect } from 'vitest';
import { apiBacktestRunToResult } from '@/pages/backtest/adapter';
import type { BacktestRun } from '@/types/api';

describe('backtest adapter', () => {
  const run: BacktestRun = {
    id: 'bt1',
    strategy_id: 's1',
    strategy_name: 'Test Strategy',
    start_date: '2024-06-01',
    end_date: '2024-06-30',
    initial_capital: 100000,
    status: 'completed',
    total_trades: 4,
    winning_trades: 3,
    losing_trades: 1,
    win_rate: 75,
    net_pnl: 5000,
    net_pnl_pct: 5,
    gross_profit: 6000,
    gross_loss: 1000,
    profit_factor: 6,
    max_drawdown: 500,
    max_drawdown_pct: 0.5,
    sharpe_ratio: 1.5,
    avg_profit_per_trade: 1000,
    avg_loss_per_trade: 500,
    avg_holding_period: 2,
    equity_curve: [{ timestamp: '2024-06-01', equity: 100000 }],
    drawdown_curve: [{ timestamp: '2024-06-01', drawdown_pct: 0 }],
    monthly_returns: { monthly: [{ month: 'Jun 2024', trades: 4, wins: 3, losses: 1, win_rate: 75, gross_pnl: 6000, charges: 200, net_pnl: 5800 }] },
    trade_log: [
      { entry_time: '2024-06-03T09:15:00Z', exit_time: '2024-06-03T15:15:00Z', symbol: 'RELIANCE', direction: 'buy', entry_price: 2500, exit_price: 2550, pnl: 50, pnl_pct: 2 },
      { entry_time: '2024-06-04T09:15:00Z', exit_time: '2024-06-04T15:15:00Z', symbol: 'RELIANCE', direction: 'buy', entry_price: 2550, exit_price: 2520, pnl: -30, pnl_pct: -1.2 },
    ],
  };

  it('converts a completed backtest run into a UI result', () => {
    const result = apiBacktestRunToResult(run);
    expect(result.totalTrades).toBe(4);
    expect(result.winRate).toBe(75);
    expect(result.netPnl).toBe(5000);
    expect(result.trades).toHaveLength(2);
    expect(result.trades[0].status).toBe('WIN');
    expect(result.trades[1].status).toBe('LOSS');
    expect(result.equityCurve).toHaveLength(1);
    expect(result.monthlyReturns).toHaveLength(1);
  });

  it('handles empty trade logs and curves gracefully', () => {
    const empty = { ...run, trade_log: [], equity_curve: [], drawdown_curve: [], monthly_returns: {} };
    const result = apiBacktestRunToResult(empty);
    expect(result.trades).toHaveLength(0);
    expect(result.equityCurve).toHaveLength(0);
    expect(result.monthlyReturns).toHaveLength(0);
  });
});
