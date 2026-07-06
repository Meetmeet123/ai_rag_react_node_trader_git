import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router';
import { toast } from 'sonner';
import {
  Landmark,
  Wifi,
  WifiOff,
  Save,
  Plug,
  Unplug,
  ExternalLink,
  AlertCircle,
  Lock,
  Eye,
  EyeOff,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  fetchBrokers,
  fetchBrokerConfig,
  saveBrokerConfig,
  deleteBrokerConfig,
  connectBroker,
  disconnectBroker,
  fetchBrokerStatus,
  fetchUpstoxLoginUrl,
  exchangeUpstoxToken,
} from '@/lib/api';
import type { BrokerConfig, BrokerStatusResponse } from '@/types/api';

const POLL_INTERVAL_MS = 5000;

const SUPPORTED_BROKERS = [
  { value: 'paper', label: 'Paper Trading' },
  { value: 'upstox', label: 'Upstox' },
];

interface FormState {
  broker: string;
  apiKey: string;
  apiSecret: string;
  clientId: string;
  accessToken: string;
  redirectUri: string;
  isActive: boolean;
  isPaper: boolean;
}

function defaultFormState(broker = 'paper'): FormState {
  return {
    broker,
    apiKey: '',
    apiSecret: '',
    clientId: '',
    accessToken: '',
    redirectUri: '',
    isActive: true,
    isPaper: broker === 'paper',
  };
}

function configToFormState(config: BrokerConfig): FormState {
  return {
    broker: config.broker || 'paper',
    apiKey: config.api_key || '',
    apiSecret: config.api_secret || '',
    clientId: config.client_id || '',
    accessToken: config.access_token || '',
    redirectUri: config.redirect_uri || '',
    isActive: config.is_active ?? true,
    isPaper: config.is_paper ?? config.broker === 'paper',
  };
}

