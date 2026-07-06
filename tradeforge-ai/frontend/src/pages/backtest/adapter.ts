import type { BacktestRun as ApiBacktestRun, Strategy as ApiStrategy } from '@/types/api';
import type { BacktestResult, BacktestStrategy, Trade, MonthlyReturn, EquityPoint, DrawdownPoint } from './types';
import type { SavedStrategy } from '../strategies/types';
import { apiToSaved } from '../strategies/adapter';

export function apiStrategyToBacktestStrategy(strategy: ApiStrategy): BacktestStrategy {
  const saved = apiToSaved(strategy);
  return savedStrategyToBacktestStrategy(saved);
}

export function savedStrategyToBacktestStrategy(strategy: SavedStrategy): BacktestStrategy {
  return {
    id: strategy.id,
    name: strategy.name,
    description: strategy.description,
    segment: strategy.segment,
    status: strategy.status,
    lastModified: strategy.lastModified,
  };
}

export function apiBacktestRunToResult(run: ApiBacktestRun): BacktestResult {
  const trades: Trade[] = (run.trade_log || []).map((t, index) => {
    const trade = t as Record<string, unknown>;
    const pnl = Number(trade.pnl ?? 0);
    return {
      id: index + 1,
      entryDate: formatDate(String(trade.entry_time ?? '')),
      exitDate: formatDate(String(trade.exit_time ?? '')),
      symbol: String(trade.symbol ?? ''),
      side: (trade.direction as string)?.toLowerCase() === 'short' ? 'Short' : 'Long',
      entryPrice: Number(trade.entry_price ?? 0),
      exitPrice: Number(trade.exit_price ?? 0),
      pnl,
      pnlPercent: Number(trade.pnl_pct ?? 0),
      status: pnl >= 0 ? 'WIN' : 'LOSS',
    };
  });

  const equityCurve: EquityPoint[] = (run.equity_curve || []).map((p) => {
    const point = p as Record<string, unknown>;
    return {
      date: formatDate(String(point.timestamp ?? '')),
      value: Number(point.equity ?? 0),
    };
  });

  const drawdownCurve: DrawdownPoint[] = (run.drawdown_curve || []).map((p) => {
    const point = p as Record<string, unknown>;
    return {
      date: formatDate(String(point.timestamp ?? '')),
      value: Number(point.drawdown_pct ?? point.drawdown ?? 0),
    };
  });

  const monthlyRaw = run.monthly_returns;
  let monthlyReturns: MonthlyReturn[] = [];
  if (monthlyRaw && Array.isArray((monthlyRaw as Record<string, unknown>).monthly)) {
    monthlyReturns = ((monthlyRaw as Record<string, unknown>).monthly as unknown[]).map((m) => {
      const item = m as Record<string, unknown>;
      return {
        month: String(item.month ?? ''),
        trades: Number(item.trades ?? 0),
        wins: Number(item.wins ?? 0),
        losses: Number(item.losses ?? 0),
        winRate: Number(item.win_rate ?? 0),
        grossPnl: Number(item.gross_pnl ?? 0),
        charges: Number(item.charges ?? 0),
        netPnl: Number(item.net_pnl ?? 0),
      };
    });
  }

  const wins = trades.filter((t) => t.status === 'WIN');
  const losses = trades.filter((t) => t.status === 'LOSS');
  const largestWin = wins.length > 0 ? Math.max(...wins.map((t) => t.pnl)) : 0;
  const largestLoss = losses.length > 0 ? Math.min(...losses.map((t) => t.pnl)) : 0;
  const avgWin = wins.length > 0 ? wins.reduce((s, t) => s + t.pnl, 0) / wins.length : 0;
  const avgLoss = losses.length > 0 ? losses.reduce((s, t) => s + t.pnl, 0) / losses.length : 0;

  let consecutiveWins = 0;
  let consecutiveLosses = 0;
  let currentWinStreak = 0;
  let currentLossStreak = 0;
  for (const trade of trades) {
    if (trade.status === 'WIN') {
      currentWinStreak += 1;
      currentLossStreak = 0;
      consecutiveWins = Math.max(consecutiveWins, currentWinStreak);
    } else {
      currentLossStreak += 1;
      currentWinStreak = 0;
      consecutiveLosses = Math.max(consecutiveLosses, currentLossStreak);
    }
  }

  const grossProfit = wins.reduce((s, t) => s + t.pnl, 0);
  const grossLoss = Math.abs(losses.reduce((s, t) => s + t.pnl, 0));
  const payoffRatio = grossLoss > 0 ? grossProfit / grossLoss : 0;

  const bestMonth = monthlyReturns.reduce(
    (best, m) => (m.netPnl > best.netPnl ? m : best),
    monthlyReturns[0] ?? { month: '-', netPnl: 0 },
  );
  const worstMonth = monthlyReturns.reduce(
    (worst, m) => (m.netPnl < worst.netPnl ? m : worst),
    monthlyReturns[0] ?? { month: '-', netPnl: 0 },
  );

  return {
    netPnl: run.net_pnl ?? 0,
    totalTrades: run.total_trades ?? 0,
    winRate: run.win_rate ?? 0,
    profitFactor: run.profit_factor ?? 0,
    maxDrawdown: run.max_drawdown ?? 0,
    sharpeRatio: run.sharpe_ratio ?? 0,
    avgProfitPerTrade: run.avg_profit_per_trade ?? 0,
    avgLossPerTrade: run.avg_loss_per_trade ?? 0,
    expectancy: (run.avg_profit_per_trade ?? 0) * (run.win_rate ?? 0) / 100 - Math.abs(run.avg_loss_per_trade ?? 0) * (1 - (run.win_rate ?? 0) / 100),
    calmarRatio: run.max_drawdown_pct ? (run.net_pnl_pct ?? 0) / Math.abs(run.max_drawdown_pct) : 0,
    sortinoRatio: 0,
    avgHoldingPeriod: run.avg_holding_period ?? 0,
    largestWin,
    largestLoss,
    consecutiveWins,
    consecutiveLosses,
    recoveryFactor: run.max_drawdown ? (run.net_pnl ?? 0) / Math.abs(run.max_drawdown) : 0,
    payoffRatio,
    avgWin,
    avgLoss: Math.abs(avgLoss),
    bestMonth: bestMonth.month ? `${bestMonth.month} (${formatPnl(bestMonth.netPnl)})` : '-',
    worstMonth: worstMonth.month ? `${worstMonth.month} (${formatPnl(worstMonth.netPnl)})` : '-',
    currentWinStreak,
    equityCurve,
    drawdownCurve,
    monthlyReturns,
    trades,
  };
}

function formatDate(iso: string): string {
  if (!iso) return '-';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

function formatPnl(value: number): string {
  const sign = value >= 0 ? '+' : '-';
  return `${sign}Rs.${Math.abs(value).toLocaleString('en-IN')}`;
}
