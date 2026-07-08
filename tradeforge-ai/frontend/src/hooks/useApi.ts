/**
 * TradeForge AI — React hooks for backend API calls.
 *
 * Thin wrappers around `src/lib/api.ts` that expose loading/error/state
 * management for components. As the app grows, this is the natural place
 * to swap in TanStack Query without touching UI code.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type { ApiError } from '@/types/api';

export interface QueryState<T> {
  data: T | null;
  isLoading: boolean;
  error: ApiError | Error | null;
  refetch: () => void;
}

export interface MutationState<TInput, TOutput> {
  mutate: (input: TInput) => Promise<TOutput | undefined>;
  data: TOutput | null;
  isLoading: boolean;
  error: ApiError | Error | null;
  reset: () => void;
}

/**
 * Fetch data on mount and whenever `deps` change.
 */
export function useQuery<T>(
  fetcher: () => Promise<T>,
  deps: React.DependencyList = [],
  options: { enabled?: boolean } = {},
): QueryState<T> {
  const { enabled = true } = options;
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const fetcherRef = useRef(fetcher);

  useEffect(() => {
    fetcherRef.current = fetcher;
  }, [fetcher]);

  const execute = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await fetcherRef.current();
      setData(result);
      return result;
    } catch (err) {
      const normalized = normalizeError(err);
      setError(normalized);
      throw normalized;
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;
    execute().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, execute, ...deps]);

  return { data, isLoading, error, refetch: execute };
}

/**
 * Execute a mutation manually (e.g. form submit, button click).
 */
export function useMutation<TInput, TOutput>(
  mutator: (input: TInput) => Promise<TOutput>,
): MutationState<TInput, TOutput> {
  const [data, setData] = useState<TOutput | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const mutatorRef = useRef(mutator);

  useEffect(() => {
    mutatorRef.current = mutator;
  }, [mutator]);

  const mutate = useCallback(async (input: TInput) => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await mutatorRef.current(input);
      setData(result);
      return result;
    } catch (err) {
      const normalized = normalizeError(err);
      setError(normalized);
      throw normalized;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setIsLoading(false);
  }, []);

  return { mutate, data, isLoading, error, reset };
}

function normalizeError(err: unknown): ApiError | Error {
  if (err && typeof err === 'object' && 'detail' in err) {
    return err as ApiError;
  }
  if (err instanceof Error) return err;
  return new Error(String(err));
}
