import { useState } from 'react';
import { User, Lock, Shield, Key, Trash2, Upload, Check, Copy, Eye, EyeOff } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';

export default function AccountSettings() {
  const [showPassword, setShowPassword] = useState(false);
  const [showApiToken, setShowApiToken] = useState(false);
  const [copied, setCopied] = useState(false);
  const [twoFA, setTwoFA] = useState(false);
  const [name, setName] = useState('Rahul Sharma');
  const [phone, setPhone] = useState('+91 98765 43210');

  const handleCopyToken = () => {
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6 max-w-[720px]">
      {/* Title */}
      <div>
        <h2 className="font-display text-[28px] font-semibold text-[#F1F5F9]">Account Settings</h2>
        <p className="text-[14px] text-[#94A3B8] mt-1">Manage your profile, subscription, and security</p>
      </div>

      {/* Profile Card */}
      <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-5">
        <h3 className="text-[15px] font-semibold text-[#F1F5F9] mb-4 flex items-center gap-2">
          <User size={16} className="text-[#22D3EE]" />
          Profile
        </h3>

        <div className="flex items-start gap-5 mb-5">
          {/* Avatar */}
          <div className="relative shrink-0">
            <div className="w-16 h-16 rounded-full bg-[#06060A] border border-[rgba(255,255,255,0.06)] flex items-center justify-center text-[22px] font-semibold text-[#22D3EE]">
              RS
            </div>
            <button className="absolute -bottom-1 -right-1 w-7 h-7 rounded-full bg-[#22D3EE] flex items-center justify-center hover:brightness-110 transition-all">
              <Upload size={12} className="text-[#030305]" />
            </button>
          </div>

          {/* Name + Tier */}
          <div className="flex-1 space-y-3">
            <div>
              <Label className="text-[12px] font-medium text-[#64748B]">Full Name</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[14px] font-medium focus:border-[#22D3EE] focus:shadow-[0_0_0_2px_rgba(34,211,238,0.08)]"
              />
            </div>
          </div>

          {/* Tier Badge */}
          <div className="shrink-0">
            <Badge className="bg-[rgba(34,211,238,0.12)] text-[#22D3EE] hover:bg-[rgba(34,211,238,0.20)] text-[11px] font-semibold px-2.5 py-0.5">
              PRO
            </Badge>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">Email</Label>
            <Input
              value="rahul@tradeforge.ai"
              readOnly
              className="mt-1 bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#64748B] text-[13px] cursor-not-allowed"
            />
          </div>
          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">Phone</Label>
            <Input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="mt-1 bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] font-mono focus:border-[#22D3EE]"
            />
          </div>
        </div>

        {/* KYC Status */}
        <div className="mt-4 flex items-center gap-3 px-3 py-2.5 bg-[rgba(16,185,129,0.08)] rounded-[6px] border border-[rgba(16,185,129,0.15)]">
          <Shield size={14} className="text-[#10B981]" />
          <span className="text-[12px] text-[#10B981] font-medium">KYC Verified</span>
          <span className="text-[11px] text-[#94A3B8]">— Complete access to all features</span>
        </div>

        <div className="mt-4 flex justify-end">
          <Button className="bg-[#22D3EE] text-[#030305] hover:brightness-110 font-semibold text-[13px] h-9 px-4 shadow-[0_0_20px_rgba(34,211,238,0.15)]">
            Save Changes
          </Button>
        </div>
      </div>

      {/* Subscription Card */}
      <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-5">
        <h3 className="text-[15px] font-semibold text-[#F1F5F9] mb-4">Subscription</h3>

        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className="text-[18px] font-semibold text-[#F1F5F9]">Pro Plan</span>
            <Badge className="bg-[rgba(16,185,129,0.15)] text-[#10B981] text-[11px] font-semibold">
              Active
            </Badge>
          </div>
          <span className="font-mono text-[16px] font-semibold text-[#F1F5F9]">₹2,999/mo</span>
        </div>

        <p className="text-[13px] text-[#94A3B8] mb-4">Next billing: <span className="text-[#F1F5F9]">15 Aug 2025</span></p>

        {/* Usage Stats */}
        <div className="space-y-3 mb-4">
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-[12px] text-[#94A3B8]">Strategies</span>
              <span className="text-[12px] font-mono text-[#F1F5F9]">18 / 25</span>
            </div>
            <div className="h-1.5 bg-[#06060A] rounded-full overflow-hidden">
              <div className="h-full w-[72%] bg-[#22D3EE] rounded-full" />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Check size={12} className="text-[#10B981]" />
            <span className="text-[12px] text-[#94A3B8]">Backtests — Unlimited</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Button variant="outline" className="border-[rgba(255,255,255,0.06)] text-[#F1F5F9] hover:bg-[#1A1A25] hover:border-[rgba(255,255,255,0.10)] text-[13px] h-9">
            Upgrade
          </Button>
          <Button variant="ghost" className="text-[#64748B] hover:text-[#F1F5F9] hover:bg-[#1A1A25] text-[13px] h-9">
            Cancel
          </Button>
        </div>
      </div>

      {/* API Usage */}
      <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-5">
        <h3 className="text-[15px] font-semibold text-[#F1F5F9] mb-4">API Usage</h3>
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-[#06060A] rounded-[6px] p-3 border border-[rgba(255,255,255,0.06)]">
            <p className="text-[11px] text-[#64748B] mb-1">Requests Today</p>
            <p className="font-mono text-[18px] font-semibold text-[#F1F5F9]">2,847</p>
          </div>
          <div className="bg-[#06060A] rounded-[6px] p-3 border border-[rgba(255,255,255,0.06)]">
            <p className="text-[11px] text-[#64748B] mb-1">Daily Limit</p>
            <p className="font-mono text-[18px] font-semibold text-[#F1F5F9]">10,000</p>
          </div>
        </div>
      </div>

      {/* Change Password */}
      <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-5">
        <h3 className="text-[15px] font-semibold text-[#F1F5F9] mb-4 flex items-center gap-2">
          <Lock size={16} className="text-[#22D3EE]" />
          Change Password
        </h3>

        <div className="space-y-3">
          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">Current Password</Label>
            <div className="relative mt-1">
              <Input
                type={showPassword ? 'text' : 'password'}
                placeholder="Enter current password"
                className="bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] pr-10 focus:border-[#22D3EE]"
              />
              <button
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#64748B] hover:text-[#94A3B8]"
              >
                {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>
          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">New Password</Label>
            <Input
              type="password"
              placeholder="Enter new password"
              className="mt-1 bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] focus:border-[#22D3EE]"
            />
          </div>
          <div>
            <Label className="text-[12px] font-medium text-[#64748B]">Confirm New Password</Label>
            <Input
              type="password"
              placeholder="Confirm new password"
              className="mt-1 bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[13px] focus:border-[#22D3EE]"
            />
          </div>
          <Button className="bg-[#22D3EE] text-[#030305] hover:brightness-110 font-semibold text-[13px] h-9 px-4">
            Update Password
          </Button>
        </div>
      </div>

      {/* Security - 2FA + API Token */}
      <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-5">
        <h3 className="text-[15px] font-semibold text-[#F1F5F9] mb-4 flex items-center gap-2">
          <Shield size={16} className="text-[#22D3EE]" />
          Security
        </h3>

        {/* 2FA */}
        <div className="flex items-center justify-between py-3 border-b border-[rgba(255,255,255,0.06)]">
          <div>
            <p className="text-[13px] font-medium text-[#F1F5F9]">Two-Factor Authentication</p>
            <p className="text-[11px] text-[#64748B] mt-0.5">Add an extra layer of security</p>
          </div>
          <div className="flex items-center gap-3">
            <Switch checked={twoFA} onCheckedChange={setTwoFA} />
            <Button variant="outline" size="sm" className="border-[rgba(255,255,255,0.06)] text-[#F1F5F9] hover:bg-[#1A1A25] text-[12px] h-8">
              Setup
            </Button>
          </div>
        </div>

        {/* API Access Token */}
        <div className="pt-3">
          <Label className="text-[12px] font-medium text-[#64748B] flex items-center gap-1.5">
            <Key size={12} />
            API Access Token
          </Label>
          <div className="flex items-center gap-2 mt-1">
            <div className="relative flex-1">
              <Input
                type={showApiToken ? 'text' : 'password'}
                value="tf_live_51HYx7qK8Q2M9NpL4vEwR5tUj"
                readOnly
                className="bg-[#06060A] border-[rgba(255,255,255,0.06)] text-[#94A3B8] text-[12px] font-mono pr-20"
              />
              <button
                onClick={() => setShowApiToken(!showApiToken)}
                className="absolute right-10 top-1/2 -translate-y-1/2 text-[#64748B] hover:text-[#94A3B8]"
              >
                {showApiToken ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopyToken}
              className="border-[rgba(255,255,255,0.06)] text-[#F1F5F9] hover:bg-[#1A1A25] h-9 px-3"
            >
              {copied ? <Check size={14} className="text-[#10B981]" /> : <Copy size={14} />}
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="border-[rgba(255,255,255,0.06)] text-[#F1F5F9] hover:bg-[#1A1A25] h-9 px-3 text-[12px]"
            >
              Regenerate
            </Button>
          </div>
        </div>
      </div>

      {/* Danger Zone */}
      <div className="bg-[#12121A] border border-[rgba(239,68,68,0.20)] rounded-[8px] p-5">
        <h3 className="text-[15px] font-semibold text-[#EF4444] mb-2 flex items-center gap-2">
          <Trash2 size={16} />
          Danger Zone
        </h3>
        <p className="text-[13px] text-[#94A3B8] mb-4">
          Deleting your account will permanently remove all your data, strategies, and trading history. This action cannot be undone.
        </p>
        <Button
          variant="outline"
          className="border-[#EF4444] text-[#EF4444] hover:bg-[rgba(239,68,68,0.15)] hover:text-[#EF4444] text-[13px] h-9"
        >
          Delete Account
        </Button>
      </div>
    </div>
  );
}
