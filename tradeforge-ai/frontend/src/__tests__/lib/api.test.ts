import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  getAccessToken,
  getRefreshToken,
  setTokens,
  clearTokens,
  login,
  register,
  logout,
  fetchHealth,
  fetchCurrentUser,
} from '@/lib/api';
import type { TokenResponse, User } from '@/types/api';

describe('api token helpers', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('returns null when tokens are absent', () => {
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });

  it('sets and clears tokens', () => {
    const tokens: TokenResponse = {
      access_token: 'access123',
      refresh_token: 'refresh456',
      token_type: 'bearer',
      expires_in: 3600,
    };

    setTokens(tokens);
    expect(getAccessToken()).toBe('access123');
    expect(getRefreshToken()).toBe('refresh456');

    clearTokens();
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });
});

describe('api request', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    localStorage.clear();
    fetchSpy = vi.spyOn(globalThis, 'fetch');
  });

  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it('injects Authorization header when token exists', async () => {
    setTokens({
      access_token: 'token_xyz',
      refresh_token: 'refresh_xyz',
      token_type: 'bearer',
      expires_in: 3600,
    });

    fetchSpy.mockResolvedValue(
      new Response(JSON.stringify({ id: '1', username: 'trader', role: 'user' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await fetchCurrentUser();

    const call = fetchSpy.mock.calls[0];
    const headers = call[1]?.headers as Headers;
    expect(headers.get('Authorization')).toBe('Bearer token_xyz');
  });

  it('skips Authorization header when skipAuth is true', async () => {
    fetchSpy.mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await fetchHealth();

    const call = fetchSpy.mock.calls[0];
    const headers = call[1]?.headers as Headers;
    expect(headers.get('Authorization')).toBeNull();
  });

  it('parses JSON response', async () => {
    fetchSpy.mockResolvedValue(
      new Response(JSON.stringify({ status: 'healthy' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const result = await fetchHealth();
    expect(result).toEqual({ status: 'healthy' });
  });

  it('parses text response', async () => {
    fetchSpy.mockResolvedValue(
      new Response('plain text', {
        status: 200,
        headers: { 'Content-Type': 'text/plain' },
      }),
    );

    const result = await fetchHealth();
    expect(result).toBe('plain text');
  });

  it('returns undefined for 204 responses', async () => {
    fetchSpy.mockResolvedValue(new Response(null, { status: 204 }));

    const result = await logout();
    expect(result).toBeUndefined();
  });

  it('throws structured ApiError on non-ok JSON', async () => {
    fetchSpy.mockResolvedValue(
      new Response(JSON.stringify({ error: true, status_code: 400, detail: 'bad request' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await expect(login({ username: 'u', password: 'p' })).rejects.toMatchObject({
      error: true,
      status_code: 400,
      detail: 'bad request',
    });
  });

  it('throws fallback error on non-ok text', async () => {
    fetchSpy.mockResolvedValue(
      new Response('server error', {
        status: 500,
        headers: { 'Content-Type': 'text/plain' },
      }),
    );

    await expect(login({ username: 'u', password: 'p' })).rejects.toMatchObject({
      error: true,
      status_code: 500,
      detail: 'server error',
    });
  });

  it('login sends form-encoded credentials and stores tokens', async () => {
    const tokens: TokenResponse = {
      access_token: 'access_login',
      refresh_token: 'refresh_login',
      token_type: 'bearer',
      expires_in: 3600,
    };

    fetchSpy.mockResolvedValue(
      new Response(JSON.stringify(tokens), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const result = await login({ username: 'trader', password: 'secret' });

    expect(result).toEqual(tokens);
    expect(getAccessToken()).toBe('access_login');
    expect(getRefreshToken()).toBe('refresh_login');

    const call = fetchSpy.mock.calls[0];
    expect(call[0]).toMatch(/\/api\/v1\/auth\/login$/);
    const body = call[1]?.body as URLSearchParams;
    expect(body.get('username')).toBe('trader');
    expect(body.get('password')).toBe('secret');
  });

  it('register sends JSON credentials', async () => {
    const user: User = {
      id: '1',
      email: 'a@b.com',
      username: 'trader',
      role: 'user',
      is_active: true,
      is_approved_for_live: false,
    };

    fetchSpy.mockResolvedValue(
      new Response(JSON.stringify(user), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const result = await register({
      email: 'a@b.com',
      username: 'trader',
      password: 'secret',
    });

    expect(result).toEqual(user);

    const call = fetchSpy.mock.calls[0];
    expect(call[0]).toMatch(/\/api\/v1\/auth\/register$/);
    expect(call[1]?.body).toBe(
      JSON.stringify({ email: 'a@b.com', username: 'trader', password: 'secret' }),
    );
  });

  it('logout clears tokens even when request fails', async () => {
    setTokens({
      access_token: 'to_clear',
      refresh_token: 'to_clear_refresh',
      token_type: 'bearer',
      expires_in: 3600,
    });

    fetchSpy.mockRejectedValue(new Error('network error'));

    await expect(logout()).rejects.toBeInstanceOf(Error);
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });

  it('fetchHealth calls /health without auth', async () => {
    fetchSpy.mockResolvedValue(
      new Response(JSON.stringify({ status: 'healthy' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await fetchHealth();

    const call = fetchSpy.mock.calls[0];
    expect(call[0]).toMatch(/\/health$/);
    expect(call[1]).toMatchObject({ skipAuth: true });
  });
});
