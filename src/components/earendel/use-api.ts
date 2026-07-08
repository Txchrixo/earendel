"use client";

import * as React from "react";

/**
 * useApi — small data-fetching hook for Earendel views.
 *
 * Uses a manual useEffect + AbortController implementation so it works
 * without a QueryClientProvider. TanStack Query is installed but not wired
 * globally yet; the API here mirrors a useQuery surface so we can swap
 * implementations later without changing call sites.
 *
 * Fetches are aborted on unmount / dependency change to avoid races, and an
 * optional refetchInterval polls the endpoint (default off).
 */
export interface UseApiResult<T> {
  data: T | undefined;
  loading: boolean;
  error: Error | undefined;
  refetch: () => void;
}

export interface UseApiOptions {
  refetchInterval?: number; // ms, 0 = off
  enabled?: boolean; // gate the fetch (default true)
}

export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: React.DependencyList = [],
  opts: UseApiOptions = {},
): UseApiResult<T> {
  const { refetchInterval = 0, enabled = true } = opts;
  const [data, setData] = React.useState<T | undefined>(undefined);
  const [loading, setLoading] = React.useState<boolean>(enabled);
  const [error, setError] = React.useState<Error | undefined>(undefined);
  const [nonce, setNonce] = React.useState(0);

  // Keep the latest fetcher in a ref so deps changes drive re-fetching
  // without forcing fetcher identity into the effect deps.
  const fetcherRef = React.useRef(fetcher);
  React.useEffect(() => {
    fetcherRef.current = fetcher;
  });
  const refetch = React.useCallback(() => setNonce((n) => n + 1), []);

  React.useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    (async () => {
      try {
        const result = await fetcherRef.current();
        if (!active) return;
        setData(result);
        setError(undefined);
      } catch (err) {
        if (!active) return;
        // AbortError happens on teardown — never surface as user error.
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
      controller.abort();
    };
  }, [enabled, nonce, ...deps]);

  // Polling
  React.useEffect(() => {
    if (!enabled || !refetchInterval) return;
    const id = setInterval(() => setNonce((n) => n + 1), refetchInterval);
    return () => clearInterval(id);
  }, [enabled, refetchInterval]);

  return { data, loading, error, refetch };
}

/**
 * useApiMutation — for POST/PUT/DELETE calls.
 *
 * Returns a stable `mutate` function plus loading/error/data state.
 * `reset` clears data/error so callers can dismiss toasts / state.
 */
export interface UseApiMutationResult<TPayload, TResult> {
  mutate: (payload: TPayload) => Promise<TResult | undefined>;
  loading: boolean;
  error: Error | undefined;
  data: TResult | undefined;
  reset: () => void;
}

export function useApiMutation<TPayload, TResult>(
  mutator: (payload: TPayload) => Promise<TResult>,
): UseApiMutationResult<TPayload, TResult> {
  const mutatorRef = React.useRef(mutator);
  React.useEffect(() => {
    mutatorRef.current = mutator;
  });
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<Error | undefined>(undefined);
  const [data, setData] = React.useState<TResult | undefined>(undefined);

  const mutate = React.useCallback(async (payload: TPayload) => {
    setLoading(true);
    setError(undefined);
    try {
      const result = await mutatorRef.current(payload);
      setData(result);
      return result;
    } catch (err) {
      const e = err instanceof Error ? err : new Error(String(err));
      setError(e);
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = React.useCallback(() => {
    setData(undefined);
    setError(undefined);
  }, []);

  return { mutate, loading, error, data, reset };
}
