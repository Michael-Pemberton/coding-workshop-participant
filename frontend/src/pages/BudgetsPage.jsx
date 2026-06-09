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

const CATEGORIES = ['labor', 'equipment', 'software', 'travel', 'other'];
const EMPTY_FORM = { category: 'other', description: '', amount_planned: '', amount_consumed: '' };

/**
 * Budget item create/edit dialog.
 */
function BudgetFormDialog({ open, item, projectId, onSave, onClose, saving }) {
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
    } else {
      setForm(EMPTY_FORM);
    }
    setErrors({});
  }, [item, open]);

  const handleSubmit = () => {
    if (!form.category) { setErrors({ category: 'Category is required' }); return; }
    onSave({ ...form, project_id: projectId });
  };

  const set = (field) => (ev) => setForm((f) => ({ ...f, [field]: ev.target.value }));

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{item ? 'Edit Budget Item' : 'New Budget Item'}</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
        <TextField select label="Category *" value={form.category} onChange={set('category')} error={!!errors.category} helperText={errors.category} fullWidth>
          {CATEGORIES.map((c) => <MenuItem key={c} value={c} sx={{ textTransform: 'capitalize' }}>{c}</MenuItem>)}
        </TextField>
        <TextField label="Description" value={form.description} onChange={set('description')} multiline rows={2} fullWidth />
        <TextField
          label="Amount Planned"
          type="number"
          value={form.amount_planned}
          onChange={set('amount_planned')}
          fullWidth
          InputProps={{ startAdornment: <InputAdornment position="start">$</InputAdornment> }}
        />
        <TextField
          label="Amount Consumed"
          type="number"
          value={form.amount_consumed}
          onChange={set('amount_consumed')}
          fullWidth
          InputProps={{ startAdornment: <InputAdornment position="start">$</InputAdornment> }}
        />
      </DialogContent>
      <DialogActions>
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
};
BudgetFormDialog.defaultProps = { item: null, projectId: null };

/**
 * Budgets page — per-project budget item tracking with planned vs consumed.
 */
function BudgetsPage() {
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
    try {
      if (editing) await budgetsApi.update(editing.id, form);
      else await budgetsApi.create(form);
      setFormOpen(false);
      setEditing(null);
      await fetchBudgets();
    } catch (err) {
      setError(err.message);
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
    { field: 'amount_planned', headerName: 'Planned', width: 120, valueFormatter: ({ value }) => `$${Number(value || 0).toLocaleString()}` },
    { field: 'amount_consumed', headerName: 'Consumed', width: 120, valueFormatter: ({ value }) => `$${Number(value || 0).toLocaleString()}` },
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
              color={pct > 100 ? 'error' : pct > 80 ? 'warning' : 'primary'}
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
          onChange={(e) => setSelectedProject(e.target.value)}
          sx={{ minWidth: 280 }}
        >
          <MenuItem value="">Select a project…</MenuItem>
          {projects.map((p) => <MenuItem key={p.id} value={p.id}>{p.title}</MenuItem>)}
        </TextField>
      </Box>

      {selectedProject && rows.length > 0 && (
        <Box sx={{ display: 'flex', gap: 4, mb: 2, p: 2, bgcolor: 'grey.100', borderRadius: 1 }}>
          <Box>
            <Typography variant="caption" color="text.secondary">Total Planned</Typography>
            <Typography fontWeight="bold">${totalPlanned.toLocaleString()}</Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">Total Consumed</Typography>
            <Typography fontWeight="bold" color={totalConsumed > totalPlanned ? 'error.main' : 'text.primary'}>
              ${totalConsumed.toLocaleString()}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">Variance</Typography>
            <Typography fontWeight="bold">${(totalPlanned - totalConsumed).toLocaleString()}</Typography>
          </Box>
        </Box>
      )}

      {error && <ErrorAlert message={error} onRetry={fetchBudgets} />}

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
          sx={{ bgcolor: 'white' }}
        />
      )}

      <BudgetFormDialog
        open={formOpen}
        item={editing}
        projectId={selectedProject}
        onSave={handleSave}
        onClose={() => { setFormOpen(false); setEditing(null); }}
        saving={saving}
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
