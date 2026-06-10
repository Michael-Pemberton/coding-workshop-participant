import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ErrorAlert from './ErrorAlert';

describe('ErrorAlert', () => {
  it('renders the message', () => {
    render(<ErrorAlert message="Something broke" />);
    expect(screen.getByText('Something broke')).toBeInTheDocument();
  });

  it('does not render a Retry button when onRetry is not provided', () => {
    render(<ErrorAlert message="broken" />);
    expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument();
  });

  it('renders Retry button and fires callback when onRetry is provided', async () => {
    const onRetry = vi.fn();
    render(<ErrorAlert message="broken" onRetry={onRetry} />);
    await userEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