export default function Brokers() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [supported, setSupported] = useState<string[]>(['paper', 'upstox']);
  const [config, setConfig] = useState<BrokerConfig | null>(null);
  const [status, setStatus] = useState<BrokerStatusResponse | null>(null);
  const [form, setForm] = useState<FormState>(defaultFormState());
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [lastAction, setLastAction] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const brokerOptions = useMemo(() => {
    const available = supported.length > 0 ? supported : SUPPORTED_BROKERS.map((b) => b.value);
    return SUPPORTED_BROKERS.filter((b) => available.includes(b.value));
  }, [supported]);

  const loadData = useCallback(async () => {
    try {
      const [brokersRes, configRes, statusRes] = await Promise.all([
        fetchBrokers(),
        fetchBrokerConfig(),
        fetchBrokerStatus(),
      ]);
      setSupported(brokersRes.supported);
      setConfig(configRes);
      setStatus(statusRes);
      if (configRes) {
        setForm(configToFormState(configRes));
      }
      setLastAction(null);
    } catch (err) {
      const message = err && typeof err === 'object' && 'detail' in err ? String(err.detail) : 'Failed to load broker configuration';
      setLastAction({ type: 'error', message });
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load and status polling
  useEffect(() => {
    loadData();
    const interval = setInterval(async () => {
      try {
        const statusRes = await fetchBrokerStatus();
        setStatus(statusRes);
      } catch {
        // Polling errors are silent; the main loadData handles visible errors
      }
    }, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [loadData]);

  // Handle OAuth redirect code
  useEffect(() => {
    const code = searchParams.get('code');
    if (!code) return;

    const exchange = async () => {
      try {
        const result = await exchangeUpstoxToken(code);
        if (result.success) {
          toast.success(result.message || 'Upstox connected successfully');
        } else {
          toast.error(result.message || 'Failed to exchange Upstox token');
        }
        setLastAction({
          type: result.success ? 'success' : 'error',
          message: result.message || 'Token exchange completed',
        });
      } catch (err) {
        const message = err && typeof err === 'object' && 'detail' in err ? String(err.detail) : 'Token exchange failed';
        toast.error(message);
        setLastAction({ type: 'error', message });
      } finally {
        // Remove the code from the URL without reloading
        setSearchParams({}, { replace: true });
        await loadData();
      }
    };

    exchange();
  }, [searchParams, setSearchParams, loadData]);

  const updateForm = useCallback(<K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => {
      const next = { ...prev, [key]: value };
      if (key === 'broker') {
        next.isPaper = value === 'paper';
      }
      return next;
    });
  }, []);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setLastAction(null);
    try {
      const payload = {
        broker: form.broker,
        api_key: form.broker === 'paper' ? null : form.apiKey || null,
        api_secret: form.broker === 'paper' ? null : form.apiSecret || null,
        client_id: form.broker === 'paper' ? null : form.clientId || null,
        access_token: form.broker === 'paper' ? null : form.accessToken || null,
        redirect_uri: form.broker === 'paper' ? null : form.redirectUri || null,
        is_active: form.isActive,
        is_paper: form.isPaper,
      };
      const saved = await saveBrokerConfig(payload);
      setConfig(saved);
      setForm(configToFormState(saved));
      toast.success('Broker configuration saved');
      setLastAction({ type: 'success', message: 'Configuration saved successfully' });
    } catch (err) {
      const message = err && typeof err === 'object' && 'detail' in err ? String(err.detail) : 'Failed to save configuration';
      toast.error(message);
      setLastAction({ type: 'error', message });
    } finally {
      setSaving(false);
    }
  }, [form]);

  const handleConnect = useCallback(async () => {
    setConnecting(true);
    setLastAction(null);
    try {
      const result = await connectBroker(form.broker);
      if (result.success) {
        toast.success(result.message || `${form.broker} connected`);
      } else {
        toast.error(result.message || `Failed to connect ${form.broker}`);
      }
      setLastAction({
        type: result.success ? 'success' : 'error',
        message: result.message || 'Connection attempt completed',
      });
    } catch (err) {
      const message = err && typeof err === 'object' && 'detail' in err ? String(err.detail) : 'Failed to connect broker';
      toast.error(message);
      setLastAction({ type: 'error', message });
    } finally {
      setConnecting(false);
      await loadData();
    }
  }, [form.broker, loadData]);

  const handleDisconnect = useCallback(async () => {
    setConnecting(true);
    setLastAction(null);
    try {
      const result = await disconnectBroker();
      if (result.success) {
        toast.success(result.message || 'Broker disconnected');
      } else {
        toast.error(result.message || 'Failed to disconnect broker');
      }
      setLastAction({
        type: result.success ? 'success' : 'error',
        message: result.message || 'Disconnection completed',
      });
    } catch (err) {
      const message = err && typeof err === 'object' && 'detail' in err ? String(err.detail) : 'Failed to disconnect broker';
      toast.error(message);
      setLastAction({ type: 'error', message });
    } finally {
      setConnecting(false);
      await loadData();
    }
  }, [loadData]);

  const handleDelete = useCallback(async () => {
    if (!config?.id) return;
    setLastAction(null);
    try {
      const result = await deleteBrokerConfig(config.id);
      if (result.success) {
        toast.success(result.message || 'Configuration deleted');
        setConfig(null);
        setForm(defaultFormState(form.broker));
      } else {
        toast.error(result.message || 'Failed to delete configuration');
      }
    } catch (err) {
      const message = err && typeof err === 'object' && 'detail' in err ? String(err.detail) : 'Failed to delete configuration';
      toast.error(message);
      setLastAction({ type: 'error', message });
    }
  }, [config?.id, form.broker]);

  const handleUpstoxLogin = useCallback(async () => {
    try {
      const { login_url: loginUrl } = await fetchUpstoxLoginUrl();
      window.open(loginUrl, '_blank', 'noopener,noreferrer');
    } catch (err) {
      const message = err && typeof err === 'object' && 'detail' in err ? String(err.detail) : 'Failed to get Upstox login URL';
      toast.error(message);
      setLastAction({ type: 'error', message });
    }
  }, []);

  const isConnected = status?.is_connected ?? config?.is_connected ?? false;
  const activeBroker = status?.broker ?? config?.broker ?? form.broker;
  const isPaper = status?.is_paper ?? config?.is_paper ?? form.isPaper;
  const isUpstox = form.broker === 'upstox';

  const renderCredentialField = (
    label: string,
    key: keyof Omit<FormState, 'broker' | 'isActive' | 'isPaper'>,
    type: 'text' | 'password' = 'text',
  ) => (
    <div key={key}>
      <Label className="text-[12px] font-medium text-[#64748B]">{label}</Label>
      <div className="relative mt-1">
        <Input
          type={type === 'password' && showSecrets[key] ? 'text' : type}
          value={form[key]}
          onChange={(e) => updateForm(key, e.target.value)}
          placeholder={`Enter ${label.toLowerCase()}`}
          className="bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono pr-10 focus:border-[#22D3EE]"
        />
          {type === 'password' && (
            <button
              type="button"
              onClick={() => setShowSecrets((prev) => ({ ...prev, [key]: !prev[key] }))}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[#64748B] hover:text-[#94A3B8]"
              aria-label={showSecrets[key] ? 'Hide secret' : 'Show secret'}
            >
              {showSecrets[key] ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
          )}
        </div>
      </div>
    );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[300px]">
        <div className="w-8 h-8 border-2 border-[#22D3EE] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-[720px] mx-auto space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3">
          <Landmark size={24} className="text-[#22D3EE]" />
          <h1 className="text-[24px] font-semibold text-[#F1F5F9]">Broker Configuration</h1>
        </div>
        <p className="text-[14px] text-[#94A3B8] mt-1">
          Connect a broker to enable live trading or use paper trading to simulate orders.
        </p>
      </div>

      {/* Info Banner */}
      <div className="flex items-start gap-2.5 px-3 py-2.5 bg-[rgba(245,158,11,0.08)] rounded-[6px] border border-[rgba(245,158,11,0.15)]">
        <AlertCircle size={14} className="text-[#F59E0B] shrink-0 mt-0.5" />
        <p className="text-[12px] text-[#94A3B8]">
          Credentials are encrypted by the backend. Sensitive fields are masked in the UI.
        </p>
      </div>

      {/* Status Card */}
      <Card className="bg-[#12121A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9]">
        <CardHeader className="pb-2">
          <CardTitle className="text-[15px] font-semibold">Connection Status</CardTitle>
          <CardDescription className="text-[#94A3B8] text-[12px]">
            Current broker and connection state
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-3">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center ${
                  isConnected ? 'bg-[rgba(16,185,129,0.15)]' : 'bg-[rgba(100,116,139,0.15)]'
                }`}
              >
                {isConnected ? (
                  <Wifi size={18} className="text-[#10B981]" />
                ) : (
                  <WifiOff size={18} className="text-[#64748B]" />
                )}
              </div>
              <div>
                <span className="text-[13px] font-semibold text-[#F1F5F9] capitalize">
                  {activeBroker || 'Not configured'}
                </span>
                <div className="flex items-center gap-2 mt-0.5">
                  <Badge
                    className={`text-[10px] font-semibold px-1.5 py-0 ${
                      isConnected
                        ? 'bg-[rgba(16,185,129,0.15)] text-[#10B981]'
                        : 'bg-[rgba(100,116,139,0.15)] text-[#64748B]'
                    }`}
                  >
                    {isConnected ? 'Connected' : 'Disconnected'}
                  </Badge>
                  {isPaper ? (
                    <Badge className="bg-[rgba(34,211,238,0.12)] text-[#22D3EE] text-[10px] font-semibold px-1.5 py-0">
                      Paper
                    </Badge>
                  ) : (
                    <Badge className="bg-[rgba(245,158,11,0.12)] text-[#F59E0B] text-[10px] font-semibold px-1.5 py-0">
                      Live
                    </Badge>
                  )}
                </div>
              </div>
            </div>

            {status?.last_connected_at && (
              <div className="text-[11px] text-[#64748B]">
                Last connected: {new Date(status.last_connected_at).toLocaleString()}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Configuration Card */}
      <Card className="bg-[#12121A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9]">
        <CardHeader className="pb-2">
          <CardTitle className="text-[15px] font-semibold">Broker Settings</CardTitle>
          <CardDescription className="text-[#94A3B8] text-[12px]">
            Select a broker and provide the required credentials
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* Broker selector */}
          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">Broker</Label>
            <Select value={form.broker} onValueChange={(value) => updateForm('broker', value)}>
              <SelectTrigger className="mt-1 w-full bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px]">
                <SelectValue placeholder="Select broker" />
              </SelectTrigger>
              <SelectContent className="bg-[#12121A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9]">
                {brokerOptions.map((option) => (
                  <SelectItem
                    key={option.value}
                    value={option.value}
                    className="text-[13px] focus:bg-[#1A1A25] focus:text-[#F1F5F9]"
                  >
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Mode toggles */}
          <div className="flex flex-wrap items-center gap-6">
            <div className="flex items-center gap-3">
              <Switch
                id="is-active"
                checked={form.isActive}
                onCheckedChange={(checked) => updateForm('isActive', checked)}
              />
              <Label htmlFor="is-active" className="text-[13px] text-[#94A3B8]">
                Active
              </Label>
            </div>
            <div className="flex items-center gap-3">
              <Switch
                id="is-paper"
                checked={form.isPaper}
                onCheckedChange={(checked) => updateForm('isPaper', checked)}
                disabled={form.broker === 'paper'}
              />
              <Label htmlFor="is-paper" className="text-[13px] text-[#94A3B8]">
                Paper Mode
              </Label>
            </div>
          </div>

          {/* Credentials */}
          {isUpstox ? (
            <div className="space-y-3">
              {renderCredentialField('API Key', 'apiKey')}
              {renderCredentialField('API Secret', 'apiSecret', 'password')}
              {renderCredentialField('Client ID', 'clientId')}
              {renderCredentialField('Access Token', 'accessToken', 'password')}
              {renderCredentialField('Redirect URI', 'redirectUri')}

              <Button
                type="button"
                variant="outline"
                onClick={handleUpstoxLogin}
                className="w-full border-[rgba(255,255,255,0.06)] text-[#F1F5F9] hover:bg-[#1A1A25] hover:text-[#F1F5F9]"
              >
                <ExternalLink size={14} className="mr-2" />
                Login with Upstox
              </Button>
              <p className="text-[11px] text-[#64748B]">
                Opens the Upstox authorization page. After authorization, you will be redirected back with a code that is automatically exchanged for tokens.
              </p>
            </div>
          ) : (
            <div className="px-3 py-3 bg-[rgba(16,185,129,0.08)] rounded-[6px] border border-[rgba(16,185,129,0.15)]">
              <p className="text-[12px] text-[#94A3B8]">
                Paper trading does not require any credentials. Save the configuration to start using paper mode.
              </p>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex flex-wrap items-center gap-3 pt-2">
            <Button
              onClick={handleSave}
              disabled={saving}
              className="bg-[#22D3EE] text-[#030305] hover:brightness-110 font-semibold text-[13px] h-9"
            >
              <Save size={14} className="mr-1.5" />
              {saving ? 'Saving…' : 'Save Config'}
            </Button>

            {isConnected ? (
              <Button
                onClick={handleDisconnect}
                disabled={connecting}
                variant="outline"
                className="border-[#EF4444] text-[#EF4444] hover:bg-[rgba(239,68,68,0.15)] text-[13px] h-9"
              >
                <Unplug size={14} className="mr-1.5" />
                {connecting ? 'Disconnecting…' : 'Disconnect'}
              </Button>
            ) : (
              <Button
                onClick={handleConnect}
                disabled={connecting || (isUpstox && !form.accessToken && !form.apiKey)}
                className="bg-[#10B981] text-white hover:brightness-110 font-semibold text-[13px] h-9"
              >
                <Plug size={14} className="mr-1.5" />
                {connecting ? 'Connecting…' : 'Connect'}
              </Button>
            )}

            {config?.id && (
              <Button
                onClick={handleDelete}
                variant="ghost"
                className="text-[#64748B] hover:text-[#EF4444] hover:bg-[rgba(239,68,68,0.10)] text-[13px] h-9"
              >
                Delete Config
              </Button>
            )}
          </div>

          {/* Security note */}
          <div className="flex items-center gap-1.5 text-[11px] text-[#64748B]">
            <Lock size={10} />
            Your credentials are encrypted and stored securely by the backend.
          </div>

          {/* Result / error banner */}
          {lastAction && (
            <div
              className={`flex items-start gap-2.5 px-3 py-2.5 rounded-[6px] border text-[12px] ${
                lastAction.type === 'success'
                  ? 'bg-[rgba(16,185,129,0.08)] border-[rgba(16,185,129,0.15)] text-[#10B981]'
                  : 'bg-[rgba(239,68,68,0.08)] border-[rgba(239,68,68,0.15)] text-[#EF4444]'
              }`}
            >
              <AlertCircle size={14} className="shrink-0 mt-0.5" />
              {lastAction.message}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
