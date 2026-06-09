import { useCallback, useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import TextField from '@mui/material/TextField';
import MenuItem from '@mui/material/MenuItem';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import IconButton from '@mui/material/IconButton';
import Chip from '@mui/material/Chip';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';

import { authApi } from '../services/api.js';
import { useAuth } from '../contexts/AuthContext.jsx';
import ConfirmDialog from '../components/ConfirmDialog.jsx';
import LoadingOverlay from '../components/LoadingOverlay.jsx';
import ErrorAlert from '../components/ErrorAlert.jsx';

const ROLES = ['admin', 'manager', 'contributor', 'viewer'];

const EMPTY_FORM = {
  username: '',
  name: '',
  email: '',
  password: '',
  role: 'viewer',
};

/**
 * Admin-only user management page: create, edit role/password, deactivate.
 */
function AdminUsersPage() {
  const { isAdmin, user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(null);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const result = await authApi.getUsers();
      setUsers(result?.data ?? result ?? []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAdmin()) fetchUsers();
  }, [isAdmin, fetchUsers]);

  if (!isAdmin()) return <Navigate to="/" replace />;

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  };

  const openEdit = (u) => {
    setEditing(u);
    setForm({
      username: u.username ?? '',
      name: u.name ?? '',
      email: u.email ?? '',
      password: '',
      role: u.user_role ?? 'viewer',
    });
    setDialogOpen(true);
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      if (editing) {
        const payload = {
          username: form.username,
          name: form.name,
          email: form.email,
          role: form.role,
        };
        if (form.password) payload.password = form.password;
        await authApi.updateUser(editing.id, payload);
      } else {
        await authApi.createUser(form);
      }
      setDialogOpen(false);
      await fetchUsers();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setSaving(true);
    try {
      await authApi.deleteUser(confirmDelete.id);
      setConfirmDelete(null);
      await fetchUsers();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingOverlay />;

  const canSubmit =
    form.username.trim() &&
    form.name.trim() &&
    form.email.trim() &&
    (editing || form.password) &&
    ROLES.includes(form.role);

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5" fontWeight="bold" sx={{ flexGrow: 1 }}>
          Users
        </Typography>
        <Button startIcon={<AddIcon />} variant="contained" onClick={openCreate}>
          New User
        </Button>
      </Box>

      {error && <ErrorAlert message={error} />}

      <Table size="small" component={Paper}>
        <TableHead>
          <TableRow>
            <TableCell>Name</TableCell>
            <TableCell>Username</TableCell>
            <TableCell>Email</TableCell>
            <TableCell>Role</TableCell>
            <TableCell>Status</TableCell>
            <TableCell align="right" />
          </TableRow>
        </TableHead>
        <TableBody>
          {users.map((u) => {
            const isSelf = currentUser?.id === u.id;
            return (
              <TableRow key={u.id}>
                <TableCell>{u.name}</TableCell>
                <TableCell>{u.username ?? '—'}</TableCell>
                <TableCell>{u.email}</TableCell>
                <TableCell>
                  <Chip
                    label={u.user_role}
                    size="small"
                    sx={{ textTransform: 'capitalize' }}
                    color={u.user_role === 'admin' ? 'secondary' : 'default'}
                  />
                </TableCell>
                <TableCell>
                  <Chip
                    label={u.is_active ? 'active' : 'inactive'}
                    size="small"
                    color={u.is_active ? 'success' : 'default'}
                  />
                </TableCell>
                <TableCell align="right">
                  <IconButton size="small" onClick={() => openEdit(u)}>
                    <EditIcon fontSize="small" />
                  </IconButton>
                  <IconButton
                    size="small"
                    color="error"
                    disabled={isSelf}
                    onClick={() => setConfirmDelete(u)}
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>{editing ? 'Edit User' : 'New User'}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
          <TextField
            label="Name *"
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            fullWidth
          />
          <TextField
            label="Username *"
            value={form.username}
            onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
            fullWidth
          />
          <TextField
            label="Email *"
            type="email"
            value={form.email}
            onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
            fullWidth
          />
          <TextField
            label={editing ? 'New Password (leave blank to keep current)' : 'Password *'}
            type="password"
            value={form.password}
            onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
            fullWidth
          />
          <TextField
            select
            label="Role"
            value={form.role}
            onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
            fullWidth
          >
            {ROLES.map((r) => (
              <MenuItem key={r} value={r} sx={{ textTransform: 'capitalize' }}>
                {r}
              </MenuItem>
            ))}
          </TextField>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleSave} variant="contained" disabled={!canSubmit || saving}>
            Save
          </Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={!!confirmDelete}
        title="Deactivate User"
        message={`Deactivate ${confirmDelete?.name}? They will no longer be able to log in.`}
        onConfirm={handleDelete}
        onCancel={() => setConfirmDelete(null)}
        loading={saving}
      />
    </Box>
  );
}

export default AdminUsersPage;
