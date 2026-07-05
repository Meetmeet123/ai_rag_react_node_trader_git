import { useEffect, useRef } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Clock, Layers, Sliders, Target, Shield } from 'lucide-react';
import type { SavedStrategy, StopLossConfig, TargetConfig, PositionSizingConfig } from './types';
import ConditionBuilder from './ConditionBuilder';
import { TIMEFRAMES, NIFTY50_STOCKS, timeframeLabel } from './types';
import { strategyFormSchema, type StrategyFormData } from './validation';

interface StrategyEditorProps {
  strategy: SavedStrategy | null;
  onUpdate: (strategy: SavedStrategy) => void;
  activeTab: 'entry' | 'exit' | 'risk' | 'params';
  onActiveTabChange: (tab: 'entry' | 'exit' | 'risk' | 'params') => void;
}

function savedToFormData(strategy: SavedStrategy): StrategyFormData {
  return {
    name: strategy.name,
    description: strategy.description,
    instrument: strategy.instrument,
    segment: strategy.segment,
    status: strategy.status,
    timeframe: strategy.timeframe as StrategyFormData['timeframe'],
    entryConditions: strategy.entryConditions,
    exitConditions: strategy.exitConditions,
    stopLoss: strategy.stopLoss,
    target: strategy.target,
    positionSizing: strategy.positionSizing,
  };
}

function formDataToSaved(strategy: SavedStrategy, data: StrategyFormData): SavedStrategy {
  return {
    ...strategy,
    ...data,
  };
}

