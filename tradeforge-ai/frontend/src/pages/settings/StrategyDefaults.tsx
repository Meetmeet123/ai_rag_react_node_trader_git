import { useState } from 'react';
import { GitBranch, Play, CheckCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';

export default function StrategyDefaults() {
  const [timeframe, setTimeframe] = useState('15m');
  const [stopLossType, setStopLossType] = useState('fixed');
  const [stopLossValue, setStopLossValue] = useState('1.0');
  const [targetType, setTargetType] = useState('fixed');
  const [targetValue, setTargetValue] = useState('2.0');
  const [positionSize, setPositionSize] = useState('100');
  const [orderType, setOrderType] = useState('market');
  const [autoTrading, setAutoTrading] = useState(false);
  const [strategyValidation, setStrategyValidation] = useState(true);
  const [segment, setSegment] = useState('nse');
  const [productType, setProductType] = useState('mis');
  const [rsiPeriod, setRsiPeriod] = useState('14');
  const [smaPeriod, setSmaPeriod] = useState('20');
  const [emaPeriod, setEmaPeriod] = useState('50');

  const SelectStyle = ({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: { value: string; label: string }[] }) => (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full h-9 px-3 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[6px] text-[13px] text-[#F1F5F9] focus:border-[#22D3EE] focus:outline-none focus:shadow-[0_0_0_2px_rgba(34,211,238,0.08)] cursor-pointer"
    >
      {options.map((o) => (
        <option key={o.value} value={o.value} className="bg-[#12121A]">{o.label}</option>
      ))}
    </select>
  );

  return (
    <div className="space-y-6 max-w-[720px]">
      <div>
        <h2 className="font-display text-[28px] font-semibold text-[#F1F5F9]">Strategy Defaults</h2>
        <p className="text-[14px] text-[#94A3B8] mt-1">
          Configure default parameters for new strategies
        </p>
      </div>

      {/* Entry/Exit Defaults */}
      <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-5">
        <h3 className="text-[15px] font-semibold text-[#F1F5F9] mb-4 flex items-center gap-2">
          <GitBranch size={16} className="text-[#22D3EE]" />
          Entry / Exit Defaults
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">Default Segment</Label>
            <div className="mt-1">
              <SelectStyle
                value={segment}
                onChange={setSegment}
                options={[
                  { value: 'nse', label: 'NSE Stocks' },
                  { value: 'nfo', label: 'NFO (F&O)' },
                  { value: 'bse', label: 'BSE' },
                  { value: 'mcx', label: 'MCX (Commodity)' },
                ]}
              />
            </div>
          </div>

          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">Default Timeframe</Label>
            <div className="mt-1">
              <SelectStyle
                value={timeframe}
                onChange={setTimeframe}
                options={[
                  { value: '5m', label: '5 Minutes' },
                  { value: '15m', label: '15 Minutes' },
                  { value: '30m', label: '30 Minutes' },
                  { value: '1h', label: '1 Hour' },
                  { value: '1d', label: '1 Day' },
                ]}
              />
            </div>
          </div>

          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">Default Order Type</Label>
            <div className="mt-1">
              <SelectStyle
                value={orderType}
                onChange={setOrderType}
                options={[
                  { value: 'market', label: 'Market' },
                  { value: 'limit', label: 'Limit' },
                  { value: 'sl', label: 'Stop Loss (SL)' },
                  { value: 'sl-m', label: 'SL-M' },
                ]}
              />
            </div>
          </div>

          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">Default Product Type</Label>
            <div className="mt-1">
              <SelectStyle
                value={productType}
                onChange={setProductType}
                options={[
                  { value: 'mis', label: 'MIS (Intraday)' },
                  { value: 'cnc', label: 'CNC (Delivery)' },
                  { value: 'nrml', label: 'NRML (Carry Forward)' },
                ]}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Stop Loss & Target */}
      <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-5">
        <h3 className="text-[15px] font-semibold text-[#F1F5F9] mb-4">Stop Loss & Target</h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">Stop Loss Type</Label>
            <div className="mt-1">
              <SelectStyle
                value={stopLossType}
                onChange={setStopLossType}
                options={[
                  { value: 'fixed', label: 'Fixed %' },
                  { value: 'trailing', label: 'Trailing' },
                  { value: 'atr', label: 'ATR Based' },
                ]}
              />
            </div>
          </div>
          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">Stop Loss Value</Label>
            <div className="relative mt-1">
              <Input
                type="number"
                value={stopLossValue}
                onChange={(e) => setStopLossValue(e.target.value)}
                step="0.1"
                className="pr-8 bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono focus:border-[#22D3EE]"
              />
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[#64748B] text-[12px]">%</span>
            </div>
          </div>
          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">Target Type</Label>
            <div className="mt-1">
              <SelectStyle
                value={targetType}
                onChange={setTargetType}
                options={[
                  { value: 'fixed', label: 'Fixed %' },
                  { value: 'trailing', label: 'Trailing' },
                  { value: 'atr', label: 'ATR Based' },
                  { value: 'rr', label: 'R:R Based' },
                ]}
              />
            </div>
          </div>
          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">Target Value</Label>
            <div className="relative mt-1">
              <Input
                type="number"
                value={targetValue}
                onChange={(e) => setTargetValue(e.target.value)}
                step="0.1"
                className="pr-8 bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono focus:border-[#22D3EE]"
              />
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[#64748B] text-[12px]">%</span>
            </div>
          </div>
        </div>

        <Separator className="bg-[rgba(255,255,255,0.06)] my-4" />

        <div>
          <Label className="text-[12px] font-medium text-[#64748B]">Default Position Size (Qty)</Label>
          <Input
            type="number"
            value={positionSize}
            onChange={(e) => setPositionSize(e.target.value)}
            className="mt-1 w-[200px] bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono focus:border-[#22D3EE]"
          />
          <p className="text-[11px] text-[#64748B] mt-1">Number of shares/lots per trade</p>
        </div>
      </div>

      {/* Indicator Defaults */}
      <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-5">
        <h3 className="text-[15px] font-semibold text-[#F1F5F9] mb-4">Indicator Defaults</h3>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">RSI Period</Label>
            <Input
              type="number"
              value={rsiPeriod}
              onChange={(e) => setRsiPeriod(e.target.value)}
              className="mt-1 bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono text-center focus:border-[#22D3EE]"
            />
          </div>
          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">SMA Period</Label>
            <Input
              type="number"
              value={smaPeriod}
              onChange={(e) => setSmaPeriod(e.target.value)}
              className="mt-1 bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono text-center focus:border-[#22D3EE]"
            />
          </div>
          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">EMA Period</Label>
            <Input
              type="number"
              value={emaPeriod}
              onChange={(e) => setEmaPeriod(e.target.value)}
              className="mt-1 bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono text-center focus:border-[#22D3EE]"
            />
          </div>
          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">ATR Period</Label>
            <Input
              type="number"
              defaultValue="14"
              className="mt-1 bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono text-center focus:border-[#22D3EE]"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4">
          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">MACD Fast</Label>
            <Input
              type="number"
              defaultValue="12"
              className="mt-1 bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono text-center focus:border-[#22D3EE]"
            />
          </div>
          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">MACD Slow</Label>
            <Input
              type="number"
              defaultValue="26"
              className="mt-1 bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono text-center focus:border-[#22D3EE]"
            />
          </div>
          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">MACD Signal</Label>
            <Input
              type="number"
              defaultValue="9"
              className="mt-1 bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono text-center focus:border-[#22D3EE]"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">Bollinger Bands Period</Label>
            <Input
              type="number"
              defaultValue="20"
              className="mt-1 bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono text-center focus:border-[#22D3EE]"
            />
          </div>
          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">BB Std Dev</Label>
            <Input
              type="number"
              defaultValue="2"
              step="0.5"
              className="mt-1 bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono text-center focus:border-[#22D3EE]"
            />
          </div>
        </div>
      </div>

      {/* Auto-Trading Defaults */}
      <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-5">
        <h3 className="text-[15px] font-semibold text-[#F1F5F9] mb-4 flex items-center gap-2">
          <Play size={16} className="text-[#22D3EE]" />
          Auto-Trading Defaults
        </h3>

        <div className="space-y-4">
          {/* Auto-trading toggle */}
          <div className="flex items-center justify-between py-2">
            <div>
              <p className="text-[13px] font-medium text-[#F1F5F9]">Auto-Trading</p>
              <p className="text-[11px] text-[#64748B] mt-0.5">Automatically execute strategy signals</p>
            </div>
            <Switch checked={autoTrading} onCheckedChange={setAutoTrading} />
          </div>

          <Separator className="bg-[rgba(255,255,255,0.06)]" />

          {/* Auto-confirm orders */}
          <div className="flex items-center justify-between py-2">
            <div>
              <p className="text-[13px] font-medium text-[#F1F5F9]">Auto-confirm Orders</p>
              <p className="text-[11px] text-[#64748B] mt-0.5">Skip confirmation dialog for order execution</p>
            </div>
            <Switch />
          </div>

          <Separator className="bg-[rgba(255,255,255,0.06)]" />

          {/* Order confirmation timeout */}
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-[13px] font-medium text-[#F1F5F9]">Confirmation Timeout</p>
              <p className="text-[11px] text-[#64748B] mt-0.5">Auto-dismiss confirmation after</p>
            </div>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                defaultValue="10"
                className="w-[80px] bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono text-right focus:border-[#22D3EE]"
              />
              <span className="text-[12px] text-[#64748B]">sec</span>
            </div>
          </div>

          <Separator className="bg-[rgba(255,255,255,0.06)]" />

          {/* Retry failed orders */}
          <div className="flex items-center justify-between py-2">
            <div>
              <p className="text-[13px] font-medium text-[#F1F5F9]">Retry Failed Orders</p>
              <p className="text-[11px] text-[#64748B] mt-0.5">Automatically retry on order failure</p>
            </div>
            <Switch defaultChecked />
          </div>

          <Separator className="bg-[rgba(255,255,255,0.06)]" />

          {/* Max retry attempts */}
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-[13px] font-medium text-[#F1F5F9]">Max Retry Attempts</p>
              <p className="text-[11px] text-[#64748B] mt-0.5">Maximum retries per failed order</p>
            </div>
            <Input
              type="number"
              defaultValue="3"
              min={1}
              max={5}
              className="w-[80px] bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono text-right focus:border-[#22D3EE]"
            />
          </div>

          <Separator className="bg-[rgba(255,255,255,0.06)]" />

          {/* Paper trading before live */}
          <div className="flex items-center justify-between py-2">
            <div>
              <p className="text-[13px] font-medium text-[#F1F5F9]">Paper Trading Before Live</p>
              <p className="text-[11px] text-[#64748B] mt-0.5">Require 7 days of paper trading before live</p>
            </div>
            <Switch defaultChecked />
          </div>

          <Separator className="bg-[rgba(255,255,255,0.06)]" />

          {/* Strategy validation */}
          <div className="flex items-center justify-between py-2">
            <div className="flex items-center gap-2">
              <CheckCircle size={14} className="text-[#A78BFA]" />
              <div>
                <p className="text-[13px] font-medium text-[#F1F5F9]">Strategy Validation</p>
                <p className="text-[11px] text-[#64748B] mt-0.5">Validate strategy before deploying</p>
              </div>
            </div>
            <Switch checked={strategyValidation} onCheckedChange={setStrategyValidation} />
          </div>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end pt-2 pb-6">
        <Button className="bg-[#22D3EE] text-[#030305] hover:brightness-110 font-semibold text-[13px] h-10 px-6 shadow-[0_0_20px_rgba(34,211,238,0.15)]">
          Save Defaults
        </Button>
      </div>
    </div>
  );
}
