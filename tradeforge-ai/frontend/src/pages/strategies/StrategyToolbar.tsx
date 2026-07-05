import { Save, Copy, Trash2, Play, Shield, Rocket, Loader2 } from 'lucide-react';
import type { SavedStrategy } from './types';
import { SEGMENTS } from './types';

const statusColors: Record<SavedStrategy['status'], { bg: string; text: string; label: string }> = {
  active: { bg: 'bg-[rgba(16,185,129,0.15)]', text: 'text-[#10B981]', label: 'Active' },
  paper: { bg: 'bg-[rgba(245,158,11,0.15)]', text: 'text-[#F59E0B]', label: 'Paper' },
  backtesting: { bg: 'bg-[rgba(167,139,250,0.15)]', text: 'text-[#A78BFA]', label: 'Testing' },
  draft: { bg: 'bg-[rgba(100,116,139,0.15)]', text: 'text-[#64748B]', label: 'Draft' },
};

interface StrategyToolbarProps {
  strategy: SavedStrategy | null;
  isLoading?: Record<string, boolean>;
  onSave: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
  onBacktest: () => void;
  onPaperTrade: () => void;
  onDeploy: () => void;
  onStop: () => void;
  onNameChange: (name: string) => void;
  onSegmentChange: (segment: string) => void;
}

export default function StrategyToolbar({
  strategy,
  isLoading = {},
  onSave,
  onDuplicate,
  onDelete,
  onBacktest,
  onPaperTrade,
  onDeploy,
  onStop,
  onNameChange,
  onSegmentChange,
}: StrategyToolbarProps) {
  if (!strategy) return null;

  const status = statusColors[strategy.status];
  const anyLoading = Object.values(isLoading).some(Boolean);

  return (
    <div className="h-12 shrink-0 bg-[#06060A] border-b border-[rgba(255,255,255,0.06)] flex items-center px-4 gap-3">
      {/* Strategy Name */}
      <input
        type="text"
        value={strategy.name}
        onChange={(e) => onNameChange(e.target.value)}
        placeholder="Untitled Strategy"
        disabled={anyLoading}
        className="w-[260px] h-8 px-3 bg-transparent border-b border-transparent focus:border-[#22D3EE] text-[16px] font-display font-semibold text-[#F1F5F9] placeholder:text-[#475569] focus:outline-none transition-all disabled:opacity-50"
      />

      {/* Status Badge */}
      <span className={`text-[11px] font-semibold px-2.5 py-0.5 rounded-full ${status.bg} ${status.text}`}>
        {status.label}
      </span>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Segment Selector */}
      <div className="flex items-center bg-[#12121A] rounded-[6px] p-0.5">
        {SEGMENTS.map((seg) => (
          <button
            key={seg}
            onClick={() => onSegmentChange(seg)}
            disabled={anyLoading}
            className={`px-3 py-1 rounded-[4px] text-[11px] font-medium transition-all disabled:opacity-50 ${
              strategy.segment === seg
                ? 'bg-[#1A1A25] text-[#F1F5F9] shadow-sm'
                : 'text-[#64748B] hover:text-[#94A3B8]'
            }`}
          >
            {seg}
          </button>
        ))}
      </div>

      <div className="w-px h-5 bg-[rgba(255,255,255,0.06)]" />

      {/* Action Buttons */}
      <button
        onClick={onBacktest}
        disabled={anyLoading}
        className="flex items-center gap-1.5 px-3 py-1.5 border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] text-[#94A3B8] hover:text-[#F1F5F9] hover:bg-[#12121A] hover:border-[rgba(167,139,250,0.30)] transition-all disabled:opacity-50"
      >
        <Play size={12} />
        Backtest
      </button>

      <button
        onClick={onPaperTrade}
        disabled={anyLoading || strategy.status === 'paper'}
        className="flex items-center gap-1.5 px-3 py-1.5 border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] text-[#94A3B8] hover:text-[#F59E0B] hover:bg-[#12121A] hover:border-[rgba(245,158,11,0.30)] transition-all disabled:opacity-50"
      >
        <Shield size={12} />
        Paper
      </button>

      <button
        onClick={onSave}
        disabled={isLoading.save || anyLoading}
        className="flex items-center gap-1.5 px-3 py-1.5 border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] text-[#94A3B8] hover:text-[#F1F5F9] hover:bg-[#12121A] transition-all disabled:opacity-50 min-w-[80px]"
      >
        {isLoading.save ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
        Save
      </button>

      {strategy.status === 'active' || strategy.status === 'paper' ? (
        <button
          onClick={onStop}
          disabled={isLoading.stop || anyLoading}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[#EF4444] text-[#FFFFFF] rounded-[4px] text-[12px] font-semibold hover:brightness-110 transition-all hover:shadow-[0_0_20px_rgba(239,68,68,0.15)] active:scale-[0.98] disabled:opacity-50 min-w-[80px]"
        >
          {isLoading.stop ? <Loader2 size={12} className="animate-spin" /> : <Rocket size={12} />}
          Stop
        </button>
      ) : (
        <button
          onClick={onDeploy}
          disabled={isLoading.deploy || anyLoading}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[#22D3EE] text-[#030305] rounded-[4px] text-[12px] font-semibold hover:brightness-110 transition-all hover:shadow-[0_0_20px_rgba(34,211,238,0.15)] active:scale-[0.98] disabled:opacity-50 min-w-[80px]"
        >
          {isLoading.deploy ? <Loader2 size={12} className="animate-spin" /> : <Rocket size={12} />}
          Deploy
        </button>
      )}

      <div className="w-px h-5 bg-[rgba(255,255,255,0.06)]" />

      <button
        onClick={onDuplicate}
        disabled={isLoading.duplicate || anyLoading}
        className="w-7 h-7 flex items-center justify-center rounded-[4px] text-[#475569] hover:text-[#94A3B8] hover:bg-[#12121A] transition-all disabled:opacity-50"
        title="Duplicate"
      >
        {isLoading.duplicate ? <Loader2 size={13} className="animate-spin" /> : <Copy size={13} />}
      </button>

      <button
        onClick={onDelete}
        disabled={isLoading.delete || anyLoading}
        className="w-7 h-7 flex items-center justify-center rounded-[4px] text-[#475569] hover:text-[#EF4444] hover:bg-[rgba(239,68,68,0.10)] transition-all disabled:opacity-50"
        title="Delete"
      >
        {isLoading.delete ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
      </button>
    </div>
  );
}
