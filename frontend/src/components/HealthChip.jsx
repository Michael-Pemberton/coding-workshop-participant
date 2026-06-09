import PropTypes from 'prop-types';
import Chip from '@mui/material/Chip';

const HEALTH_CONFIG = {
  green: { color: 'success', label: 'Green' },
  amber: { color: 'warning', label: 'Amber' },
  red: { color: 'error', label: 'Red' },
};

/**
 * Displays a colored RAG health indicator chip.
 * @param {object} props
 * @param {string} props.health - 'green' | 'amber' | 'red'
 * @param {string} [props.size]
 */
function HealthChip({ health, size }) {
  const config = HEALTH_CONFIG[health] || { color: 'default', label: health };
  return <Chip label={config.label} color={config.color} size={size} />;
}

HealthChip.propTypes = {
  health: PropTypes.oneOf(['green', 'amber', 'red']).isRequired,
  size: PropTypes.string,
};

HealthChip.defaultProps = { size: 'small' };

export default HealthChip;
