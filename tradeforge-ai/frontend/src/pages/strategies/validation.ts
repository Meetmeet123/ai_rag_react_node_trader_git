import { z } from 'zod';

const conditionSchema = z.object({
  id: z.string(),
  indicator: z.string().min(1, 'Indicator is required'),
  operator: z.string().min(1, 'Operator is required'),
  value: z.string().min(1, 'Value is required'),
  valueType: z.enum(['indicator', 'number']),
  logic: z.enum(['AND', 'OR']).optional(),
});

export const strategyFormSchema = z.object({
  name: z.string().min(1, 'Strategy name is required').max(200, 'Name must be 200 characters or less'),
  description: z.string().max(2000, 'Description must be 2000 characters or less'),
  instrument: z.string().min(1, 'Instrument is required').max(50, 'Instrument must be 50 characters or less'),
  segment: z.enum(['Stocks', 'Futures', 'Options', 'MCX']),
  status: z.enum(['active', 'paper', 'backtesting', 'draft']),
  timeframe: z.enum(['1m', '5m', '15m', '30m', '1h', '1d']),
  entryConditions: z.array(conditionSchema),
  exitConditions: z.array(conditionSchema),
  stopLoss: z.object({
    type: z.enum(['fixed', 'trailing', 'atr']),
    value: z.number().min(0, 'Stop loss value must be non-negative'),
  }),
  target: z.object({
    type: z.enum(['fixed', 'rr', 'trailing']),
    value: z.number().min(0, 'Target value must be non-negative'),
  }),
  positionSizing: z.object({
    type: z.enum(['fixed', 'percent', 'risk']),
    value: z.number().positive('Position sizing value must be positive'),
  }),
});

export type StrategyFormData = z.infer<typeof strategyFormSchema>;
