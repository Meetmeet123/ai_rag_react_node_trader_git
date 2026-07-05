export type StrategyStatus = 'active' | 'paper' | 'backtesting' | 'draft';
export type Segment = 'Stocks' | 'Futures' | 'Options' | 'MCX';
export type TimeFrame = '1m' | '5m' | '15m' | '30m' | '1h' | '1d';

export interface SavedStrategy {
  id: string;
  name: string;
  description: string;
  instrument: string;
  segment: Segment;
  status: StrategyStatus;
  lastModified: string;
  entryConditions: Condition[];
  exitConditions: Condition[];
  stopLoss: StopLossConfig;
  target: TargetConfig;
  positionSizing: PositionSizingConfig;
  timeframe: TimeFrame;
}

export interface Condition {
  id: string;
  indicator: string;
  operator: string;
  value: string;
  valueType: 'indicator' | 'number';
  logic?: 'AND' | 'OR';
}

export interface StopLossConfig {
  type: 'fixed' | 'trailing' | 'atr';
  value: number;
}

export interface TargetConfig {
  type: 'fixed' | 'rr' | 'trailing';
  value: number;
}

export interface PositionSizingConfig {
  type: 'fixed' | 'percent' | 'risk';
  value: number;
}

export interface IndicatorMeta {
  name: string;
  shortName: string;
  category: 'trend' | 'momentum' | 'volatility' | 'volume';
  description: string;
  params: { name: string; default: number }[];
}

export const INDICATORS: IndicatorMeta[] = [
  { name: 'Simple Moving Average', shortName: 'SMA', category: 'trend', description: 'Average price over N periods', params: [{ name: 'Period', default: 20 }] },
  { name: 'Exponential Moving Average', shortName: 'EMA', category: 'trend', description: 'Weighted average favoring recent prices', params: [{ name: 'Period', default: 20 }] },
  { name: 'Weighted Moving Average', shortName: 'WMA', category: 'trend', description: 'Linearly weighted average', params: [{ name: 'Period', default: 20 }] },
  { name: 'Relative Strength Index', shortName: 'RSI', category: 'momentum', description: 'Momentum oscillator (0-100)', params: [{ name: 'Period', default: 14 }] },
  { name: 'MACD', shortName: 'MACD', category: 'momentum', description: 'Moving Average Convergence Divergence', params: [{ name: 'Fast', default: 12 }, { name: 'Slow', default: 26 }, { name: 'Signal', default: 9 }] },
  { name: 'Stochastic Oscillator', shortName: 'Stoch', category: 'momentum', description: 'Compares close to price range', params: [{ name: '%K Period', default: 14 }, { name: '%D Period', default: 3 }] },
  { name: 'Bollinger Bands', shortName: 'BB', category: 'volatility', description: 'Volatility bands around SMA', params: [{ name: 'Period', default: 20 }, { name: 'StdDev', default: 2 }] },
  { name: 'Average True Range', shortName: 'ATR', category: 'volatility', description: 'Measures market volatility', params: [{ name: 'Period', default: 14 }] },
  { name: 'Volume Weighted Avg Price', shortName: 'VWAP', category: 'volume', description: 'Volume-weighted average price', params: [{ name: 'Anchor', default: 1 }] },
  { name: 'On Balance Volume', shortName: 'OBV', category: 'volume', description: 'Cumulative volume flow', params: [] },
  { name: 'Average Directional Index', shortName: 'ADX', category: 'trend', description: 'Trend strength indicator', params: [{ name: 'Period', default: 14 }] },
  { name: 'Commodity Channel Index', shortName: 'CCI', category: 'momentum', description: 'Measures deviation from average', params: [{ name: 'Period', default: 20 }] },
  { name: 'Money Flow Index', shortName: 'MFI', category: 'volume', description: 'Volume-weighted RSI', params: [{ name: 'Period', default: 14 }] },
  { name: 'Supertrend', shortName: 'Supertrend', category: 'trend', description: 'ATR-based trend follower', params: [{ name: 'Period', default: 10 }, { name: 'Multiplier', default: 3 }] },
  { name: 'Parabolic SAR', shortName: 'PSAR', category: 'trend', description: 'Trailing stop and reverse', params: [{ name: 'Step', default: 0.02 }, { name: 'Max', default: 0.2 }] },
];

export const TIMEFRAMES = ['1m', '5m', '15m', '30m', '1h', '1d'] as const;

export function timeframeLabel(tf: string): string {
  if (tf === '1h') return '1H';
  if (tf === '1d') return '1D';
  return tf.toUpperCase();
}

export const NIFTY50_STOCKS = [
  'RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'HINDUNILVR', 'SBIN', 'BHARTIARTL',
  'ITC', 'LICI', 'KOTAKBANK', 'BAJFINANCE', 'LT', 'HCLTECH', 'ASIANPAINT', 'AXISBANK',
  'MARUTI', 'SUNPHARMA', 'TITAN', 'ULTRACEMCO', 'NESTLEIND', 'BAJAJFINSV', 'ADANIENT',
  'WIPRO', 'ONGC', 'NTPC', 'TATAMOTORS', 'POWERGRID', 'JSWSTEEL', 'COALINDIA', 'M&M',
  'GRASIM', 'ADANIPORTS', 'CIPLA', 'SAIL', 'BRITANNIA', 'TECHM', 'DRREDDY', 'EICHERMOT',
  'APOLLOHOSP', 'TATACONSUM', 'HINDALCO', 'ZOMATO', 'INDUSINDBK', 'UPL', 'TATASTEEL',
  'BPCL', 'DIVISLAB', 'SBILIFE', 'HAVELLS',
];

export const SEGMENTS = ['Stocks', 'Futures', 'Options', 'MCX'] as const;

export const OPERATORS = [
  { value: 'crosses_above', label: 'crosses above' },
  { value: 'crosses_below', label: 'crosses below' },
  { value: '>', label: '>' },
  { value: '<', label: '<' },
  { value: '=', label: '=' },
  { value: '>=', label: '>=' },
  { value: '<=', label: '<=' },
];
