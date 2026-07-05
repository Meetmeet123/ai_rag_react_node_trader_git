// Paper Trading Mock Data

export interface Strategy {
  id: string;
  name: string;
  symbol: string;
  segment: string;
  status: 'Running' | 'Paused' | 'Stopped';
  pnl: number;
  activeSince: string;
  signalCount: number;
  allocation: number;
}

export interface Signal {
  id: string;
  time: string;
  strategy: string;
  symbol: string;
  type: 'LONG' | 'SHORT';
  signal: 'ENTRY' | 'EXIT';
  price: number;
  executedPrice: number;
  slippage: number;
  pnl: number | null;
  status: 'Executed' | 'Pending' | 'Failed';
}

export interface Position {
  id: string;
  symbol: string;
  qty: number;
  avgPrice: number;
  ltp: number;
  pnl: number;
  pnlPercent: number;
  strategy: string;
  type: 'LONG' | 'SHORT';
}

export interface PaperOrder {
  id: string;
  time: string;
  symbol: string;
  type: 'BUY' | 'SELL';
  qty: number;
  price: number;
  status: 'Filled' | 'Partial' | 'Pending' | 'Rejected' | 'Cancelled';
  strategy: string;
}

export const STARTING_CAPITAL = 1000000;
export const USED_MARGIN = 342000;
export const AVAILABLE_BALANCE = STARTING_CAPITAL - USED_MARGIN;
export const TODAY_PNL = 12450;
export const OVERALL_PNL = 45680;

export const strategies: Strategy[] = [
  {
    id: '1',
    name: 'Momentum Crossover',
    symbol: 'RELIANCE',
    segment: 'NSE Stocks',
    status: 'Running',
    pnl: 15230,
    activeSince: '2025-06-15 09:15:00',
    signalCount: 47,
    allocation: 150000,
  },
  {
    id: '2',
    name: 'RSI Reversal',
    symbol: 'INFY',
    segment: 'NSE Stocks',
    status: 'Running',
    pnl: -4120,
    activeSince: '2025-06-20 09:15:00',
    signalCount: 32,
    allocation: 100000,
  },
  {
    id: '3',
    name: 'Bollinger Bounce',
    symbol: 'TCS',
    segment: 'NSE Stocks',
    status: 'Running',
    pnl: 8900,
    activeSince: '2025-06-25 09:15:00',
    signalCount: 28,
    allocation: 92000,
  },
];

