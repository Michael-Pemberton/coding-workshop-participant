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
import HealthChip from '../components/HealthChip.jsx';
import ConfirmDialog from '../components/ConfirmDialog.jsx';
import ErrorAlert from '../components/ErrorAlert.jsx';
import { timeLeft } from '../utils/dueDate.js';

const EMPTY_FORM = { title: '', description: '', due_date: '', depends_on_id: '' };
const DRAFT_KEY_PREFIX = 'deliverables:newDraft:';

/**
 * Deliverable create/edit dialog.
 */
function DeliverableFormDialog({ open, deliverable, projects, projectId, onSave, onClose, saving, saveError }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [depProjectId, setDepProjectId] = useState(projectId || '');
  const [depOptions, setDepOptions] = useState([]);
  const [errors, setErrors] = useState({});

  const draftKey = DRAFT_KEY_PREFIX + (projectId || 'none');

  // When opening: load form, then if there's an existing depends_on_id, look up which project it belongs to.
  useEffect(() => {
    if (!open) { setForm(EMPTY_FORM); return; }
    if (deliverable) {
      setForm({
        title: deliverable.title || '',
        description: deliverable.description || '',
        due_date: deliverable.due_date?.slice(0, 10) || '',
        depends_on_id: deliverable.depends_on_id || '',
      });
      if (deliverable.depends_on_id) {
        deliverablesApi.getById(deliverable.depends_on_id)
          .then((r) => setDepProjectId((r?.data ?? r)?.project_id || projectId || ''))
          .catch(() => setDepProjectId(projectId || ''));
      } else {
        setDepProjectId(projectId || '');
      }
    } else {
      const saved = localStorage.getItem(draftKey);
      if (saved) { try { setForm({ ...EMPTY_FORM, ...JSON.parse(saved) }); } catch { setForm(EMPTY_FORM); } }
      else setForm(EMPTY_FORM);
      setDepProjectId(projectId || '');
    }
    setErrors({});
  }, [deliverable, open, draftKey, projectId]);

  // Load deliverables for the chosen dependency project.
  useEffect(() => {
    if (!open || !depProjectId) { setDepOptions([]); return; }
    let cancelled = false;
    deliverablesApi.getAll({ project_id: depProjectId })
      .then((r) => { if (!cancelled) setDepOptions(r?.data ?? r ?? []); })
      .catch(() => { if (!cancelled) setDepOptions([]); });
    return () => { cancelled = true; };
  }, [depProjectId, open]);

  useEffect(() => {
    if (open && !deliverable) localStorage.setItem(draftKey, JSON.stringify(form));
  }, [form, open, deliverable, draftKey]);

  const handleClear = () => {
    setForm(EMPTY_FORM);
    setDepProjectId(projectId || '');
    localStorage.removeItem(draftKey);
    setErrors({});
  };

  const handleSubmit = () => {
    if (!form.title.trim()) { setErrors({ title: 'Missing required field' }); return; }
    onSave({ ...form, project_id: projectId });
  };

  const set = (field) => (ev) => setForm((f) => ({ ...f, [field]: ev.target.value }));

  const filteredDepOptions = depOptions.filter((s) => s.id !== deliverable?.id);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{deliverable ? 'Edit Deliverable' : 'New Deliverable'}</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 3 }}>
        {saveError && (
          <Box sx={{ bgcolor: 'error.light', color: 'error.contrastText', p: 1.5, borderRadius: 1, fontSize: 14 }}>
            {saveError}
          </Box>
        )}
        <TextField label="Title *" value={form.title} onChange={set('title')} error={!!errors.title} helperText={errors.title} fullWidth />
        <TextField label="Description" value={form.description} onChange={set('description')} multiline rows={2} fullWidth />
        <TextField label="Due Date" type="date" value={form.due_date} onChange={set('due_date')} fullWidth InputLabelProps={{ shrink: true }} helperText="Status is computed: red = overdue, amber = ≤5 days, green = otherwise" />
        <Box sx={{ display: 'flex', gap: 2 }}>
          <TextField
            select label="Dependency Project" value={depProjectId}
            onChange={(e) => { setDepProjectId(e.target.value); setForm((f) => ({ ...f, depends_on_id: '' })); }}
            fullWidth
          >
            {projects.map((p) => <MenuItem key={p.id} value={p.id}>{p.title}</MenuItem>)}
          </TextField>
          <TextField select label="Depends On" value={form.depends_on_id} onChange={set('depends_on_id')} fullWidth disabled={!depProjectId}>
            <MenuItem value="">None</MenuItem>
            {filteredDepOptions.map((d) => <MenuItem key={d.id} value={d.id}>{d.title}</MenuItem>)}
          </TextField>
        </Box>
      </DialogContent>
      <DialogActions>
        {!deliverable && <Button onClick={handleClear} disabled={saving} color="inherit">Clear</Button>}
        <Box sx={{ flexGrow: 1 }} />
        <Button onClick={onClose} disabled={saving}>Cancel</Button>
        <Button onClick={handleSubmit} variant="contained" disabled={saving}>{saving ? 'Saving…' : 'Save'}</Button>
      </DialogActions>
    </Dialog>
  );
}

DeliverableFormDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  deliverable: PropTypes.object,
  projects: PropTypes.array.isRequired,
  projectId: PropTypes.string,
  onSave: PropTypes.func.isRequired,
  onClose: PropTypes.func.isRequired,
  saving: PropTypes.bool.isRequired,
  saveError: PropTypes.string,
};
DeliverableFormDialog.defaultProps = { deliverable: null, projectId: null, saveError: '' };

/**
 * Deliverables page with project filter, DataGrid, and CRUD dialogs.
 */
function DeliverablesPage() {
  const { canEdit, canDelete } = useAuth();
  const [rows, setRows] = useState([]);
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(() => localStorage.getItem('deliverables:selectedProject') || '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [saveError, setSaveError] = useState('');

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
    setSaveError('');
    try {
      const payload = { ...form };
      // Backend rejects "" for date/UUID fields — strip empties so they're treated as unset.
      ['due_date', 'depends_on_id', 'description'].forEach((k) => {
        if (payload[k] === '' || payload[k] == null) delete payload[k];
      });
      if (editing) await deliverablesApi.update(editing.id, payload);
      else { await deliverablesApi.create(payload); localStorage.removeItem(DRAFT_KEY_PREFIX + (selectedProject || 'none')); }
      setFormOpen(false);
      setEditing(null);
      await fetchDeliverables();
    } catch (err) {
      setSaveError(err.message);
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
    { field: 'status', headerName: 'Status', width: 110, renderCell: ({ row }) => <HealthChip health={row.status} reason={row.health_reason} /> },
    { field: 'due_date', headerName: 'Due Date', width: 120, valueFormatter: (value) => value?.slice(0, 10) ?? '—' },
    { field: 'time_left', headerName: 'Time Left', width: 110, valueGetter: (_, row) => timeLeft(row.due_date) },
    { field: 'depends_on_title', headerName: 'Depends On', flex: 1, valueGetter: (_, row) => row.depends_on_title ? `${row.depends_on_title}${row.depends_on_project_title ? ` (${row.depends_on_project_title})` : ''}` : '—' },
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
          onChange={(e) => { setSelectedProject(e.target.value); localStorage.setItem('deliverables:selectedProject', e.target.value); }}
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
          sx={{ bgcolor: 'background.paper' }}
        />
      )}

      <DeliverableFormDialog
        open={formOpen}
        deliverable={editing}
        projects={projects}
        projectId={selectedProject}
        onSave={handleSave}
        onClose={() => { setFormOpen(false); setEditing(null); setSaveError(''); }}
        saving={saving}
        saveError={saveError}
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
