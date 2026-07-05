import { useState } from 'react';
import { Mail, Smartphone, MessageSquare, Volume2, Send, Headphones } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Slider } from '@/components/ui/slider';
import { Badge } from '@/components/ui/badge';

interface EventOption {
  id: string;
  label: string;
  priority: 'High' | 'Medium' | 'Low';
}

const eventOptions: EventOption[] = [
  { id: 'signal', label: 'Signal Generated', priority: 'Medium' },
  { id: 'executed', label: 'Order Executed', priority: 'High' },
  { id: 'failed', label: 'Order Failed / Rejected', priority: 'High' },
  { id: 'sl', label: 'Stop Loss Hit', priority: 'High' },
  { id: 'target', label: 'Target Reached', priority: 'High' },
  { id: 'daily-limit', label: 'Daily Loss Limit Reached', priority: 'High' },
  { id: 'drawdown', label: 'Drawdown Alert', priority: 'High' },
  { id: 'error', label: 'Strategy Error', priority: 'Medium' },
  { id: 'broker', label: 'Broker Disconnected', priority: 'High' },
  { id: 'market', label: 'Market Open / Close', priority: 'Low' },
];

const priorityColors = {
  High: 'bg-[rgba(239,68,68,0.15)] text-[#EF4444]',
  Medium: 'bg-[rgba(245,158,11,0.15)] text-[#F59E0B]',
  Low: 'bg-[rgba(100,116,139,0.15)] text-[#64748B]',
};

function EventCheckboxes({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (id: string) => void;
}) {
  return (
    <div className="space-y-1.5">
      {eventOptions.map((event) => (
        <label
          key={event.id}
          className="flex items-center justify-between p-2 rounded-[6px] hover:bg-[#1A1A25] transition-colors cursor-pointer group"
        >
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={selected.includes(event.id)}
              onChange={() => onChange(event.id)}
              className="w-4 h-4 rounded border-[rgba(255,255,255,0.14)] bg-[#06060A] text-[#22D3EE] focus:ring-[#22D3EE] focus:ring-offset-0 cursor-pointer accent-[#22D3EE]"
            />
            <span className="text-[13px] text-[#F1F5F9] group-hover:text-[#F1F5F9]">{event.label}</span>
          </div>
          <Badge className={`${priorityColors[event.priority]} text-[10px] font-semibold px-1.5 py-0`}>
            {event.priority}
          </Badge>
        </label>
      ))}
    </div>
  );
}

