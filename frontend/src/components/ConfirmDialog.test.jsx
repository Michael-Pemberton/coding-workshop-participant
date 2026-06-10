import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ConfirmDialog from './ConfirmDialog';

function setup(overrides = {}) {
  const props = {
    open: true,
    title: 'Delete Thing',
    message: 'Are you sure?',
    onConfirm: vi.fn(),
    onCancel: vi.fn(),
    loading: false,
    ...overrides,
  };
  render(<ConfirmDialog {...props} />);
  return props;
}

describe('ConfirmDialog', () => {
  it('renders title and message when open', () => {
    setup();
    expect(screen.getByText('Delete Thing')).toBeInTheDocument();
    expect(screen.getByText('Are you sure?')).toBeInTheDocument();
  });

  it('does not render dialog content when closed', () => {
    setup({ open: false });
    expect(screen.queryByText('Delete Thing')).not.toBeInTheDocument();
  });

  it('fires onConfirm when Delete button clicked', async () => {
    const { onConfirm } = setup();
    await userEvent.click(screen.getByRole('button', { name: /^delete$/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('fires onCancel when Cancel button clicked', async () => {
    const { onCancel } = setup();
    await userEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('shows loading state and disables both buttons', () => {
    setup({ loading: true });
    expect(screen.getByRole('button', { name: /deleting/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /cancel/i })).toBeDisabled();
  });
});
