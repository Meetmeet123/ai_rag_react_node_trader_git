import type { BacktestStrategy, BacktestResult, BacktestConfig, Trade, EquityPoint, DrawdownPoint, MonthlyReturn } from './types';

export const BACKTEST_STRATEGIES: BacktestStrategy[] = [
  {
    id: '1',
    name: 'RSI Mean Reversion',
    description: 'Buy when RSI crosses above 30, sell when above 70',
    segment: 'NSE Stocks',
    status: 'active',
    lastModified: '2d ago',
  },
  {
    id: '2',
    name: 'Golden Cross Scanner',
    description: 'SMA 50 crosses above SMA 200 with volume confirmation',
    segment: 'NSE Stocks',
    status: 'paper',
    lastModified: '1w ago',
  },
  {
    id: '3',
    name: 'BankNifty Breakout',
    description: 'ATR-based breakout with trailing stop',
    segment: 'NFO Futures',
    status: 'draft',
    lastModified: '3d ago',
  },
  {
    id: '4',
    name: 'Options Straddle',
    description: 'Entry at 9:20 AM, exit at 3:15 PM',
    segment: 'NFO Options',
    status: 'draft',
    lastModified: '5d ago',
  },
];

export const DEFAULT_CONFIG: BacktestConfig = {
  strategyId: '',
  symbol: 'NIFTY 50',
  segment: 'Stocks',
  exchange: 'NSE',
  timeframe: '1D',
  startDate: '2024-06-01',
  endDate: '2024-12-01',
  initialCapital: 1000000,
  positionSizing: 'percent',
  lotSize: 1,
  stopLossType: 'fixed',
  stopLossValue: 1,
  targetType: 'fixed',
  targetValue: 2,
  maxTradesPerDay: 10,
  maxLossPerDay: 50000,
  slippage: 0.05,
  brokerage: 20,
  stt: 0.025,
  gst: 18,
  exchangeCharges: 0.00325,
  sebiCharges: 0.0001,
};

function generateEquityCurve(): EquityPoint[] {
  const points: EquityPoint[] = [];
  const startDate = new Date('2024-06-01');
  const endDate = new Date('2024-12-01');
  let value = 1000000;
  let trend = 1;
  let trendDays = 0;

  for (let d = new Date(startDate); d <= endDate; d.setDate(d.getDate() + 1)) {
    if (d.getDay() === 0 || d.getDay() === 6) continue;

    trendDays++;
    if (trendDays > 15 && Math.random() > 0.7) {
      trend *= -1;
      trendDays = 0;
    }

    const dailyReturn = (Math.random() * 0.008 - 0.003) * trend + (Math.random() * 0.004 - 0.002);
    value = value * (1 + dailyReturn);
    value = Math.max(value, 950000);

    points.push({
      date: d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }),
      value: Math.round(value),
    });
  }

  return points;
}

function generateDrawdownCurve(equity: EquityPoint[]): DrawdownPoint[] {
  let peak = equity[0]?.value ?? 1000000;
  return equity.map((p) => {
    if (p.value > peak) peak = p.value;
    const dd = ((peak - p.value) / peak) * 100;
    return { date: p.date, value: Math.max(0, dd) };
  });
}

