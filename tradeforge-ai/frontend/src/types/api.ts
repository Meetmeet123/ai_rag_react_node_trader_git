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

export interface AuditLog {
  id: string;
  user_id: string;
  username: string;
  role: string;
  action: string;
  resource: string;
  resource_id?: string | null;
  ip_address?: string | null;
  user_agent?: string | null;
  status_code?: number | null;
  timestamp: string;
  details?: Record<string, unknown> | null;
}

export interface AuditLogListResponse {
  logs: AuditLog[];
  total: number;
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

// ---------------------------------------------------------------------------
// Market data
// ---------------------------------------------------------------------------

export interface OHLCVRecord {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface HistoricalDataResponse {
  symbol: string;
  timeframe: string;
  from_date: string;
  to_date: string;
  records: number;
  data: OHLCVRecord[];
}

export interface LTPResponse {
  symbol: string;
  price: number;
  timestamp: string;
  source: string;
}

export interface Nifty50Response {
  constituents: string[];
  count: number;
  source: string;
}

export interface QuoteResponse {
  symbol: string;
  timestamp: string;
  price_data: {
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    change: number;
    change_pct: number;
  };
  indicators: Record<string, number | null>;
}

export interface IndicatorsResponse {
  indicators: Record<string, (number | null)[]>;
  record_count: number;
  calculated_at: string;
}

export interface SymbolsResponse {
  nifty50: string[];
  total_count: number;
  popular: string[];
  indices: string[];
}

// ---------------------------------------------------------------------------
// Execution / paper trading
// ---------------------------------------------------------------------------

export interface SignalRequest {
  symbol: string;
  direction: 'buy' | 'sell';
  quantity: number;
  strategy_id?: string;
  confidence?: number;
  price?: number;
  order_type?: string;
  product_type?: string;
}

export interface SignalResponse {
  success: boolean;
  order_id?: string | null;
  message: string;
  risk_result?: Record<string, unknown> | null;
  latency_ms?: number | null;
}

export interface PositionResponse {
  symbol: string;
  quantity: number;
  avg_price: number;
  current_price: number;
  unrealized_pnl: number;
  realized_pnl: number;
  entry_time: string | null;
  strategy_id: string | number;
}

export interface PortfolioResponse {
  mode: 'paper' | 'live' | string;
  halted: boolean;
  halt_reason: string;
  position_count: number;
  positions: Record<string, PositionResponse>;
  total_unrealized_pnl: number;
  total_realized_pnl: number;
  daily_stats: Record<string, unknown> & {
    pnl_today?: number;
    trades_today?: number;
    buys_today?: number;
    sells_today?: number;
    volume_traded?: number;
    loss_today?: number;
  };
  total_signals_processed: number;
  total_trades_executed: number;
  risk_summary: Record<string, unknown>;
}

export interface OrderHistoryResponse {
  signals: unknown[];
  trades: unknown[];
  total_signals: number;
  total_trades: number;
}

export interface ExecutionHealthResponse {
  status: string;
  broker_connected: boolean;
  halted: boolean;
  mode: string;
  positions: number;
  pending_orders: number;
  daily_stats: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// AI / LLM / RAG
// ---------------------------------------------------------------------------

export interface StrategySuggestion {
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
  nl_prompt?: string;
  definition?: Record<string, unknown>;
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
  strategy?: StrategySuggestion;
  // Frontend-only metadata for generated strategy cards
  strategyResponse?: GenerateStrategyResponse;
  originalPrompt?: string;
  strategySavedId?: string;
}

export interface ChatRequest {
  message: string;
  context?: ChatMessage[];
}

export interface ChatResponse {
  response: string;
  model_loaded: boolean;
}

export interface GenerateStrategyRequest {
  prompt: string;
  instrument?: string;
  segment?: string;
  timeframe?: string;
}

export interface GenerateStrategyResponse {
  strategy: Record<string, unknown>;
  confidence: number;
  reasoning: string;
  generated_code: string;
}

export interface ParseStrategyResponse {
  name: string;
  description?: string;
  instrument: string;
  segment?: string;
  timeframe?: string;
  indicators?: unknown[];
  entry_conditions?: unknown[];
  exit_conditions?: unknown[];
  risk_params?: Record<string, unknown>;
  generated_code?: string;
  validation?: Record<string, unknown>;
}

export interface ExplainStrategyRequest {
  strategy: Record<string, unknown>;
}

export interface ExplainStrategyResponse {
  explanation: string;
  strategy_name: string;
}

export interface AnalyzeBacktestRequest {
  results: Record<string, unknown>;
}

export interface AnalyzeBacktestResponse {
  analysis: string;
  metrics_summary: string;
}

export interface RAGStatusResponse {
  initialized: boolean;
  queries_served: number;
  total_query_time_ms: number;
  ingestion?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Training & Model Registry
// ---------------------------------------------------------------------------

export interface TrainingStatusResponse {
  is_running: boolean;
  current_job_id: string | null;
  last_training_time: string | null;
  next_scheduled_run: string | null;
  interval_minutes: number;
  total_jobs_completed: number;
  total_jobs_failed: number;
  consecutive_failures: number;
  active_model_version_id: string | null;
  active_model_name: string | null;
  last_formula_hash: string | null;
  circuit_breaker_open: boolean;
}

export interface TrainingJob {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | string;
  trigger_reason?: string | null;
  sample_count?: number | null;
  epochs?: number | null;
  final_loss?: number | null;
  validation_loss?: number | null;
  deployed?: boolean;
  error_message?: string | null;
  created_at?: string;
  completed_at?: string | null;
}

export interface TrainingJobListResponse {
  jobs: TrainingJob[];
  total: number;
  limit: number;
}

export interface TrainingTriggerResponse {
  success: boolean;
  job_id?: string;
  message: string;
}

export interface RollbackResponse {
  success: boolean;
  message: string;
  new_active_version?: string | null;
}

export interface ModelVersion {
  version_id: string;
  version_name: string;
  description?: string | null;
  checkpoint_path?: string | null;
  training_data_size?: number | null;
  training_duration_sec?: number | null;
  epochs?: number | null;
  final_loss?: number | null;
  validation_loss?: number | null;
  accuracy?: number | null;
  precision?: number | null;
  recall?: number | null;
  f1_score?: number | null;
  backtest_pnl?: number | null;
  status: 'active' | 'archived' | 'pending' | 'failed' | string;
  is_active: boolean;
  triggered_by?: string | null;
  created_at?: string;
  completed_at?: string | null;
}

export interface ModelListResponse {
  versions: ModelVersion[];
  total: number;
  active_version_id: string | null;
}

export interface ActivateModelResponse {
  success: boolean;
  message: string;
  activated_version?: string | null;
}

// ---------------------------------------------------------------------------
// Broker configuration
// ---------------------------------------------------------------------------

export interface BrokerConfig {
  id: string;
  broker: string;
  api_key?: string | null;
  api_secret?: string | null;
  client_id?: string | null;
  access_token?: string | null;
  redirect_uri?: string | null;
  is_active: boolean;
  is_paper: boolean;
  is_connected: boolean;
  last_connected_at?: string | null;
}

export interface BrokerStatusResponse {
  broker?: string | null;
  is_connected: boolean;
  is_paper: boolean;
  is_active: boolean;
  last_connected_at?: string | null;
}

export interface BrokerListResponse {
  supported: string[];
  active_config?: BrokerConfig | null;
}

export interface BrokerConnectResponse {
  success: boolean;
  message: string;
  broker?: string | null;
}

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

export interface KPIs {
  net_pnl: number;
  total_trades: number;
  win_rate: number;
  max_drawdown: number;
  avg_profit_per_trade: number;
  avg_loss_per_trade: number;
  profit_factor: number;
}

export interface DailyPnlItem {
  date: string;
  pnl: number;
  cumulative: number;
}

export interface StrategyPerformance {
  strategy_id: string;
  name: string;
  trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  net_pnl: number;
  avg_profit: number;
  avg_loss: number;
  profit_factor: number;
}

export interface AnalyticsTrade {
  id: string;
  symbol: string;
  strategy_name: string;
  side: string;
  entry_price: number;
  exit_price: number;
  quantity: number;
  pnl: number;
  pnl_pct: number;
  entry_time?: string;
  exit_time?: string;
  status?: string;
}

export interface AnalyticsDashboardResponse {
  kpis: KPIs;
  daily_pnl: DailyPnlItem[];
  strategy_performance: StrategyPerformance[];
  recent_trades: AnalyticsTrade[];
}

export interface AnalyticsTradesResponse {
  trades: AnalyticsTrade[];
  total: number;
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

export interface RiskSettings {
  daily_loss_limit: number;
  daily_loss_limit_enabled: boolean;
  max_positions: number;
  max_exposure_per_trade_pct: number;
  max_exposure_overall_pct: number;
  kill_switch_enabled: boolean;
  auto_square_off_time: string;
}

export interface SettingsResponse extends RiskSettings {}
