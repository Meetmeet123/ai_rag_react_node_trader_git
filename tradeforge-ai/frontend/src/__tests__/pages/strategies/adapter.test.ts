import { describe, it, expect } from 'vitest';
import { apiToSaved, savedToApiRequest } from '@/pages/strategies/adapter';
import type { Strategy } from '@/types/api';

describe('strategy adapter', () => {
  const apiStrategy: Strategy = {
    id: 's1',
    name: 'Golden Cross',
    description: 'SMA crossover strategy',
    instrument: 'NIFTY50',
    segment: 'equity',
    timeframe: '1d',
    status: 'draft',
    is_ai_generated: false,
    entry_conditions: [{ id: 'c1', indicator: 'SMA(20)', operator: 'crosses_above', value: 'SMA(50)', valueType: 'indicator' }],
    exit_conditions: [],
    stop_loss_type: 'fixed_pct',
    stop_loss_value: 1,
    target_type: 'fixed_pct',
    target_value: 2,
    position_sizing_type: 'pct_capital',
    position_sizing_value: 10,
  };

  it('maps an API strategy to the saved UI shape', () => {
    const saved = apiToSaved(apiStrategy);
    expect(saved.id).toBe('s1');
    expect(saved.name).toBe('Golden Cross');
    expect(saved.segment).toBe('Stocks');
    expect(saved.status).toBe('draft');
    expect(saved.stopLoss).toEqual({ type: 'fixed', value: 1 });
    expect(saved.target).toEqual({ type: 'fixed', value: 2 });
    expect(saved.positionSizing).toEqual({ type: 'percent', value: 10 });
    expect(saved.entryConditions).toHaveLength(1);
  });

  it('maps a saved UI strategy back to the API request shape', () => {
    const saved = apiToSaved(apiStrategy);
    const request = savedToApiRequest(saved);
    expect(request.segment).toBe('equity');
    expect(request.timeframe).toBe('1d');
    expect(request.stop_loss).toEqual({ type: 'fixed_pct', value: 1 });
    expect(request.target).toEqual({ type: 'fixed_pct', value: 2 });
    expect(request.position_sizing).toEqual({ type: 'pct_capital', value: 10 });
  });
});
