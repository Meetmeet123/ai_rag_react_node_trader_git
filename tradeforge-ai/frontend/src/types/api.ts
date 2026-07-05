/**
 * TradeForge AI — shared API type definitions mirroring backend schemas.
 */

export interface User {
  id: string;
  email: string;
  username: string;
  full_name?: string;
  role: 'user' | 'admin';
  is_active: boolean;
  is_approved_for_live: boolean;
  created_at?: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface Strategy {
  id: string;
  name: string;
  description?: string;
  instrument: string;
  segment: string;
  timeframe: string;
  definition?: Record<string, unknown>;
  generated_code?: string;
  nl_prompt?: string;
  status: 'draft' | 'active' | 'paper' | 'backtesting' | 'archived';
  is_ai_generated: boolean;
  backtest_results?: Record<string, unknown>;
  entry_conditions?: unknown;
  exit_conditions?: unknown;
  stop_loss_type?: string;
  stop_loss_value?: number;
  target_type?: string;
  target_value?: number;
  position_sizing_type?: string;
  position_sizing_value?: number;
  created_at?: string;
  updated_at?: string;
}

export interface StrategyListResponse {
  strategies: Strategy[];
  total: number;
  status_filter?: string | null;
}

export interface StrategyCreateRequest {
  name: string;
  description?: string;
  instrument: string;
  segment?: string;
  timeframe?: string;
  entry_conditions?: unknown[];
  exit_conditions?: unknown[];
  stop_loss?: Record<string, unknown>;
  target?: Record<string, unknown>;
  position_sizing?: Record<string, unknown>;
  definition?: Record<string, unknown>;
  nl_prompt?: string;
}

export interface BacktestRun {
  id: string;
  strategy_id?: string | null;
  strategy_name?: string | null;
  start_date?: string;
  end_date?: string;
  initial_capital: number;
  status: string;
  error_message?: string | null;
  total_trades?: number | null;
  winning_trades?: number | null;
  losing_trades?: number | null;
  win_rate?: number | null;
  net_pnl?: number | null;
  net_pnl_pct?: number | null;
  gross_profit?: number | null;
  gross_loss?: number | null;
  profit_factor?: number | null;
  max_drawdown?: number | null;
  max_drawdown_pct?: number | null;
  sharpe_ratio?: number | null;
  avg_profit_per_trade?: number | null;
  avg_loss_per_trade?: number | null;
  avg_holding_period?: number | null;
  equity_curve?: unknown[];
  drawdown_curve?: unknown[];
  monthly_returns?: Record<string, unknown>;
  trade_log?: unknown[];
  created_at?: string;
  completed_at?: string;
}

export interface BacktestListResponse {
  backtests: BacktestRun[];
  total: number;
  strategy_id_filter?: string | null;
}

export interface BacktestRequest {
  strategy_id: string;
  start_date: string;
  end_date: string;
  initial_capital?: number;
  brokerage_per_order?: number;
  slippage_pct?: number;
  position_sizing_type?: string;
  position_sizing_value?: number;
  stop_loss_type?: string;
  stop_loss_value?: number;
  target_type?: string;
  target_value?: number;
  allow_short?: boolean;
}

export interface ApiError {
  error: boolean;
  status_code: number;
  detail: string;
}