export const signals: Signal[] = [
  { id: 's1', time: '10:45:23', strategy: 'Momentum Crossover', symbol: 'RELIANCE', type: 'LONG', signal: 'ENTRY', price: 2891.5, executedPrice: 2891.75, slippage: 0.25, pnl: null, status: 'Executed' },
  { id: 's2', time: '10:42:10', strategy: 'RSI Reversal', symbol: 'INFY', type: 'SHORT', signal: 'ENTRY', price: 1856.3, executedPrice: 1856.0, slippage: -0.3, pnl: null, status: 'Executed' },
  { id: 's3', time: '10:38:55', strategy: 'Bollinger Bounce', symbol: 'TCS', type: 'LONG', signal: 'ENTRY', price: 4234.8, executedPrice: 4235.0, slippage: 0.2, pnl: null, status: 'Executed' },
  { id: 's4', time: '10:35:42', strategy: 'Momentum Crossover', symbol: 'RELIANCE', type: 'LONG', signal: 'EXIT', price: 2885.2, executedPrice: 2885.0, slippage: -0.2, pnl: 3250, status: 'Executed' },
  { id: 's5', time: '10:32:18', strategy: 'RSI Reversal', symbol: 'INFY', type: 'SHORT', signal: 'EXIT', price: 1862.1, executedPrice: 1862.3, slippage: 0.2, pnl: -1850, status: 'Executed' },
  { id: 's6', time: '10:28:33', strategy: 'Bollinger Bounce', symbol: 'TCS', type: 'LONG', signal: 'EXIT', price: 4241.5, executedPrice: 4241.2, slippage: -0.3, pnl: 1580, status: 'Executed' },
  { id: 's7', time: '10:25:47', strategy: 'Momentum Crossover', symbol: 'RELIANCE', type: 'LONG', signal: 'ENTRY', price: 2878.9, executedPrice: 2879.1, slippage: 0.2, pnl: null, status: 'Executed' },
  { id: 's8', time: '10:22:15', strategy: 'RSI Reversal', symbol: 'INFY', type: 'LONG', signal: 'ENTRY', price: 1845.6, executedPrice: 1845.8, slippage: 0.2, pnl: null, status: 'Executed' },
  { id: 's9', time: '10:18:50', strategy: 'Momentum Crossover', symbol: 'RELIANCE', type: 'LONG', signal: 'EXIT', price: 2872.4, executedPrice: 2872.2, slippage: -0.2, pnl: 2100, status: 'Executed' },
  { id: 's10', time: '10:15:22', strategy: 'Bollinger Bounce', symbol: 'TCS', type: 'SHORT', signal: 'ENTRY', price: 4256.3, executedPrice: 4256.0, slippage: -0.3, pnl: null, status: 'Executed' },
  { id: 's11', time: '10:12:08', strategy: 'RSI Reversal', symbol: 'INFY', type: 'LONG', signal: 'EXIT', price: 1852.3, executedPrice: 1852.5, slippage: 0.2, pnl: -980, status: 'Executed' },
  { id: 's12', time: '10:08:45', strategy: 'Momentum Crossover', symbol: 'RELIANCE', type: 'LONG', signal: 'ENTRY', price: 2865.7, executedPrice: 2865.9, slippage: 0.2, pnl: null, status: 'Executed' },
  { id: 's13', time: '10:05:30', strategy: 'Bollinger Bounce', symbol: 'TCS', type: 'SHORT', signal: 'EXIT', price: 4248.9, executedPrice: 4248.7, slippage: -0.2, pnl: 1120, status: 'Executed' },
  { id: 's14', time: '10:02:18', strategy: 'Momentum Crossover', symbol: 'RELIANCE', type: 'LONG', signal: 'EXIT', price: 2859.3, executedPrice: 2859.1, slippage: -0.2, pnl: -1450, status: 'Executed' },
  { id: 's15', time: '09:58:55', strategy: 'RSI Reversal', symbol: 'INFY', type: 'SHORT', signal: 'ENTRY', price: 1868.4, executedPrice: 1868.2, slippage: -0.2, pnl: null, status: 'Executed' },
  { id: 's16', time: '09:55:42', strategy: 'Bollinger Bounce', symbol: 'TCS', type: 'LONG', signal: 'ENTRY', price: 4228.5, executedPrice: 4228.7, slippage: 0.2, pnl: null, status: 'Pending' },
  { id: 's17', time: '09:52:28', strategy: 'Momentum Crossover', symbol: 'RELIANCE', type: 'LONG', signal: 'ENTRY', price: 2852.1, executedPrice: 2852.0, slippage: -0.1, pnl: null, status: 'Executed' },
  { id: 's18', time: '09:48:15', strategy: 'RSI Reversal', symbol: 'INFY', type: 'LONG', signal: 'ENTRY', price: 1839.2, executedPrice: 1839.0, slippage: -0.2, pnl: null, status: 'Failed' },
  { id: 's19', time: '09:45:00', strategy: 'Bollinger Bounce', symbol: 'TCS', type: 'SHORT', signal: 'EXIT', price: 4262.8, executedPrice: 4262.5, slippage: -0.3, pnl: 2340, status: 'Executed' },
  { id: 's20', time: '09:42:33', strategy: 'Momentum Crossover', symbol: 'RELIANCE', type: 'LONG', signal: 'EXIT', price: 2848.6, executedPrice: 2848.4, slippage: -0.2, pnl: 1890, status: 'Executed' },
];

export const positions: Position[] = [
  { id: 'p1', symbol: 'RELIANCE', qty: 50, avgPrice: 2879.1, ltp: 2891.75, pnl: 632, pnlPercent: 0.44, strategy: 'Momentum Crossover', type: 'LONG' },
  { id: 'p2', symbol: 'INFY', qty: -30, avgPrice: 1856.0, ltp: 1852.5, pnl: 105, pnlPercent: 0.19, strategy: 'RSI Reversal', type: 'SHORT' },
  { id: 'p3', symbol: 'TCS', qty: 25, avgPrice: 4235.0, ltp: 4241.2, pnl: 155, pnlPercent: 0.15, strategy: 'Bollinger Bounce', type: 'LONG' },
  { id: 'p4', symbol: 'RELIANCE', qty: 30, avgPrice: 2865.9, ltp: 2859.1, pnl: -204, pnlPercent: -0.24, strategy: 'Momentum Crossover', type: 'LONG' },
  { id: 'p5', symbol: 'TCS', qty: -20, avgPrice: 4256.0, ltp: 4248.7, pnl: 146, pnlPercent: 0.17, strategy: 'Bollinger Bounce', type: 'SHORT' },
];