export default function StrategyEditor({
  strategy,
  onUpdate,
  activeTab,
  onActiveTabChange,
}: StrategyEditorProps) {
  const lastEmittedRef = useRef<SavedStrategy | null>(null);

  const form = useForm<StrategyFormData>({
    resolver: zodResolver(strategyFormSchema),
    defaultValues: strategy ? savedToFormData(strategy) : undefined,
    mode: 'onChange',
  });

  // Reset form when the selected strategy changes
  useEffect(() => {
    if (strategy) {
      form.reset(savedToFormData(strategy));
      lastEmittedRef.current = strategy;
    }
  }, [strategy?.id, form]);

  // Sync fields controlled by the toolbar (name, segment, status) without
  // resetting the whole form and losing in-progress condition edits.
  useEffect(() => {
    if (!strategy) return;
    if (form.getValues('name') !== strategy.name) {
      form.setValue('name', strategy.name, { shouldValidate: true });
    }
    if (form.getValues('segment') !== strategy.segment) {
      form.setValue('segment', strategy.segment, { shouldValidate: true });
    }
    if (form.getValues('status') !== strategy.status) {
      form.setValue('status', strategy.status, { shouldValidate: true });
    }
  }, [strategy?.name, strategy?.segment, strategy?.status, form, strategy]);

  // Watch form values and propagate valid changes upward
  useWatch({ control: form.control });
  useEffect(() => {
    if (!strategy) return;
    const subscription = form.watch((value) => {
      if (!form.formState.isValid) return;
      const data = value as StrategyFormData;
      const updated = formDataToSaved(strategy, data);
      if (JSON.stringify(updated) !== JSON.stringify(lastEmittedRef.current)) {
        lastEmittedRef.current = updated;
        onUpdate(updated);
      }
    });
    return () => subscription.unsubscribe();
  }, [form, strategy, onUpdate]);

  if (!strategy) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[#030305]">
        <div className="text-center">
          <Layers size={32} className="text-[#1A1A25] mx-auto mb-3" />
          <p className="text-[14px] text-[#475569]">Select a strategy or create a new one</p>
        </div>
      </div>
    );
  }

  const tabs = [
    { key: 'entry' as const, label: 'Entry Rules', icon: Target },
    { key: 'exit' as const, label: 'Exit Rules', icon: Shield },
    { key: 'risk' as const, label: 'Risk & Position', icon: Sliders },
    { key: 'params' as const, label: 'Parameters', icon: Clock },
  ];

  const fieldError = (name: keyof StrategyFormData) => {
    const error = form.formState.errors[name];
    return error ? <p className="text-[11px] text-[#EF4444] mt-1">{error.message}</p> : null;
  };

  return (
    <div className="flex-1 flex flex-col bg-[#030305] overflow-hidden">
      {/* Sub-tabs */}
      <div className="flex items-center gap-1 px-4 py-2 border-b border-[rgba(255,255,255,0.06)]">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => onActiveTabChange(tab.key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-[6px] text-[12px] font-medium transition-all ${
              activeTab === tab.key
                ? 'bg-[#12121A] text-[#22D3EE]'
                : 'text-[#64748B] hover:text-[#94A3B8] hover:bg-[rgba(255,255,255,0.02)]'
            }`}
          >
            <tab.icon size={12} />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-5">
        {activeTab === 'entry' && (
          <div className="max-w-[700px] space-y-4">
            <ConditionBuilder
              title="Entry Conditions"
              conditions={form.watch('entryConditions')}
              onChange={(conds) => form.setValue('entryConditions', conds, { shouldValidate: true })}
            />
            {fieldError('entryConditions')}
            <div className="bg-[rgba(34,211,238,0.04)] border border-[rgba(34,211,238,0.08)] rounded-[8px] p-4">
              <p className="text-[12px] text-[#94A3B8]">
                <span className="text-[#22D3EE] font-semibold">Tip:</span> Entry conditions define when to open a position.
                Combine multiple indicators using AND/OR logic for more precise signals.
              </p>
            </div>
          </div>
        )}

        {activeTab === 'exit' && (
          <div className="max-w-[700px] space-y-4">
            <ConditionBuilder
              title="Exit Conditions"
              conditions={form.watch('exitConditions')}
              onChange={(conds) => form.setValue('exitConditions', conds, { shouldValidate: true })}
            />
            {fieldError('exitConditions')}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <StopLossEditor
                value={form.watch('stopLoss')}
                onChange={(sl) => form.setValue('stopLoss', sl, { shouldValidate: true })}
                error={form.formState.errors.stopLoss?.message}
              />
              <TargetEditor
                value={form.watch('target')}
                onChange={(t) => form.setValue('target', t, { shouldValidate: true })}
                error={form.formState.errors.target?.message}
              />
            </div>
          </div>
        )}

        {activeTab === 'risk' && (
          <div className="max-w-[700px] space-y-4">
            <PositionSizingEditor
              value={form.watch('positionSizing')}
              onChange={(ps) => form.setValue('positionSizing', ps, { shouldValidate: true })}
              error={form.formState.errors.positionSizing?.message}
            />
          </div>
        )}

        {activeTab === 'params' && (
          <div className="max-w-[500px] space-y-5">
            {/* Timeframe */}
            <div>
              <label className="text-[12px] font-medium text-[#94A3B8] mb-2 block">Timeframe</label>
              <div className="flex flex-wrap gap-2">
                {TIMEFRAMES.map((tf) => (
                  <button
                    key={tf}
                    type="button"
                    onClick={() => form.setValue('timeframe', tf, { shouldValidate: true })}
                    className={`px-3 py-1.5 rounded-[6px] text-[12px] font-mono font-medium transition-all ${
                      form.watch('timeframe') === tf
                        ? 'bg-[rgba(34,211,238,0.12)] text-[#22D3EE] border border-[rgba(34,211,238,0.20)]'
                        : 'bg-[#12121A] text-[#64748B] border border-[rgba(255,255,255,0.06)] hover:text-[#94A3B8]'
                    }`}
                  >
                    {timeframeLabel(tf)}
                  </button>
                ))}
              </div>
              {fieldError('timeframe')}
            </div>

            {/* Instrument */}
            <div>
              <label className="text-[12px] font-medium text-[#94A3B8] mb-2 block">Instrument</label>
              <select
                {...form.register('instrument')}
                className="w-full h-9 px-3 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[6px] text-[13px] text-[#F1F5F9] font-mono focus:outline-none focus:border-[#22D3EE]"
              >
                <option value="NIFTY50">NIFTY 50 Index</option>
                <option value="BANKNIFTY">BANKNIFTY Index</option>
                <option value="FINNIFTY">FINNIFTY Index</option>
                <option value="SENSEX">SENSEX Index</option>
                {NIFTY50_STOCKS.map((stock) => (
                  <option key={stock} value={stock}>{stock}</option>
                ))}
              </select>
              {fieldError('instrument')}
            </div>

            {/* Description */}
            <div>
              <label className="text-[12px] font-medium text-[#94A3B8] mb-2 block">Description</label>
              <textarea
                {...form.register('description')}
                rows={3}
                className="w-full px-3 py-2 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[6px] text-[13px] text-[#F1F5F9] placeholder:text-[#475569] focus:outline-none focus:border-[#22D3EE] resize-none"
              />
              {fieldError('description')}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Sub-components ─── */

function StopLossEditor({
  value,
  onChange,
  error,
}: {
  value: StopLossConfig;
  onChange: (v: StopLossConfig) => void;
  error?: string;
}) {
  return (
    <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.02)]">
        <Shield size={14} className="text-[#EF4444]" />
        <span className="text-[14px] font-semibold text-[#F1F5F9]">Stop Loss</span>
      </div>
      <div className="p-4 space-y-3">
        <select
          value={value.type}
          onChange={(e) => onChange({ ...value, type: e.target.value as StopLossConfig['type'] })}
          className="w-full h-8 px-2 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] text-[#F1F5F9] focus:outline-none focus:border-[#22D3EE]"
        >
          <option value="fixed">Fixed %</option>
          <option value="trailing">Trailing Stop</option>
          <option value="atr">ATR-based</option>
        </select>
        <div className="flex items-center gap-2">
          <input
            type="number"
            value={value.value}
            onChange={(e) => onChange({ ...value, value: parseFloat(e.target.value) || 0 })}
            step={0.1}
            min={0}
            className="flex-1 h-8 px-2 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[13px] text-[#F1F5F9] font-mono focus:outline-none focus:border-[#22D3EE]"
          />
          <span className="text-[11px] text-[#64748B]">
            {value.type === 'fixed' ? '%' : value.type === 'trailing' ? '% trail' : 'x ATR'}
          </span>
        </div>
        {error && <p className="text-[11px] text-[#EF4444]">{error}</p>}
      </div>
    </div>
  );
}

function TargetEditor({
  value,
  onChange,
  error,
}: {
  value: TargetConfig;
  onChange: (v: TargetConfig) => void;
  error?: string;
}) {
  const labels: Record<TargetConfig['type'], string> = {
    fixed: '% profit',
    rr: 'R:R ratio',
    trailing: '% trail',
  };

  return (
    <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.02)]">
        <Target size={14} className="text-[#10B981]" />
        <span className="text-[14px] font-semibold text-[#F1F5F9]">Profit Target</span>
      </div>
      <div className="p-4 space-y-3">
        <select
          value={value.type}
          onChange={(e) => onChange({ ...value, type: e.target.value as TargetConfig['type'] })}
          className="w-full h-8 px-2 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] text-[#F1F5F9] focus:outline-none focus:border-[#22D3EE]"
        >
          <option value="fixed">Fixed %</option>
          <option value="rr">Risk:Reward Ratio</option>
          <option value="trailing">Trailing</option>
        </select>
        <div className="flex items-center gap-2">
          <input
            type="number"
            value={value.value}
            onChange={(e) => onChange({ ...value, value: parseFloat(e.target.value) || 0 })}
            step={0.1}
            min={0}
            className="flex-1 h-8 px-2 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[13px] text-[#F1F5F9] font-mono focus:outline-none focus:border-[#22D3EE]"
          />
          <span className="text-[11px] text-[#64748B]">{labels[value.type]}</span>
        </div>
        {error && <p className="text-[11px] text-[#EF4444]">{error}</p>}
      </div>
    </div>
  );
}

function PositionSizingEditor({
  value,
  onChange,
  error,
}: {
  value: PositionSizingConfig;
  onChange: (v: PositionSizingConfig) => void;
  error?: string;
}) {
  const labels: Record<PositionSizingConfig['type'], string> = {
    fixed: 'shares/lots',
    percent: '% of capital',
    risk: '% risk per trade',
  };

  return (
    <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.02)]">
        <Layers size={14} className="text-[#A78BFA]" />
        <span className="text-[14px] font-semibold text-[#F1F5F9]">Position Sizing</span>
      </div>
      <div className="p-4 space-y-3">
        <select
          value={value.type}
          onChange={(e) => onChange({ ...value, type: e.target.value as PositionSizingConfig['type'] })}
          className="w-full h-8 px-2 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] text-[#F1F5F9] focus:outline-none focus:border-[#22D3EE]"
        >
          <option value="fixed">Fixed Quantity</option>
          <option value="percent">% of Capital</option>
          <option value="risk">Risk-based</option>
        </select>
        <div className="flex items-center gap-2">
          <input
            type="number"
            value={value.value}
            onChange={(e) => onChange({ ...value, value: parseFloat(e.target.value) || 0 })}
            step={value.type === 'fixed' ? 1 : 0.1}
            min={0.000001}
            className="flex-1 h-8 px-2 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[13px] text-[#F1F5F9] font-mono focus:outline-none focus:border-[#22D3EE]"
          />
          <span className="text-[11px] text-[#64748B]">{labels[value.type]}</span>
        </div>
        {error && <p className="text-[11px] text-[#EF4444]">{error}</p>}
      </div>
    </div>
  );
}
