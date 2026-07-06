import { TrendingUp, Activity, Target, TrendingDown } from 'lucide-react';
import type { KPIs } from '@/types/api';
import {
  NET_PNL,
  WIN_RATE,
  MAX_DRAWDOWN,
  TOTAL_TRADES,
} from './data';

interface KPICardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  change: string;
  changeColor: string;
  accentColor: string;
  gradient?: string;
}

function KPICard({ icon, label, value, change, changeColor, accentColor, gradient }: KPICardProps) {
  return (
    <div
      className={`bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-5 relative overflow-hidden ${
        gradient || ''
      }`}
      style={gradient ? {
        background: gradient,
      } : undefined}
    >
      {/* Top accent line */}
      <div className="absolute top-0 left-0 right-0 h-[2px] rounded-t-[8px]" style={{ backgroundColor: accentColor }} />

      <div className="flex items-start justify-between mb-3">
        <span className="text-[12px] font-medium text-[#64748B]">{label}</span>
        <div style={{ color: accentColor }}>{icon}</div>
      </div>

      <div className="text-[28px] font-mono font-semibold text-[#F1F5F9] mb-1" style={{ color: accentColor === '#22D3EE' ? '#F1F5F9' : undefined }}>
        {value}
      </div>

      <span className={`text-[12px] font-medium ${changeColor}`}>{change}</span>
    </div>
  );
}

interface KPICardsRowProps {
  kpis?: KPIs;
}

export default function KPICardsRow({ kpis }: KPICardsRowProps) {
  const netPnl = kpis?.net_pnl ?? NET_PNL;
  const totalTrades = kpis?.total_trades ?? TOTAL_TRADES;
  const winRate = kpis?.win_rate ?? WIN_RATE;
  const maxDrawdown = kpis?.max_drawdown ?? MAX_DRAWDOWN;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <KPICard
        icon={<TrendingUp size={20} />}
        label="Net P&L"
        value={`${netPnl >= 0 ? '+' : ''}₹${Math.abs(netPnl).toLocaleString('en-IN')}`}
        change="+12.5% vs last period"
        changeColor="text-[#10B981]"
        accentColor="#10B981"
        gradient="linear-gradient(180deg, rgba(16,185,129,0.08) 0%, transparent 100%)"
      />

      <KPICard
        icon={<Activity size={20} />}
        label="Total Trades"
        value={totalTrades.toString()}
        change="+8 vs last period"
        changeColor="text-[#94A3B8]"
        accentColor="#22D3EE"
      />

      <KPICard
        icon={<Target size={20} />}
        label="Win Rate"
        value={`${winRate}%`}
        change="+3.2% vs last period"
        changeColor="text-[#94A3B8]"
        accentColor="#A78BFA"
      />

      <KPICard
        icon={<TrendingDown size={20} />}
        label="Max Drawdown"
        value={`-₹${Math.abs(maxDrawdown).toLocaleString('en-IN')}`}
        change="-2.1% vs last period"
        changeColor="text-[#EF4444]"
        accentColor="#EF4444"
        gradient="linear-gradient(180deg, rgba(239,68,68,0.08) 0%, transparent 100%)"
      />
    </div>
  );
}
