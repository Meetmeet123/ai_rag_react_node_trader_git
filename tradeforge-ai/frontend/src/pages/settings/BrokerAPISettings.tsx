import { useState } from 'react';
import { Wifi, WifiOff, Eye, EyeOff, Check, AlertCircle, Lock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';

interface Broker {
  id: string;
  name: string;
  connected: boolean;
  accountId?: string;
  margin?: string;
  lastConnected?: string;
  fields: { key: string; label: string; type: string }[];
}

const brokers: Broker[] = [
  {
    id: 'angel',
    name: 'Angel One SmartAPI',
    connected: true,
    accountId: 'A3***24',
    margin: '₹4,23,500',
    lastConnected: 'Today, 09:15 AM',
    fields: [
      { key: 'apiKey', label: 'API Key', type: 'text' },
      { key: 'apiSecret', label: 'API Secret', type: 'password' },
      { key: 'clientId', label: 'Client ID', type: 'text' },
      { key: 'totpKey', label: 'TOTP Key', type: 'password' },
    ],
  },
  {
    id: 'zerodha',
    name: 'Zerodha Kite',
    connected: false,
    fields: [
      { key: 'apiKey', label: 'API Key', type: 'text' },
      { key: 'apiSecret', label: 'API Secret', type: 'password' },
      { key: 'accessToken', label: 'Access Token', type: 'password' },
    ],
  },
  {
    id: 'fyers',
    name: 'Fyers',
    connected: false,
    fields: [
      { key: 'appId', label: 'App ID', type: 'text' },
      { key: 'secretKey', label: 'Secret Key', type: 'password' },
      { key: 'redirectUri', label: 'Redirect URI', type: 'text' },
    ],
  },
  {
    id: 'upstox',
    name: 'Upstox',
    connected: false,
    fields: [
      { key: 'apiKey', label: 'API Key', type: 'text' },
      { key: 'apiSecret', label: 'API Secret', type: 'password' },
      { key: 'redirectUri', label: 'Redirect URI', type: 'text' },
    ],
  },
];

function BrokerCard({ broker }: { broker: Broker }) {
  const [expanded, setExpanded] = useState(broker.connected);
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [formData, setFormData] = useState<Record<string, string>>(() => {
    if (broker.id === 'angel') {
      return {
        apiKey: 'ABCD****XXXX',
        apiSecret: '••••••••••••••••',
        clientId: 'A3123456',
        totpKey: '••••••••••••••••',
      };
    }
    return {} as Record<string, string>;
  });
  const [isConnected, setIsConnected] = useState(broker.connected);

  const toggleSecret = (key: string) => {
    setShowSecrets((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleConnect = () => {
    setIsConnected(true);
    setExpanded(false);
  };

  const handleDisconnect = () => {
    setIsConnected(false);
    setFormData({});
  };

  return (
    <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-5 transition-all">
      {/* Header Row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Logo placeholder */}
          <div className="w-10 h-10 rounded-full bg-[#06060A] border border-[rgba(255,255,255,0.06)] flex items-center justify-center">
            <span className="text-[13px] font-bold text-[#22D3EE]">
              {broker.name.charAt(0)}
            </span>
          </div>
          <div>
            <h4 className="text-[15px] font-semibold text-[#F1F5F9]">{broker.name}</h4>
            <div className="flex items-center gap-2 mt-0.5">
              {isConnected ? (
                <>
                  <Wifi size={12} className="text-[#10B981]" />
                  <Badge className="bg-[rgba(16,185,129,0.15)] text-[#10B981] text-[10px] font-semibold px-1.5 py-0">
                    Connected
                  </Badge>
                  {broker.accountId && (
                    <span className="text-[11px] font-mono text-[#64748B]">{broker.accountId}</span>
                  )}
                </>
              ) : (
                <>
                  <WifiOff size={12} className="text-[#64748B]" />
                  <span className="text-[11px] text-[#64748B]">Not Connected</span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {isConnected ? (
            <>
              {broker.margin && (
                <div className="hidden sm:block mr-3 text-right">
                  <p className="text-[10px] text-[#64748B]">Available Margin</p>
                  <p className="font-mono text-[12px] font-semibold text-[#F1F5F9]">{broker.margin}</p>
                </div>
              )}
              {broker.lastConnected && (
                <span className="hidden md:block text-[11px] text-[#64748B] mr-2">
                  {broker.lastConnected}
                </span>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setExpanded(!expanded)}
                className="text-[#64748B] hover:text-[#F1F5F9] hover:bg-[#1A1A25] h-8 text-[12px]"
              >
                {expanded ? 'Hide' : 'Edit'}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleDisconnect}
                className="border-[#EF4444] text-[#EF4444] hover:bg-[rgba(239,68,68,0.15)] h-8 text-[12px]"
              >
                Disconnect
              </Button>
            </>
          ) : (
            <Button
              size="sm"
              onClick={() => setExpanded(!expanded)}
              className="bg-[#22D3EE] text-[#030305] hover:brightness-110 h-8 text-[12px] font-semibold"
            >
              {expanded ? 'Cancel' : 'Connect'}
            </Button>
          )}
        </div>
      </div>

      {/* Expanded Form */}
      {expanded && (
        <div className="mt-4 pt-4 border-t border-[rgba(255,255,255,0.06)] space-y-3">
          {broker.fields.map((field) => (
            <div key={field.key}>
              <Label className="text-[12px] font-medium text-[#64748B]">{field.label}</Label>
              <div className="relative mt-1">
                <Input
                  type={showSecrets[field.key] ? 'text' : field.type}
                  value={formData[field.key] || ''}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, [field.key]: e.target.value }))
                  }
                  placeholder={`Enter ${field.label.toLowerCase()}`}
                  className="bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono pr-10 focus:border-[#22D3EE]"
                />
                {field.type === 'password' && (
                  <button
                    onClick={() => toggleSecret(field.key)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[#64748B] hover:text-[#94A3B8]"
                  >
                    {showSecrets[field.key] ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                )}
              </div>
            </div>
          ))}

          <div className="flex items-center gap-3 pt-2">
            {!isConnected ? (
              <Button
                onClick={handleConnect}
                className="bg-[#22D3EE] text-[#030305] hover:brightness-110 font-semibold text-[13px] h-9"
              >
                <Check size={14} className="mr-1.5" />
                Connect Broker
              </Button>
            ) : (
              <Button
                onClick={() => setExpanded(false)}
                className="bg-[#22D3EE] text-[#030305] hover:brightness-110 font-semibold text-[13px] h-9"
              >
                <Check size={14} className="mr-1.5" />
                Save Changes
              </Button>
            )}
            <Button
              variant="ghost"
              onClick={() => setExpanded(false)}
              className="text-[#64748B] hover:text-[#F1F5F9] hover:bg-[#1A1A25] text-[13px] h-9"
            >
              Cancel
            </Button>
          </div>

          <div className="flex items-center gap-1.5 text-[11px] text-[#64748B]">
            <Lock size={10} />
            Your credentials are encrypted and stored securely.
          </div>
        </div>
      )}
    </div>
  );
}

export default function BrokerAPISettings() {
  return (
    <div className="space-y-6 max-w-[720px]">
      <div>
        <h2 className="font-display text-[28px] font-semibold text-[#F1F5F9]">Broker Integration</h2>
        <p className="text-[14px] text-[#94A3B8] mt-1">
          Connect your trading accounts to execute strategies live
        </p>
      </div>

      {/* Info Banner */}
      <div className="flex items-start gap-2.5 px-3 py-2.5 bg-[rgba(245,158,11,0.08)] rounded-[6px] border border-[rgba(245,158,11,0.15)]">
        <AlertCircle size={14} className="text-[#F59E0B] shrink-0 mt-0.5" />
        <p className="text-[12px] text-[#94A3B8]">
          At least one broker must be connected for live trading. Paper trading does not require a broker connection.
        </p>
      </div>

      <div className="space-y-3">
        {brokers.map((broker) => (
          <BrokerCard key={broker.id} broker={broker} />
        ))}
      </div>
    </div>
  );
}
