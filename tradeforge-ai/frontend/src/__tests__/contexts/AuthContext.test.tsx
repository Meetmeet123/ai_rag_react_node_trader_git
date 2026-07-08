import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import * as api from '@/lib/api';
import type { User } from '@/types/api';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    getAccessToken: vi.fn(),
    fetchCurrentUser: vi.fn(),
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  };
});

const mockUser: User = {
  id: '1',
  email: 'trader@example.com',
  username: 'trader',
  role: 'user',
  is_active: true,
  is_approved_for_live: false,
};

function TestComponent() {
  const { user, isLoading, isAuthenticated, login, logout, register } = useAuth();
  return (
    <div>
      {isLoading && <span data-testid="loading">Loading</span>}
      <span data-testid="authenticated">{isAuthenticated ? 'yes' : 'no'}</span>
      <span data-testid="user">{user?.username ?? 'none'}</span>
      <button data-testid="login" onClick={() => login('trader', 'secret')}>
        Login
      </button>
      <button data-testid="register" onClick={() => register({ email: 'a@b.com', username: 'u', password: 'p' })}>
        Register
      </button>
      <button data-testid="logout" onClick={logout}>
        Logout
      </button>
    </div>
  );
}

describe('AuthContext', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    localStorage.clear();
  });

  it('starts loading and then resolves to unauthenticated when no token', async () => {
    vi.mocked(api.getAccessToken).mockReturnValue(null);
    vi.mocked(api.fetchCurrentUser).mockRejectedValue(new Error('no token'));

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId('authenticated')).toHaveTextContent('no'));
    expect(screen.getByTestId('user')).toHaveTextContent('none');
  });

  it('loads current user when token exists', async () => {
    vi.mocked(api.getAccessToken).mockReturnValue('token');
    vi.mocked(api.fetchCurrentUser).mockResolvedValue(mockUser);

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId('authenticated')).toHaveTextContent('yes'));
    expect(screen.getByTestId('user')).toHaveTextContent('trader');
  });

  it('login stores tokens and sets user', async () => {
    vi.mocked(api.getAccessToken).mockReturnValue(null);
    vi.mocked(api.login).mockResolvedValue({
      access_token: 'access',
      refresh_token: 'refresh',
      token_type: 'bearer',
      expires_in: 3600,
    });
    vi.mocked(api.fetchCurrentUser).mockResolvedValue(mockUser);

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId('authenticated')).toHaveTextContent('no'));
    await userEvent.click(screen.getByTestId('login'));

    await waitFor(() => expect(screen.getByTestId('authenticated')).toHaveTextContent('yes'));
    expect(api.login).toHaveBeenCalledWith({ username: 'trader', password: 'secret' });
    expect(screen.getByTestId('user')).toHaveTextContent('trader');
  });

  it('register logs in and sets user', async () => {
    vi.mocked(api.getAccessToken).mockReturnValue(null);
    vi.mocked(api.register).mockResolvedValue(mockUser);
    vi.mocked(api.login).mockResolvedValue({
      access_token: 'access',
      refresh_token: 'refresh',
      token_type: 'bearer',
      expires_in: 3600,
    });
    vi.mocked(api.fetchCurrentUser).mockResolvedValue(mockUser);

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId('authenticated')).toHaveTextContent('no'));
    await userEvent.click(screen.getByTestId('register'));

    await waitFor(() => expect(screen.getByTestId('authenticated')).toHaveTextContent('yes'));
    expect(api.register).toHaveBeenCalledWith({ email: 'a@b.com', username: 'u', password: 'p' });
    expect(api.login).toHaveBeenCalledWith({ username: 'u', password: 'p' });
  });

  it('logout clears user', async () => {
    vi.mocked(api.getAccessToken).mockReturnValue('token');
    vi.mocked(api.fetchCurrentUser).mockResolvedValue(mockUser);
    vi.mocked(api.logout).mockResolvedValue(undefined);

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId('authenticated')).toHaveTextContent('yes'));
    await userEvent.click(screen.getByTestId('logout'));

    await waitFor(() => expect(screen.getByTestId('authenticated')).toHaveTextContent('no'));
    expect(screen.getByTestId('user')).toHaveTextContent('none');
  });
});
