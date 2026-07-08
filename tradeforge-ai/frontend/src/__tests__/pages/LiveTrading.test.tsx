import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import LiveTrading from '@/pages/LiveTrading';
import * as auth from '@/contexts/AuthContext';

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="recharts-container">{children}</div>,
  ComposedChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => null,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Cell: () => null,
  ReferenceLine: () => null,
}));
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
    requestLiveApproval: vi.fn(),
    closeAllPositions: vi.fn(),
  };
});

describe('LiveTrading page', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('shows an approval banner for unapproved users', () => {
    vi.mocked(auth.useAuth).mockReturnValue({
      user: { id: '1', username: 'trader', email: 'trader@example.com', role: 'user', is_active: true, is_approved_for_live: false },
      isLoading: false,
      isAuthenticated: true,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    });

    render(<LiveTrading />);
    expect(screen.getByText(/Live trading requires admin approval/i)).toBeInTheDocument();
    expect(screen.getByTestId('request-approval-btn')).toBeInTheDocument();
  });

  it('does not show the approval banner for approved users', () => {
    vi.mocked(auth.useAuth).mockReturnValue({
      user: { id: '1', username: 'trader', email: 'trader@example.com', role: 'user', is_active: true, is_approved_for_live: true },
      isLoading: false,
      isAuthenticated: true,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    });

    render(<LiveTrading />);
    expect(screen.queryByText(/Live trading requires admin approval/i)).not.toBeInTheDocument();
    expect(screen.queryByTestId('request-approval-btn')).not.toBeInTheDocument();
  });

  it('requests live trading approval', async () => {
    vi.mocked(auth.useAuth).mockReturnValue({
      user: { id: '1', username: 'trader', email: 'trader@example.com', role: 'user', is_active: true, is_approved_for_live: false },
      isLoading: false,
      isAuthenticated: true,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    });
    vi.mocked(api.requestLiveApproval).mockResolvedValue({ success: true, message: 'Request submitted' });

    render(<LiveTrading />);
    await userEvent.click(screen.getByTestId('request-approval-btn'));

    await waitFor(() => expect(api.requestLiveApproval).toHaveBeenCalled());
  });

  it('triggers the kill switch and closes all positions', async () => {
    vi.mocked(auth.useAuth).mockReturnValue({
      user: { id: '1', username: 'trader', email: 'trader@example.com', role: 'user', is_active: true, is_approved_for_live: true },
      isLoading: false,
      isAuthenticated: true,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    });
    vi.mocked(api.closeAllPositions).mockResolvedValue({ success: true, message: 'Positions closed', closed_count: 0, results: [] });

    render(<LiveTrading />);
    await userEvent.click(screen.getByRole('button', { name: /KILL SWITCH/i }));
    await userEvent.click(screen.getByRole('button', { name: /Confirm Kill Switch/i }));

    await waitFor(() => expect(api.closeAllPositions).toHaveBeenCalled());
  });
});
