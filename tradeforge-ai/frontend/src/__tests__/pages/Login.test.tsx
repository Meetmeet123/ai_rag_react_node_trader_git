import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router';
import { Toaster } from 'sonner';
import Login from '@/pages/Login';
import * as auth from '@/contexts/AuthContext';

vi.mock('@/contexts/AuthContext', async () => {
  const actual = await vi.importActual<typeof import('@/contexts/AuthContext')>('@/contexts/AuthContext');
  return {
    ...actual,
    useAuth: vi.fn(),
  };
});

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/app" element={<div data-testid="dashboard">Dashboard</div>} />
      </Routes>
      <Toaster position="top-right" richColors />
    </MemoryRouter>,
  );
}

describe('Login page', () => {
  const mockLogin = vi.fn();

  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(auth.useAuth).mockReturnValue({
      user: null,
      isLoading: false,
      isAuthenticated: false,
      login: mockLogin,
      register: vi.fn(),
      logout: vi.fn(),
    });
  });

  it('renders the login form', () => {
    renderLogin();
    expect(screen.getByTestId('login-email')).toBeInTheDocument();
    expect(screen.getByTestId('login-password')).toBeInTheDocument();
    expect(screen.getByTestId('login-submit')).toBeInTheDocument();
  });

  it('submits credentials and navigates to the dashboard on success', async () => {
    mockLogin.mockResolvedValue(undefined);
    renderLogin();

    await userEvent.type(screen.getByTestId('login-email'), 'trader');
    await userEvent.type(screen.getByTestId('login-password'), 'secret');
    await userEvent.click(screen.getByTestId('login-submit'));

    await waitFor(() => expect(mockLogin).toHaveBeenCalledWith('trader', 'secret'));
    expect(screen.getByTestId('dashboard')).toBeInTheDocument();
  });

  it('does not submit when fields are empty', async () => {
    renderLogin();
    await userEvent.click(screen.getByTestId('login-submit'));
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it('shows an error message when login fails', async () => {
    mockLogin.mockRejectedValue({ detail: 'Invalid credentials' });
    renderLogin();

    await userEvent.type(screen.getByTestId('login-email'), 'trader');
    await userEvent.type(screen.getByTestId('login-password'), 'secret');
    await userEvent.click(screen.getByTestId('login-submit'));

    await waitFor(() => expect(screen.getByText('Invalid credentials')).toBeInTheDocument());
  });
});
