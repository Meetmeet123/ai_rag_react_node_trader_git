import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router';
import { Toaster } from 'sonner';
import Register from '@/pages/Register';
import * as auth from '@/contexts/AuthContext';

vi.mock('@/contexts/AuthContext', async () => {
  const actual = await vi.importActual<typeof import('@/contexts/AuthContext')>('@/contexts/AuthContext');
  return {
    ...actual,
    useAuth: vi.fn(),
  };
});

function renderRegister() {
  return render(
    <MemoryRouter initialEntries={['/register']}>
      <Routes>
        <Route path="/register" element={<Register />} />
        <Route path="/app" element={<div data-testid="dashboard">Dashboard</div>} />
      </Routes>
      <Toaster position="top-right" richColors />
    </MemoryRouter>,
  );
}

describe('Register page', () => {
  const mockRegister = vi.fn();

  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(auth.useAuth).mockReturnValue({
      user: null,
      isLoading: false,
      isAuthenticated: false,
      login: vi.fn(),
      register: mockRegister,
      logout: vi.fn(),
    });
  });

  it('renders the registration form', () => {
    renderRegister();
    expect(screen.getByTestId('register-email')).toBeInTheDocument();
    expect(screen.getByTestId('register-username')).toBeInTheDocument();
    expect(screen.getByTestId('register-password')).toBeInTheDocument();
    expect(screen.getByTestId('register-confirm-password')).toBeInTheDocument();
    expect(screen.getByTestId('register-submit')).toBeInTheDocument();
  });

  it('registers a new user and navigates to the dashboard', async () => {
    mockRegister.mockResolvedValue(undefined);
    renderRegister();

    await userEvent.type(screen.getByTestId('register-email'), 'trader@example.com');
    await userEvent.type(screen.getByTestId('register-username'), 'trader');
    await userEvent.type(screen.getByTestId('register-password'), 'secret123');
    await userEvent.type(screen.getByTestId('register-confirm-password'), 'secret123');
    await userEvent.click(screen.getByTestId('register-submit'));

    await waitFor(() =>
      expect(mockRegister).toHaveBeenCalledWith({
        email: 'trader@example.com',
        username: 'trader',
        password: 'secret123',
        full_name: undefined,
      }),
    );
    expect(screen.getByTestId('dashboard')).toBeInTheDocument();
  });

  it('shows an error when passwords do not match', async () => {
    renderRegister();
    await userEvent.type(screen.getByTestId('register-password'), 'secret123');
    await userEvent.type(screen.getByTestId('register-confirm-password'), 'different');
    await userEvent.click(screen.getByTestId('register-submit'));

    expect(mockRegister).not.toHaveBeenCalled();
    expect(screen.getByText('Passwords do not match')).toBeInTheDocument();
  });

  it('shows an error when password is too short', async () => {
    renderRegister();
    await userEvent.type(screen.getByTestId('register-email'), 'trader@example.com');
    await userEvent.type(screen.getByTestId('register-username'), 'trader');
    await userEvent.type(screen.getByTestId('register-password'), 'short');
    await userEvent.type(screen.getByTestId('register-confirm-password'), 'short');
    await userEvent.click(screen.getByTestId('register-submit'));

    expect(mockRegister).not.toHaveBeenCalled();
    expect(screen.getByText('Password must be at least 6 characters')).toBeInTheDocument();
  });
});
