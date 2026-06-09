import PropTypes from 'prop-types';
import Chip from '@mui/material/Chip';

const PROJECT_STATUS_CONFIG = {
  active: { color: 'success', label: 'Active' },
  inactive: { color: 'default', label: 'Inactive' },
  completed: { color: 'info', label: 'Completed' },
  on_hold: { color: 'warning', label: 'On Hold' },
  cancelled: { color: 'error', label: 'Cancelled' },
};

const DELIVERABLE_STATUS_CONFIG = {
  pending: { color: 'default', label: 'Pending' },
  in_progress: { color: 'info', label: 'In Progress' },
  completed: { color: 'success', label: 'Completed' },
  blocked: { color: 'error', label: 'Blocked' },
  cancelled: { color: 'warning', label: 'Cancelled' },
};

/**
 * Displays a colored chip for project or deliverable statuses.
 * @param {object} props
 * @param {string} props.status - Status string value.
 * @param {'project'|'deliverable'} [props.type]
 * @param {string} [props.size]
 */
function StatusChip({ status, type, size }) {
  const configMap =
    type === 'deliverable' ? DELIVERABLE_STATUS_CONFIG : PROJECT_STATUS_CONFIG;
  const config = configMap[status] || { color: 'default', label: status };
  return (
    <Chip
      label={config.label}
      color={config.color}
      size={size}
      sx={{ textTransform: 'capitalize' }}
    />
  );
}

StatusChip.propTypes = {
  status: PropTypes.string.isRequired,
  type: PropTypes.oneOf(['project', 'deliverable']),
  size: PropTypes.string,
};

StatusChip.defaultProps = { type: 'project', size: 'small' };

export default StatusChip;
