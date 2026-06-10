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
import InputAdornment from '@mui/material/InputAdornment';
import TableRow from '@mui/material/TableRow';
import TableCell from '@mui/material/TableCell';
import { DataGrid } from '@mui/x-data-grid';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';

import { budgetsApi, projectsApi } from '../services/api.js';
import { useAuth } from '../contexts/AuthContext.jsx';
import ConfirmDialog from '../components/ConfirmDialog.jsx';
import ErrorAlert from '../components/ErrorAlert.jsx';
import StaffBudgetSection from '../components/StaffBudgetSection.jsx';
import { useColorMode } from '../contexts/ColorModeContext.jsx';

const CATEGORIES = ['staff', 'tooling', 'infrastructure', 'travel', 'other'];
const EMPTY_FORM = { category: 'other', description: '', amount_planned: '', amount_consumed: '' };
const DRAFT_KEY = 'budgets:newDraft';

function parseMoney(input) {
  const cleaned = String(input).replace(/[^\d.]/g, '');
  const parts = cleaned.split('.');
  return parts.length > 1 ? `${parts[0]}.${parts.slice(1).join('')}` : parts[0];
}

function formatMoney(value) {
  if (value === '' || value == null) return '';
  const [int, dec] = String(value).split('.');
  const withCommas = Number(int || 0).toLocaleString('en-US');
  return dec !== undefined ? `${withCommas}.${dec}` : withCommas;
}

/**
 * Budget item create/edit dialog.
 */
function BudgetFormDialog({ open, item, projectId, onSave, onClose, saving, saveError }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (item) {
      setForm({
        category: item.category || 'other',
        description: item.description || '',
        amount_planned: item.amount_planned ?? '',
        amount_consumed: item.amount_consumed ?? '',
      });
    } else if (open) {
      const saved = localStorage.getItem(DRAFT_KEY);
      if (saved) { try { setForm({ ...EMPTY_FORM, ...JSON.parse(saved) }); } catch { setForm(EMPTY_FORM); } }
      else setForm(EMPTY_FORM);
    } else {
      setForm(EMPTY_FORM);
    }
    setErrors({});
  }, [item, open]);

  useEffect(() => {
    if (open && !item) localStorage.setItem(DRAFT_KEY, JSON.stringify(form));
  }, [form, open, item]);

  const handleClear = () => {
    setForm(EMPTY_FORM);
    localStorage.removeItem(DRAFT_KEY);
    setErrors({});
  };

  const handleSubmit = () => {
    if (!form.category) { setErrors({ category: 'Missing required field' }); return; }
    onSave({ ...form, project_id: projectId });
  };

  const set = (field) => (ev) => setForm((f) => ({ ...f, [field]: ev.target.value }));

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{item ? 'Edit Budget Item' : 'New Budget Item'}</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 3 }}>
        {saveError && (
          <Box sx={{ bgcolor: 'error.light', color: 'error.contrastText', p: 1.5, borderRadius: 1, fontSize: 14 }}>
            {saveError}
          </Box>
        )}
        <TextField select label="Category *" value={form.category} onChange={set('category')} error={!!errors.category} helperText={errors.category} fullWidth sx={{ mt: 1 }}>
          {CATEGORIES.map((c) => <MenuItem key={c} value={c} sx={{ textTransform: 'capitalize' }}>{c}</MenuItem>)}
        </TextField>
        <TextField label="Description" value={form.description} onChange={set('description')} multiline rows={2} fullWidth />
        <TextField
          label="Amount Planned"
          value={formatMoney(form.amount_planned)}
          onChange={(e) => setForm((f) => ({ ...f, amount_planned: parseMoney(e.target.value) }))}
          fullWidth
          inputProps={{ inputMode: 'decimal' }}
          InputProps={{ startAdornment: <InputAdornment position="start">$</InputAdornment> }}
        />
        <TextField
          label="Amount Consumed"
          value={formatMoney(form.amount_consumed)}
          onChange={(e) => setForm((f) => ({ ...f, amount_consumed: parseMoney(e.target.value) }))}
          fullWidth
          inputProps={{ inputMode: 'decimal' }}
          InputProps={{ startAdornment: <InputAdornment position="start">$</InputAdornment> }}
        />
      </DialogContent>
      <DialogActions>
        {!item && <Button onClick={handleClear} disabled={saving} color="inherit">Clear</Button>}
        <Box sx={{ flexGrow: 1 }} />
        <Button onClick={onClose} disabled={saving}>Cancel</Button>
        <Button onClick={handleSubmit} variant="contained" disabled={saving}>{saving ? 'Saving…' : 'Save'}</Button>
      </DialogActions>
    </Dialog>
  );
}

BudgetFormDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  item: PropTypes.object,
  projectId: PropTypes.string,
  onSave: PropTypes.func.isRequired,
  onClose: PropTypes.func.isRequired,
  saving: PropTypes.bool.isRequired,
  saveError: PropTypes.string,
};
BudgetFormDialog.defaultProps = { item: null, projectId: null, saveError: '' };

/**
 * Budgets page — per-project budget item tracking with planned vs consumed.
 */
