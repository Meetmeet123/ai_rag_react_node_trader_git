import { useEffect, useState } from 'react';
import { Shield, AlertTriangle, Skull, Clock } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import { Slider } from '@/components/ui/slider';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Spinner } from '@/components/ui/spinner';
import { useQuery, useMutation } from '@/hooks/useApi';
import { fetchSettings, updateSettings } from '@/lib/api';

export default function RiskManagementSettings() {
  const [dailyLossEnabled, setDailyLossEnabled] = useState(true);
  const [dailyLossLimit, setDailyLossLimit] = useState('50000');
  const [weeklyLossLimit, setWeeklyLossLimit] = useState('200000');
  const [maxDrawdown, setMaxDrawdown] = useState('10');
  const [maxPositions, setMaxPositions] = useState([5]);
  const [maxExposurePerTrade, setMaxExposurePerTrade] = useState([25]);
  const [maxExposureOverall, setMaxExposureOverall] = useState([60]);
  const [killSwitchEnabled, setKillSwitchEnabled] = useState(false);
  const [squareOffTime, setSquareOffTime] = useState('15:15');
  const [consecutiveLossLimit, setConsecutiveLossLimit] = useState('3');
  const [positionSizing, setPositionSizing] = useState('risk-based');
  const [maxTradesPerDay, setMaxTradesPerDay] = useState('20');
  const [maxTradesPerStrategy, setMaxTradesPerStrategy] = useState('5');

  const { data: settings, isLoading } = useQuery(fetchSettings);
  const { mutate: saveSettings, isLoading: isSaving } = useMutation(updateSettings);

  useEffect(() => {
    if (!settings) return;
    setDailyLossLimit(String(settings.daily_loss_limit));
    setDailyLossEnabled(settings.daily_loss_limit_enabled);
    setMaxPositions([settings.max_positions]);
    setMaxExposurePerTrade([settings.max_exposure_per_trade_pct]);
    setMaxExposureOverall([settings.max_exposure_overall_pct]);
    setKillSwitchEnabled(settings.kill_switch_enabled);
    setSquareOffTime(settings.auto_square_off_time);
  }, [settings]);

  const handleSave = async () => {
    const payload = {
      daily_loss_limit: Number(dailyLossLimit) || 0,
      daily_loss_limit_enabled: dailyLossEnabled,
      max_positions: maxPositions[0],
      max_exposure_per_trade_pct: maxExposurePerTrade[0],
      max_exposure_overall_pct: maxExposureOverall[0],
      kill_switch_enabled: killSwitchEnabled,
      auto_square_off_time: squareOffTime,
    };

    try {
      await saveSettings(payload);
      toast.success('Risk settings saved successfully');
    } catch (err) {
      const message = err && typeof err === 'object' && 'detail' in err
        ? String(err.detail)
        : 'Failed to save risk settings';
      toast.error(message);
    }
  };

  return (
    <div className="space-y-6 max-w-[720px] relative">
      {isLoading && (
        <div className="absolute inset-0 z-10 bg-[#030305]/60 backdrop-blur-[2px] rounded-[8px] flex items-center justify-center">
          <div className="flex items-center gap-2 text-[#94A3B8] text-[13px]">
            <Spinner className="text-[#22D3EE]" />
            Loading settings…
          </div>
        </div>
      )}

      <div>
        <h2 className="font-display text-[28px] font-semibold text-[#F1F5F9]">Risk Management</h2>
        <p className="text-[14px] text-[#94A3B8] mt-1">
          Set capital protection rules and position limits to safeguard your trading capital
        </p>
      </div>

      {/* Capital Protection Card */}
      <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-5">
        <h3 className="text-[15px] font-semibold text-[#F1F5F9] mb-4 flex items-center gap-2">
          <Shield size={16} className="text-[#22D3EE]" />
          Capital Protection
        </h3>

        <div className="space-y-4">
          {/* Daily Loss Limit */}
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <Label className="text-[13px] font-medium text-[#F1F5F9]">Daily Loss Limit</Label>
                {parseInt(dailyLossLimit) > 50000 && (
                  <span className="flex items-center gap-1 text-[10px] text-[#F59E0B]">
                    <AlertTriangle size={10} />
                    {'>'} 5% of capital
                  </span>
                )}
              </div>
              <p className="text-[11px] text-[#64748B] mt-0.5">Stop all trading when daily loss exceeds</p>
            </div>
            <div className="flex items-center gap-3">
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[#64748B] text-[13px]">₹</span>
                <Input
                  type="number"
                  value={dailyLossLimit}
                  onChange={(e) => setDailyLossLimit(e.target.value)}
                  disabled={!dailyLossEnabled}
                  className="w-[140px] pl-7 bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono disabled:opacity-50 focus:border-[#22D3EE]"
                />
              </div>
              <Switch checked={dailyLossEnabled} onCheckedChange={setDailyLossEnabled} />
            </div>
          </div>

          <Separator className="bg-[rgba(255,255,255,0.06)]" />

          {/* Weekly Loss Limit */}
          <div className="flex items-center justify-between gap-4">
            <div className="flex-1">
              <Label className="text-[13px] font-medium text-[#F1F5F9]">Weekly Loss Limit</Label>
              <p className="text-[11px] text-[#64748B] mt-0.5">Pause all strategies for the week</p>
            </div>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[#64748B] text-[13px]">₹</span>
              <Input
                type="number"
                value={weeklyLossLimit}
                onChange={(e) => setWeeklyLossLimit(e.target.value)}
                className="w-[140px] pl-7 bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono focus:border-[#22D3EE]"
              />
            </div>
          </div>

          <Separator className="bg-[rgba(255,255,255,0.06)]" />

          {/* Max Drawdown */}
          <div className="flex items-center justify-between gap-4">
            <div className="flex-1">
              <Label className="text-[13px] font-medium text-[#F1F5F9]">Max Drawdown %</Label>
              <p className="text-[11px] text-[#64748B] mt-0.5">Auto-pause all strategies if exceeded</p>
            </div>
            <div className="relative">
              <Input
                type="number"
                value={maxDrawdown}
                onChange={(e) => setMaxDrawdown(e.target.value)}
                className="w-[100px] pr-8 bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono focus:border-[#22D3EE]"
              />
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[#64748B] text-[13px]">%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Position Limits Card */}
      <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-5">
        <h3 className="text-[15px] font-semibold text-[#F1F5F9] mb-4 flex items-center gap-2">
          <AlertTriangle size={16} className="text-[#F59E0B]" />
          Position Limits
        </h3>

        <div className="space-y-5">
          {/* Max Positions */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <Label className="text-[13px] font-medium text-[#F1F5F9]">Max Open Positions</Label>
              <span className="font-mono text-[13px] font-semibold text-[#22D3EE]">{maxPositions[0]}</span>
            </div>
            <Slider
              value={maxPositions}
              onValueChange={setMaxPositions}
              min={1}
              max={20}
              step={1}
              className="w-full"
            />
            <div className="flex justify-between mt-1">
              <span className="text-[10px] text-[#64748B]">1</span>
              <span className="text-[10px] text-[#64748B]">20</span>
            </div>
          </div>

          <Separator className="bg-[rgba(255,255,255,0.06)]" />

          {/* Max Exposure Per Trade */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <Label className="text-[13px] font-medium text-[#F1F5F9]">Max Exposure per Trade</Label>
              <span className="font-mono text-[13px] font-semibold text-[#22D3EE]">{maxExposurePerTrade[0]}%</span>
            </div>
            <Slider
              value={maxExposurePerTrade}
              onValueChange={setMaxExposurePerTrade}
              min={5}
              max={100}
              step={5}
              className="w-full"
            />
            <div className="flex justify-between mt-1">
              <span className="text-[10px] text-[#64748B]">5%</span>
              <span className="text-[10px] text-[#64748B]">100%</span>
            </div>
          </div>

          <Separator className="bg-[rgba(255,255,255,0.06)]" />

          {/* Max Exposure Overall */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <Label className="text-[13px] font-medium text-[#F1F5F9]">Max Exposure Overall</Label>
              <span className="font-mono text-[13px] font-semibold text-[#22D3EE]">{maxExposureOverall[0]}%</span>
            </div>
            <Slider
              value={maxExposureOverall}
              onValueChange={setMaxExposureOverall}
              min={10}
              max={100}
              step={5}
              className="w-full"
            />
            <div className="flex justify-between mt-1">
              <span className="text-[10px] text-[#64748B]">10%</span>
              <span className="text-[10px] text-[#64748B]">100%</span>
            </div>
          </div>

          <Separator className="bg-[rgba(255,255,255,0.06)]" />

          {/* Max Trades Per Day */}
          <div className="flex items-center justify-between gap-4">
            <div>
              <Label className="text-[13px] font-medium text-[#F1F5F9]">Max Trades per Day</Label>
              <p className="text-[11px] text-[#64748B] mt-0.5">Across all strategies</p>
            </div>
            <Input
              type="number"
              value={maxTradesPerDay}
              onChange={(e) => setMaxTradesPerDay(e.target.value)}
              className="w-[100px] bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono text-right focus:border-[#22D3EE]"
            />
          </div>

          <Separator className="bg-[rgba(255,255,255,0.06)]" />

          {/* Max Trades Per Strategy */}
          <div className="flex items-center justify-between gap-4">
            <div>
              <Label className="text-[13px] font-medium text-[#F1F5F9]">Max Trades per Strategy / Day</Label>
              <p className="text-[11px] text-[#64748B] mt-0.5">Per individual strategy</p>
            </div>
            <Input
              type="number"
              value={maxTradesPerStrategy}
              onChange={(e) => setMaxTradesPerStrategy(e.target.value)}
              className="w-[100px] bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono text-right focus:border-[#22D3EE]"
            />
          </div>
        </div>
      </div>

      {/* Stop Loss Defaults */}
      <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-5">
        <h3 className="text-[15px] font-semibold text-[#F1F5F9] mb-4 flex items-center gap-2">
          <Clock size={16} className="text-[#22D3EE]" />
          Stop Loss & Target Defaults
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">Default Stop Loss %</Label>
            <div className="relative mt-1">
              <Input
                type="number"
                defaultValue="1.0"
                step="0.1"
                className="pr-8 bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono focus:border-[#22D3EE]"
              />
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[#64748B] text-[12px]">%</span>
            </div>
          </div>
          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">Default Target %</Label>
            <div className="relative mt-1">
              <Input
                type="number"
                defaultValue="2.0"
                step="0.1"
                className="pr-8 bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono focus:border-[#22D3EE]"
              />
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[#64748B] text-[12px]">%</span>
            </div>
          </div>
          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">Risk:Reward Ratio</Label>
            <Input
              type="text"
              defaultValue="1:2"
              className="mt-1 bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono focus:border-[#22D3EE]"
            />
          </div>
          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">Auto Square-off Time (MIS)</Label>
            <div className="relative mt-1">
              <Clock size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#64748B]" />
              <Input
                type="time"
                value={squareOffTime}
                onChange={(e) => setSquareOffTime(e.target.value)}
                className="pl-8 bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono focus:border-[#22D3EE]"
              />
            </div>
            <p className="text-[10px] text-[#64748B] mt-1">Default 3:15 PM for MIS orders</p>
          </div>
        </div>
      </div>

      {/* Position Sizing */}
      <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-5">
        <h3 className="text-[15px] font-semibold text-[#F1F5F9] mb-4">Position Sizing Default</h3>
        <RadioGroup value={positionSizing} onValueChange={setPositionSizing} className="space-y-2">
          <div className="flex items-center space-x-3 p-2.5 rounded-[6px] hover:bg-[#1A1A25] transition-colors">
            <RadioGroupItem value="fixed" id="fixed" className="border-[rgba(255,255,255,0.14)] text-[#22D3EE]" />
            <Label htmlFor="fixed" className="text-[13px] text-[#F1F5F9] cursor-pointer">
              Fixed Quantity
              <span className="block text-[11px] text-[#64748B] font-normal">Fixed number of shares per trade</span>
            </Label>
          </div>
          <div className="flex items-center space-x-3 p-2.5 rounded-[6px] hover:bg-[#1A1A25] transition-colors">
            <RadioGroupItem value="percent" id="percent" className="border-[rgba(255,255,255,0.14)] text-[#22D3EE]" />
            <Label htmlFor="percent" className="text-[13px] text-[#F1F5F9] cursor-pointer">
              % of Capital
              <span className="block text-[11px] text-[#64748B] font-normal">Allocate a percentage of total capital</span>
            </Label>
          </div>
          <div className="flex items-center space-x-3 p-2.5 rounded-[6px] hover:bg-[#1A1A25] transition-colors">
            <RadioGroupItem value="risk-based" id="risk-based" className="border-[rgba(255,255,255,0.14)] text-[#22D3EE]" />
            <Label htmlFor="risk-based" className="text-[13px] text-[#F1F5F9] cursor-pointer">
              Risk-based
              <span className="block text-[11px] text-[#64748B] font-normal">Size based on stop loss distance and risk per trade</span>
            </Label>
          </div>
        </RadioGroup>

        <Separator className="bg-[rgba(255,255,255,0.06)] my-4" />

        {/* Consecutive Loss Limit */}
        <div className="flex items-center justify-between gap-4">
          <div>
            <Label className="text-[13px] font-medium text-[#F1F5F9]">Consecutive Loss Limit</Label>
            <p className="text-[11px] text-[#64748B] mt-0.5">Auto-pause after N consecutive losses</p>
          </div>
          <Input
            type="number"
            value={consecutiveLossLimit}
            onChange={(e) => setConsecutiveLossLimit(e.target.value)}
            min={1}
            max={10}
            className="w-[80px] bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono text-right focus:border-[#22D3EE]"
          />
        </div>
      </div>

      {/* Kill Switch */}
      <div className="bg-[#12121A] border-l-2 border-[#EF4444] rounded-[8px] p-5">
        <div className="flex items-start gap-3">
          <Skull size={18} className="text-[#EF4444] shrink-0 mt-0.5" />
          <div className="flex-1">
            <h3 className="text-[15px] font-semibold text-[#EF4444]">Kill Switch</h3>
            <p className="text-[13px] text-[#94A3B8] mt-1">
              Immediately close all positions and pause all strategies. Use only in emergencies.
            </p>
            <div className="flex items-center gap-3 mt-3">
              <Switch
                checked={killSwitchEnabled}
                onCheckedChange={setKillSwitchEnabled}
              />
              <span className="text-[12px] text-[#94A3B8]">
                {killSwitchEnabled ? 'Enabled — will activate on trigger' : 'Disabled'}
              </span>
            </div>
            {killSwitchEnabled && (
              <div className="mt-3 p-3 bg-[rgba(239,68,68,0.08)] rounded-[6px] border border-[rgba(239,68,68,0.15)]">
                <p className="text-[11px] text-[#EF4444] font-medium mb-2">
                  <AlertTriangle size={10} className="inline mr-1" />
                  Warning: Activating the kill switch will:
                </p>
                <ul className="text-[11px] text-[#94A3B8] space-y-0.5 ml-4 list-disc">
                  <li>Square off all open positions immediately</li>
                  <li>Pause all active strategies</li>
                  <li>Cancel all pending orders</li>
                  <li>Require manual restart to resume trading</li>
                </ul>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end pt-2 pb-6">
        <Button
          onClick={handleSave}
          disabled={isSaving || isLoading}
          className="bg-[#22D3EE] text-[#030305] hover:brightness-110 font-semibold text-[13px] h-10 px-6 shadow-[0_0_20px_rgba(34,211,238,0.15)]"
        >
          {isSaving ? (
            <span className="flex items-center gap-2">
              <Spinner className="text-[#030305]" />
              Saving…
            </span>
          ) : (
            'Save Risk Settings'
          )}
        </Button>
      </div>
    </div>
  );
}
