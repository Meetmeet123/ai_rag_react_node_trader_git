/**
 * TradeForge AI — typed API client.
 *
 * Centralizes all backend communication, token refresh, and error handling.
 */

import type {
  ActivateModelResponse,
  AnalyzeBacktestRequest,
  AnalyzeBacktestResponse,
  AnalyticsDashboardResponse,
  AnalyticsTradesResponse,
  ApiError,
  AuditLogListResponse,
  BacktestListResponse,
  BacktestRequest,
  BacktestRun,
  BrokerConfig,
  BrokerConnectResponse,
  BrokerListResponse,
  BrokerStatusResponse,
  ChatRequest,
  ChatResponse,
  ExecutionHealthResponse,
  ExplainStrategyRequest,
  ExplainStrategyResponse,
  GenerateStrategyRequest,
  GenerateStrategyResponse,
  HistoricalDataResponse,
  IndicatorsResponse,
  LTPResponse,
  ModelListResponse,
  ModelVersion,
  Nifty50Response,
  OrderHistoryResponse,
  ParseStrategyResponse,
  PortfolioResponse,
  PositionResponse,
  QuoteResponse,
  RAGStatusResponse,
  RiskSettings,
  RollbackResponse,
  SettingsResponse,
  SignalRequest,
  SignalResponse,
  Strategy,
  StrategyCreateRequest,
  StrategyListResponse,
  SymbolsResponse,
  TokenResponse,
  TrainingJobListResponse,
  TrainingStatusResponse,
  TrainingTriggerResponse,
  User,
} from '@/types/api';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ---------------------------------------------------------------------------
// Storage helpers
// ---------------------------------------------------------------------------

const TOKEN_KEY = 'tradeforge_access_token';
const REFRESH_KEY = 'tradeforge_refresh_token';

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(tokens: TokenResponse): void {
  localStorage.setItem(TOKEN_KEY, tokens.access_token);
  localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
}

export function clearTokens(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

// ---------------------------------------------------------------------------
// Low-level request helper
// ---------------------------------------------------------------------------

interface RequestOptions extends RequestInit {
  skipAuth?: boolean;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const headers = new Headers(options.headers);

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  if (!options.skipAuth) {
    const token = getAccessToken();
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  // Handle empty responses (e.g., 204)
  if (response.status === 204) {
    return undefined as T;
  }

  let data: unknown;
  const contentType = response.headers.get('content-type');
  if (contentType?.includes('application/json')) {
    data = await response.json();
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    const error = (data as ApiError) || {
      error: true,
      status_code: response.status,
      detail: typeof data === 'string' ? data : response.statusText,
    };
    throw error;
  }

  return data as T;
}

// ---------------------------------------------------------------------------
// Auth endpoints
// ---------------------------------------------------------------------------

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface RegisterCredentials {
  email: string;
  username: string;
  password: string;
  full_name?: string;
}

export async function login(credentials: LoginCredentials): Promise<TokenResponse> {
  const formData = new URLSearchParams();
  formData.append('username', credentials.username);
  formData.append('password', credentials.password);

  const tokens = await request<TokenResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: formData,
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    skipAuth: true,
  });

  setTokens(tokens);
  return tokens;
}

export async function register(credentials: RegisterCredentials): Promise<User> {
  return request<User>('/api/v1/auth/register', {
    method: 'POST',
    body: JSON.stringify(credentials),
    skipAuth: true,
  });
}

export async function fetchCurrentUser(): Promise<User> {
  return request<User>('/api/v1/auth/me');
}

export interface AuditLogParams {
  limit?: number;
  offset?: number;
  user_id?: string;
  action?: string;
  resource?: string;
}

export async function fetchAuditLogs(params: AuditLogParams = {}): Promise<AuditLogListResponse> {
  const searchParams = new URLSearchParams();
  if (params.limit !== undefined) searchParams.set('limit', String(params.limit));
  if (params.offset !== undefined) searchParams.set('offset', String(params.offset));
  if (params.user_id) searchParams.set('user_id', params.user_id);
  if (params.action) searchParams.set('action', params.action);
  if (params.resource) searchParams.set('resource', params.resource);
  const query = searchParams.toString();
  return request<AuditLogListResponse>(`/api/v1/audit-logs${query ? `?${query}` : ''}`);
}

export async function logout(): Promise<void> {
  try {
    await request('/api/v1/auth/logout', { method: 'POST' });
  } finally {
    clearTokens();
  }
}

// ---------------------------------------------------------------------------
// Strategy endpoints
// ---------------------------------------------------------------------------

export async function fetchStrategies(status?: string): Promise<StrategyListResponse> {
  const params = status ? `?status=${encodeURIComponent(status)}` : '';
  return request<StrategyListResponse>(`/api/v1/strategies/${params}`);
}

