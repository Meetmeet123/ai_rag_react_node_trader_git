// Mock data for Dashboard page

export interface Stock {
  symbol: string;
  name: string;
  exchange: string;
  ltp: number;
  change: number;
  changePercent: number;
  volume: number;
  high: number;
  low: number;
  open: number;
  close: number;
}

export interface OHLCData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  sma20?: number;
  ema50?: number;
  bbUpper?: number;
  bbLower?: number;
}

export interface Position {
  id: string;
  symbol: string;
  exchange: string;
  product: 'MIS' | 'NRML' | 'CNC';
  qty: number;
  avgPrice: number;
  ltp: number;
  pnl: number;
  pnlPercent: number;
}

export interface Order {
  id: string;
  time: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  type: string;
  qty: number;
  price: number;
  status: 'COMPLETE' | 'OPEN' | 'REJECTED' | 'CANCELLED';
}

export interface ActiveStrategy {
  id: string;
  name: string;
  instrument: string;
  status: 'Running' | 'Paused';
  pnl: number;
  pnlPercent: number;
}

export const INDICES = [
  { name: 'NIFTY 50', value: 22456.3, change: 0.45 },
  { name: 'NIFTY BANK', value: 48712.65, change: -0.23 },
  { name: 'SENSEX', value: 73892.15, change: 0.38 },
  { name: 'NIFTY IT', value: 34123.8, change: -0.67 },
  { name: 'INDIA VIX', value: 14.32, change: 2.15 },
  { name: 'USD/INR', value: 83.42, change: 0.05 },
  { name: 'NIFTY FUT', value: 22489.5, change: 0.52 },
  { name: 'BANKNIFTY FUT', value: 48756.2, change: -0.18 },
];

export const STOCKS: Stock[] = [
  { symbol: 'RELIANCE', name: 'Reliance Industries', exchange: 'NSE', ltp: 2891.45, change: 23.7, changePercent: 0.82, volume: 4523100, high: 2901.0, low: 2870.2, open: 2875.0, close: 2867.75 },
  { symbol: 'TCS', name: 'Tata Consultancy', exchange: 'NSE', ltp: 4234.6, change: -14.5, changePercent: -0.34, volume: 1234500, high: 4260.0, low: 4210.5, open: 4250.0, close: 4249.1 },
  { symbol: 'HDFCBANK', name: 'HDFC Bank', exchange: 'NSE', ltp: 1678.9, change: 18.6, changePercent: 1.12, volume: 6789000, high: 1685.0, low: 1662.3, open: 1665.0, close: 1660.3 },
  { symbol: 'INFY', name: 'Infosys Ltd', exchange: 'NSE', ltp: 1892.3, change: -10.65, changePercent: -0.56, volume: 3456700, high: 1910.0, low: 1885.5, open: 1903.0, close: 1902.95 },
  { symbol: 'ICICIBANK', name: 'ICICI Bank', exchange: 'NSE', ltp: 1123.45, change: 7.45, changePercent: 0.67, volume: 5678900, high: 1129.0, low: 1115.2, open: 1117.0, close: 1116.0 },
  { symbol: 'SBIN', name: 'State Bank of India', exchange: 'NSE', ltp: 789.2, change: 11.3, changePercent: 1.45, volume: 8912300, high: 792.5, low: 778.0, open: 780.0, close: 777.9 },
  { symbol: 'BHARTIARTL', name: 'Bharti Airtel', exchange: 'NSE', ltp: 1234.55, change: 5.2, changePercent: 0.42, volume: 2345600, high: 1240.0, low: 1228.0, open: 1230.0, close: 1229.35 },
  { symbol: 'ITC', name: 'ITC Limited', exchange: 'NSE', ltp: 456.7, change: -2.1, changePercent: -0.46, volume: 12345600, high: 460.0, low: 454.5, open: 459.0, close: 458.8 },
  { symbol: 'KOTAKBANK', name: 'Kotak Mahindra Bank', exchange: 'NSE', ltp: 1789.3, change: 12.8, changePercent: 0.72, volume: 1892300, high: 1795.0, low: 1775.5, open: 1778.0, close: 1776.5 },
  { symbol: 'LT', name: 'Larsen & Toubro', exchange: 'NSE', ltp: 3456.8, change: -8.4, changePercent: -0.24, volume: 1567800, high: 3475.0, low: 3445.0, open: 3465.0, close: 3465.2 },
  { symbol: 'AXISBANK', name: 'Axis Bank', exchange: 'NSE', ltp: 1123.6, change: 6.7, changePercent: 0.6, volume: 4567800, high: 1128.0, low: 1116.0, open: 1118.0, close: 1116.9 },
  { symbol: 'ASIANPAINT', name: 'Asian Paints', exchange: 'NSE', ltp: 3123.45, change: -15.3, changePercent: -0.49, volume: 876500, high: 3145.0, low: 3115.0, open: 3140.0, close: 3138.75 },
  { symbol: 'MARUTI', name: 'Maruti Suzuki', exchange: 'NSE', ltp: 10987.6, change: 45.2, changePercent: 0.41, volume: 567800, high: 11020.0, low: 10940.0, open: 10950.0, close: 10942.4 },
  { symbol: 'TITAN', name: 'Titan Company', exchange: 'NSE', ltp: 3456.3, change: 22.8, changePercent: 0.66, volume: 1234500, high: 3465.0, low: 3432.0, open: 3435.0, close: 3433.5 },
  { symbol: 'SUNPHARMA', name: 'Sun Pharma', exchange: 'NSE', ltp: 1567.8, change: -5.6, changePercent: -0.36, volume: 2345600, high: 1578.0, low: 1562.0, open: 1574.0, close: 1573.4 },
];

