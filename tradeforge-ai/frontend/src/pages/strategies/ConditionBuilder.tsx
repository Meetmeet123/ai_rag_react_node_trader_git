import { useState } from 'react';
import { Plus, X, TrendingUp, TrendingDown } from 'lucide-react';
import type { Condition } from './types';
import { INDICATORS, OPERATORS } from './types';

interface ConditionBuilderProps {
  title: string;
  conditions: Condition[];
  onChange: (conditions: Condition[]) => void;
}

const indicatorOptions = INDICATORS.map((i) => {
  const params = i.params.map((p) => p.default).join(',');
  return params ? `${i.shortName}(${params})` : i.shortName;
});
const allOptions = [
  ...indicatorOptions,
  'Price',
  'VWAP',
  'BB Upper',
  'BB Lower',
  'BB Mid',
  'MACD Line',
  'MACD Signal',
  'MACD Hist',
  'Volume',
];

export default function ConditionBuilder({ title, conditions, onChange }: ConditionBuilderProps) {
  const [nextLogic, setNextLogic] = useState<'AND' | 'OR'>('AND');

  const addCondition = () => {
    const newCondition: Condition = {
      id: `c_${Date.now()}`,
      indicator: 'SMA(20)',
      operator: 'crosses_above',
      value: 'SMA(50)',
      valueType: 'indicator',
      ...(conditions.length > 0 ? { logic: nextLogic } : {}),
    };
    onChange([...conditions, newCondition]);
  };

  const removeCondition = (id: string) => {
    const filtered = conditions.filter((c) => c.id !== id);
    // Remove logic from first remaining condition
    if (filtered.length > 0) {
      const cleaned = filtered.map((c, i) => (i === 0 ? { ...c, logic: undefined } : c));
      onChange(cleaned);
    } else {
      onChange([]);
    }
  };

  const updateCondition = (id: string, updates: Partial<Condition>) => {
    onChange(conditions.map((c) => (c.id === id ? { ...c, ...updates } : c)));
  };

  return (
    <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.02)]">
        {title.includes('Entry') ? (
          <TrendingUp size={14} className="text-[#10B981]" />
        ) : (
          <TrendingDown size={14} className="text-[#EF4444]" />
        )}
        <span className="text-[14px] font-semibold text-[#F1F5F9]">{title}</span>
        <span className="text-[11px] text-[#64748B] ml-auto">{conditions.length} rule{conditions.length !== 1 ? 's' : ''}</span>
      </div>

      <div className="p-4 space-y-3">
        {conditions.length === 0 && (
          <p className="text-[12px] text-[#475569] text-center py-3 italic">No conditions set. Click + to add.</p>
        )}

        {conditions.map((condition, index) => (
          <div key={condition.id} className="space-y-2">
            {/* Logic connector */}
            {index > 0 && condition.logic && (
              <div className="flex items-center justify-center py-1">
                <span className={`text-[11px] font-bold px-3 py-0.5 rounded-full ${
                  condition.logic === 'AND'
                    ? 'bg-[rgba(34,211,238,0.12)] text-[#22D3EE]'
                    : 'bg-[rgba(167,139,250,0.12)] text-[#A78BFA]'
                }`}>
                  {condition.logic}
                </span>
              </div>
            )}

            {/* Condition row */}
            <div className="flex items-center gap-2 bg-[#06060A] rounded-[6px] p-2 border border-[rgba(255,255,255,0.06)]">
              {/* Indicator */}
              <select
                value={condition.indicator}
                onChange={(e) => updateCondition(condition.id, { indicator: e.target.value })}
                className="flex-1 min-w-0 h-7 px-2 bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] text-[#F1F5F9] focus:outline-none focus:border-[#22D3EE]"
              >
                {allOptions.map((opt) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>

              {/* Operator */}
              <select
                value={condition.operator}
                onChange={(e) => updateCondition(condition.id, { operator: e.target.value })}
                className="h-7 px-2 bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] text-[#F1F5F9] focus:outline-none focus:border-[#22D3EE]"
              >
                {OPERATORS.map((op) => (
                  <option key={op.value} value={op.value}>{op.label}</option>
                ))}
              </select>

              {/* Value */}
              <div className="flex items-center gap-1">
                <select
                  value={condition.valueType}
                  onChange={(e) => updateCondition(condition.id, { valueType: e.target.value as 'indicator' | 'number' })}
                  className="h-7 px-1 bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[11px] text-[#94A3B8]"
                >
                  <option value="indicator">Ind</option>
                  <option value="number">#</option>
                </select>
                {condition.valueType === 'indicator' ? (
                  <select
                    value={condition.value}
                    onChange={(e) => updateCondition(condition.id, { value: e.target.value })}
                    className="flex-1 min-w-[60px] h-7 px-2 bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] text-[#F1F5F9]"
                  >
                    {allOptions.map((opt) => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="number"
                    value={condition.value}
                    onChange={(e) => updateCondition(condition.id, { value: e.target.value })}
                    className="w-[70px] h-7 px-2 bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[4px] text-[12px] text-[#F1F5F9] font-mono focus:outline-none focus:border-[#22D3EE]"
                  />
                )}
              </div>

              {/* Remove */}
              <button
                onClick={() => removeCondition(condition.id)}
                className="w-6 h-6 flex items-center justify-center rounded-[4px] text-[#475569] hover:text-[#EF4444] hover:bg-[rgba(239,68,68,0.10)] transition-all shrink-0"
              >
                <X size={12} />
              </button>
            </div>
          </div>
        ))}

        {/* Logic selector for next condition */}
        {conditions.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-[#64748B]">Next:</span>
            <button
              onClick={() => setNextLogic(nextLogic === 'AND' ? 'OR' : 'AND')}
              className={`text-[11px] font-bold px-3 py-0.5 rounded-full transition-all ${
                nextLogic === 'AND'
                  ? 'bg-[rgba(34,211,238,0.12)] text-[#22D3EE]'
                  : 'bg-[rgba(167,139,250,0.12)] text-[#A78BFA]'
              }`}
            >
              {nextLogic}
            </button>
          </div>
        )}

        {/* Add button */}
        <button
          onClick={addCondition}
          className="flex items-center gap-1.5 px-3 py-1.5 border border-dashed border-[rgba(255,255,255,0.10)] rounded-[6px] text-[12px] text-[#64748B] hover:text-[#22D3EE] hover:border-[#22D3EE] transition-all"
        >
          <Plus size={12} />
          Add Condition
        </button>
      </div>
    </div>
  );
}
