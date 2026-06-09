import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import PropTypes from 'prop-types';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import IconButton from '@mui/material/IconButton';
import TextField from '@mui/material/TextField';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import MenuItem from '@mui/material/MenuItem';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';

import {
  projectsApi,
  peopleApi,
  assignmentsApi,
  deliverablesApi,
  budgetsApi,
} from '../services/api.js';
import { useAuth } from '../contexts/AuthContext.jsx';
import HealthChip from '../components/HealthChip.jsx';
import StatusChip from '../components/StatusChip.jsx';
import ConfirmDialog from '../components/ConfirmDialog.jsx';
import LoadingOverlay from '../components/LoadingOverlay.jsx';
import ErrorAlert from '../components/ErrorAlert.jsx';

const DELIVERABLE_STATUSES = ['pending', 'in_progress', 'completed', 'blocked', 'cancelled'];
const BUDGET_CATEGORIES = ['labor', 'equipment', 'software', 'travel', 'other'];

/** Tab panel wrapper */
function TabPanel({ children, value, index }) {
  return value === index ? <Box sx={{ pt: 2 }}>{children}</Box> : null;
}
TabPanel.propTypes = {
  children: PropTypes.node.isRequired,
  value: PropTypes.number.isRequired,
  index: PropTypes.number.isRequired,
};

/**
 * Full project detail page with tabs for overview, people, deliverables, and budget.
 */
function ProjectDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { canEdit, canDelete } = useAuth();
  const [project, setProject] = useState(null);
  const [allPeople, setAllPeople] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [deliverables, setDeliverables] = useState([]);
  const [budgets, setBudgets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tab, setTab] = useState(0);

  // Dialog states
  const [assignDialog, setAssignDialog] = useState(false);
  const [assignEditing, setAssignEditing] = useState(null);
  const [assignForm, setAssignForm] = useState({ person_id: '', role_on_project: '', hours_per_week: '' });
  const [delivDialog, setDelivDialog] = useState(false);
  const [delivEditing, setDelivEditing] = useState(null);
  const [delivForm, setDelivForm] = useState({ title: '', description: '', status: 'pending', due_date: '', depends_on_id: '' });
  const [budgetDialog, setBudgetDialog] = useState(false);
  const [budgetEditing, setBudgetEditing] = useState(null);
  const [budgetForm, setBudgetForm] = useState({ category: 'other', description: '', amount_planned: '', amount_consumed: '' });
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [saving, setSaving] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [pj, pp, as, dl, bg] = await Promise.all([
        projectsApi.getById(id),
        peopleApi.getAll(),
        assignmentsApi.getAll({ project_id: id }),
        deliverablesApi.getAll({ project_id: id }),
        budgetsApi.getAll({ project_id: id }),
      ]);
      setProject(pj?.data ?? pj);
      setAllPeople(pp?.data ?? pp ?? []);
      setAssignments(as?.data ?? as ?? []);
      setDeliverables(dl?.data ?? dl ?? []);
      setBudgets(bg?.data ?? bg ?? []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  if (loading) return <LoadingOverlay />;
  if (error) return <ErrorAlert message={error} onRetry={fetchAll} />;
  if (!project) return <Typography>Project not found.</Typography>;

  const budgetPct =
    project.budget_planned > 0
      ? Math.round((project.budget_consumed / project.budget_planned) * 100)
      : 0;

  const assignedPersonIds = new Set(assignments.map((a) => a.person_id));
  const unassignedPeople = allPeople.filter((p) => !assignedPersonIds.has(p.id));

  // --- Assignments ---
  const openAssignDialog = (a) => {
    setAssignEditing(a || null);
    setAssignForm(a
      ? { person_id: a.person_id, role_on_project: a.role_on_project ?? '', hours_per_week: a.hours_per_week ?? '' }
      : { person_id: '', role_on_project: '', hours_per_week: '' });
    setAssignDialog(true);
  };
  const handleAssign = async () => {
    setSaving(true);
    try {
      if (assignEditing) {
        await assignmentsApi.update(assignEditing.id, {
          role_on_project: assignForm.role_on_project,
          hours_per_week: assignForm.hours_per_week,
        });
      } else {
        await assignmentsApi.create({ ...assignForm, project_id: id });
      }
      setAssignDialog(false);
      setAssignEditing(null);
      setAssignForm({ person_id: '', role_on_project: '', hours_per_week: '' });
      await fetchAll();
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  };

  // --- Deliverables ---
  const openDelivDialog = (d) => {
    setDelivEditing(d || null);
    setDelivForm(d ? { title: d.title, description: d.description || '', status: d.status, due_date: d.due_date?.slice(0, 10) || '', depends_on_id: d.depends_on_id || '' } : { title: '', description: '', status: 'pending', due_date: '', depends_on_id: '' });
    setDelivDialog(true);
  };
  const handleSaveDeliv = async () => {
    setSaving(true);
    try {
      const payload = { ...delivForm, project_id: id };
      if (delivEditing) await deliverablesApi.update(delivEditing.id, payload);
      else await deliverablesApi.create(payload);
      setDelivDialog(false);
      await fetchAll();
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  };

  // --- Budgets ---
  const openBudgetDialog = (b) => {
    setBudgetEditing(b || null);
    setBudgetForm(b ? { category: b.category, description: b.description || '', amount_planned: b.amount_planned, amount_consumed: b.amount_consumed } : { category: 'other', description: '', amount_planned: '', amount_consumed: '' });
    setBudgetDialog(true);
  };
  const handleSaveBudget = async () => {
    setSaving(true);
    try {
      const payload = { ...budgetForm, project_id: id };
      if (budgetEditing) await budgetsApi.update(budgetEditing.id, payload);
      else await budgetsApi.create(payload);
      setBudgetDialog(false);
      await fetchAll();
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  };

  const handleDelete = async () => {
    setSaving(true);
    try {
      const { type, item } = confirmDelete;
      if (type === 'assignment') await assignmentsApi.remove(item.id);
      if (type === 'deliverable') await deliverablesApi.remove(item.id);
      if (type === 'budget') await budgetsApi.remove(item.id);
      setConfirmDelete(null);
      await fetchAll();
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  };

  const totalBudgetPlanned = budgets.reduce((s, b) => s + Number(b.amount_planned || 0), 0);
  const totalBudgetConsumed = budgets.reduce((s, b) => s + Number(b.amount_consumed || 0), 0);

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <IconButton onClick={() => navigate('/projects')}><ArrowBackIcon /></IconButton>
        <Typography variant="h5" fontWeight="bold" sx={{ flexGrow: 1 }}>
          {project.title}
        </Typography>
        <StatusChip status={project.status} />
        <HealthChip health={project.health} />
      </Box>

      {error && <ErrorAlert message={error} />}

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 1 }}>
        <Tab label="Overview" />
        <Tab label={`People (${assignments.length})`} />
        <Tab label={`Deliverables (${deliverables.length})`} />
        <Tab label={`Budget (${budgets.length})`} />
      </Tabs>

      {/* Overview */}
      <TabPanel value={tab} index={0}>
        <Paper sx={{ p: 3 }}>
          {project.description && <Typography sx={{ mb: 2 }}>{project.description}</Typography>}
          <Box sx={{ display: 'flex', gap: 4, flexWrap: 'wrap', mb: 2 }}>
            <Box><Typography variant="caption" color="text.secondary">Start Date</Typography><Typography>{project.start_date?.slice(0, 10) ?? '—'}</Typography></Box>
            <Box><Typography variant="caption" color="text.secondary">End Date</Typography><Typography>{project.end_date?.slice(0, 10) ?? '—'}</Typography></Box>
            <Box><Typography variant="caption" color="text.secondary">Budget Planned</Typography><Typography>${Number(project.budget_planned || 0).toLocaleString()}</Typography></Box>
            <Box><Typography variant="caption" color="text.secondary">Budget Consumed</Typography><Typography>${Number(project.budget_consumed || 0).toLocaleString()}</Typography></Box>
          </Box>
          <Box sx={{ mb: 2 }}>
            <Typography variant="caption" color="text.secondary">Budget Usage</Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <LinearProgress variant="determinate" value={Math.min(budgetPct, 100)} color={budgetPct > 80 ? 'error' : 'primary'} sx={{ flexGrow: 1, height: 10, borderRadius: 5 }} />
              <Typography variant="body2">{budgetPct}%</Typography>
            </Box>
          </Box>
          {project.dependency_ids?.length > 0 && (
            <Box>
              <Typography variant="caption" color="text.secondary">Dependencies</Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 0.5 }}>
                {project.dependency_ids.map((depId) => (
                  <Chip key={depId} label={depId} size="small" onClick={() => navigate(`/projects/${depId}`)} />
                ))}
              </Box>
            </Box>
          )}
        </Paper>
      </TabPanel>

      {/* People / Assignments */}
      <TabPanel value={tab} index={1}>
        {canEdit() && (
          <Button startIcon={<AddIcon />} variant="outlined" sx={{ mb: 2 }} onClick={() => openAssignDialog(null)}>
            Assign Person
          </Button>
        )}
        <Table size="small" component={Paper}>
          <TableHead><TableRow><TableCell>Name</TableCell><TableCell>Role</TableCell><TableCell>Hrs/Week</TableCell>{canEdit() && <TableCell />}</TableRow></TableHead>
          <TableBody>
            {assignments.map((a) => {
              const person = allPeople.find((p) => p.id === a.person_id);
              return (
                <TableRow key={a.id}>
                  <TableCell>{person?.name ?? a.person_id}</TableCell>
                  <TableCell>{a.role_on_project ?? '—'}</TableCell>
                  <TableCell>{a.hours_per_week}</TableCell>
                  {canEdit() && (
                    <TableCell>
                      <IconButton size="small" onClick={() => openAssignDialog(a)}><EditIcon fontSize="small" /></IconButton>
                      {canDelete() && <IconButton size="small" color="error" onClick={() => setConfirmDelete({ type: 'assignment', item: a })}><DeleteIcon fontSize="small" /></IconButton>}
                    </TableCell>
                  )}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TabPanel>

      {/* Deliverables */}
      <TabPanel value={tab} index={2}>
        {canEdit() && (
          <Button startIcon={<AddIcon />} variant="outlined" sx={{ mb: 2 }} onClick={() => openDelivDialog(null)}>
            Add Deliverable
          </Button>
        )}
        <Table size="small" component={Paper}>
          <TableHead><TableRow><TableCell>Title</TableCell><TableCell>Status</TableCell><TableCell>Due Date</TableCell><TableCell>Depends On</TableCell>{canEdit() && <TableCell />}</TableRow></TableHead>
          <TableBody>
            {deliverables.map((d) => {
              const dep = deliverables.find((x) => x.id === d.depends_on_id);
              return (
                <TableRow key={d.id}>
                  <TableCell>{d.title}</TableCell>
                  <TableCell><StatusChip status={d.status} type="deliverable" /></TableCell>
                  <TableCell>{d.due_date?.slice(0, 10) ?? '—'}</TableCell>
                  <TableCell>{dep?.title ?? '—'}</TableCell>
                  {canEdit() && (
                    <TableCell>
                      <IconButton size="small" onClick={() => openDelivDialog(d)}><EditIcon fontSize="small" /></IconButton>
                      {canDelete() && <IconButton size="small" color="error" onClick={() => setConfirmDelete({ type: 'deliverable', item: d })}><DeleteIcon fontSize="small" /></IconButton>}
                    </TableCell>
                  )}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TabPanel>

      {/* Budget */}
      <TabPanel value={tab} index={3}>
        {canEdit() && (
          <Button startIcon={<AddIcon />} variant="outlined" sx={{ mb: 2 }} onClick={() => openBudgetDialog(null)}>
            Add Budget Item
          </Button>
        )}
        <Table size="small" component={Paper}>
          <TableHead><TableRow><TableCell>Category</TableCell><TableCell>Description</TableCell><TableCell align="right">Planned</TableCell><TableCell align="right">Consumed</TableCell>{canEdit() && <TableCell />}</TableRow></TableHead>
          <TableBody>
            {budgets.map((b) => (
              <TableRow key={b.id}>
                <TableCell sx={{ textTransform: 'capitalize' }}>{b.category}</TableCell>
                <TableCell>{b.description ?? '—'}</TableCell>
                <TableCell align="right">${Number(b.amount_planned || 0).toLocaleString()}</TableCell>
                <TableCell align="right">${Number(b.amount_consumed || 0).toLocaleString()}</TableCell>
                {canEdit() && (
                  <TableCell>
                    <IconButton size="small" onClick={() => openBudgetDialog(b)}><EditIcon fontSize="small" /></IconButton>
                    {canDelete() && <IconButton size="small" color="error" onClick={() => setConfirmDelete({ type: 'budget', item: b })}><DeleteIcon fontSize="small" /></IconButton>}
                  </TableCell>
                )}
              </TableRow>
            ))}
            <TableRow sx={{ fontWeight: 'bold' }}>
              <TableCell colSpan={2}><strong>Total</strong></TableCell>
              <TableCell align="right"><strong>${totalBudgetPlanned.toLocaleString()}</strong></TableCell>
              <TableCell align="right"><strong>${totalBudgetConsumed.toLocaleString()}</strong></TableCell>
              {canEdit() && <TableCell />}
            </TableRow>
          </TableBody>
        </Table>
      </TabPanel>

      {/* Assign Person Dialog */}
      <Dialog open={assignDialog} onClose={() => { setAssignDialog(false); setAssignEditing(null); }} maxWidth="xs" fullWidth>
        <DialogTitle>{assignEditing ? 'Edit Assignment' : 'Assign Person'}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
          <TextField select label="Person *" value={assignForm.person_id} onChange={(e) => setAssignForm((f) => ({ ...f, person_id: e.target.value }))} fullWidth disabled={!!assignEditing}>
            {(assignEditing ? allPeople : unassignedPeople).map((p) => <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>)}
          </TextField>
          <TextField label="Role on Project" value={assignForm.role_on_project} onChange={(e) => setAssignForm((f) => ({ ...f, role_on_project: e.target.value }))} fullWidth />
          <TextField label="Hours/Week" type="number" value={assignForm.hours_per_week} onChange={(e) => setAssignForm((f) => ({ ...f, hours_per_week: e.target.value }))} fullWidth />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { setAssignDialog(false); setAssignEditing(null); }}>Cancel</Button>
          <Button onClick={handleAssign} variant="contained" disabled={!assignForm.person_id || saving}>{assignEditing ? 'Save' : 'Assign'}</Button>
        </DialogActions>
      </Dialog>

      {/* Deliverable Dialog */}
      <Dialog open={delivDialog} onClose={() => setDelivDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{delivEditing ? 'Edit Deliverable' : 'Add Deliverable'}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
          <TextField label="Title *" value={delivForm.title} onChange={(e) => setDelivForm((f) => ({ ...f, title: e.target.value }))} fullWidth />
          <TextField label="Description" value={delivForm.description} onChange={(e) => setDelivForm((f) => ({ ...f, description: e.target.value }))} multiline rows={2} fullWidth />
          <TextField select label="Status" value={delivForm.status} onChange={(e) => setDelivForm((f) => ({ ...f, status: e.target.value }))} fullWidth>
            {DELIVERABLE_STATUSES.map((s) => <MenuItem key={s} value={s} sx={{ textTransform: 'capitalize' }}>{s.replace('_', ' ')}</MenuItem>)}
          </TextField>
          <TextField label="Due Date" type="date" value={delivForm.due_date} onChange={(e) => setDelivForm((f) => ({ ...f, due_date: e.target.value }))} fullWidth InputLabelProps={{ shrink: true }} />
          <TextField select label="Depends On" value={delivForm.depends_on_id} onChange={(e) => setDelivForm((f) => ({ ...f, depends_on_id: e.target.value }))} fullWidth>
            <MenuItem value="">None</MenuItem>
            {deliverables.filter((d) => d.id !== delivEditing?.id).map((d) => <MenuItem key={d.id} value={d.id}>{d.title}</MenuItem>)}
          </TextField>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDelivDialog(false)}>Cancel</Button>
          <Button onClick={handleSaveDeliv} variant="contained" disabled={!delivForm.title || saving}>Save</Button>
        </DialogActions>
      </Dialog>

      {/* Budget Dialog */}
      <Dialog open={budgetDialog} onClose={() => setBudgetDialog(false)} maxWidth="xs" fullWidth>
        <DialogTitle>{budgetEditing ? 'Edit Budget Item' : 'Add Budget Item'}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
          <TextField select label="Category" value={budgetForm.category} onChange={(e) => setBudgetForm((f) => ({ ...f, category: e.target.value }))} fullWidth>
            {BUDGET_CATEGORIES.map((c) => <MenuItem key={c} value={c} sx={{ textTransform: 'capitalize' }}>{c}</MenuItem>)}
          </TextField>
          <TextField label="Description" value={budgetForm.description} onChange={(e) => setBudgetForm((f) => ({ ...f, description: e.target.value }))} fullWidth />
          <TextField label="Amount Planned" type="number" value={budgetForm.amount_planned} onChange={(e) => setBudgetForm((f) => ({ ...f, amount_planned: e.target.value }))} fullWidth />
          <TextField label="Amount Consumed" type="number" value={budgetForm.amount_consumed} onChange={(e) => setBudgetForm((f) => ({ ...f, amount_consumed: e.target.value }))} fullWidth />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setBudgetDialog(false)}>Cancel</Button>
          <Button onClick={handleSaveBudget} variant="contained" disabled={saving}>Save</Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={!!confirmDelete}
        title="Confirm Delete"
        message="Are you sure you want to delete this item?"
        onConfirm={handleDelete}
        onCancel={() => setConfirmDelete(null)}
        loading={saving}
      />
    </Box>
  );
}

export default ProjectDetailPage;
