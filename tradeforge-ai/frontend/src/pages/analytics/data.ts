// Analytics Mock Data

export interface Trade {
  id: string;
  date: string;
  symbol: string;
  strategy: string;
  side: 'Long' | 'Short';
  entryPrice: number;
  exitPrice: number;
  qty: number;
  pnl: number;
  pnlPercent: number;
  holdingPeriod: string;
  notes: string;
  tags: string[];
}

export interface StrategyPerformance {
  name: string;
  trades: number;
  wins: number;
  losses: number;
  winRate: number;
  netPnl: number;
  avgProfit: number;
  avgLoss: number;
  profitFactor: number;
  sharpe: number;
  maxDrawdown: number;
}

export interface MonthlyData {
  month: string;
  trades: number;
  wins: number;
  losses: number;
  winRate: number;
  grossPnl: number;
  brokerage: number;
  netPnl: number;
  cumulative: number;
  bestTrade: number;
  worstTrade: number;
}

export interface DailyPnl {
  date: string;
  pnl: number;
  cumulative: number;
}

// KPI Summary
export const NET_PNL = 145000;
export const WIN_RATE = 58;
export const PROFIT_FACTOR = 1.85;
export const SHARPE_RATIO = 1.42;
export const MAX_DRAWDOWN = -45000;
export const TOTAL_TRADES = 124;
export const AVG_HOLDING_PERIOD = '2.3 days';
export const BEST_TRADE = 34200;
export const WORST_TRADE = -18500;

// Gross metrics
export const GROSS_PROFIT = 253500;
export const GROSS_LOSS = -128940;
export const EXPECTANCY = 2595;
export const AVG_TRADE = 1169;
export const AVG_WIN = 8450;
export const AVG_LOSS = -3200;
export const LARGEST_WIN = 34200;
export const LARGEST_LOSS = -18500;
export const TOTAL_COMMISSION = 2880;

// Strategy Performance
export const strategyPerformance: StrategyPerformance[] = [
  { name: 'Momentum Crossover', trades: 32, wins: 20, losses: 12, winRate: 62.5, netPnl: 68400, avgProfit: 5200, avgLoss: -2100, profitFactor: 2.45, sharpe: 1.68, maxDrawdown: -12500 },
  { name: 'RSI Reversal', trades: 28, wins: 15, losses: 13, winRate: 53.6, netPnl: 28500, avgProfit: 4800, avgLoss: -2800, profitFactor: 1.56, sharpe: 1.12, maxDrawdown: -18200 },
  { name: 'Bollinger Bounce', trades: 24, wins: 15, losses: 9, winRate: 62.5, netPnl: 32100, avgProfit: 3600, avgLoss: -1900, profitFactor: 1.89, sharpe: 1.45, maxDrawdown: -9800 },
  { name: 'Breakout Scout', trades: 22, wins: 11, losses: 11, winRate: 50.0, netPnl: 12800, avgProfit: 4100, avgLoss: -3100, profitFactor: 1.21, sharpe: 0.85, maxDrawdown: -22500 },
  { name: 'Mean Reversion', trades: 18, wins: 12, losses: 6, winRate: 66.7, netPnl: 3200, avgProfit: 2900, avgLoss: -2400, profitFactor: 2.42, sharpe: 1.55, maxDrawdown: -7200 },
];

