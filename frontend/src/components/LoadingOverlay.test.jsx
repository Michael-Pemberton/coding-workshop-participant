import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import LoadingOverlay from './LoadingOverlay';

describe('LoadingOverlay', () => {
  it('renders a progressbar', () => {
    render(<LoadingOverlay />);
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });
});
