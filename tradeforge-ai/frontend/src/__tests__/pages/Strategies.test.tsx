import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router';
import Strategies from '@/pages/Strategies';
import * as api from '@/lib/api';
import type { Strategy, StrategyListResponse } from '@/types/api';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    fetchStrategies: vi.fn(),
    createStrategy: vi.fn(),
    updateStrategy: vi.fn(),
    deleteStrategy: vi.fn(),
    deployStrategy: vi.fn(),
    duplicateStrategy: vi.fn(),
    stopStrategy: vi.fn(),
  };
});

const mockStrategy: Strategy = {
  id: '1',
  name: 'Test Strategy',
  instrument: 'RELIANCE',
  segment: 'equity',
  timeframe: '1d',
  status: 'draft',
  is_ai_generated: false,
  definition: {},
  entry_conditions: [],
  exit_conditions: [],
  stop_loss_type: 'fixed_pct',
  stop_loss_value: 1,
  target_type: 'fixed_pct',
  target_value: 2,
  position_sizing_type: 'pct_capital',
  position_sizing_value: 10,
};

function renderStrategies() {
  return render(
    <MemoryRouter initialEntries={['/app/strategies']}>
      <Routes>
        <Route path="/app/strategies" element={<Strategies />} />
        <Route path="/app/backtest" element={<div data-testid="backtest-page">Backtest</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('Strategies page', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('loads and displays strategies', async () => {
    vi.mocked(api.fetchStrategies).mockResolvedValue({
      strategies: [mockStrategy],
      total: 1,
    } as StrategyListResponse);

    renderStrategies();
    await waitFor(() => expect(screen.getByText('Test Strategy')).toBeInTheDocument());
    expect(screen.getByText('RELIANCE')).toBeInTheDocument();
  });

  it('shows an error message when loading fails', async () => {
    vi.mocked(api.fetchStrategies).mockRejectedValue({ detail: 'Network error' });

    renderStrategies();
    await waitFor(() => expect(screen.getByText('Network error')).toBeInTheDocument());
  });

  it('creates a new strategy', async () => {
    vi.mocked(api.fetchStrategies).mockResolvedValue({ strategies: [], total: 0 } as StrategyListResponse);
    vi.mocked(api.createStrategy).mockResolvedValue(mockStrategy);

    renderStrategies();
    await waitFor(() => expect(screen.getByText('New Strategy')).toBeEnabled());
    await userEvent.click(screen.getByText('New Strategy'));

    await waitFor(() => expect(api.createStrategy).toHaveBeenCalled());
    expect(screen.getByDisplayValue('Test Strategy')).toBeInTheDocument();
  });

  it('saves the selected strategy', async () => {
    vi.mocked(api.fetchStrategies).mockResolvedValue({
      strategies: [mockStrategy],
      total: 1,
    } as StrategyListResponse);
    vi.mocked(api.updateStrategy).mockResolvedValue({ ...mockStrategy, name: 'Updated Strategy' });

    renderStrategies();
    await waitFor(() => expect(screen.getByTestId('strategy-name')).toBeInTheDocument());

    await userEvent.clear(screen.getByTestId('strategy-name'));
    await userEvent.type(screen.getByTestId('strategy-name'), 'Updated Strategy');
    await userEvent.click(screen.getByRole('button', { name: /Save/i }));

    await waitFor(() => expect(api.updateStrategy).toHaveBeenCalled());
  });

  it('navigates to backtest for the selected strategy', async () => {
    vi.mocked(api.fetchStrategies).mockResolvedValue({
      strategies: [mockStrategy],
      total: 1,
    } as StrategyListResponse);

    renderStrategies();
    await waitFor(() => expect(screen.getByRole('button', { name: /Backtest/i })).toBeEnabled());
    await userEvent.click(screen.getByRole('button', { name: /Backtest/i }));

    await waitFor(() => expect(screen.getByTestId('backtest-page')).toBeInTheDocument());
  });
});