// Daily P&L for 6 months (~126 trading days)
const generateDailyPnl = (): DailyPnl[] => {
  const data: DailyPnl[] = [];
  let cumulative = 0;
  const baseDate = new Date('2025-01-01');

  const dailyValues = [
    3200, -1500, 4800, -2200, 1200, 5600, -3800, 2100, -900, 4200,
    -1800, 3500, -4100, 2800, 1500, -3200, 6800, -1200, 4500, -2800,
    5200, -3500, 1800, 4200, -2100, 2900, -4500, 7200, -1800, 3800,
    5200, -2900, 1500, 6800, -3200, 4200, -1500, 5600, -4100, 2800,
    3200, -2200, 4800, -1200, 6200, -3800, 2100, 4500, -2800, 3800,
    -1500, 5200, -3200, 6800, -4100, 2800, 4200, -1800, 5600, -2900,
    7200, -3500, 1800, 4800, -2200, 3200, -1200, 5600, -3800, 4200,
    2800, -4500, 6800, -1800, 5200, -2900, 3800, -1500, 6200, -3200,
    4200, -2100, 4800, -1200, 5600, -4100, 3200, -2800, 7200, -1800,
    4500, -3500, 2800, -1500, 5200, -2200, 6800, -3800, 4200, -1200,
    5600, -2900, 3200, -4100, 4800, -1800, 6200, -3200, 2800, -1500,
    5200, -2800, 3800, -2200, 6800, -4500, 4200, -1200, 5600, -3800,
    7200, -1800, 3200, -2900, 4800, -1500, 5200, -4100, 2800, -2200,
    6200, -3200, 4200, -1800, 5600, -1200, 3800, -3500, 6800, -2800,
    5200, -1500, 7200, -4100, 3200, -2200, 4800, -3800, 2800, -1200,
  ];

  for (let i = 0; i < dailyValues.length; i++) {
    const date = new Date(baseDate);
    date.setDate(date.getDate() + i);
    // Skip weekends
    const day = date.getDay();
    if (day === 0 || day === 6) continue;

    const pnl = dailyValues[data.length % dailyValues.length];
    cumulative += pnl;
    data.push({
      date: date.toISOString().split('T')[0],
      pnl,
      cumulative,
    });
  }

  return data;
};

export const dailyPnl: DailyPnl[] = generateDailyPnl();

// Drawdown data
export const drawdownData = dailyPnl.map((d, i) => {
  const peak = Math.max(...dailyPnl.slice(0, i + 1).map(x => x.cumulative));
  const drawdown = d.cumulative - peak;
  const drawdownPercent = (drawdown / (peak || 1)) * 100;
  return {
    date: d.date,
    drawdown,
    drawdownPercent: Math.round(drawdownPercent * 100) / 100,
  };
});

// Monthly data
export const monthlyData: MonthlyData[] = [
  { month: 'Jan 2025', trades: 22, wins: 12, losses: 10, winRate: 54.5, grossPnl: 28500, brokerage: 520, netPnl: 27980, cumulative: 27980, bestTrade: 8200, worstTrade: -6800 },
  { month: 'Feb 2025', trades: 18, wins: 10, losses: 8, winRate: 55.6, grossPnl: 18200, brokerage: 420, netPnl: 17780, cumulative: 45760, bestTrade: 6500, worstTrade: -5200 },
  { month: 'Mar 2025', trades: 24, wins: 15, losses: 9, winRate: 62.5, grossPnl: 42800, brokerage: 560, netPnl: 42240, cumulative: 88000, bestTrade: 12400, worstTrade: -4500 },
  { month: 'Apr 2025', trades: 20, wins: 13, losses: 7, winRate: 65.0, grossPnl: 35200, brokerage: 480, netPnl: 34720, cumulative: 122720, bestTrade: 10200, worstTrade: -3800 },
  { month: 'May 2025', trades: 22, wins: 12, losses: 10, winRate: 54.5, grossPnl: 21500, brokerage: 520, netPnl: 20980, cumulative: 143700, bestTrade: 7800, worstTrade: -7200 },
  { month: 'Jun 2025', trades: 18, wins: 10, losses: 8, winRate: 55.6, grossPnl: 1800, brokerage: 380, netPnl: 1300, cumulative: 145000, bestTrade: 3400, worstTrade: -18500 },
];

