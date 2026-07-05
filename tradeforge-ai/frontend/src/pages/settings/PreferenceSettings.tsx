import { useState } from 'react';
import { Settings, Monitor, Keyboard, RotateCcw, Moon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';

const shortcuts = [
  { key: 'B', action: 'Buy order' },
  { key: 'S', action: 'Sell order' },
  { key: 'Esc', action: 'Cancel order' },
  { key: 'Ctrl + S', action: 'Save strategy' },
  { key: 'Ctrl + B', action: 'Run backtest' },
  { key: 'Ctrl + P', action: 'Toggle paper/live mode' },
  { key: 'Space', action: 'Pause / resume strategy' },
  { key: 'Ctrl + K', action: 'Kill switch' },
];

export default function PreferenceSettings() {
  const [fontSize, setFontSize] = useState('medium');
  const [dataDensity, setDataDensity] = useState('comfortable');
  const [landingPage, setLandingPage] = useState('dashboard');
  const [chartColors, setChartColors] = useState('green-up');
  const [numberFormat, setNumberFormat] = useState('indian');
  const [timeZone, setTimeZone] = useState('ist');
  const [language, setLanguage] = useState('en');
  const [autoSave, setAutoSave] = useState(true);
  const [keyboardShortcuts, setKeyboardShortcuts] = useState(true);

  const SegmentedControl = ({
    value,
    onChange,
    options,
  }: {
    value: string;
    onChange: (v: string) => void;
    options: { value: string; label: string }[];
  }) => (
    <div className="flex bg-[#06060A] rounded-[6px] p-0.5">
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`flex-1 px-3 py-1.5 rounded-[4px] text-[12px] font-medium transition-all ${
            value === opt.value
              ? 'bg-[#12121A] text-[#F1F5F9] shadow-sm'
              : 'text-[#64748B] hover:text-[#94A3B8]'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );

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
        <h2 className="font-display text-[28px] font-semibold text-[#F1F5F9]">Platform Preferences</h2>
        <p className="text-[14px] text-[#94A3B8] mt-1">
          Customize the appearance and behavior of your trading terminal
        </p>
      </div>

      {/* Display Card */}
      <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-5">
        <h3 className="text-[15px] font-semibold text-[#F1F5F9] mb-4 flex items-center gap-2">
          <Monitor size={16} className="text-[#22D3EE]" />
          Display
        </h3>

        <div className="space-y-4">
          {/* Theme - Dark only */}
          <div className="flex items-center justify-between gap-4">
            <div>
              <Label className="text-[13px] font-medium text-[#F1F5F9]">Theme</Label>
              <p className="text-[11px] text-[#64748B] mt-0.5">Trading requires dark mode for optimal visibility</p>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 bg-[rgba(34,211,238,0.08)] rounded-[6px] border border-[rgba(34,211,238,0.12)]">
              <Moon size={12} className="text-[#22D3EE]" />
              <span className="text-[12px] font-medium text-[#22D3EE]">Dark</span>
            </div>
          </div>

          <Separator className="bg-[rgba(255,255,255,0.06)]" />

          {/* Font Size */}
          <div className="flex items-center justify-between gap-4">
            <div>
              <Label className="text-[13px] font-medium text-[#F1F5F9]">Font Size</Label>
              <p className="text-[11px] text-[#64748B] mt-0.5">Adjust text size across the interface</p>
            </div>
            <div className="w-[240px]">
              <SegmentedControl
                value={fontSize}
                onChange={setFontSize}
                options={[
                  { value: 'small', label: 'Small' },
                  { value: 'medium', label: 'Medium' },
                  { value: 'large', label: 'Large' },
                ]}
              />
            </div>
          </div>

          <Separator className="bg-[rgba(255,255,255,0.06)]" />

          {/* Data Density */}
          <div className="flex items-center justify-between gap-4">
            <div>
              <Label className="text-[13px] font-medium text-[#F1F5F9]">Data Density</Label>
              <p className="text-[11px] text-[#64748B] mt-0.5">Control information density in tables and lists</p>
            </div>
            <div className="w-[200px]">
              <SegmentedControl
                value={dataDensity}
                onChange={setDataDensity}
                options={[
                  { value: 'compact', label: 'Compact' },
                  { value: 'comfortable', label: 'Comfortable' },
                ]}
              />
            </div>
          </div>

          <Separator className="bg-[rgba(255,255,255,0.06)]" />

          {/* Default Landing Page */}
          <div className="flex items-center justify-between gap-4">
            <div>
              <Label className="text-[13px] font-medium text-[#F1F5F9]">Default Landing Page</Label>
              <p className="text-[11px] text-[#64748B] mt-0.5">Page to show on login</p>
            </div>
            <div className="w-[200px]">
              <SelectStyle
                value={landingPage}
                onChange={setLandingPage}
                options={[
                  { value: 'dashboard', label: 'Dashboard' },
                  { value: 'strategies', label: 'Strategies' },
                  { value: 'backtest', label: 'Backtest' },
                ]}
              />
            </div>
          </div>

          <Separator className="bg-[rgba(255,255,255,0.06)]" />

          {/* Chart Color Scheme */}
          <div className="flex items-center justify-between gap-4">
            <div>
              <Label className="text-[13px] font-medium text-[#F1F5F9]">Chart Color Scheme</Label>
              <p className="text-[11px] text-[#64748B] mt-0.5">Candlestick up/down colors</p>
            </div>
            <div className="w-[240px]">
              <SegmentedControl
                value={chartColors}
                onChange={setChartColors}
                options={[
                  { value: 'green-up', label: 'Green Up' },
                  { value: 'red-up', label: 'Red Up' },
                ]}
              />
            </div>
          </div>

          <Separator className="bg-[rgba(255,255,255,0.06)]" />

          {/* Number Format */}
          <div className="flex items-center justify-between gap-4">
            <div>
              <Label className="text-[13px] font-medium text-[#F1F5F9]">Number Format</Label>
              <p className="text-[11px] text-[#64748B] mt-0.5">How numbers are formatted</p>
            </div>
            <div className="w-[240px]">
              <SegmentedControl
                value={numberFormat}
                onChange={setNumberFormat}
                options={[
                  { value: 'indian', label: 'Indian (₹)' },
                  { value: 'intl', label: 'Int\'l ($)' },
                ]}
              />
            </div>
          </div>

          <Separator className="bg-[rgba(255,255,255,0.06)]" />

          {/* Time Zone */}
          <div className="flex items-center justify-between gap-4">
            <div>
              <Label className="text-[13px] font-medium text-[#F1F5F9]">Time Zone</Label>
              <p className="text-[11px] text-[#64748B] mt-0.5">Display timestamps in this zone</p>
            </div>
            <div className="w-[200px]">
              <SelectStyle
                value={timeZone}
                onChange={setTimeZone}
                options={[
                  { value: 'ist', label: 'IST (UTC+5:30)' },
                  { value: 'utc', label: 'UTC' },
                  { value: 'est', label: 'EST (UTC-5)' },
                ]}
              />
            </div>
          </div>

          <Separator className="bg-[rgba(255,255,255,0.06)]" />

          {/* Language */}
          <div className="flex items-center justify-between gap-4">
            <div>
              <Label className="text-[13px] font-medium text-[#F1F5F9]">Language</Label>
              <p className="text-[11px] text-[#64748B] mt-0.5">Interface language</p>
            </div>
            <div className="w-[200px]">
              <SelectStyle
                value={language}
                onChange={setLanguage}
                options={[
                  { value: 'en', label: 'English' },
                  { value: 'hi', label: 'Hindi' },
                ]}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Data & Behavior Card */}
      <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-5">
        <h3 className="text-[15px] font-semibold text-[#F1F5F9] mb-4 flex items-center gap-2">
          <Settings size={16} className="text-[#22D3EE]" />
          Data & Behavior
        </h3>

        <div className="space-y-4">
          {/* Auto-save strategies */}
          <div className="flex items-center justify-between py-1">
            <div>
              <p className="text-[13px] font-medium text-[#F1F5F9]">Auto-save Strategies</p>
              <p className="text-[11px] text-[#64748B] mt-0.5">Automatically save strategy changes</p>
            </div>
            <Switch checked={autoSave} onCheckedChange={setAutoSave} />
          </div>

          <Separator className="bg-[rgba(255,255,255,0.06)]" />

          {/* Keyboard Shortcuts */}
          <div className="flex items-center justify-between py-1">
            <div>
              <p className="text-[13px] font-medium text-[#F1F5F9]">Keyboard Shortcuts</p>
              <p className="text-[11px] text-[#64748B] mt-0.5">Enable keyboard navigation and actions</p>
            </div>
            <Switch checked={keyboardShortcuts} onCheckedChange={setKeyboardShortcuts} />
          </div>

          <Separator className="bg-[rgba(255,255,255,0.06)]" />

          {/* Real-time Update Frequency */}
          <div className="flex items-center justify-between gap-4">
            <div>
              <Label className="text-[13px] font-medium text-[#F1F5F9]">Real-time Update Frequency</Label>
              <p className="text-[11px] text-[#64748B] mt-0.5">How often data refreshes</p>
            </div>
            <div className="w-[200px]">
              <SegmentedControl
                value="5s"
                onChange={() => {}}
                options={[
                  { value: '1s', label: '1s' },
                  { value: '5s', label: '5s' },
                  { value: '15s', label: '15s' },
                  { value: 'manual', label: 'Manual' },
                ]}
              />
            </div>
          </div>

          <Separator className="bg-[rgba(255,255,255,0.06)]" />

          {/* Auto-refresh Charts */}
          <div className="flex items-center justify-between py-1">
            <div>
              <p className="text-[13px] font-medium text-[#F1F5F9]">Auto-refresh Charts</p>
              <p className="text-[11px] text-[#64748B] mt-0.5">Update charts in real-time</p>
            </div>
            <Switch defaultChecked />
          </div>

          <Separator className="bg-[rgba(255,255,255,0.06)]" />

          {/* Historical Data Depth */}
          <div className="flex items-center justify-between gap-4">
            <div>
              <Label className="text-[13px] font-medium text-[#F1F5F9]">Historical Data Depth</Label>
              <p className="text-[11px] text-[#64748B] mt-0.5">Available backtesting data range</p>
            </div>
            <div className="w-[180px]">
              <SelectStyle
                value="3y"
                onChange={() => {}}
                options={[
                  { value: '1y', label: '1 Year' },
                  { value: '3y', label: '3 Years' },
                  { value: '5y', label: '5 Years' },
                  { value: '10y', label: '10 Years' },
                ]}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Keyboard Shortcuts Reference */}
      {keyboardShortcuts && (
        <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-5">
          <h3 className="text-[15px] font-semibold text-[#F1F5F9] mb-4 flex items-center gap-2">
            <Keyboard size={16} className="text-[#22D3EE]" />
            Keyboard Shortcuts
          </h3>

          <div className="overflow-hidden rounded-[6px] border border-[rgba(255,255,255,0.06)]">
            <table className="w-full">
              <thead>
                <tr className="bg-[#06060A]">
                  <th className="text-left px-4 py-2 text-[11px] font-medium text-[#64748B] uppercase tracking-wider w-[120px]">Shortcut</th>
                  <th className="text-left px-4 py-2 text-[11px] font-medium text-[#64748B] uppercase tracking-wider">Action</th>
                </tr>
              </thead>
              <tbody>
                {shortcuts.map((s, i) => (
                  <tr
                    key={s.key}
                    className={`border-t border-[rgba(255,255,255,0.06)] hover:bg-[rgba(255,255,255,0.02)] transition-colors ${
                      i % 2 === 0 ? 'bg-transparent' : 'bg-[rgba(255,255,255,0.01)]'
                    }`}
                  >
                    <td className="px-4 py-2">
                      <kbd className="inline-flex items-center px-2 py-0.5 bg-[#06060A] border border-[rgba(255,255,255,0.10)] rounded-[4px] font-mono text-[11px] font-semibold text-[#94A3B8]">
                        {s.key}
                      </kbd>
                    </td>
                    <td className="px-4 py-2 text-[13px] text-[#F1F5F9]">{s.action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Actions Footer */}
      <div className="flex items-center justify-between pt-2 pb-6">
        <Button
          variant="outline"
          className="border-[rgba(255,255,255,0.06)] text-[#EF4444] hover:bg-[rgba(239,68,68,0.08)] hover:border-[rgba(239,68,68,0.20)] text-[13px] h-10"
        >
          <RotateCcw size={14} className="mr-2" />
          Reset to Defaults
        </Button>
        <Button className="bg-[#22D3EE] text-[#030305] hover:brightness-110 font-semibold text-[13px] h-10 px-6 shadow-[0_0_20px_rgba(34,211,238,0.15)]">
          Save Preferences
        </Button>
      </div>
    </div>
  );
}
