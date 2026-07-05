/**
 * TradeForge AI — typed API client.
 *
 * Centralizes all backend communication, token refresh, and error handling.
 */

import type {
  ApiError,
  BacktestListResponse,
  BacktestRequest,
  BacktestRun,
  Strategy,
  StrategyCreateRequest,
  StrategyListResponse,
  TokenResponse,
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
  return request<StrategyListResponse>(`/api/v1/strategies${params}`);
}

export async function fetchStrategy(id: string): Promise<Strategy> {
  return request<Strategy>(`/api/v1/strategies/${id}`);
}

export async function createStrategy(strategy: StrategyCreateRequest): Promise<Strategy> {
  return request<Strategy>('/api/v1/strategies', {
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

export async function runBacktest(request: BacktestRequest): Promise<BacktestRun> {
  return request<BacktestRun>('/api/v1/backtest/run', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function fetchBacktests(strategyId?: string): Promise<BacktestListResponse> {
  const params = strategyId ? `?strategy_id=${encodeURIComponent(strategyId)}` : '';
  return request<BacktestListResponse>(`/api/v1/backtest${params}`);
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
// Health / status
// ---------------------------------------------------------------------------

export async function fetchHealth(): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>('/health', { skipAuth: true });
}

export async function fetchSystemStatus(): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>('/api/v1/status');
}
