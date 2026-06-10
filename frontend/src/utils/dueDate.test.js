import { beforeEach, afterEach, describe, it, expect, vi } from 'vitest';
import { timeLeft } from './dueDate';

describe('timeLeft', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-06-10T12:00:00'));
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns em-dash for missing date', () => {
    expect(timeLeft(null)).toBe('—');
    expect(timeLeft(undefined)).toBe('—');
    expect(timeLeft('')).toBe('—');
  });

  it('returns "Today" when due today', () => {
    expect(timeLeft('2026-06-10')).toBe('Today');
  });

  it('formats overdue dates', () => {
    expect(timeLeft('2026-06-09')).toBe('1d overdue');
    expect(timeLeft('2026-06-01')).toBe('9d overdue');
  });

  it('formats days when ≤14 days away', () => {
    expect(timeLeft('2026-06-11')).toBe('1d');
    expect(timeLeft('2026-06-24')).toBe('14d');
  });

  it('formats weeks when >14 days away', () => {
    expect(timeLeft('2026-06-25')).toBe('3w');
    expect(timeLeft('2026-07-10')).toBe('5w');
  });

  it('accepts full ISO timestamps and ignores the time portion', () => {
    expect(timeLeft('2026-06-10T23:59:59Z')).toBe('Today');
  });
});
