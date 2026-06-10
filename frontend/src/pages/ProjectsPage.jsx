import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
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
import LinearProgress from '@mui/material/LinearProgress';
import InputAdornment from '@mui/material/InputAdornment';
import { DataGrid } from '@mui/x-data-grid';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import IconButton from '@mui/material/IconButton';

import { projectsApi } from '../services/api.js';
import { useAuth } from '../contexts/AuthContext.jsx';
import HealthChip from '../components/HealthChip.jsx';
import StatusChip from '../components/StatusChip.jsx';
import ConfirmDialog from '../components/ConfirmDialog.jsx';
import ErrorAlert from '../components/ErrorAlert.jsx';

const STATUS_OPTIONS = ['active', 'inactive', 'completed', 'on_hold', 'cancelled'];
const HEALTH_OPTIONS = ['green', 'amber', 'red'];

// Strip non-numeric input (keeps one decimal point) so the stored value is always a clean numeric string.
function parseMoney(input) {
  const cleaned = String(input).replace(/[^\d.]/g, '');
  const parts = cleaned.split('.');
  return parts.length > 1 ? `${parts[0]}.${parts.slice(1).join('')}` : parts[0];
}

// Render with thousands separators; preserves a trailing "." or partial decimals while typing.
function formatMoney(value) {
  if (value === '' || value == null) return '';
  const [int, dec] = String(value).split('.');
  const withCommas = Number(int || 0).toLocaleString('en-US');
  return dec !== undefined ? `${withCommas}.${dec}` : withCommas;
}

const EMPTY_FORM = {
  title: '',
  description: '',
  status: 'active',
  health: 'green',
  start_date: '',
  end_date: '',
  budget_planned: '',
  budget_consumed: '',
  dependency_ids: [],
};
const DRAFT_KEY = 'projects:newDraft';

/**
 * Project create/edit form dialog.
 */
