import { describe, it, expect, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useQuery, useMutation } from '@/hooks/useApi';

describe('useQuery', () => {
  it('fetches data on mount', async () => {
    const fetcher = vi.fn().mockResolvedValue({ status: 'ok' });
    const { result } = renderHook(() => useQuery(fetcher, []));

    expect(result.current.isLoading).toBe(true);
    await waitFor(() => expect(result.current.data).toEqual({ status: 'ok' }));
    expect(result.current.error).toBeNull();
  });

  it('sets error when fetch fails', async () => {
    const fetcher = vi.fn().mockRejectedValue({ detail: 'boom' });
    const { result } = renderHook(() => useQuery(fetcher, []));

    await waitFor(() => expect(result.current.error).toMatchObject({ detail: 'boom' }));
    expect(result.current.data).toBeNull();
  });

  it('does not fetch when disabled', async () => {
    const fetcher = vi.fn().mockResolvedValue({ status: 'ok' });
    renderHook(() => useQuery(fetcher, [], { enabled: false }));

    expect(fetcher).not.toHaveBeenCalled();
  });
});

describe('useMutation', () => {
  it('executes a mutation and stores the result', async () => {
    const mutator = vi.fn().mockResolvedValue({ id: '1' });
    const { result } = renderHook(() => useMutation(mutator));

    await result.current.mutate({ name: 'test' });

    expect(mutator).toHaveBeenCalledWith({ name: 'test' });
    await waitFor(() => expect(result.current.data).toEqual({ id: '1' }));
    expect(result.current.error).toBeNull();
  });

  it('stores an error when the mutation fails', async () => {
    const mutator = vi.fn().mockRejectedValue({ detail: 'failed' });
    const { result } = renderHook(() => useMutation(mutator));

    await expect(result.current.mutate({})).rejects.toMatchObject({ detail: 'failed' });
    await waitFor(() => expect(result.current.error).toMatchObject({ detail: 'failed' }));
  });
});
