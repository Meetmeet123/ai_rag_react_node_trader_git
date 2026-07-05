import { Play } from 'lucide-react';
import type { BacktestConfig } from './types';

interface Step2Props {
  config: BacktestConfig;
  onChange: (config: BacktestConfig) => void;
  onRun: () => void;
}

const PRESETS = [
  { label: '1M', months: 1 },
  { label: '3M', months: 3 },
  { label: '6M', months: 6 },
  { label: '1Y', months: 12 },
  { label: '5Y', months: 60 },
];

const SEGMENTS = ['Stocks', 'Futures', 'Options', 'MCX'];
const EXCHANGES = ['NSE', 'BSE', 'NFO', 'MCX'];
const TIMEFRAMES = ['1m', '5m', '15m', '30m', '1H', '1D'];
const POSITION_SIZING = [
  { value: 'fixed' as const, label: 'Fixed Qty' },
  { value: 'percent' as const, label: '% of Capital' },
  { value: 'risk' as const, label: 'Risk Based' },
];

export default function Step2_Parameters({ config, onChange, onRun }: Step2Props) {
  const setPreset = (months: number) => {
    const end = new Date();
    const start = new Date();
    start.setMonth(start.getMonth() - months);
    onChange({
      ...config,
      startDate: start.toISOString().split('T')[0],
      endDate: end.toISOString().split('T')[0],
    });
  };

  const update = <K extends keyof BacktestConfig>(field: K, value: BacktestConfig[K]) => {
    onChange({ ...config, [field]: value });
  };

  return (
    <div className="max-w-[1000px] mx-auto pt-6 pb-8 px-6">
      <div className="grid grid-cols-1 lg:grid-cols-[40%_60%] gap-6">
        {/* Left: Configuration Form */}
        <div className="space-y-5">
          <h3 className="text-[16px] font-semibold text-[#F1F5F9]">Backtest Configuration</h3>

          {/* Basic Settings */}
          <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-4 space-y-3">
            <h4 className="text-[12px] font-semibold text-[#64748B] uppercase tracking-wider mb-2">Basic Settings</h4>

            <div>
              <label className="text-[11px] text-[#64748B] mb-1 block">Symbol</label>
              <input
                type="text"
                value={config.symbol}
                onChange={(e) => update('symbol', e.target.value)}
                className="w-full h-8 px-2 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] text-[#F1F5F9] font-mono focus:outline-none focus:border-[#22D3EE]"
              />
            </div>

            <div>
              <label className="text-[11px] text-[#64748B] mb-1 block">Segment</label>
              <div className="flex flex-wrap gap-1">
                {SEGMENTS.map((seg) => (
                  <button
                    key={seg}
                    onClick={() => update('segment', seg)}
                    className={`px-2.5 py-1 rounded-[4px] text-[11px] font-medium transition-all ${
                      config.segment === seg
                        ? 'bg-[#1A1A25] text-[#F1F5F9]'
                        : 'text-[#475569] hover:text-[#94A3B8]'
                    }`}
                  >
                    {seg}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[11px] text-[#64748B] mb-1 block">Exchange</label>
                <select
                  value={config.exchange}
                  onChange={(e) => update('exchange', e.target.value)}
                  className="w-full h-8 px-2 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] text-[#F1F5F9] focus:outline-none focus:border-[#22D3EE]"
                >
                  {EXCHANGES.map((ex) => <option key={ex} value={ex}>{ex}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[11px] text-[#64748B] mb-1 block">Timeframe</label>
                <select
                  value={config.timeframe}
                  onChange={(e) => update('timeframe', e.target.value)}
                  className="w-full h-8 px-2 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] text-[#F1F5F9] font-mono focus:outline-none focus:border-[#22D3EE]"
                >
                  {TIMEFRAMES.map((tf) => <option key={tf} value={tf}>{tf}</option>)}
                </select>
              </div>
            </div>
          </div>

          {/* Date Range */}
          <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-4 space-y-3">
            <h4 className="text-[12px] font-semibold text-[#64748B] uppercase tracking-wider mb-2">Date Range</h4>
            <div className="flex flex-wrap gap-1 mb-2">
              {PRESETS.map((p) => (
                <button
                  key={p.label}
                  onClick={() => setPreset(p.months)}
                  className="px-2 py-0.5 rounded-[4px] text-[11px] text-[#475569] hover:text-[#22D3EE] hover:bg-[rgba(34,211,238,0.06)] transition-all"
                >
                  {p.label}
                </button>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[11px] text-[#64748B] mb-1 block">From</label>
                <input
                  type="date"
                  value={config.startDate}
                  onChange={(e) => update('startDate', e.target.value)}
                  className="w-full h-8 px-2 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] text-[#F1F5F9] font-mono focus:outline-none focus:border-[#22D3EE]"
                />
              </div>
              <div>
                <label className="text-[11px] text-[#64748B] mb-1 block">To</label>
                <input
                  type="date"
                  value={config.endDate}
                  onChange={(e) => update('endDate', e.target.value)}
                  className="w-full h-8 px-2 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] text-[#F1F5F9] font-mono focus:outline-none focus:border-[#22D3EE]"
                />
              </div>
            </div>
          </div>

          {/* Capital & Position */}
          <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-4 space-y-3">
            <h4 className="text-[12px] font-semibold text-[#64748B] uppercase tracking-wider mb-2">Capital & Position</h4>
            <div>
              <label className="text-[11px] text-[#64748B] mb-1 block">Initial Capital</label>
              <div className="relative">
                <span className="absolute left-2 top-1/2 -translate-y-1/2 text-[11px] text-[#475569]">Rs.</span>
                <input
                  type="number"
                  value={config.initialCapital}
                  onChange={(e) => update('initialCapital', Number(e.target.value))}
                  className="w-full h-8 pl-7 pr-2 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] text-[#F1F5F9] font-mono focus:outline-none focus:border-[#22D3EE]"
                />
              </div>
            </div>
            <div>
              <label className="text-[11px] text-[#64748B] mb-1 block">Position Sizing</label>
              <div className="flex flex-wrap gap-1">
                {POSITION_SIZING.map((ps) => (
                  <button
                    key={ps.value}
                    onClick={() => update('positionSizing', ps.value)}
                    className={`px-2.5 py-1 rounded-[4px] text-[11px] font-medium transition-all ${
                      config.positionSizing === ps.value
                        ? 'bg-[#1A1A25] text-[#F1F5F9]'
                        : 'text-[#475569] hover:text-[#94A3B8]'
                    }`}
                  >
                    {ps.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Risk Parameters */}
          <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-4 space-y-3">
            <h4 className="text-[12px] font-semibold text-[#64748B] uppercase tracking-wider mb-2">Risk Parameters</h4>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[11px] text-[#64748B] mb-1 block">Stop Loss</label>
                <select
                  value={config.stopLossType}
                  onChange={(e) => update('stopLossType', e.target.value as BacktestConfig['stopLossType'])}
                  className="w-full h-8 px-2 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] text-[#F1F5F9]"
                >
                  <option value="fixed">Fixed %</option>
                  <option value="trailing">Trailing</option>
                  <option value="atr">ATR</option>
                </select>
              </div>
              <div>
                <label className="text-[11px] text-[#64748B] mb-1 block">Value</label>
                <input
                  type="number"
                  value={config.stopLossValue}
                  onChange={(e) => update('stopLossValue', Number(e.target.value))}
                  step={0.1}
                  className="w-full h-8 px-2 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] text-[#F1F5F9] font-mono"
                />
              </div>
              <div>
                <label className="text-[11px] text-[#64748B] mb-1 block">Target</label>
                <select
                  value={config.targetType}
                  onChange={(e) => update('targetType', e.target.value as BacktestConfig['targetType'])}
                  className="w-full h-8 px-2 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] text-[#F1F5F9]"
                >
                  <option value="fixed">Fixed %</option>
                  <option value="rr">R:R Ratio</option>
                  <option value="atr">ATR</option>
                </select>
              </div>
              <div>
                <label className="text-[11px] text-[#64748B] mb-1 block">Value</label>
                <input
                  type="number"
                  value={config.targetValue}
                  onChange={(e) => update('targetValue', Number(e.target.value))}
                  step={0.1}
                  className="w-full h-8 px-2 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] text-[#F1F5F9] font-mono"
                />
              </div>
            </div>
          </div>

          {/* Slippage & Charges */}
          <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-4 space-y-3">
            <h4 className="text-[12px] font-semibold text-[#64748B] uppercase tracking-wider mb-2">Slippage & Charges</h4>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[11px] text-[#64748B] mb-1 block">Slippage %</label>
                <input
                  type="number"
                  value={config.slippage}
                  onChange={(e) => update('slippage', Number(e.target.value))}
                  step={0.01}
                  className="w-full h-8 px-2 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] text-[#F1F5F9] font-mono"
                />
              </div>
              <div>
                <label className="text-[11px] text-[#64748B] mb-1 block">Brokerage (per order)</label>
                <input
                  type="number"
                  value={config.brokerage}
                  onChange={(e) => update('brokerage', Number(e.target.value))}
                  className="w-full h-8 px-2 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] text-[#F1F5F9] font-mono"
                />
              </div>
            </div>
          </div>

          {/* Run Button */}
          <button
            onClick={onRun}
            className="w-full h-12 flex items-center justify-center gap-2 bg-[#22D3EE] text-[#030305] text-[14px] font-semibold rounded-[6px] hover:brightness-110 transition-all hover:shadow-[0_0_20px_rgba(34,211,238,0.15)] active:scale-[0.98]"
          >
            <Play size={16} />
            Run Backtest
          </button>
        </div>

        {/* Right: Summary */}
        <div className="lg:pl-4">
          <h3 className="text-[16px] font-semibold text-[#F1F5F9] mb-4">Configuration Summary</h3>
          <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-5 space-y-3">
            <SummaryRow label="Symbol" value={config.symbol} />
            <SummaryRow label="Segment" value={config.segment} />
            <SummaryRow label="Exchange" value={config.exchange} />
            <SummaryRow label="Timeframe" value={config.timeframe} />
            <SummaryRow label="Date Range" value={`${config.startDate} to ${config.endDate}`} />
            <SummaryRow label="Initial Capital" value={`Rs. ${config.initialCapital.toLocaleString('en-IN')}`} />
            <SummaryRow label="Position Sizing" value={config.positionSizing === 'fixed' ? 'Fixed Qty' : config.positionSizing === 'percent' ? '% of Capital' : 'Risk Based'} />
            <SummaryRow label="Stop Loss" value={`${config.stopLossType === 'fixed' ? 'Fixed' : config.stopLossType === 'trailing' ? 'Trailing' : 'ATR'} (${config.stopLossValue})`} />
            <SummaryRow label="Target" value={`${config.targetType === 'fixed' ? 'Fixed %' : config.targetType === 'rr' ? 'R:R' : 'ATR'} (${config.targetValue})`} />
            <SummaryRow label="Slippage" value={`${config.slippage}%`} />
            <SummaryRow label="Brokerage" value={`Rs. ${config.brokerage}/order`} />
          </div>

          <div className="mt-4 p-4 bg-[rgba(34,211,238,0.04)] border border-[rgba(34,211,238,0.08)] rounded-[8px]">
            <p className="text-[11px] text-[#94A3B8]">
              <span className="text-[#22D3EE] font-semibold">Estimated runtime:</span> ~45 seconds
            </p>
            <p className="text-[11px] text-[#475569] mt-1">
              Based on date range and data volume. Historical data will be fetched from NSE.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-[rgba(255,255,255,0.04)] last:border-0">
      <span className="text-[11px] text-[#64748B]">{label}</span>
      <span className="text-[12px] font-medium text-[#F1F5F9] font-mono">{value}</span>
    </div>
  );
}