function generateTrades(): Trade[] {
  const trades: Trade[] = [];
  const symbols = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK'];
  const startDate = new Date('2024-06-03');

  for (let i = 0; i < 50; i++) {
    const entryDate = new Date(startDate);
    entryDate.setDate(entryDate.getDate() + i * 3 + Math.floor(Math.random() * 2));
    if (entryDate.getDay() === 0) entryDate.setDate(entryDate.getDate() + 1);
    if (entryDate.getDay() === 6) entryDate.setDate(entryDate.getDate() + 2);

    const exitDate = new Date(entryDate);
    exitDate.setDate(exitDate.getDate() + 1 + Math.floor(Math.random() * 4));
    if (exitDate.getDay() === 0) exitDate.setDate(exitDate.getDate() + 1);
    if (exitDate.getDay() === 6) exitDate.setDate(exitDate.getDate() + 2);

    const isWin = Math.random() > 0.38;
    const entryPrice = 21000 + Math.random() * 3000;
    const pnlPercent = isWin
      ? (Math.random() * 3.5 + 0.3)
      : -(Math.random() * 2.5 + 0.2);
    const pnl = Math.round((pnlPercent / 100) * entryPrice * 5);

    trades.push({
      id: i + 1,
      entryDate: entryDate.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }),
      exitDate: exitDate.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }),
      symbol: symbols[i % symbols.length],
      side: Math.random() > 0.2 ? 'Long' : 'Short',
      entryPrice: Math.round(entryPrice),
      exitPrice: Math.round(entryPrice * (1 + pnlPercent / 100)),
      pnl,
      pnlPercent: Math.round(pnlPercent * 100) / 100,
      status: pnl > 0 ? 'WIN' : 'LOSS',
    });
  }

  return trades;
}

function generateMonthlyReturns(): MonthlyReturn[] {
  return [
    { month: 'Jun 2024', trades: 9, wins: 6, losses: 3, winRate: 66.7, grossPnl: 85200, charges: 4850, netPnl: 80350 },
    { month: 'Jul 2024', trades: 8, wins: 5, losses: 3, winRate: 62.5, grossPnl: 45600, charges: 4320, netPnl: 41280 },
    { month: 'Aug 2024', trades: 7, wins: 3, losses: 4, winRate: 42.9, grossPnl: -32400, charges: 3780, netPnl: -36180 },
    { month: 'Sep 2024', trades: 9, wins: 6, losses: 3, winRate: 66.7, grossPnl: 98400, charges: 4850, netPnl: 93550 },
    { month: 'Oct 2024', trades: 8, wins: 4, losses: 4, winRate: 50.0, grossPnl: 12800, charges: 4320, netPnl: 8480 },
    { month: 'Nov 2024', trades: 9, wins: 6, losses: 3, winRate: 66.7, grossPnl: 67800, charges: 4850, netPnl: 62950 },
  ];
}

const equityCurve = generateEquityCurve();
const drawdownCurve = generateDrawdownCurve(equityCurve);
const trades = generateTrades();
const monthlyReturns = generateMonthlyReturns();

const totalPnl = trades.reduce((s, t) => s + t.pnl, 0);
const winCount = trades.filter((t) => t.status === 'WIN').length;
const lossCount = trades.filter((t) => t.status === 'LOSS').length;
const winRate = Math.round((winCount / trades.length) * 1000) / 10;
const grossProfit = trades.filter((t) => t.pnl > 0).reduce((s, t) => s + t.pnl, 0);
const grossLoss = Math.abs(trades.filter((t) => t.pnl < 0).reduce((s, t) => s + t.pnl, 0));
const profitFactor = Math.round((grossProfit / Math.max(grossLoss, 1)) * 100) / 100;

export const MOCK_RESULT: BacktestResult = {
  netPnl: totalPnl,
  totalTrades: trades.length,
  winRate,
  profitFactor,
  maxDrawdown: -34200,
  sharpeRatio: 1.62,
  avgProfitPerTrade: Math.round((grossProfit / Math.max(winCount, 1)) * 100) / 100,
  avgLossPerTrade: Math.round((grossLoss / Math.max(lossCount, 1)) * 100) / 100,
  expectancy: 1560,
  calmarRatio: 3.64,
  sortinoRatio: 2.31,
  avgHoldingPeriod: 3.2,
  largestWin: 67800,
  largestLoss: -34200,
  consecutiveWins: 7,
  consecutiveLosses: 4,
  recoveryFactor: 3.64,
  payoffRatio: 1.98,
  avgWin: 8234,
  avgLoss: -4156,
  bestMonth: 'Sep 2024 (+\u20b993,550)',
  worstMonth: 'Aug 2024 (-\u20b936,180)',
  currentWinStreak: 3,
  equityCurve,
  drawdownCurve,
  monthlyReturns,
  trades,
};
