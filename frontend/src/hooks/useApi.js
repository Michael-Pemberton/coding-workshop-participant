import { useState, useCallback, useEffect } from 'react';

/**
 * Generic data-fetching hook. Replaces the duplicated useEffect+useState
 * pattern across all page components.
 *
 * @param {Function} apiFn - Async function that returns API data
 * @param {Array} deps - Dependencies that trigger a refetch when changed
 */
export function useApi(apiFn, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const refetch = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const result = await apiFn();
      setData(result?.data ?? result ?? null);
    } catch (err) {
      setError(err.message || 'An error occurred');
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { data, loading, error, refetch };
}
