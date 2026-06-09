import { useEffect, useState, useCallback } from 'react';
import PropTypes from 'prop-types';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import TextField from '@mui/material/TextField';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import IconButton from '@mui/material/IconButton';
import LinearProgress from '@mui/material/LinearProgress';
import Chip from '@mui/material/Chip';
import { DataGrid } from '@mui/x-data-grid';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';

import { peopleApi } from '../services/api.js';
import { useAuth } from '../contexts/AuthContext.jsx';
import ConfirmDialog from '../components/ConfirmDialog.jsx';
import ErrorAlert from '../components/ErrorAlert.jsx';

const EMPTY_FORM = { name: '', email: '', title: '', weekly_hours_capacity: 40 };

/**
 * Person create/edit form dialog.
 * @param {object} props
 */
function PersonFormDialog({ open, person, onSave, onClose, saving }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (person) {
      setForm({
        name: person.name || '',
        email: person.email || '',
        title: person.title || '',
        weekly_hours_capacity: person.weekly_hours_capacity ?? 40,
      });
    } else {
      setForm(EMPTY_FORM);
    }
    setErrors({});
  }, [person, open]);

  const validate = () => {
    const e = {};
    if (!form.name.trim()) e.name = 'Name is required';
    if (!form.email.trim()) e.email = 'Email is required';
    else if (!/\S+@\S+\.\S+/.test(form.email)) e.email = 'Invalid email address';
    return e;
  };

  const handleSubmit = () => {
    const e = validate();
    if (Object.keys(e).length) { setErrors(e); return; }
    onSave(form);
  };

  const set = (field) => (ev) => setForm((f) => ({ ...f, [field]: ev.target.value }));

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{person ? 'Edit Person' : 'New Person'}</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
        <TextField
          label="Name *"
          value={form.name}
          onChange={set('name')}
          error={!!errors.name}
          helperText={errors.name}
          fullWidth
        />
        <TextField
          label="Email *"
          type="email"
          value={form.email}
          onChange={set('email')}
          error={!!errors.email}
          helperText={errors.email}
          fullWidth
        />
        <TextField label="Job Title" value={form.title} onChange={set('title')} fullWidth />
        <TextField
          label="Weekly Hours Capacity"
          type="number"
          value={form.weekly_hours_capacity}
          onChange={set('weekly_hours_capacity')}
          fullWidth
          inputProps={{ min: 1, max: 168 }}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving}>Cancel</Button>
        <Button onClick={handleSubmit} variant="contained" disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

PersonFormDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  person: PropTypes.object,
  onSave: PropTypes.func.isRequired,
  onClose: PropTypes.func.isRequired,
  saving: PropTypes.bool.isRequired,
};
PersonFormDialog.defaultProps = { person: null };

/**
 * People list page with allocation tracking and CRUD operations.
 */
function PeoplePage() {
  const { canEdit, canDelete } = useAuth();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const fetchPeople = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const result = await peopleApi.getAll();
      setRows(result?.data ?? result ?? []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchPeople(); }, [fetchPeople]);

  const filtered = rows.filter((r) =>
    !search ||
    r.name?.toLowerCase().includes(search.toLowerCase()) ||
    r.email?.toLowerCase().includes(search.toLowerCase()),
  );

  const handleSave = async (form) => {
    setSaving(true);
    try {
      if (editing) await peopleApi.update(editing.id, form);
      else await peopleApi.create(form);
      setFormOpen(false);
      setEditing(null);
      await fetchPeople();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await peopleApi.remove(deleteTarget.id);
      setDeleteTarget(null);
      await fetchPeople();
    } catch (err) {
      setError(err.message);
    } finally {
      setDeleting(false);
    }
  };

  const columns = [
    { field: 'name', headerName: 'Name', flex: 1, minWidth: 140 },
    { field: 'email', headerName: 'Email', flex: 1, minWidth: 160 },
    { field: 'title', headerName: 'Title', width: 150 },
    { field: 'weekly_hours_capacity', headerName: 'Capacity (h/w)', width: 130 },
    {
      field: 'allocation',
      headerName: 'Allocation',
      width: 180,
      renderCell: ({ row }) => {
        const allocated = row.allocated_hours_per_week || 0;
        const capacity = row.weekly_hours_capacity || 40;
        const pct = Math.round((allocated / capacity) * 100);
        return (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
            <LinearProgress
              variant="determinate"
              value={Math.min(pct, 100)}
              color={pct > 100 ? 'error' : pct > 80 ? 'warning' : 'success'}
              sx={{ flexGrow: 1, height: 8, borderRadius: 4 }}
            />
            <Typography variant="caption" sx={{ minWidth: 50 }}>
              {allocated}h/{capacity}h
            </Typography>
          </Box>
        );
      },
    },
    {
      field: 'is_overallocated',
      headerName: 'Status',
      width: 120,
      renderCell: ({ value }) =>
        value ? (
          <Chip label="Over" color="error" size="small" />
        ) : (
          <Chip label="OK" color="success" size="small" />
        ),
    },
    {
      field: 'actions',
      headerName: '',
      width: 90,
      sortable: false,
      renderCell: ({ row }) => (
        <Box onClick={(e) => e.stopPropagation()}>
          {canEdit() && (
            <IconButton size="small" onClick={() => { setEditing(row); setFormOpen(true); }}>
              <EditIcon fontSize="small" />
            </IconButton>
          )}
          {canDelete() && (
            <IconButton size="small" color="error" onClick={() => setDeleteTarget(row)}>
              <DeleteIcon fontSize="small" />
            </IconButton>
          )}
        </Box>
      ),
    },
  ];

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5" fontWeight="bold">People</Typography>
        {canEdit() && (
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => { setEditing(null); setFormOpen(true); }}>
            New Person
          </Button>
        )}
      </Box>

      <Box sx={{ mb: 2 }}>
        <TextField
          size="small"
          label="Search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          sx={{ minWidth: 240 }}
        />
      </Box>

      {error && <ErrorAlert message={error} onRetry={fetchPeople} />}

      <DataGrid
        rows={filtered}
        columns={columns}
        loading={loading}
        autoHeight
        pageSize={20}
        rowsPerPageOptions={[20, 50]}
        disableSelectionOnClick
        sx={{ bgcolor: 'white' }}
      />

      <PersonFormDialog
        open={formOpen}
        person={editing}
        onSave={handleSave}
        onClose={() => { setFormOpen(false); setEditing(null); }}
        saving={saving}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete Person"
        message={`Delete "${deleteTarget?.name}"? This cannot be undone.`}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
        loading={deleting}
      />
    </Box>
  );
}

export default PeoplePage;
