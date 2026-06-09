import { renderHook, waitFor, act } from '@testing-library/react';
import { useApi } from '../hooks/useApi';

describe('useApi', () => {
  it('starts in loading state', () => {
    const apiFn = vi.fn().mockResolvedValue({ data: [] });
    const { result } = renderHook(() => useApi(apiFn));
    expect(result.current.loading).toBe(true);
  });

  it('sets data on success', async () => {
    const apiFn = vi.fn().mockResolvedValue({ data: [{ id: 1 }] });
    const { result } = renderHook(() => useApi(apiFn));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.data).toEqual([{ id: 1 }]);
    expect(result.current.error).toBe('');
  });

  it('unwraps non-envelope responses', async () => {
    const apiFn = vi.fn().mockResolvedValue([{ id: 2 }]);
    const { result } = renderHook(() => useApi(apiFn));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.data).toEqual([{ id: 2 }]);
  });

  it('sets error message on failure', async () => {
    const apiFn = vi.fn().mockRejectedValue(new Error('Network error'));
    const { result } = renderHook(() => useApi(apiFn));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('Network error');
    expect(result.current.data).toBeNull();
  });

  it('refetch re-invokes the API', async () => {
    const apiFn = vi.fn().mockResolvedValue({ data: [] });
    const { result } = renderHook(() => useApi(apiFn));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(apiFn).toHaveBeenCalledTimes(1);

    await act(() => result.current.refetch());
    expect(apiFn).toHaveBeenCalledTimes(2);
  });
});