export const paperOrders: PaperOrder[] = [
  { id: 'ORD001', time: '10:45:23', symbol: 'RELIANCE', type: 'BUY', qty: 50, price: 2891.75, status: 'Filled', strategy: 'Momentum Crossover' },
  { id: 'ORD002', time: '10:42:10', symbol: 'INFY', type: 'SELL', qty: 30, price: 1856.0, status: 'Filled', strategy: 'RSI Reversal' },
  { id: 'ORD003', time: '10:38:55', symbol: 'TCS', type: 'BUY', qty: 25, price: 4235.0, status: 'Filled', strategy: 'Bollinger Bounce' },
  { id: 'ORD004', time: '10:35:42', symbol: 'RELIANCE', type: 'SELL', qty: 50, price: 2885.0, status: 'Filled', strategy: 'Momentum Crossover' },
  { id: 'ORD005', time: '10:32:18', symbol: 'INFY', type: 'BUY', qty: 30, price: 1862.3, status: 'Filled', strategy: 'RSI Reversal' },
  { id: 'ORD006', time: '10:28:33', symbol: 'TCS', type: 'SELL', qty: 25, price: 4241.2, status: 'Filled', strategy: 'Bollinger Bounce' },
  { id: 'ORD007', time: '10:25:47', symbol: 'RELIANCE', type: 'BUY', qty: 50, price: 2879.1, status: 'Filled', strategy: 'Momentum Crossover' },
  { id: 'ORD008', time: '10:22:15', symbol: 'INFY', type: 'BUY', qty: 40, price: 1845.8, status: 'Filled', strategy: 'RSI Reversal' },
  { id: 'ORD009', time: '10:18:50', symbol: 'RELIANCE', type: 'SELL', qty: 50, price: 2872.2, status: 'Filled', strategy: 'Momentum Crossover' },
  { id: 'ORD010', time: '10:15:22', symbol: 'TCS', type: 'SELL', qty: 20, price: 4256.0, status: 'Filled', strategy: 'Bollinger Bounce' },
  { id: 'ORD011', time: '10:12:08', symbol: 'INFY', type: 'SELL', qty: 40, price: 1852.5, status: 'Filled', strategy: 'RSI Reversal' },
  { id: 'ORD012', time: '10:08:45', symbol: 'RELIANCE', type: 'BUY', qty: 30, price: 2865.9, status: 'Filled', strategy: 'Momentum Crossover' },
  { id: 'ORD013', time: '10:05:30', symbol: 'TCS', type: 'BUY', qty: 20, price: 4248.7, status: 'Filled', strategy: 'Bollinger Bounce' },
  { id: 'ORD014', time: '10:02:18', symbol: 'RELIANCE', type: 'SELL', qty: 30, price: 2859.1, status: 'Partial', strategy: 'Momentum Crossover' },
  { id: 'ORD015', time: '09:58:55', symbol: 'INFY', type: 'SELL', qty: 35, price: 1868.2, status: 'Filled', strategy: 'RSI Reversal' },
  { id: 'ORD016', time: '09:55:42', symbol: 'TCS', type: 'BUY', qty: 25, price: 4228.7, status: 'Pending', strategy: 'Bollinger Bounce' },
  { id: 'ORD017', time: '09:52:28', symbol: 'RELIANCE', type: 'BUY', qty: 50, price: 2852.0, status: 'Filled', strategy: 'Momentum Crossover' },
  { id: 'ORD018', time: '09:48:15', symbol: 'INFY', type: 'BUY', qty: 40, price: 1839.0, status: 'Rejected', strategy: 'RSI Reversal' },
  { id: 'ORD019', time: '09:45:00', symbol: 'TCS', type: 'BUY', qty: 20, price: 4262.5, status: 'Filled', strategy: 'Bollinger Bounce' },
  { id: 'ORD020', time: '09:42:33', symbol: 'RELIANCE', type: 'SELL', qty: 50, price: 2848.4, status: 'Filled', strategy: 'Momentum Crossover' },
  { id: 'ORD021', time: '09:38:20', symbol: 'INFY', type: 'SELL', qty: 25, price: 1875.5, status: 'Cancelled', strategy: 'RSI Reversal' },
  { id: 'ORD022', time: '09:35:15', symbol: 'TCS', type: 'BUY', qty: 15, price: 4218.3, status: 'Filled', strategy: 'Bollinger Bounce' },
  { id: 'ORD023', time: '09:32:00', symbol: 'RELIANCE', type: 'BUY', qty: 40, price: 2845.2, status: 'Filled', strategy: 'Momentum Crossover' },
  { id: 'ORD024', time: '09:28:45', symbol: 'INFY', type: 'BUY', qty: 30, price: 1882.1, status: 'Filled', strategy: 'RSI Reversal' },
];

// Mini sparkline data for strategies
export const sparklineData = [
  [4200, 4500, 4100, 4800, 5200, 4900, 5600, 5800, 6200, 6800],
  [3200, 3100, 2800, 2600, 2400, 2200, 2000, 1800, 1600, 1400],
  [1500, 1800, 2200, 2600, 2400, 2800, 3200, 3500, 3800, 4200],
];

// Recent mini signals for the chart area (5 most recent)
export const recentSignals = signals.slice(0, 5);
