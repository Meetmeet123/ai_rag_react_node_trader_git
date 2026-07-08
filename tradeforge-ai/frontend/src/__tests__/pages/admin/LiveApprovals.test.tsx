import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import LiveApprovals from '@/pages/admin/LiveApprovals';
import * as auth from '@/contexts/AuthContext';
import * as api from '@/lib/api';

vi.mock('@/contexts/AuthContext', async () => {
  const actual = await vi.importActual<typeof import('@/contexts/AuthContext')>('@/contexts/AuthContext');
  return {
    ...actual,
    useAuth: vi.fn(),
  };
});

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    fetchPendingLiveApprovals: vi.fn(),
    approveUserForLive: vi.fn(),
  };
});

describe('LiveApprovals admin page', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('shows admin access required for non-admins', () => {
    vi.mocked(auth.useAuth).mockReturnValue({
      user: { id: '1', username: 'trader', email: 'trader@example.com', role: 'user', is_active: true, is_approved_for_live: false },
      isLoading: false,
      isAuthenticated: true,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    });

    render(<LiveApprovals />);
    expect(screen.getByText('Admin Access Required')).toBeInTheDocument();
  });

  it('loads and displays pending approvals for admins', async () => {
    vi.mocked(auth.useAuth).mockReturnValue({
      user: { id: 'a1', username: 'admin', email: 'admin@example.com', role: 'admin', is_active: true, is_approved_for_live: true },
      isLoading: false,
      isAuthenticated: true,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    });
    vi.mocked(api.fetchPendingLiveApprovals).mockResolvedValue([
      {
        user: { id: 'u1', username: 'pendinguser', email: 'pending@example.com', role: 'user', is_active: true, is_approved_for_live: false },
        requested_at: '2024-01-01T00:00:00Z',
      },
    ]);

    render(<LiveApprovals />);
    await waitFor(() => expect(screen.getByText('pendinguser')).toBeInTheDocument());
    expect(screen.getByText('pending@example.com')).toBeInTheDocument();
  });

  it('approves a pending user', async () => {
    vi.mocked(auth.useAuth).mockReturnValue({
      user: { id: 'a1', username: 'admin', email: 'admin@example.com', role: 'admin', is_active: true, is_approved_for_live: true },
      isLoading: false,
      isAuthenticated: true,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    });
    vi.mocked(api.fetchPendingLiveApprovals).mockResolvedValue([
      {
        user: { id: 'u1', username: 'pendinguser', email: 'pending@example.com', role: 'user', is_active: true, is_approved_for_live: false },
        requested_at: '2024-01-01T00:00:00Z',
      },
    ]);
    vi.mocked(api.approveUserForLive).mockResolvedValue({ success: true, message: 'Approved', user: { id: 'u1', username: 'pendinguser', email: 'pending@example.com', role: 'user', is_active: true, is_approved_for_live: true } });

    render(<LiveApprovals />);
    await waitFor(() => expect(screen.getByTestId('approve-u1')).toBeEnabled());
    await userEvent.click(screen.getByTestId('approve-u1'));

    await waitFor(() => expect(api.approveUserForLive).toHaveBeenCalledWith('u1'));
  });
});
