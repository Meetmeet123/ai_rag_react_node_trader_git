import type { Strategy as ApiStrategy } from '@/types/api';
import type { SavedStrategy, StrategyStatus } from './types';

const API_TO_UI_STATUS: Record<string, StrategyStatus> = {
  draft: 'draft',
  active: 'active',
  paper: 'paper',
  backtesting: 'backtesting',
  archived: 'draft',
};

const UI_TO_API_SEGMENT: Record<string, string> = {
  Stocks: 'equity',
  Futures: 'futures',
  Options: 'options',
  MCX: 'mcx',
};

const API_TO_UI_SEGMENT: Record<string, string> = {
  equity: 'Stocks',
  futures: 'Futures',
  options: 'Options',
  mcx: 'MCX',
  index: 'Stocks',
};

function formatLastModified(dateString?: string): string {
  if (!dateString) return 'Just now';
  const date = new Date(dateString);
  if (Number.isNaN(date.getTime())) return 'Just now';

  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return 'Just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHour < 24) return `${diffHour}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return date.toLocaleDateString();
}

function mapStopLoss(type?: string, value?: number): SavedStrategy['stopLoss'] {
  if (type === 'fixed' || type === 'fixed_pct') return { type: 'fixed', value: value ?? 1.0 };
  if (type === 'trailing') return { type: 'trailing', value: value ?? 1.0 };
  if (type === 'atr') return { type: 'atr', value: value ?? 1.0 };
  return { type: 'fixed', value: value ?? 1.0 };
}

function mapTarget(type?: string, value?: number): SavedStrategy['target'] {
  if (type === 'fixed' || type === 'fixed_pct') return { type: 'fixed', value: value ?? 2.0 };
  if (type === 'rr' || type === 'rr_based') return { type: 'rr', value: value ?? 2.0 };
  if (type === 'trailing') return { type: 'trailing', value: value ?? 2.0 };
  return { type: 'fixed', value: value ?? 2.0 };
}

function mapPositionSizing(type?: string, value?: number): SavedStrategy['positionSizing'] {
  if (type === 'fixed' || type === 'fixed_qty') return { type: 'fixed', value: value ?? 1 };
  if (type === 'percent' || type === 'pct_capital') return { type: 'percent', value: value ?? 10 };
  if (type === 'risk' || type === 'risk_based') return { type: 'risk', value: value ?? 1 };
  return { type: 'percent', value: value ?? 10 };
}

function mapSegment(segment?: string): SavedStrategy['segment'] {
  return (API_TO_UI_SEGMENT[segment || ''] || 'Stocks') as SavedStrategy['segment'];
}

function mapConditions(conditions: unknown): SavedStrategy['entryConditions'] {
  if (!Array.isArray(conditions)) return [];
  return conditions.map((c, index) => {
    const cond = c as Record<string, unknown>;
    return {
      id: String(cond.id || `c_${index}_${Date.now()}`),
      indicator: String(cond.indicator || ''),
      operator: String(cond.operator || ''),
      value: String(cond.value || ''),
      valueType: (cond.valueType as 'indicator' | 'number') || 'indicator',
      logic: index > 0 ? (cond.logic as 'AND' | 'OR') || 'AND' : undefined,
    };
  });
}

export function apiToSaved(strategy: ApiStrategy): SavedStrategy {
  return {
    id: strategy.id,
    name: strategy.name,
    description: strategy.description || '',
    instrument: strategy.instrument,
    segment: mapSegment(strategy.segment),
    status: API_TO_UI_STATUS[strategy.status] || 'draft',
    lastModified: formatLastModified(strategy.updated_at),
    entryConditions: mapConditions(strategy.entry_conditions),
    exitConditions: mapConditions(strategy.exit_conditions),
    stopLoss: mapStopLoss(strategy.stop_loss_type, strategy.stop_loss_value),
    target: mapTarget(strategy.target_type, strategy.target_value),
    positionSizing: mapPositionSizing(strategy.position_sizing_type, strategy.position_sizing_value),
    timeframe: (strategy.timeframe || '1d') as SavedStrategy['timeframe'],
  };
}

export function savedToApiRequest(strategy: SavedStrategy): {
  name: string;
  description: string;
  instrument: string;
  segment: string;
  timeframe: string;
  entry_conditions: unknown[];
  exit_conditions: unknown[];
  stop_loss: { type: string; value: number };
  target: { type: string; value: number };
  position_sizing: { type: string; value: number };
} {
  const targetType = strategy.target.type === 'rr' ? 'rr_based' : strategy.target.type === 'fixed' ? 'fixed_pct' : strategy.target.type;

  const stopLossType =
    strategy.stopLoss.type === 'fixed'
      ? 'fixed_pct'
      : strategy.stopLoss.type === 'trailing'
        ? 'fixed_pct'
        : strategy.stopLoss.type;

  let positionSizingType: string;
  switch (strategy.positionSizing.type) {
    case 'fixed':
      positionSizingType = 'fixed_qty';
      break;
    case 'risk':
      positionSizingType = 'risk_based';
      break;
    case 'percent':
    default:
      positionSizingType = 'pct_capital';
      break;
  }

  return {
    name: strategy.name,
    description: strategy.description,
    instrument: strategy.instrument,
    segment: UI_TO_API_SEGMENT[strategy.segment] || 'equity',
    timeframe: strategy.timeframe.toLowerCase(),
    entry_conditions: strategy.entryConditions,
    exit_conditions: strategy.exitConditions,
    stop_loss: { type: stopLossType, value: strategy.stopLoss.value },
    target: { type: targetType, value: strategy.target.value },
    position_sizing: { type: positionSizingType, value: strategy.positionSizing.value },
  };
}
