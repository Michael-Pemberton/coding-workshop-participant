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
import LinearProgress from '@mui/material/LinearProgress';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import InputAdornment from '@mui/material/InputAdornment';
import { DataGrid } from '@mui/x-data-grid';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';

import { peopleApi, projectsApi, assignmentsApi } from '../services/api.js';
import { useAuth } from '../contexts/AuthContext.jsx';
import ConfirmDialog from '../components/ConfirmDialog.jsx';
import ErrorAlert from '../components/ErrorAlert.jsx';

const EMPTY_FORM = { name: '', email: '', title: '', weekly_hours_capacity: 40, hourly_pay: '' };
const EMPTY_NEW_ASSIGN = { project_id: '', role_on_project: '', hours_per_week: 0 };
const DRAFT_KEY = 'people:newDraft';

/**
 * Person create/edit form dialog. Edits person details + project assignments.
 */
function PersonFormDialog({ open, person, projects, onSave, onClose, saving, saveError }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [errors, setErrors] = useState({});
  // Existing assignments fetched from server (edit mode). Local-only until save.
  const [initialAssignments, setInitialAssignments] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [newAssign, setNewAssign] = useState(EMPTY_NEW_ASSIGN);

  useEffect(() => {
    if (!open) return;
    if (person) {
      setForm({
        name: person.name || '',
        email: person.email || '',
        title: person.title || '',
        weekly_hours_capacity: person.weekly_hours_capacity ?? 40,
        hourly_pay: person.hourly_pay ?? '',
      });
      assignmentsApi.getAll({ person_id: person.id }).then((res) => {
        const list = res?.data ?? res ?? [];
        setInitialAssignments(list);
        setAssignments(list);
      }).catch(() => { setInitialAssignments([]); setAssignments([]); });
    } else {
      const saved = localStorage.getItem(DRAFT_KEY);
      if (saved) { try { setForm({ ...EMPTY_FORM, ...JSON.parse(saved) }); } catch { setForm(EMPTY_FORM); } }
      else setForm(EMPTY_FORM);
      setInitialAssignments([]);
      setAssignments([]);
    }
    setNewAssign(EMPTY_NEW_ASSIGN);
    setErrors({});
  }, [person, open]);

  useEffect(() => {
    if (open && !person) localStorage.setItem(DRAFT_KEY, JSON.stringify(form));
  }, [form, open, person]);

  const handleClear = () => {
    setForm(EMPTY_FORM);
    setAssignments([]);
    setNewAssign(EMPTY_NEW_ASSIGN);
    localStorage.removeItem(DRAFT_KEY);
    setErrors({});
  };

  const validate = () => {
    const e = {};
    if (!form.name.trim()) e.name = 'Missing required field';
    if (!form.email.trim()) e.email = 'Missing required field';
    else if (!/\S+@\S+\.\S+/.test(form.email)) e.email = 'Invalid email address';
    if (form.hourly_pay !== '' && form.hourly_pay != null) {
      const n = Number(form.hourly_pay);
      if (Number.isNaN(n) || n < 0) e.hourly_pay = 'Must be a non-negative number';
    }
    return e;
  };

  const handleAddAssignment = () => {
    if (!newAssign.project_id) return;
    if (assignments.some((a) => a.project_id === newAssign.project_id)) return;
    setAssignments((prev) => [
      ...prev,
      { _new: true, _tempId: `tmp-${Date.now()}`, ...newAssign, hours_per_week: Number(newAssign.hours_per_week) || 0 },
    ]);
    setNewAssign(EMPTY_NEW_ASSIGN);
  };

  const handleRemoveAssignment = (key) => {
    setAssignments((prev) => prev.filter((a) => (a.id ?? a._tempId) !== key));
  };

  const handleUpdateAssignment = (key, patch) => {
    setAssignments((prev) => prev.map((a) =>
      (a.id ?? a._tempId) === key ? { ...a, ...patch } : a,
    ));
  };

  const handleSubmit = () => {
    const e = validate();
    if (Object.keys(e).length) { setErrors(e); return; }
    const payload = { ...form };
    if (payload.hourly_pay === '' || payload.hourly_pay == null) delete payload.hourly_pay;
    onSave(payload, { initialAssignments, assignments });
  };

  const set = (field) => (ev) => setForm((f) => ({ ...f, [field]: ev.target.value }));

  const assignedIds = new Set(assignments.map((a) => a.project_id));
  const availableProjects = projects.filter((p) => !assignedIds.has(p.id));
  const projectTitle = (id) => projects.find((p) => p.id === id)?.title ?? id;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{person ? 'Edit Person' : 'New Person'}</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 3 }}>
        {saveError && (
          <Box sx={{ bgcolor: 'error.light', color: 'error.contrastText', p: 1.5, borderRadius: 1, fontSize: 14 }}>
            {saveError}
          </Box>
        )}
        <TextField label="Name *" value={form.name} onChange={set('name')} error={!!errors.name} helperText={errors.name} fullWidth />
        <TextField label="Email *" type="email" value={form.email} onChange={set('email')} error={!!errors.email} helperText={errors.email} fullWidth />
        <TextField label="Job Title" value={form.title} onChange={set('title')} fullWidth />
        <Box sx={{ display: 'flex', gap: 2 }}>
          <TextField
            label="Weekly Hours Capacity"
            type="number"
            value={form.weekly_hours_capacity}
            onChange={set('weekly_hours_capacity')}
            fullWidth
            inputProps={{ min: 1, max: 168 }}
          />
          <TextField
            label="Hourly Pay"
            type="number"
            value={form.hourly_pay}
            onChange={set('hourly_pay')}
            error={!!errors.hourly_pay}
            helperText={errors.hourly_pay}
            fullWidth
            inputProps={{ min: 0, step: '0.01' }}
            InputProps={{ startAdornment: <InputAdornment position="start">$</InputAdornment> }}
          />
        </Box>

        <Divider sx={{ my: 1 }}>
          <Typography variant="caption" color="text.secondary">Project Assignments</Typography>
        </Divider>

        {assignments.length === 0 && (
          <Typography variant="body2" color="text.secondary">No projects assigned.</Typography>
        )}
        {assignments.map((a) => {
          const key = a.id ?? a._tempId;
          return (
            <Box key={key} sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
              <Typography sx={{ flex: 1, fontSize: 14 }}>{projectTitle(a.project_id)}</Typography>
              <TextField
                size="small"
                label="Role"
                value={a.role_on_project ?? ''}
                onChange={(e) => handleUpdateAssignment(key, { role_on_project: e.target.value })}
                sx={{ width: 140 }}
              />
              <TextField
                size="small"
                label="h/wk"
                type="number"
                value={a.hours_per_week ?? 0}
                onChange={(e) => handleUpdateAssignment(key, { hours_per_week: Number(e.target.value) || 0 })}
                sx={{ width: 90 }}
                inputProps={{ min: 0, max: 168 }}
              />
              <IconButton size="small" color="error" onClick={() => handleRemoveAssignment(key)}>
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Box>
          );
        })}

        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mt: 1 }}>
          <TextField
            select
            size="small"
            label="Add Project"
            value={newAssign.project_id}
            onChange={(e) => setNewAssign((n) => ({ ...n, project_id: e.target.value }))}
            sx={{ flex: 1 }}
          >
            <MenuItem value="">Select…</MenuItem>
            {availableProjects.map((p) => <MenuItem key={p.id} value={p.id}>{p.title}</MenuItem>)}
          </TextField>
          <TextField
            size="small"
            label="Role"
            value={newAssign.role_on_project}
            onChange={(e) => setNewAssign((n) => ({ ...n, role_on_project: e.target.value }))}
            sx={{ width: 140 }}
          />
          <TextField
            size="small"
            label="h/wk"
            type="number"
            value={newAssign.hours_per_week}
            onChange={(e) => setNewAssign((n) => ({ ...n, hours_per_week: e.target.value }))}
            sx={{ width: 90 }}
            inputProps={{ min: 0, max: 168 }}
          />
          <IconButton size="small" color="primary" onClick={handleAddAssignment} disabled={!newAssign.project_id}>
            <AddIcon />
          </IconButton>
        </Box>
      </DialogContent>
      <DialogActions>
        {!person && <Button onClick={handleClear} disabled={saving} color="inherit">Clear</Button>}
        <Box sx={{ flexGrow: 1 }} />
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
  projects: PropTypes.array.isRequired,
  onSave: PropTypes.func.isRequired,
  onClose: PropTypes.func.isRequired,
  saving: PropTypes.bool.isRequired,
  saveError: PropTypes.string,
};
PersonFormDialog.defaultProps = { person: null, saveError: '' };

