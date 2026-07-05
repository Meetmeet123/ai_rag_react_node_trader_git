export type BacktestStep = 1 | 2 | 3 | 4;

export interface BacktestStrategy {
  id: string;
  name: string;
  description: string;
  segment: string;
  status: string;
  lastModified: string;
}

export interface BacktestConfig {
  strategyId: string;
  symbol: string;
  segment: string;
  exchange: string;
  timeframe: string;
  startDate: string;
  endDate: string;
  initialCapital: number;
  positionSizing: 'fixed' | 'percent' | 'risk';
  lotSize: number;
  stopLossType: 'fixed' | 'trailing' | 'atr';
  stopLossValue: number;
  targetType: 'fixed' | 'rr' | 'atr';
  targetValue: number;
  maxTradesPerDay: number;
  maxLossPerDay: number;
  slippage: number;
  brokerage: number;
  stt: number;
  gst: number;
  exchangeCharges: number;
  sebiCharges: number;
}

export interface Trade {
  id: number;
  entryDate: string;
  exitDate: string;
  symbol: string;
  side: 'Long' | 'Short';
  entryPrice: number;
  exitPrice: number;
  pnl: number;
  pnlPercent: number;
  status: 'WIN' | 'LOSS';
}

export interface MonthlyReturn {
  month: string;
  trades: number;
  wins: number;
  losses: number;
  winRate: number;
  grossPnl: number;
  charges: number;
  netPnl: number;
}

export interface BacktestResult {
  netPnl: number;
  totalTrades: number;
  winRate: number;
  profitFactor: number;
  maxDrawdown: number;
  sharpeRatio: number;
  avgProfitPerTrade: number;
  avgLossPerTrade: number;
  expectancy: number;
  calmarRatio: number;
  sortinoRatio: number;
  avgHoldingPeriod: number;
  largestWin: number;
  largestLoss: number;
  consecutiveWins: number;
  consecutiveLosses: number;
  recoveryFactor: number;
  payoffRatio: number;
  avgWin: number;
  avgLoss: number;
  bestMonth: string;
  worstMonth: string;
  currentWinStreak: number;
  equityCurve: EquityPoint[];
  drawdownCurve: DrawdownPoint[];
  monthlyReturns: MonthlyReturn[];
  trades: Trade[];
}

export interface EquityPoint {
  date: string;
  value: number;
}

export interface DrawdownPoint {
  date: string;
  value: number;
}
