import { useState, useEffect } from 'react';
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
import Brightness4Icon from '@mui/icons-material/Brightness4';
import Brightness7Icon from '@mui/icons-material/Brightness7';
import useMediaQuery from '@mui/material/useMediaQuery';
import { useTheme } from '@mui/material/styles';

import { useAuth } from '../contexts/AuthContext.jsx';
import { useColorMode } from '../contexts/ColorModeContext.jsx';

const DRAWER_WIDTH = 220;
const DRAWER_PREF_KEY = 'layout:drawerOpen';

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
                '&.active': { bgcolor: 'primary.main', color: 'primary.contrastText' },
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
 * Main application layout with AppBar and an always-toggleable sidebar.
 */
function MainLayout() {
  const { user, logout, isAdmin } = useAuth();
  const { mode, toggle: toggleColorMode } = useColorMode();
  const navigate = useNavigate();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [drawerOpen, setDrawerOpen] = useState(() => {
    const saved = localStorage.getItem(DRAWER_PREF_KEY);
    return saved == null ? true : saved === 'true';
  });
  const showAdmin = isAdmin();

  // Auto-close on shrinking to mobile; reopen on growing back to desktop
  // if the user hadn't explicitly closed it.
  useEffect(() => {
    if (isMobile) setDrawerOpen(false);
  }, [isMobile]);

  const toggleDrawer = () => {
    setDrawerOpen((prev) => {
      const next = !prev;
      if (!isMobile) localStorage.setItem(DRAWER_PREF_KEY, String(next));
      return next;
    });
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const persistentOpen = !isMobile && drawerOpen;

  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar position="fixed" sx={{ zIndex: (t) => t.zIndex.drawer + 1 }}>
        <Toolbar>
          <IconButton
            color="inherit"
            edge="start"
            sx={{ mr: 1 }}
            onClick={toggleDrawer}
            aria-label="toggle navigation"
          >
            <MenuIcon />
          </IconButton>
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
              <Tooltip title={mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}>
                <IconButton color="inherit" onClick={toggleColorMode} size="small">
                  {mode === 'dark' ? <Brightness7Icon /> : <Brightness4Icon />}
                </IconButton>
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

      {/* Persistent drawer on desktop — toggleable */}
      {!isMobile && (
        <Drawer
          variant="persistent"
          open={drawerOpen}
          sx={{
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
          minWidth: 0,
          p: 3,
          mt: 8,
          ml: persistentOpen ? `${DRAWER_WIDTH}px` : 0,
          transition: (t) => t.transitions.create('margin-left', {
            easing: t.transitions.easing.sharp,
            duration: t.transitions.duration.leavingScreen,
          }),
          minHeight: '100vh',
          bgcolor: 'background.default',
        }}
      >
        <Outlet />
      </Box>
    </Box>
  );
}

export default MainLayout;