/**
 * Diffs initial vs current assignments and applies create/update/delete calls.
 */
async function syncAssignments(personId, initial, current) {
  const initialById = new Map(initial.map((a) => [a.id, a]));
  const currentIds = new Set(current.filter((a) => a.id).map((a) => a.id));

  // Deletes
  for (const a of initial) {
    if (!currentIds.has(a.id)) await assignmentsApi.remove(a.id);
  }
  // Creates + updates
  for (const a of current) {
    const payload = {
      person_id: personId,
      project_id: a.project_id,
      role_on_project: a.role_on_project || null,
      hours_per_week: Number(a.hours_per_week) || 0,
    };
    if (a._new || !a.id) {
      await assignmentsApi.create(payload);
    } else {
      const orig = initialById.get(a.id);
      const changed = !orig
        || orig.role_on_project !== a.role_on_project
        || Number(orig.hours_per_week) !== Number(a.hours_per_week);
      if (changed) {
        await assignmentsApi.update(a.id, {
          role_on_project: payload.role_on_project,
          hours_per_week: payload.hours_per_week,
        });
      }
    }
  }
}

/**
 * People list page with allocation tracking and CRUD operations.
 */
function PeoplePage() {
  const { canEdit, canDelete } = useAuth();
  const [rows, setRows] = useState([]);
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [saveError, setSaveError] = useState('');

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

  const fetchProjects = useCallback(async () => {
    try {
      const result = await projectsApi.getAll();
      setProjects(result?.data ?? result ?? []);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => { fetchPeople(); fetchProjects(); }, [fetchPeople, fetchProjects]);

  const filtered = rows.filter((r) =>
    !search ||
    r.name?.toLowerCase().includes(search.toLowerCase()) ||
    r.email?.toLowerCase().includes(search.toLowerCase()),
  );

  const handleSave = async (form, { initialAssignments, assignments }) => {
    setSaving(true);
    setSaveError('');
    try {
      let personId;
      if (editing) {
        await peopleApi.update(editing.id, form);
        personId = editing.id;
      } else {
        const created = await peopleApi.create(form);
        personId = (created?.data ?? created)?.id;
        localStorage.removeItem(DRAFT_KEY);
      }
      if (personId) await syncAssignments(personId, initialAssignments, assignments);
      setFormOpen(false);
      setEditing(null);
      await fetchPeople();
    } catch (err) {
      setSaveError(err.message);
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
      field: 'hourly_pay',
      headerName: 'Pay',
      width: 100,
      valueFormatter: (value) => (value != null && value !== '' ? `$${Number(value).toFixed(2)}` : '—'),
    },
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
        sx={{ bgcolor: 'background.paper' }}
      />

      <PersonFormDialog
        open={formOpen}
        person={editing}
        projects={projects}
        onSave={handleSave}
        onClose={() => { setFormOpen(false); setEditing(null); setSaveError(''); }}
        saving={saving}
        saveError={saveError}
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