// Trade journal
export const trades: Trade[] = [
  { id: 'T001', date: '2025-06-28', symbol: 'RELIANCE', strategy: 'Momentum Crossover', side: 'Long', entryPrice: 2875.2, exitPrice: 2924.8, qty: 50, pnl: 2480, pnlPercent: 1.73, holdingPeriod: '2 days', notes: 'Strong momentum after earnings', tags: ['earnings', 'momentum'] },
  { id: 'T002', date: '2025-06-27', symbol: 'INFY', strategy: 'RSI Reversal', side: 'Short', entryPrice: 1862.5, exitPrice: 1848.2, qty: 30, pnl: 429, pnlPercent: 0.77, holdingPeriod: '1 day', notes: 'RSI overbought reversal', tags: ['rsi', 'reversal'] },
  { id: 'T003', date: '2025-06-26', symbol: 'TCS', strategy: 'Bollinger Bounce', side: 'Long', entryPrice: 4218.4, exitPrice: 4265.1, qty: 25, pnl: 1168, pnlPercent: 1.11, holdingPeriod: '3 days', notes: 'Bounced off lower band', tags: ['bollinger', 'mean-reversion'] },
  { id: 'T004', date: '2025-06-25', symbol: 'RELIANCE', strategy: 'Momentum Crossover', side: 'Long', entryPrice: 2845.8, exitPrice: 2832.5, qty: 40, pnl: -532, pnlPercent: -0.47, holdingPeriod: '1 day', notes: 'False breakout, stopped out', tags: ['false-breakout', 'stop-loss'] },
  { id: 'T005', date: '2025-06-24', symbol: 'HDFCBANK', strategy: 'Breakout Scout', side: 'Long', entryPrice: 1856.3, exitPrice: 1882.5, qty: 35, pnl: 917, pnlPercent: 1.41, holdingPeriod: '2 days', notes: 'Clean breakout from consolidation', tags: ['breakout', 'bank-nifty'] },
  { id: 'T006', date: '2025-06-23', symbol: 'INFY', strategy: 'RSI Reversal', side: 'Long', entryPrice: 1832.1, exitPrice: 1845.6, qty: 30, pnl: 405, pnlPercent: 0.74, holdingPeriod: '1 day', notes: 'Oversold bounce', tags: ['oversold', 'bounce'] },
  { id: 'T007', date: '2025-06-22', symbol: 'TCS', strategy: 'Bollinger Bounce', side: 'Short', entryPrice: 4285.6, exitPrice: 4252.3, qty: 20, pnl: 666, pnlPercent: 0.78, holdingPeriod: '2 days', notes: 'Upper band rejection', tags: ['bollinger', 'short'] },
  { id: 'T008', date: '2025-06-21', symbol: 'RELIANCE', strategy: 'Momentum Crossover', side: 'Long', entryPrice: 2812.4, exitPrice: 2856.8, qty: 50, pnl: 2220, pnlPercent: 1.58, holdingPeriod: '4 days', notes: 'Golden cross confirmed', tags: ['golden-cross', 'trend'] },
  { id: 'T009', date: '2025-06-20', symbol: 'SBIN', strategy: 'Mean Reversion', side: 'Long', entryPrice: 756.2, exitPrice: 748.5, qty: 60, pnl: -462, pnlPercent: -1.02, holdingPeriod: '1 day', notes: 'Mean reversion failed', tags: ['mean-reversion', 'loss'] },
  { id: 'T010', date: '2025-06-19', symbol: 'ICICIBANK', strategy: 'Breakout Scout', side: 'Long', entryPrice: 1245.8, exitPrice: 1268.2, qty: 25, pnl: 560, pnlPercent: 1.80, holdingPeriod: '2 days', notes: 'ATH breakout', tags: ['breakout', 'ath'] },
  { id: 'T011', date: '2025-06-18', symbol: 'INFY', strategy: 'RSI Reversal', side: 'Short', entryPrice: 1885.2, exitPrice: 1872.5, qty: 35, pnl: 445, pnlPercent: 0.67, holdingPeriod: '1 day', notes: '', tags: ['rsi', 'short'] },
  { id: 'T012', date: '2025-06-17', symbol: 'RELIANCE', strategy: 'Momentum Crossover', side: 'Long', entryPrice: 2785.6, exitPrice: 2812.4, qty: 45, pnl: 1206, pnlPercent: 0.96, holdingPeriod: '3 days', notes: 'Trend continuation', tags: ['trend', 'momentum'] },
  { id: 'T013', date: '2025-06-16', symbol: 'TCS', strategy: 'Bollinger Bounce', side: 'Long', entryPrice: 4185.2, exitPrice: 4202.8, qty: 20, pnl: 352, pnlPercent: 0.42, holdingPeriod: '1 day', notes: 'Quick scalp off lower band', tags: ['scalp', 'bollinger'] },
  { id: 'T014', date: '2025-06-15', symbol: 'HDFCBANK', strategy: 'Breakout Scout', side: 'Long', entryPrice: 1825.4, exitPrice: 1818.2, qty: 30, pnl: -216, pnlPercent: -0.39, holdingPeriod: '1 day', notes: 'Fake breakout', tags: ['fakeout', 'loss'] },
  { id: 'T015', date: '2025-06-14', symbol: 'RELIANCE', strategy: 'Momentum Crossover', side: 'Long', entryPrice: 2756.8, exitPrice: 2785.2, qty: 50, pnl: 1420, pnlPercent: 1.03, holdingPeriod: '2 days', notes: 'Strong volume surge', tags: ['volume', 'momentum'] },
  { id: 'T016', date: '2025-06-13', symbol: 'INFY', strategy: 'RSI Reversal', side: 'Long', entryPrice: 1802.5, exitPrice: 1825.6, qty: 40, pnl: 924, pnlPercent: 1.28, holdingPeriod: '3 days', notes: 'Deep oversold bounce', tags: ['oversold', 'bounce'] },
  { id: 'T017', date: '2025-06-12', symbol: 'TCS', strategy: 'Bollinger Bounce', side: 'Short', entryPrice: 4256.8, exitPrice: 4228.5, qty: 25, pnl: 708, pnlPercent: 0.66, holdingPeriod: '2 days', notes: '', tags: ['bollinger', 'short'] },
  { id: 'T018', date: '2025-06-11', symbol: 'SBIN', strategy: 'Mean Reversion', side: 'Long', entryPrice: 742.5, exitPrice: 748.2, qty: 50, pnl: 285, pnlPercent: 0.77, holdingPeriod: '1 day', notes: 'Mean reversion worked', tags: ['mean-reversion', 'profit'] },
  { id: 'T019', date: '2025-06-10', symbol: 'RELIANCE', strategy: 'Momentum Crossover', side: 'Long', entryPrice: 2725.4, exitPrice: 2718.2, qty: 45, pnl: -324, pnlPercent: -0.26, holdingPeriod: '1 day', notes: 'Gap down stop', tags: ['gap-down', 'stop'] },
  { id: 'T020', date: '2025-06-09', symbol: 'ICICIBANK', strategy: 'Breakout Scout', side: 'Long', entryPrice: 1218.5, exitPrice: 1235.2, qty: 30, pnl: 501, pnlPercent: 1.37, holdingPeriod: '2 days', notes: 'Clean range breakout', tags: ['breakout', 'range'] },
];