export default function NotificationSettings() {
  const [emailEnabled, setEmailEnabled] = useState(true);
  const [emailEvents, setEmailEvents] = useState(['executed', 'sl', 'target', 'daily-limit', 'error', 'broker']);
  const [pushEnabled, setPushEnabled] = useState(true);
  const [pushEvents, setPushEvents] = useState(['executed', 'sl', 'target', 'failed']);
  const [telegramEnabled, setTelegramEnabled] = useState(false);
  const [telegramToken, setTelegramToken] = useState('');
  const [telegramChatId, setTelegramChatId] = useState('');
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [volume, setVolume] = useState([70]);

  const toggleEvent = (setter: React.Dispatch<React.SetStateAction<string[]>>, id: string) => {
    setter((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  return (
    <div className="space-y-6 max-w-[720px]">
      <div>
        <h2 className="font-display text-[28px] font-semibold text-[#F1F5F9]">Notifications</h2>
        <p className="text-[14px] text-[#94A3B8] mt-1">
          Configure how and when you want to be notified
        </p>
      </div>

      {/* Email Notifications */}
      <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Mail size={16} className="text-[#22D3EE]" />
            <h3 className="text-[15px] font-semibold text-[#F1F5F9]">Email Notifications</h3>
          </div>
          <Switch checked={emailEnabled} onCheckedChange={setEmailEnabled} />
        </div>

        {emailEnabled && (
          <>
            <div className="mb-3">
              <Label className="text-[12px] font-medium text-[#64748B]">Email Address</Label>
              <Input
                value="rahul@tradeforge.ai"
                readOnly
                className="mt-1 bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#64748B] text-[13px] cursor-not-allowed"
              />
            </div>
            <p className="text-[11px] font-medium text-[#64748B] mb-2 uppercase tracking-wide">Events</p>
            <EventCheckboxes
              selected={emailEvents}
              onChange={(id) => toggleEvent(setEmailEvents, id)}
            />
          </>
        )}
      </div>

      {/* Push Notifications */}
      <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Smartphone size={16} className="text-[#A78BFA]" />
            <h3 className="text-[15px] font-semibold text-[#F1F5F9]">Push Notifications</h3>
          </div>
          <Switch checked={pushEnabled} onCheckedChange={setPushEnabled} />
        </div>

        {pushEnabled && (
          <>
            <p className="text-[11px] font-medium text-[#64748B] mb-2 uppercase tracking-wide">Events</p>
            <EventCheckboxes
              selected={pushEvents}
              onChange={(id) => toggleEvent(setPushEvents, id)}
            />
          </>
        )}
      </div>

      {/* Telegram Notifications */}
      <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <MessageSquare size={16} className="text-[#60A5FA]" />
            <h3 className="text-[15px] font-semibold text-[#F1F5F9]">Telegram Notifications</h3>
          </div>
          <Switch checked={telegramEnabled} onCheckedChange={setTelegramEnabled} />
        </div>

        {telegramEnabled && (
          <div className="space-y-3">
            <div>
              <Label className="text-[12px] font-medium text-[#64748B]">Bot Token</Label>
              <div className="relative mt-1">
                <Input
                  type="password"
                  value={telegramToken}
                  onChange={(e) => setTelegramToken(e.target.value)}
                  placeholder="Enter your Telegram bot token"
                  className="bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono focus:border-[#22D3EE]"
                />
              </div>
            </div>
            <div>
              <Label className="text-[12px] font-medium text-[#64748B]">Chat ID</Label>
              <Input
                value={telegramChatId}
                onChange={(e) => setTelegramChatId(e.target.value)}
                placeholder="Enter your Telegram chat ID"
                className="mt-1 bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono focus:border-[#22D3EE]"
              />
            </div>
            <p className="text-[11px] text-[#64748B] flex items-center gap-1">
              <Headphones size={10} />
              Create a bot with @BotFather on Telegram to get a token
            </p>
          </div>
        )}
      </div>

      {/* Sound Alerts */}
      <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Volume2 size={16} className="text-[#F59E0B]" />
            <h3 className="text-[15px] font-semibold text-[#F1F5F9]">Sound Alerts</h3>
          </div>
          <Switch checked={soundEnabled} onCheckedChange={setSoundEnabled} />
        </div>

        {soundEnabled && (
          <div>
            <div className="flex items-center justify-between mb-2">
              <Label className="text-[12px] font-medium text-[#64748B]">Alert Volume</Label>
              <span className="font-mono text-[12px] text-[#22D3EE]">{volume[0]}%</span>
            </div>
            <Slider
              value={volume}
              onValueChange={setVolume}
              min={0}
              max={100}
              step={5}
              className="w-full"
            />
          </div>
        )}
      </div>

      {/* Test Notification */}
      <div className="flex items-center gap-3 pt-2 pb-6">
        <Button
          variant="outline"
          className="border-[rgba(255,255,255,0.06)] text-[#F1F5F9] hover:bg-[#1A1A25] hover:border-[rgba(255,255,255,0.10)] text-[13px] h-10"
        >
          <Send size={14} className="mr-2" />
          Send Test Notification
        </Button>
        <Button className="bg-[#22D3EE] text-[#030305] hover:brightness-110 font-semibold text-[13px] h-10 px-6 shadow-[0_0_20px_rgba(34,211,238,0.15)]">
          Save Preferences
        </Button>
      </div>
    </div>
  );
}
