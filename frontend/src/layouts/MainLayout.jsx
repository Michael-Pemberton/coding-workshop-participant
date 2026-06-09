import { useState } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import PropTypes from 'prop-types';
import AppBar from '@mui/material/AppBar';
import Box from '@mui/material/Box';
import Drawer from '@mui/material/Drawer';
import IconButton from '@mui/material/IconButton';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import Avatar from '@mui/material/Avatar';
import Tooltip from '@mui/material/Tooltip';
import Chip from '@mui/material/Chip';
import MenuIcon from '@mui/icons-material/Menu';
import DashboardIcon from '@mui/icons-material/Dashboard';
import FolderIcon from '@mui/icons-material/Folder';
import PeopleIcon from '@mui/icons-material/People';
import ChecklistIcon from '@mui/icons-material/Checklist';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings';
import LogoutIcon from '@mui/icons-material/Logout';
import useMediaQuery from '@mui/material/useMediaQuery';
import { useTheme } from '@mui/material/styles';

import { useAuth } from '../contexts/AuthContext.jsx';

const DRAWER_WIDTH = 220;

const NAV_ITEMS = [
  { label: 'Dashboard', to: '/', icon: <DashboardIcon /> },
  { label: 'Projects', to: '/projects', icon: <FolderIcon /> },
  { label: 'People', to: '/people', icon: <PeopleIcon /> },
  { label: 'Deliverables', to: '/deliverables', icon: <ChecklistIcon /> },
  { label: 'Budgets', to: '/budgets', icon: <AccountBalanceWalletIcon /> },
];

const ADMIN_NAV_ITEMS = [
  { label: 'Users', to: '/admin/users', icon: <AdminPanelSettingsIcon /> },
];

/**
 * Sidebar navigation drawer content.
 * @param {object} props
 * @param {function} props.onClose
 * @param {boolean} props.showAdmin - When true, append admin nav items.
 */
function DrawerContent({ onClose, showAdmin }) {
  const items = showAdmin ? [...NAV_ITEMS, ...ADMIN_NAV_ITEMS] : NAV_ITEMS;
  return (
    <Box sx={{ width: DRAWER_WIDTH }}>
      <Toolbar>
        <Typography variant="h6" fontWeight="bold" color="primary">
          ACME Tracker
        </Typography>
      </Toolbar>
      <List>
        {items.map(({ label, to, icon }) => (
          <ListItem key={to} disablePadding>
            <ListItemButton
              component={NavLink}
              to={to}
              end={to === '/'}
              onClick={onClose}
              sx={{
                '&.active': { bgcolor: 'primary.light', color: 'primary.contrastText' },
                '&.active .MuiListItemIcon-root': { color: 'primary.contrastText' },
              }}
            >
              <ListItemIcon sx={{ minWidth: 36 }}>{icon}</ListItemIcon>
              <ListItemText primary={label} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
    </Box>
  );
}

DrawerContent.propTypes = {
  onClose: PropTypes.func.isRequired,
  showAdmin: PropTypes.bool,
};

DrawerContent.defaultProps = {
  showAdmin: false,
};

/**
 * Main application layout with AppBar and responsive sidebar.
 */
function MainLayout() {
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [drawerOpen, setDrawerOpen] = useState(false);
  const showAdmin = isAdmin();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar position="fixed" sx={{ zIndex: (t) => t.zIndex.drawer + 1 }}>
        <Toolbar>
          {isMobile && (
            <IconButton
              color="inherit"
              edge="start"
              sx={{ mr: 1 }}
              onClick={() => setDrawerOpen(true)}
            >
              <MenuIcon />
            </IconButton>
          )}
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            ACME Project Tracker
          </Typography>
          {user && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Chip
                label={user.role}
                size="small"
                color="secondary"
                sx={{ color: 'white', textTransform: 'capitalize' }}
              />
              <Tooltip title={user.email}>
                <Avatar sx={{ width: 32, height: 32, bgcolor: 'secondary.main' }}>
                  {user.name?.[0]?.toUpperCase()}
                </Avatar>
              </Tooltip>
              <Tooltip title="Logout">
                <IconButton color="inherit" onClick={handleLogout} size="small">
                  <LogoutIcon />
                </IconButton>
              </Tooltip>
            </Box>
          )}
        </Toolbar>
      </AppBar>

      {/* Permanent drawer on desktop */}
      {!isMobile && (
        <Drawer
          variant="permanent"
          sx={{
            width: DRAWER_WIDTH,
            '& .MuiDrawer-paper': { width: DRAWER_WIDTH, boxSizing: 'border-box' },
          }}
        >
          <DrawerContent onClose={() => {}} showAdmin={showAdmin} />
        </Drawer>
      )}

      {/* Temporary drawer on mobile */}
      {isMobile && (
        <Drawer
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          ModalProps={{ keepMounted: true }}
        >
          <DrawerContent onClose={() => setDrawerOpen(false)} showAdmin={showAdmin} />
        </Drawer>
      )}

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          mt: 8,
          ml: isMobile ? 0 : `${DRAWER_WIDTH}px`,
          minHeight: '100vh',
          bgcolor: 'grey.50',
        }}
      >
        <Outlet />
      </Box>
    </Box>
  );
}

export default MainLayout;
