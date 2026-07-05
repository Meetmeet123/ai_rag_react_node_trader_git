export interface Signal {
  id: string;
  timestamp: string;
  strategy: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  price: number;
  status: 'EXECUTED' | 'PENDING' | 'IGNORED';
}

export interface BrokerOrder {
  id: string;
  time: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  type: string;
  qty: number;
  price: number;
  status: 'FILLED' | 'PARTIAL' | 'REJECTED' | 'PENDING';
}

export interface LivePosition {
  id: string;
  symbol: string;
  qty: number;
  avgPrice: number;
  ltp: number;
  pnl: number;
}

export interface LiveStrategy {
  id: string;
  name: string;
  symbol: string;
  segment: string;
  status: 'Live' | 'Paused';
  pnl: number;
  pnlPercent: number;
  positions: number;
}

export const SIGNALS: Signal[] = [
  { id: 'sig-1', timestamp: '10:24:32', strategy: 'RSI Mean Reversion', symbol: 'NIFTY FUT', side: 'BUY', price: 22456.0, status: 'EXECUTED' },
  { id: 'sig-2', timestamp: '10:22:15', strategy: 'Moving Average Cross', symbol: 'RELIANCE', side: 'SELL', price: 2891.45, status: 'EXECUTED' },
  { id: 'sig-3', timestamp: '10:18:45', strategy: 'Breakout Strategy', symbol: 'BANKNIFTY FUT', side: 'BUY', price: 48756.2, status: 'PENDING' },
  { id: 'sig-4', timestamp: '10:15:30', strategy: 'RSI Mean Reversion', symbol: 'NIFTY FUT', side: 'SELL', price: 22489.5, status: 'EXECUTED' },
  { id: 'sig-5', timestamp: '10:12:08', strategy: 'Moving Average Cross', symbol: 'SBIN', side: 'BUY', price: 789.2, status: 'EXECUTED' },
  { id: 'sig-6', timestamp: '10:08:55', strategy: 'Breakout Strategy', symbol: 'INFY', side: 'SELL', price: 1892.3, status: 'IGNORED' },
];

export const BROKER_ORDERS: BrokerOrder[] = [
  { id: 'ord-1', time: '10:24:32', symbol: 'NIFTY FUT', side: 'BUY', type: 'MARKET', qty: 75, price: 22456.0, status: 'FILLED' },
  { id: 'ord-2', time: '10:22:15', symbol: 'RELIANCE', side: 'SELL', type: 'LIMIT', qty: 50, price: 2891.45, status: 'FILLED' },
  { id: 'ord-3', time: '10:18:45', symbol: 'BANKNIFTY FUT', side: 'BUY', type: 'SL', qty: 30, price: 48756.2, status: 'PARTIAL' },
  { id: 'ord-4', time: '10:15:30', symbol: 'NIFTY FUT', side: 'SELL', type: 'MARKET', qty: 25, price: 22489.5, status: 'FILLED' },
  { id: 'ord-5', time: '10:12:08', symbol: 'SBIN', side: 'BUY', type: 'MARKET', qty: 100, price: 789.2, status: 'FILLED' },
];

export const LIVE_POSITIONS: LivePosition[] = [
  { id: 'lpos-1', symbol: 'NIFTY 25JUL24FUT', qty: 75, avgPrice: 22412, ltp: 22456, pnl: 3300 },
  { id: 'lpos-2', symbol: 'BANKNIFTY 25JUL24FUT', qty: -30, avgPrice: 48890, ltp: 48756, pnl: 4020 },
  { id: 'lpos-3', symbol: 'RELIANCE', qty: 50, avgPrice: 2867, ltp: 2891, pnl: 1200 },
];

export const LIVE_STRATEGIES: LiveStrategy[] = [
  { id: 'ls-1', name: 'RSI Mean Reversion', symbol: 'NIFTY 50', segment: 'F&O', status: 'Live', pnl: 8340, pnlPercent: 2.14, positions: 2 },
  { id: 'ls-2', name: 'Moving Average Cross', symbol: 'BANKNIFTY FUT', segment: 'F&O', status: 'Live', pnl: -2100, pnlPercent: -0.45, positions: 1 },
  { id: 'ls-3', name: 'Breakout Strategy', symbol: 'RELIANCE', segment: 'EQ', status: 'Paused', pnl: 0, pnlPercent: 0, positions: 0 },
];

export const PNL_SUMMARY = {
  total: 24560,
  realized: 18200,
  unrealized: 6360,
  changePercent: 2.46,
};