function ProjectFormDialog({ open, project, allProjects, onSave, onClose, saving, saveError, form, setForm }) {
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (open && project) {
      setForm({
        title: project.title || '',
        description: project.description || '',
        status: project.status || 'active',
        health: project.health || 'green',
        start_date: project.start_date?.slice(0, 10) || '',
        end_date: project.end_date?.slice(0, 10) || '',
        budget_planned: project.budget_planned ?? '',
        budget_consumed: project.budget_consumed ?? '',
        dependency_ids: project.dependency_ids || [],
      });
    } else if (open && !project) {
      const saved = localStorage.getItem(DRAFT_KEY);
      if (saved) { try { setForm({ ...EMPTY_FORM, ...JSON.parse(saved) }); } catch { setForm(EMPTY_FORM); } }
      else setForm(EMPTY_FORM);
    }
    if (open) setErrors({});
  }, [project, open, setForm]);

  useEffect(() => {
    if (open && !project) localStorage.setItem(DRAFT_KEY, JSON.stringify(form));
  }, [form, open, project]);

  const validate = () => {
    const e = {};
    if (!form.title.trim()) e.title = 'Missing required field';
    return e;
  };

  const handleSubmit = () => {
    const e = validate();
    if (Object.keys(e).length) { setErrors(e); return; }
    onSave(form);
  };

  const handleClear = () => {
    setForm(EMPTY_FORM);
    localStorage.removeItem(DRAFT_KEY);
    setErrors({});
  };

  const set = (field) => (ev) => setForm((f) => ({ ...f, [field]: ev.target.value }));

  const depOptions = allProjects.filter((p) => p.id !== project?.id);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{project ? 'Edit Project' : 'New Project'}</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 3 }}>
        {saveError && (
          <Box sx={{ bgcolor: 'error.light', color: 'error.contrastText', p: 1.5, borderRadius: 1, fontSize: 14 }}>
            {saveError}
          </Box>
        )}
        <TextField
          label="Title *"
          value={form.title}
          onChange={set('title')}
          error={!!errors.title}
          helperText={errors.title}
          fullWidth
        />
        <TextField
          label="Description"
          value={form.description}
          onChange={set('description')}
          multiline
          rows={3}
          fullWidth
        />
        <Box sx={{ display: 'flex', gap: 2 }}>
          <TextField select label="Status" value={form.status} onChange={set('status')} fullWidth>
            {STATUS_OPTIONS.map((s) => (
              <MenuItem key={s} value={s} sx={{ textTransform: 'capitalize' }}>
                {s.replace('_', ' ')}
              </MenuItem>
            ))}
          </TextField>
          <TextField select label="Health" value={form.health} onChange={set('health')} fullWidth>
            {HEALTH_OPTIONS.map((h) => (
              <MenuItem key={h} value={h} sx={{ textTransform: 'capitalize' }}>
                {h}
              </MenuItem>
            ))}
          </TextField>
        </Box>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <TextField
            label="Start Date"
            type="date"
            value={form.start_date}
            onChange={set('start_date')}
            fullWidth
            InputLabelProps={{ shrink: true }}
          />
          <TextField
            label="End Date"
            type="date"
            value={form.end_date}
            onChange={set('end_date')}
            fullWidth
            InputLabelProps={{ shrink: true }}
          />
        </Box>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <TextField
            label="Budget Planned"
            value={formatMoney(form.budget_planned)}
            onChange={(e) => setForm((f) => ({ ...f, budget_planned: parseMoney(e.target.value) }))}
            fullWidth
            inputProps={{ inputMode: 'decimal' }}
            InputProps={{ startAdornment: <InputAdornment position="start">$</InputAdornment> }}
          />
          <TextField
            label="Budget Consumed"
            value={formatMoney(form.budget_consumed)}
            onChange={(e) => setForm((f) => ({ ...f, budget_consumed: parseMoney(e.target.value) }))}
            fullWidth
            inputProps={{ inputMode: 'decimal' }}
            InputProps={{ startAdornment: <InputAdornment position="start">$</InputAdornment> }}
          />
        </Box>
        <TextField
          select
          label="Dependencies"
          value={form.dependency_ids}
          onChange={(e) => setForm((f) => ({ ...f, dependency_ids: e.target.value }))}
          fullWidth
          SelectProps={{ multiple: true }}
          helperText="Projects this project depends on"
        >
          {depOptions.map((p) => (
            <MenuItem key={p.id} value={p.id}>
              {p.title}
            </MenuItem>
          ))}
        </TextField>
      </DialogContent>
      <DialogActions>
        {!project && <Button onClick={handleClear} disabled={saving} color="inherit">Clear</Button>}
        <Box sx={{ flexGrow: 1 }} />
        <Button onClick={onClose} disabled={saving}>Cancel</Button>
        <Button onClick={handleSubmit} variant="contained" disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

ProjectFormDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  project: PropTypes.object,
  allProjects: PropTypes.array.isRequired,
  onSave: PropTypes.func.isRequired,
  onClose: PropTypes.func.isRequired,
  saving: PropTypes.bool.isRequired,
  saveError: PropTypes.string,
  form: PropTypes.object.isRequired,
  setForm: PropTypes.func.isRequired,
};
ProjectFormDialog.defaultProps = { project: null, saveError: '' };

/**
 * Projects list page with DataGrid, filters, and CRUD dialogs.
 */