export function generateOHLCData(count: number = 100, basePrice: number = 2500): OHLCData[] {
  const data: OHLCData[] = [];
  let price = basePrice;
  const now = new Date();
  now.setHours(9, 15, 0, 0);

  for (let i = 0; i < count; i++) {
    const change = (Math.random() - 0.48) * (basePrice * 0.008);
    const open = price;
    const close = price + change;
    const high = Math.max(open, close) + Math.random() * (basePrice * 0.003);
    const low = Math.min(open, close) - Math.random() * (basePrice * 0.003);
    const volume = Math.floor(50000 + Math.random() * 200000);

    const time = new Date(now.getTime() + i * 5 * 60000);
    const timeStr = time.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });

    data.push({
      time: timeStr,
      open: Number(open.toFixed(2)),
      high: Number(high.toFixed(2)),
      low: Number(low.toFixed(2)),
      close: Number(close.toFixed(2)),
      volume,
    });

    price = close;
  }

  // Calculate SMA 20
  for (let i = 19; i < data.length; i++) {
    let sum = 0;
    for (let j = i - 19; j <= i; j++) {
      sum += data[j].close;
    }
    data[i].sma20 = Number((sum / 20).toFixed(2));
  }

  // Calculate EMA 50
  const k = 2 / (50 + 1);
  let ema = data[0].close;
  for (let i = 0; i < data.length; i++) {
    ema = data[i].close * k + ema * (1 - k);
    if (i >= 49) {
      data[i].ema50 = Number(ema.toFixed(2));
    }
  }

  // Calculate Bollinger Bands
  for (let i = 19; i < data.length; i++) {
    let sum = 0;
    for (let j = i - 19; j <= i; j++) {
      sum += data[j].close;
    }
    const sma = sum / 20;
    let sumSq = 0;
    for (let j = i - 19; j <= i; j++) {
      sumSq += Math.pow(data[j].close - sma, 2);
    }
    const stdDev = Math.sqrt(sumSq / 20);
    data[i].bbUpper = Number((sma + 2 * stdDev).toFixed(2));
    data[i].bbLower = Number((sma - 2 * stdDev).toFixed(2));
  }

  return data;
}

export const POSITIONS: Position[] = [
  {
    id: 'pos-1',
    symbol: 'RELIANCE',
    exchange: 'NSE',
    product: 'MIS',
    qty: 50,
    avgPrice: 2867.3,
    ltp: 2891.45,
    pnl: 1207.5,
    pnlPercent: 0.84,
  },
  {
    id: 'pos-2',
    symbol: 'NIFTY 25JUL24FUT',
    exchange: 'NSE',
    product: 'NRML',
    qty: -25,
    avgPrice: 22512.0,
    ltp: 22456.3,
    pnl: 1392.5,
    pnlPercent: 0.25,
  },
  {
    id: 'pos-3',
    symbol: 'SBIN',
    exchange: 'NSE',
    product: 'CNC',
    qty: 100,
    avgPrice: 778.5,
    ltp: 789.2,
    pnl: 1070.0,
    pnlPercent: 1.38,
  },
];

export const RECENT_ORDERS: Order[] = [
  { id: 'ord-1', time: '10:24:32', symbol: 'RELIANCE', side: 'BUY', type: 'MARKET', qty: 50, price: 2867.3, status: 'COMPLETE' },
  { id: 'ord-2', time: '10:18:45', symbol: 'NIFTY FUT', side: 'SELL', type: 'MARKET', qty: 25, price: 22512.0, status: 'COMPLETE' },
  { id: 'ord-3', time: '10:15:12', symbol: 'SBIN', side: 'BUY', type: 'LIMIT', qty: 100, price: 778.5, status: 'COMPLETE' },
];

export const ACTIVE_STRATEGIES: ActiveStrategy[] = [
  { id: 'strat-1', name: 'RSI Mean Reversion', instrument: 'NIFTY 50', status: 'Running', pnl: 8340, pnlPercent: 2.14 },
  { id: 'strat-2', name: 'Moving Average Cross', instrument: 'BANKNIFTY FUT', status: 'Running', pnl: -2100, pnlPercent: -0.45 },
  { id: 'strat-3', name: 'Breakout Strategy', instrument: 'RELIANCE', status: 'Paused', pnl: 0, pnlPercent: 0 },
];

export function generateSparklineData(points: number = 20): number[] {
  const data: number[] = [];
  let val = 100;
  for (let i = 0; i < points; i++) {
    val += (Math.random() - 0.45) * 5;
    data.push(Number(val.toFixed(2)));
  }
  return data;
}

export const TIMEFRAMES = ['1m', '5m', '15m', '30m', '1H', 'D', 'W'] as const;
export type Timeframe = (typeof TIMEFRAMES)[number];
