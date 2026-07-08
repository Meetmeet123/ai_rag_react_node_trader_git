import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Training from '@/pages/Training';
import * as api from '@/lib/api';
import type { ModelListResponse, TrainingJobListResponse, TrainingStatusResponse } from '@/types/api';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    fetchTrainingStatus: vi.fn(),
    fetchTrainingJobs: vi.fn(),
    fetchModelVersions: vi.fn(),
    rollbackModel: vi.fn(),
    activateModelVersion: vi.fn(),
  };
});

const mockStatus: TrainingStatusResponse = {
  is_running: false,
  current_job_id: null,
  last_training_time: null,
  next_scheduled_run: null,
  interval_minutes: 20,
  total_jobs_completed: 5,
  total_jobs_failed: 1,
  consecutive_failures: 0,
  active_model_version_id: 'mv1',
  active_model_name: 'v1',
  last_formula_hash: null,
  circuit_breaker_open: false,
};

describe('Training page', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders loading state then displays training data', async () => {
    vi.mocked(api.fetchTrainingStatus).mockResolvedValue(mockStatus);
    vi.mocked(api.fetchTrainingJobs).mockResolvedValue({ jobs: [], total: 0, limit: 50 } as TrainingJobListResponse);
    vi.mocked(api.fetchModelVersions).mockResolvedValue({
      versions: [
        {
          version_id: 'mv1',
          version_name: 'v1',
          status: 'active',
          is_active: true,
        },
      ],
      total: 1,
      active_version_id: 'mv1',
    } as ModelListResponse);

    render(<Training />);
    await waitFor(() => expect(screen.getByText('Training & Models')).toBeInTheDocument());
    expect(screen.getByText('Model Versions')).toBeInTheDocument();
    expect(screen.getAllByText('v1').length).toBeGreaterThan(0);
    expect(screen.getByText('5')).toBeInTheDocument();
  });

  it('rolls back to the previous model version', async () => {
    vi.mocked(api.fetchTrainingStatus).mockResolvedValue(mockStatus);
    vi.mocked(api.fetchTrainingJobs).mockResolvedValue({ jobs: [], total: 0, limit: 50 } as TrainingJobListResponse);
    vi.mocked(api.fetchModelVersions).mockResolvedValue({ versions: [], total: 0, active_version_id: null } as ModelListResponse);
    vi.mocked(api.rollbackModel).mockResolvedValue({ success: true, message: 'Rolled back', new_active_version: 'mv0' });

    render(<Training />);
    await waitFor(() => expect(screen.getByRole('button', { name: /Rollback to Previous/i })).toBeEnabled());
    await userEvent.click(screen.getByRole('button', { name: /Rollback to Previous/i }));

    await waitFor(() => expect(api.rollbackModel).toHaveBeenCalled());
  });

  it('activates a model version', async () => {
    vi.mocked(api.fetchTrainingStatus).mockResolvedValue(mockStatus);
    vi.mocked(api.fetchTrainingJobs).mockResolvedValue({ jobs: [], total: 0, limit: 50 } as TrainingJobListResponse);
    vi.mocked(api.fetchModelVersions).mockResolvedValue({
      versions: [
        { version_id: 'mv2', version_name: 'v2', status: 'ready', is_active: false },
      ],
      total: 1,
      active_version_id: 'mv1',
    } as ModelListResponse);
    vi.mocked(api.activateModelVersion).mockResolvedValue({ success: true, message: 'Activated', activated_version: 'mv2' });

    render(<Training />);
    await waitFor(() => expect(screen.getByText('v2')).toBeInTheDocument());
    await userEvent.click(screen.getByRole('button', { name: /Activate/i }));

    await waitFor(() => expect(api.activateModelVersion).toHaveBeenCalledWith('mv2'));
  });
});
