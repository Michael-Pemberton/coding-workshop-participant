import PropTypes from 'prop-types';
import Chip from '@mui/material/Chip';
import Tooltip from '@mui/material/Tooltip';

const HEALTH_CONFIG = {
  green: { color: 'success', label: 'Green' },
  amber: { color: 'warning', label: 'Amber' },
  red: { color: 'error', label: 'Red' },
};  

/**
 * Displays a colored RAG health indicator chip with an optional reason tooltip.
 * @param {object} props
 * @param {string} props.health - 'green' | 'amber' | 'red'
 * @param {string} [props.reason]
 * @param {string} [props.size]
 */
function HealthChip({ health, reason, size }) {
  const config = HEALTH_CONFIG[health] || { color: 'default', label: health };
  const chip = <Chip label={config.label} color={config.color} size={size} />;
  return reason ? <Tooltip title={reason}><span>{chip}</span></Tooltip> : chip;
}

HealthChip.propTypes = {
  health: PropTypes.oneOf(['green', 'amber', 'red']).isRequired,
  reason: PropTypes.string,
  size: PropTypes.string,
};

HealthChip.defaultProps = { reason: '', size: 'small' };

export default HealthChip;