function ProjectsPage() {
  const navigate = useNavigate();
  const { canEdit, canDelete } = useAuth();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [healthFilter, setHealthFilter] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saveError, setSaveError] = useState('');

  const fetchProjects = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const result = await projectsApi.getAll();
      setRows(result?.data ?? result ?? []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchProjects(); }, [fetchProjects]);

  const filtered = rows.filter((r) => {
    if (search && !r.title.toLowerCase().includes(search.toLowerCase())) return false;
    if (statusFilter && r.status !== statusFilter) return false;
    if (healthFilter && r.health !== healthFilter) return false;
    return true;
  });

  const handleSave = async (data) => {
    setSaving(true);
    setSaveError('');
    try {
      const payload = { ...data };
      // Backend rejects "" for date/money fields — strip empties so they're treated as unset.
      ['start_date', 'end_date', 'budget_planned', 'budget_consumed'].forEach((k) => {
        if (payload[k] === '' || payload[k] == null) delete payload[k];
      });
      if (editing) {
        await projectsApi.update(editing.id, payload);
      } else {
        await projectsApi.create(payload);
        localStorage.removeItem(DRAFT_KEY);
      }
      setFormOpen(false);
      setEditing(null);
      setForm(EMPTY_FORM);
      await fetchProjects();
    } catch (err) {
      setSaveError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await projectsApi.remove(deleteTarget.id);
      setDeleteTarget(null);
      await fetchProjects();
    } catch (err) {
      setError(err.message);
    } finally {
      setDeleting(false);
    }
  };

  const columns = [
    { field: 'title', headerName: 'Title', flex: 1, minWidth: 160 },
    {
      field: 'status',
      headerName: 'Status',
      width: 130,
      renderCell: ({ value }) => <StatusChip status={value} />,
    },
    {
      field: 'health',
      headerName: 'Health',
      width: 110,
      renderCell: ({ value, row }) => <HealthChip health={value} reason={row.health_reason} />,
    },
    {
      field: 'start_date',
      headerName: 'Start',
      width: 110,
      valueFormatter: (value) => value?.slice(0, 10) ?? '—',
    },
    {
      field: 'end_date',
      headerName: 'End',
      width: 110,
      valueFormatter: (value) => value?.slice(0, 10) ?? '—',
    },
    {
      field: 'budget_planned',
      headerName: 'Budget',
      width: 120,
      valueFormatter: (value) =>
        value != null ? `$${Number(value).toLocaleString()}` : '—',
    },
    {
      field: 'budget_pct',
      headerName: 'Used',
      width: 140,
      renderCell: ({ row }) => {
        const pct =
          row.budget_planned > 0
            ? Math.round((row.budget_consumed / row.budget_planned) * 100)
            : 0;
        return (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
            <LinearProgress
              variant="determinate"
              value={Math.min(pct, 100)}
              color={pct > 95 ? 'error' : pct >= 70 ? 'warning' : 'primary'}
              sx={{ flexGrow: 1, height: 8, borderRadius: 4 }}
            />
            <Typography variant="caption" sx={{ minWidth: 32 }}>
              {pct}%
            </Typography>
          </Box>
        );
      },
    },
    {
      field: 'actions',
      headerName: '',
      width: 90,
      sortable: false,
      renderCell: ({ row }) => (
        <Box onClick={(e) => e.stopPropagation()}>
          {canEdit() && (
            <IconButton
              size="small"
              onClick={() => { setEditing(row); setFormOpen(true); }}
            >
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
        <Typography variant="h5" fontWeight="bold">
          Projects
        </Typography>
        {canEdit() && (
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => { setEditing(null); setFormOpen(true); }}
          >
            New Project
          </Button>
        )}
      </Box>

      <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <TextField
          size="small"
          label="Search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          sx={{ minWidth: 200 }}
        />
        <TextField
          select
          size="small"
          label="Status"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          sx={{ minWidth: 140 }}
        >
          <MenuItem value="">All Statuses</MenuItem>
          {STATUS_OPTIONS.map((s) => (
            <MenuItem key={s} value={s} sx={{ textTransform: 'capitalize' }}>
              {s.replace('_', ' ')}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          size="small"
          label="Health"
          value={healthFilter}
          onChange={(e) => setHealthFilter(e.target.value)}
          sx={{ minWidth: 120 }}
        >
          <MenuItem value="">All Health</MenuItem>
          {HEALTH_OPTIONS.map((h) => (
            <MenuItem key={h} value={h} sx={{ textTransform: 'capitalize' }}>
              {h}
            </MenuItem>
          ))}
        </TextField>
      </Box>

      {error && <ErrorAlert message={error} onRetry={fetchProjects} />}

      <DataGrid
        rows={filtered}
        columns={columns}
        loading={loading}
        autoHeight
        pageSize={20}
        rowsPerPageOptions={[20, 50]}
        disableSelectionOnClick
        onRowClick={({ row }) => navigate(`/projects/${row.id}`)}
        sx={{ bgcolor: 'background.paper', cursor: 'pointer' }}
      />

      <ProjectFormDialog
        open={formOpen}
        project={editing}
        allProjects={rows}
        onSave={handleSave}
        onClose={() => { setFormOpen(false); setEditing(null); setSaveError(''); }}
        saving={saving}
        saveError={saveError}
        form={form}
        setForm={setForm}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete Project"
        message={`Delete "${deleteTarget?.title}"? This cannot be undone.`}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
        loading={deleting}
      />
    </Box>
  );
}

export default ProjectsPage;