export async function fetchStrategy(id: string): Promise<Strategy> {
  return request<Strategy>(`/api/v1/strategies/${id}`);
}

export async function createStrategy(strategy: StrategyCreateRequest): Promise<Strategy> {
  return request<Strategy>('/api/v1/strategies/', {
    method: 'POST',
    body: JSON.stringify(strategy),
  });
}

export async function updateStrategy(id: string, strategy: StrategyCreateRequest): Promise<Strategy> {
  return request<Strategy>(`/api/v1/strategies/${id}`, {
    method: 'PUT',
    body: JSON.stringify(strategy),
  });
}

export async function deleteStrategy(id: string): Promise<{ success: boolean; message: string }> {
  return request<{ success: boolean; message: string }>(`/api/v1/strategies/${id}`, {
    method: 'DELETE',
  });
}

export async function deployStrategy(
  id: string,
  mode: 'paper' | 'live',
): Promise<{ success: boolean; message: string; strategy_id?: string }> {
  return request(`/api/v1/strategies/${id}/deploy`, {
    method: 'POST',
    body: JSON.stringify({ mode }),
  });
}

export async function stopStrategy(id: string): Promise<{ success: boolean; message: string; strategy_id?: string }> {
  return request(`/api/v1/strategies/${id}/stop`, {
    method: 'POST',
  });
}

export async function duplicateStrategy(id: string): Promise<Strategy> {
  return request<Strategy>(`/api/v1/strategies/${id}/duplicate`, {
    method: 'POST',
  });
}

// ---------------------------------------------------------------------------
// Backtest endpoints
// ---------------------------------------------------------------------------

