import { render, screen } from '@testing-library/react';
import StatusChip from '../components/StatusChip';

describe('StatusChip', () => {
  it('renders Active label for active project status', () => {
    render(<StatusChip status="active" />);
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('renders Completed label', () => {
    render(<StatusChip status="completed" />);
    expect(screen.getByText('Completed')).toBeInTheDocument();
  });

  it('renders On Hold label', () => {
    render(<StatusChip status="on_hold" />);
    expect(screen.getByText('On Hold')).toBeInTheDocument();
  });

  it('falls back to raw status string for unknown values', () => {
    render(<StatusChip status="unknown_xyz" />);
    expect(screen.getByText('unknown_xyz')).toBeInTheDocument();
  });

  it('renders deliverable In Progress status', () => {
    render(<StatusChip status="in_progress" type="deliverable" />);
    expect(screen.getByText('In Progress')).toBeInTheDocument();
  });

  it('renders deliverable Blocked status', () => {
    render(<StatusChip status="blocked" type="deliverable" />);
    expect(screen.getByText('Blocked')).toBeInTheDocument();
  });
});
