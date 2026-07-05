import { describe, it, expect, vi } from 'vitest';
import { fetchHealth } from '@/lib/api';

describe('API client smoke test', () => {
  it('fetchHealth calls the configured health endpoint', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ status: 'healthy' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const result = await fetchHealth();

    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringMatching(/\/health$/),
      expect.objectContaining({ skipAuth: true }),
    );
    expect(result).toEqual({ status: 'healthy' });

    fetchSpy.mockRestore();
  });
});
