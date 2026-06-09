import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';

/**
 * Full-container loading spinner overlay.
 */
function LoadingOverlay() {
  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: 200,
      }}
    >
      <CircularProgress />
    </Box>
  );
}

export default LoadingOverlay;