function BudgetsPage() {
  const { canEdit, canDelete } = useAuth();
  const { mode } = useColorMode();
  const isDark = mode === 'dark';
  const [rows, setRows] = useState([]);
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(() => localStorage.getItem('budgets:selectedProject') || '');
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

  const fetchBudgets = useCallback(async () => {
    if (!selectedProject) { setRows([]); return; }
    setLoading(true);
    setError('');
    try {
      const result = await budgetsApi.getAll({ project_id: selectedProject });
      setRows(result?.data ?? result ?? []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [selectedProject]);

  useEffect(() => { fetchProjects(); }, [fetchProjects]);
  useEffect(() => { fetchBudgets(); }, [fetchBudgets]);

  const handleSave = async (form) => {
    setSaving(true);
    setSaveError('');
    try {
      const payload = { ...form };
      ['amount_planned', 'amount_consumed', 'description'].forEach((k) => {
        if (payload[k] === '' || payload[k] == null) delete payload[k];
      });
      if (editing) await budgetsApi.update(editing.id, payload);
      else { await budgetsApi.create(payload); localStorage.removeItem(DRAFT_KEY); }
      setFormOpen(false);
      setEditing(null);
      await fetchBudgets();
    } catch (err) {
      setSaveError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await budgetsApi.remove(deleteTarget.id);
      setDeleteTarget(null);
      await fetchBudgets();
    } catch (err) {
      setError(err.message);
    } finally {
      setDeleting(false);
    }
  };

  const totalPlanned = rows.reduce((s, r) => s + Number(r.amount_planned || 0), 0);
  const totalConsumed = rows.reduce((s, r) => s + Number(r.amount_consumed || 0), 0);

  const columns = [
    { field: 'category', headerName: 'Category', width: 120, renderCell: ({ value }) => <span style={{ textTransform: 'capitalize' }}>{value}</span> },
    { field: 'description', headerName: 'Description', flex: 1 },
    { field: 'amount_planned', headerName: 'Planned', width: 120, valueFormatter: (value) => `$${Number(value || 0).toLocaleString()}` },
    { field: 'amount_consumed', headerName: 'Consumed', width: 120, valueFormatter: (value) => `$${Number(value || 0).toLocaleString()}` },
    {
      field: 'pct',
      headerName: '% Used',
      width: 160,
      renderCell: ({ row }) => {
        const planned = Number(row.amount_planned || 0);
        const consumed = Number(row.amount_consumed || 0);
        const pct = planned > 0 ? Math.round((consumed / planned) * 100) : 0;
        return (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
            <LinearProgress
              variant="determinate"
              value={Math.min(pct, 100)}
              color={pct > 95 ? 'error' : pct >= 70 ? 'warning' : 'primary'}
              sx={{ flexGrow: 1, height: 8, borderRadius: 4 }}
            />
            <Typography variant="caption">{pct}%</Typography>
          </Box>
        );
      },
    },
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
        <Typography variant="h5" fontWeight="bold">Budgets</Typography>
        {canEdit() && selectedProject && (
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => { setEditing(null); setFormOpen(true); }}>
            Add Budget Item
          </Button>
        )}
      </Box>

      <Box sx={{ mb: 2 }}>
        <TextField
          select
          size="small"
          label="Project"
          value={selectedProject}
          onChange={(e) => { setSelectedProject(e.target.value); localStorage.setItem('budgets:selectedProject', e.target.value); }}
          sx={{ minWidth: 280 }}
        >
          <MenuItem value="">Select a project…</MenuItem>
          {projects.map((p) => <MenuItem key={p.id} value={p.id}>{p.title}</MenuItem>)}
        </TextField>
      </Box>

      {selectedProject && rows.length > 0 && (
        <Box sx={{ display: 'flex', gap: 4, mb: 2, p: 2, bgcolor: isDark ? '#1e1e22' : 'action.hover', color: isDark ? '#fff' : 'inherit', borderRadius: 1 }}>
          <Box>
            <Typography variant="caption" sx={{ color: isDark ? 'rgba(255,255,255,0.7)' : 'text.secondary' }}>Total Planned</Typography>
            <Typography fontWeight="bold" sx={{ color: isDark ? '#fff' : 'text.primary' }}>${totalPlanned.toLocaleString()}</Typography>
          </Box>
          <Box>
            <Typography variant="caption" sx={{ color: isDark ? 'rgba(255,255,255,0.7)' : 'text.secondary' }}>Total Consumed</Typography>
            <Typography fontWeight="bold" sx={{ color: totalConsumed > totalPlanned ? 'error.main' : (isDark ? '#fff' : 'text.primary') }}>
              ${totalConsumed.toLocaleString()}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" sx={{ color: isDark ? 'rgba(255,255,255,0.7)' : 'text.secondary' }}>Variance</Typography>
            <Typography fontWeight="bold" sx={{ color: isDark ? '#fff' : 'text.primary' }}>${(totalPlanned - totalConsumed).toLocaleString()}</Typography>
          </Box>
        </Box>
      )}

      {error && <ErrorAlert message={error} onRetry={fetchBudgets} />}

      {selectedProject && (
        <Box sx={{ mb: 2 }}>
          <StaffBudgetSection projectId={selectedProject} />
        </Box>
      )}

      {!selectedProject ? (
        <Typography color="text.secondary">Select a project to view its budget.</Typography>
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

      <BudgetFormDialog
        open={formOpen}
        item={editing}
        projectId={selectedProject}
        onSave={handleSave}
        onClose={() => { setFormOpen(false); setEditing(null); setSaveError(''); }}
        saving={saving}
        saveError={saveError}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete Budget Item"
        message={`Delete this ${deleteTarget?.category} budget item?`}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
        loading={deleting}
      />
    </Box>
  );
}

export default BudgetsPage;