// Extend to 30+ trades
for (let i = 21; i <= 35; i++) {
  const symbols = ['RELIANCE', 'INFY', 'TCS', 'HDFCBANK', 'SBIN', 'ICICIBANK', 'BHARTIARTL', 'ITC'];
  const strategies = ['Momentum Crossover', 'RSI Reversal', 'Bollinger Bounce', 'Breakout Scout', 'Mean Reversion'];
  const sides: Array<'Long' | 'Short'> = ['Long', 'Short'];
  const symbol = symbols[i % symbols.length];
  const strategy = strategies[i % strategies.length];
  const side = sides[i % sides.length];
  const entryPrice = 1000 + (i * 25);
  const pnl = [-18500, 5200, -3200, 7800, 4200, -1500, 6800, -2800, 9200, -4200, 5800, -1800, 7200, -3800, 4500][i - 21] || 1200;
  const exitPrice = side === 'Long' ? entryPrice + pnl / 50 : entryPrice - pnl / 50;

  trades.push({
    id: `T${String(i).padStart(3, '0')}`,
    date: `2025-05-${String(36 - i).padStart(2, '0')}`,
    symbol,
    strategy,
    side,
    entryPrice,
    exitPrice,
    qty: 25 + (i % 5) * 10,
    pnl,
    pnlPercent: Number(((pnl / (entryPrice * (25 + (i % 5) * 10))) * 100).toFixed(2)),
    holdingPeriod: `${1 + (i % 4)} days`,
    notes: '',
    tags: [],
  });
}