export async function runBacktest(payload: BacktestRequest): Promise<BacktestRun> {
  return request<BacktestRun>('/api/v1/backtest/run', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchBacktests(strategyId?: string): Promise<BacktestListResponse> {
  const params = strategyId ? `?strategy_id=${encodeURIComponent(strategyId)}` : '';
  return request<BacktestListResponse>(`/api/v1/backtest/${params}`);
}

export async function fetchBacktest(id: string): Promise<BacktestRun> {
  return request<BacktestRun>(`/api/v1/backtest/${id}`);
}

export async function fetchEquityCurve(id: string): Promise<{
  backtest_id: string;
  equity_curve: unknown[];
  drawdown_curve: unknown[];
  initial_capital: number;
  data_points: number;
}> {
  return request(`/api/v1/backtest/${id}/equity-curve`);
}

export async function fetchTradeLog(id: string): Promise<{
  backtest_id: string;
  trades: unknown[];
  total_trades: number;
  winning_trades?: number;
  losing_trades?: number;
}> {
  return request(`/api/v1/backtest/${id}/trade-log`);
}

export async function deleteBacktest(id: string): Promise<{ success: boolean; message: string }> {
  return request<{ success: boolean; message: string }>(`/api/v1/backtest/${id}`, {
    method: 'DELETE',
  });
}

// ---------------------------------------------------------------------------
// Market data endpoints
// ---------------------------------------------------------------------------

export async function fetchHistorical(
  symbol: string,
  fromDate: string,
  toDate: string,
  timeframe = '1d',
): Promise<HistoricalDataResponse> {
  const params = new URLSearchParams({
    from_date: fromDate,
    to_date: toDate,
    timeframe,
  });
  return request<HistoricalDataResponse>(
    `/api/v1/market/historical/${encodeURIComponent(symbol)}?${params.toString()}`,
  );
}

export async function fetchLTP(symbol: string): Promise<LTPResponse> {
  return request<LTPResponse>(`/api/v1/market/ltp/${encodeURIComponent(symbol)}`);
}

export async function fetchNifty50(): Promise<Nifty50Response> {
  return request<Nifty50Response>('/api/v1/market/nifty50');
}

export async function fetchQuote(symbol: string, period = '30d'): Promise<QuoteResponse> {
  return request<QuoteResponse>(
    `/api/v1/market/quote/${encodeURIComponent(symbol)}?period=${encodeURIComponent(period)}`,
  );
}

export async function fetchIndicators(symbol: string, period = '30d'): Promise<QuoteResponse> {
  return request<QuoteResponse>(
    `/api/v1/market/indicators/${encodeURIComponent(symbol)}?period=${encodeURIComponent(period)}`,
  );
}

export async function calculateIndicators(payload: {
  open_prices: number[];
  high_prices: number[];
  low_prices: number[];
  close_prices: number[];
  volumes: number[];
}): Promise<IndicatorsResponse> {
  return request<IndicatorsResponse>('/api/v1/market/indicators', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchSymbols(): Promise<SymbolsResponse> {
  return request<SymbolsResponse>('/api/v1/market/symbols');
}

// ---------------------------------------------------------------------------
// Health / status
// ---------------------------------------------------------------------------

export async function fetchHealth(): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>('/health', { skipAuth: true });
}

export async function fetchSystemStatus(): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>('/api/v1/status');
}

// ---------------------------------------------------------------------------
// Execution / paper trading endpoints
// ---------------------------------------------------------------------------

export async function fetchPortfolio(): Promise<PortfolioResponse> {
  return request<PortfolioResponse>('/api/v1/execute/portfolio');
}

export async function fetchPositions(): Promise<{
  count: number;
  positions: Record<string, PositionResponse>;
  total_unrealized: number;
}> {
  return request('/api/v1/execute/positions');
}

export async function fetchSignals(limit = 100): Promise<OrderHistoryResponse['signals']> {
  const response = await request<OrderHistoryResponse>(
    `/api/v1/execute/signals?limit=${encodeURIComponent(limit)}`,
  );
  return response.signals ?? [];
}

export async function fetchOrders(limit = 100): Promise<OrderHistoryResponse> {
  return request<OrderHistoryResponse>(`/api/v1/execute/orders?limit=${encodeURIComponent(limit)}`);
}

export async function submitSignal(payload: SignalRequest): Promise<SignalResponse> {
  return request<SignalResponse>('/api/v1/execute/signal', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function closePosition(symbol: string): Promise<SignalResponse> {
  return request<SignalResponse>('/api/v1/execute/close-position', {
    method: 'POST',
    body: JSON.stringify({ symbol, reason: 'manual' }),
  });
}

export async function closeAllPositions(): Promise<{
  success: boolean;
  message: string;
  closed_count: number;
  results: Record<string, unknown>[];
}> {
  return request('/api/v1/execute/close-all', {
    method: 'POST',
  });
}

export async function fetchExecutionHealth(): Promise<ExecutionHealthResponse> {
  return request<ExecutionHealthResponse>('/api/v1/execute/health');
}

// ---------------------------------------------------------------------------
// AI / LLM / RAG endpoints
// ---------------------------------------------------------------------------

export async function sendChatMessage(payload: ChatRequest): Promise<ChatResponse> {
  return request<ChatResponse>('/api/v1/llm/chat', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function generateStrategyFromPrompt(
  payload: GenerateStrategyRequest,
): Promise<GenerateStrategyResponse> {
  return request<GenerateStrategyResponse>('/api/v1/llm/generate-strategy', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function parseStrategyPrompt(prompt: string): Promise<ParseStrategyResponse> {
  return request<ParseStrategyResponse>('/api/v1/llm/parse-strategy', {
    method: 'POST',
    body: JSON.stringify({ prompt }),
  });
}

export async function explainStrategy(
  payload: ExplainStrategyRequest,
): Promise<ExplainStrategyResponse> {
  return request<ExplainStrategyResponse>('/api/v1/llm/explain-strategy', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function analyzeBacktest(
  payload: AnalyzeBacktestRequest,
): Promise<AnalyzeBacktestResponse> {
  return request<AnalyzeBacktestResponse>('/api/v1/llm/analyze-backtest', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchRAGStatus(): Promise<RAGStatusResponse> {
  return request<RAGStatusResponse>('/api/v1/llm/rag-status');
}

// ---------------------------------------------------------------------------
// Training & Model Registry endpoints
// ---------------------------------------------------------------------------

export async function fetchTrainingStatus(): Promise<TrainingStatusResponse> {
  return request<TrainingStatusResponse>('/api/v1/train/status');
}

export async function fetchTrainingJobs(limit = 50): Promise<TrainingJobListResponse> {
  return request<TrainingJobListResponse>(`/api/v1/train/jobs?limit=${encodeURIComponent(limit)}`);
}

export async function triggerTraining(): Promise<TrainingTriggerResponse> {
  return request<TrainingTriggerResponse>('/api/v1/train/trigger', {
    method: 'POST',
  });
}

export async function startAutoTraining(): Promise<{ success: boolean; message: string }> {
  return request<{ success: boolean; message: string }>('/api/v1/train/start-auto', {
    method: 'POST',
  });
}

export async function stopAutoTraining(): Promise<{ success: boolean; message: string }> {
  return request<{ success: boolean; message: string }>('/api/v1/train/stop-auto', {
    method: 'POST',
  });
}

export async function rollbackModel(): Promise<RollbackResponse> {
  return request<RollbackResponse>('/api/v1/train/rollback', {
    method: 'POST',
  });
}

export async function fetchModelVersions(): Promise<ModelListResponse> {
  return request<ModelListResponse>('/api/v1/models/');
}

export async function fetchActiveModel(): Promise<ModelVersion | null> {
  return request<ModelVersion | null>('/api/v1/models/active');
}

export async function activateModelVersion(id: string): Promise<ActivateModelResponse> {
  return request<ActivateModelResponse>(`/api/v1/models/${encodeURIComponent(id)}/activate`, {
    method: 'POST',
  });
}

export async function archiveModelVersion(id: string): Promise<{ success: boolean; message: string }> {
  try {
    return await request<{ success: boolean; message: string }>(
      `/api/v1/models/${encodeURIComponent(id)}/archive`,
      {
        method: 'POST',
      },
    );
  } catch (err) {
    const apiErr = err as ApiError;
    if (apiErr?.status_code === 404) {
      return { success: false, message: 'Archive endpoint not implemented' };
    }
    throw err;
  }
}

// ---------------------------------------------------------------------------
// Broker configuration
// ---------------------------------------------------------------------------

export interface BrokerConfigPayload {
  broker: string;
  api_key?: string | null;
  api_secret?: string | null;
  client_id?: string | null;
  access_token?: string | null;
  redirect_uri?: string | null;
  is_active: boolean;
  is_paper: boolean;
}

export async function fetchBrokers(): Promise<BrokerListResponse> {
  return request<BrokerListResponse>('/api/v1/brokers/');
}

export async function fetchBrokerConfig(): Promise<BrokerConfig | null> {
  return request<BrokerConfig | null>('/api/v1/brokers/config');
}

export async function saveBrokerConfig(payload: BrokerConfigPayload): Promise<BrokerConfig> {
  return request<BrokerConfig>('/api/v1/brokers/config', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function deleteBrokerConfig(id: string): Promise<{ success: boolean; message: string }> {
  return request<{ success: boolean; message: string }>(
    `/api/v1/brokers/config/${encodeURIComponent(id)}`,
    {
      method: 'DELETE',
    },
  );
}

export async function connectBroker(broker: string): Promise<BrokerConnectResponse> {
  return request<BrokerConnectResponse>(`/api/v1/brokers/${encodeURIComponent(broker)}/connect`, {
    method: 'POST',
  });
}

export async function disconnectBroker(): Promise<{ success: boolean; message: string }> {
  return request<{ success: boolean; message: string }>('/api/v1/brokers/disconnect', {
    method: 'POST',
  });
}

export async function fetchBrokerStatus(): Promise<BrokerStatusResponse> {
  return request<BrokerStatusResponse>('/api/v1/brokers/status');
}

export async function fetchUpstoxLoginUrl(): Promise<{ login_url: string }> {
  return request<{ login_url: string }>('/api/v1/brokers/upstox/login-url');
}

export async function exchangeUpstoxToken(code: string): Promise<{ success: boolean; message: string }> {
  return request<{ success: boolean; message: string }>('/api/v1/brokers/upstox/exchange-token', {
    method: 'POST',
    body: JSON.stringify({ code }),
  });
}

// ---------------------------------------------------------------------------
// Analytics endpoints
// ---------------------------------------------------------------------------

export async function fetchAnalyticsDashboard(params?: {
  from_date?: string;
  to_date?: string;
}): Promise<AnalyticsDashboardResponse> {
  const searchParams = new URLSearchParams();
  if (params?.from_date) searchParams.set('from_date', params.from_date);
  if (params?.to_date) searchParams.set('to_date', params.to_date);
  const query = searchParams.toString();
  return request<AnalyticsDashboardResponse>(`/api/v1/analytics/dashboard${query ? `?${query}` : ''}`);
}

export interface AnalyticsTradesParams {
  symbol?: string;
  strategy_id?: string;
  from_date?: string;
  to_date?: string;
  limit?: number;
  offset?: number;
}

export async function fetchAnalyticsTrades(params: AnalyticsTradesParams = {}): Promise<AnalyticsTradesResponse> {
  const searchParams = new URLSearchParams();
  if (params.symbol) searchParams.set('symbol', params.symbol);
  if (params.strategy_id) searchParams.set('strategy_id', params.strategy_id);
  if (params.from_date) searchParams.set('from_date', params.from_date);
  if (params.to_date) searchParams.set('to_date', params.to_date);
  if (params.limit !== undefined) searchParams.set('limit', String(params.limit));
  if (params.offset !== undefined) searchParams.set('offset', String(params.offset));
  const query = searchParams.toString();
  return request<AnalyticsTradesResponse>(`/api/v1/analytics/trades${query ? `?${query}` : ''}`);
}

export async function exportAnalyticsReport(): Promise<string> {
  return request<string>('/api/v1/analytics/export');
}

// ---------------------------------------------------------------------------
// Settings endpoints
// ---------------------------------------------------------------------------

export async function fetchSettings(): Promise<SettingsResponse> {
  return request<SettingsResponse>('/api/v1/settings');
}

export async function updateSettings(payload: Partial<RiskSettings>): Promise<SettingsResponse> {
  return request<SettingsResponse>('/api/v1/settings', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}
