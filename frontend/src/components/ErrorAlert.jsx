import PropTypes from 'prop-types';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Box from '@mui/material/Box';

/**
 * Displays an error message with an optional retry action.
 * @param {object} props
 * @param {string} props.message
 * @param {function} [props.onRetry]
 */
function ErrorAlert({ message, onRetry }) {
  return (
    <Box sx={{ my: 2 }}>
      <Alert
        severity="error"
        action={
          onRetry && (
            <Button color="inherit" size="small" onClick={onRetry}>
              Retry
            </Button>
          )
        }
      >
        {message}
      </Alert>
    </Box>
  );
}

ErrorAlert.propTypes = {
  message: PropTypes.string.isRequired,
  onRetry: PropTypes.func,
};

ErrorAlert.defaultProps = { onRetry: null };

export default ErrorAlert;
