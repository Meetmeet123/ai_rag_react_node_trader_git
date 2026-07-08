import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import ProtectedRoute from '@/components/ProtectedRoute';
import { AuthProvider } from '@/contexts/AuthContext';
import * as api from '@/lib/api';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    getAccessToken: vi.fn(),
    fetchCurrentUser: vi.fn(),
  };
});

function renderWithRouter(initialEntries: string[]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<div data-testid="login-page">Login</div>} />
          <Route element={<ProtectedRoute><div data-testid="protected">Protected Content</div></ProtectedRoute>}>
            <Route path="/app" element={<div data-testid="app-page">App</div>} />
          </Route>
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('ProtectedRoute', () => {
  it('shows a loading spinner while auth state is loading', () => {
    vi.mocked(api.getAccessToken).mockReturnValue('token');
    vi.mocked(api.fetchCurrentUser).mockImplementation(() => new Promise(() => {}));

    renderWithRouter(['/app']);
    expect(document.querySelector('.animate-spin')).toBeInTheDocument();
  });

  it('redirects to login when the user is not authenticated', async () => {
    vi.mocked(api.getAccessToken).mockReturnValue(null);

    renderWithRouter(['/app']);
    await waitFor(() => expect(screen.getByTestId('login-page')).toBeInTheDocument());
  });

  it('renders protected content when the user is authenticated', async () => {
    vi.mocked(api.getAccessToken).mockReturnValue('token');
    vi.mocked(api.fetchCurrentUser).mockResolvedValue({
      id: '1',
      email: 'trader@example.com',
      username: 'trader',
      role: 'user',
      is_active: true,
      is_approved_for_live: false,
    });

    renderWithRouter(['/app']);
    await waitFor(() => expect(screen.getByTestId('protected')).toBeInTheDocument());
  });
});
