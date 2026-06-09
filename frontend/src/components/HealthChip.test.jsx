import { render, screen } from '@testing-library/react';
import HealthChip from '../components/HealthChip';

describe('HealthChip', () => {
  it('renders Green for green health', () => {
    render(<HealthChip health="green" />);
    expect(screen.getByText('Green')).toBeInTheDocument();
  });

  it('renders Amber for amber health', () => {
    render(<HealthChip health="amber" />);
    expect(screen.getByText('Amber')).toBeInTheDocument();
  });

  it('renders Red for red health', () => {
    render(<HealthChip health="red" />);
    expect(screen.getByText('Red')).toBeInTheDocument();
  });

  it('falls back to raw value for unknown health', () => {
    render(<HealthChip health="unknown" />);
    expect(screen.getByText('unknown')).toBeInTheDocument();
  });
});
