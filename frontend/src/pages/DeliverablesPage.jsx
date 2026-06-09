import { useEffect, useState, useCallback } from 'react';
import PropTypes from 'prop-types';
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
import { DataGrid } from '@mui/x-data-grid';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';

import { deliverablesApi, projectsApi } from '../services/api.js';
import { useAuth } from '../contexts/AuthContext.jsx';
import StatusChip from '../components/StatusChip.jsx';
import ConfirmDialog from '../components/ConfirmDialog.jsx';
import ErrorAlert from '../components/ErrorAlert.jsx';

const STATUSES = ['pending', 'in_progress', 'completed', 'blocked', 'cancelled'];
const EMPTY_FORM = { title: '', description: '', status: 'pending', due_date: '', depends_on_id: '' };

/**
 * Deliverable create/edit dialog.
 */
function DeliverableFormDialog({ open, deliverable, siblings, projectId, onSave, onClose, saving }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (deliverable) {
      setForm({
        title: deliverable.title || '',
        description: deliverable.description || '',
        status: deliverable.status || 'pending',
        due_date: deliverable.due_date?.slice(0, 10) || '',
        depends_on_id: deliverable.depends_on_id || '',
      });
    } else {
      setForm(EMPTY_FORM);
    }
    setErrors({});
  }, [deliverable, open]);

  const handleSubmit = () => {
    if (!form.title.trim()) { setErrors({ title: 'Title is required' }); return; }
    onSave({ ...form, project_id: projectId });
  };

  const set = (field) => (ev) => setForm((f) => ({ ...f, [field]: ev.target.value }));

  const depOptions = siblings.filter((s) => s.id !== deliverable?.id);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{deliverable ? 'Edit Deliverable' : 'New Deliverable'}</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
        <TextField label="Title *" value={form.title} onChange={set('title')} error={!!errors.title} helperText={errors.title} fullWidth />
        <TextField label="Description" value={form.description} onChange={set('description')} multiline rows={2} fullWidth />
        <Box sx={{ display: 'flex', gap: 2 }}>
          <TextField select label="Status" value={form.status} onChange={set('status')} fullWidth>
            {STATUSES.map((s) => <MenuItem key={s} value={s} sx={{ textTransform: 'capitalize' }}>{s.replace('_', ' ')}</MenuItem>)}
          </TextField>
          <TextField label="Due Date" type="date" value={form.due_date} onChange={set('due_date')} fullWidth InputLabelProps={{ shrink: true }} />
        </Box>
        <TextField select label="Depends On" value={form.depends_on_id} onChange={set('depends_on_id')} fullWidth>
          <MenuItem value="">None</MenuItem>
          {depOptions.map((d) => <MenuItem key={d.id} value={d.id}>{d.title}</MenuItem>)}
        </TextField>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving}>Cancel</Button>
        <Button onClick={handleSubmit} variant="contained" disabled={saving}>{saving ? 'Saving…' : 'Save'}</Button>
      </DialogActions>
    </Dialog>
  );
}

DeliverableFormDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  deliverable: PropTypes.object,
  siblings: PropTypes.array.isRequired,
  projectId: PropTypes.string,
  onSave: PropTypes.func.isRequired,
  onClose: PropTypes.func.isRequired,
  saving: PropTypes.bool.isRequired,
};
DeliverableFormDialog.defaultProps = { deliverable: null, projectId: null };

/**
 * Deliverables page with project filter, DataGrid, and CRUD dialogs.
 */
function DeliverablesPage() {
  const { canEdit, canDelete } = useAuth();
  const [rows, setRows] = useState([]);
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const fetchProjects = useCallback(async () => {
    try {
      const result = await projectsApi.getAll();
      setProjects(result?.data ?? result ?? []);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  const fetchDeliverables = useCallback(async () => {
    if (!selectedProject) { setRows([]); return; }
    setLoading(true);
    setError('');
    try {
      const result = await deliverablesApi.getAll({ project_id: selectedProject });
      setRows(result?.data ?? result ?? []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [selectedProject]);

  useEffect(() => { fetchProjects(); }, [fetchProjects]);
  useEffect(() => { fetchDeliverables(); }, [fetchDeliverables]);

  const handleSave = async (form) => {
    setSaving(true);
    try {
      if (editing) await deliverablesApi.update(editing.id, form);
      else await deliverablesApi.create(form);
      setFormOpen(false);
      setEditing(null);
      await fetchDeliverables();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await deliverablesApi.remove(deleteTarget.id);
      setDeleteTarget(null);
      await fetchDeliverables();
    } catch (err) {
      setError(err.message);
    } finally {
      setDeleting(false);
    }
  };

  const columns = [
    { field: 'title', headerName: 'Title', flex: 1, minWidth: 160 },
    { field: 'status', headerName: 'Status', width: 130, renderCell: ({ value }) => <StatusChip status={value} type="deliverable" /> },
    { field: 'due_date', headerName: 'Due Date', width: 120, valueFormatter: ({ value }) => value?.slice(0, 10) ?? '—' },
    { field: 'depends_on_title', headerName: 'Depends On', flex: 1, valueFormatter: ({ value }) => value ?? '—' },
    {
      field: 'actions', headerName: '', width: 90, sortable: false,
      renderCell: ({ row }) => (
        <Box onClick={(e) => e.stopPropagation()}>
          {canEdit() && <IconButton size="small" onClick={() => { setEditing(row); setFormOpen(true); }}><EditIcon fontSize="small" /></IconButton>}
          {canDelete() && <IconButton size="small" color="error" onClick={() => setDeleteTarget(row)}><DeleteIcon fontSize="small" /></IconButton>}
        </Box>
      ),
    },
  ];

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5" fontWeight="bold">Deliverables</Typography>
        {canEdit() && selectedProject && (
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => { setEditing(null); setFormOpen(true); }}>
            Add Deliverable
          </Button>
        )}
      </Box>

      <Box sx={{ mb: 2 }}>
        <TextField
          select
          size="small"
          label="Project"
          value={selectedProject}
          onChange={(e) => setSelectedProject(e.target.value)}
          sx={{ minWidth: 280 }}
        >
          <MenuItem value="">Select a project…</MenuItem>
          {projects.map((p) => <MenuItem key={p.id} value={p.id}>{p.title}</MenuItem>)}
        </TextField>
      </Box>

      {error && <ErrorAlert message={error} onRetry={fetchDeliverables} />}

      {!selectedProject ? (
        <Typography color="text.secondary">Select a project to view its deliverables.</Typography>
      ) : (
        <DataGrid
          rows={rows}
          columns={columns}
          loading={loading}
          autoHeight
          pageSize={20}
          rowsPerPageOptions={[20, 50]}
          disableSelectionOnClick
          sx={{ bgcolor: 'white' }}
        />
      )}

      <DeliverableFormDialog
        open={formOpen}
        deliverable={editing}
        siblings={rows}
        projectId={selectedProject}
        onSave={handleSave}
        onClose={() => { setFormOpen(false); setEditing(null); }}
        saving={saving}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete Deliverable"
        message={`Delete "${deleteTarget?.title}"?`}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
        loading={deleting}
      />
    </Box>
  );
}

export default DeliverablesPage;
