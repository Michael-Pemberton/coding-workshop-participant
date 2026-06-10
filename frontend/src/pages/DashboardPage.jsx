import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import Grid from '@mui/material/Grid';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Paper from '@mui/material/Paper';

import { projectsApi, peopleApi, assignmentsApi } from '../services/api.js';
import HealthChip from '../components/HealthChip.jsx';
import StatusChip from '../components/StatusChip.jsx';
import LoadingOverlay from '../components/LoadingOverlay.jsx';
import ErrorAlert from '../components/ErrorAlert.jsx';

/**
 * KPI summary card.
 * @param {object} props
 * @param {string} props.title
 * @param {string|number} props.value
 * @param {string} [props.color]
 */
function KpiCard({ title, value, color }) {
  return (
    <Card>
      <CardContent>
        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
          {title}
        </Typography>
        <Typography variant="h4" fontWeight="bold" color={color || 'text.primary'}>
          {value}
        </Typography>
      </CardContent>
    </Card>
  );
}

import PropTypes from 'prop-types';

KpiCard.propTypes = {
  title: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  color: PropTypes.string,
};
KpiCard.defaultProps = { color: undefined };

/**
 * Application dashboard with KPIs, project health summary, and overallocation alerts.
 */
function DashboardPage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [people, setPeople] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [pj, pp, as] = await Promise.all([
        projectsApi.getAll(),
        peopleApi.getAll(),
        assignmentsApi.getAll(),
      ]);
      setProjects(pj?.data ?? pj ?? []);
      setPeople(pp?.data ?? pp ?? []);
      setAssignments(as?.data ?? as ?? []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) return <LoadingOverlay />;
  if (error) return <ErrorAlert message={error} onRetry={fetchData} />;

  const activeProjects = projects.filter((p) => p.status === 'active');
  const atRisk = projects.filter((p) => p.health === 'red' || p.health === 'amber');
  const greenCount = projects.filter((p) => p.health === 'green').length;
  const amberCount = projects.filter((p) => p.health === 'amber').length;
  const redCount = projects.filter((p) => p.health === 'red').length;

  // Calculate overallocated people (sum hours_per_week > weekly_hours_capacity)
  const allocationByPerson = {};
  assignments.forEach((a) => {
    if (!a.is_deleted) {
      allocationByPerson[a.person_id] =
        (allocationByPerson[a.person_id] || 0) + (a.hours_per_week || 0);
    }
  });
  const overallocated = people.filter(
    (p) => (allocationByPerson[p.id] || 0) > (p.weekly_hours_capacity || 40),
  );

  const overBudget = projects.filter(
    (p) => Number(p.budget_planned || 0) > 0
      && Number(p.budget_consumed || 0) > Number(p.budget_planned || 0),
  );

  const recentProjects = [...projects]
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    .slice(0, 5);

  return (
    <Box>
      <Typography variant="h5" fontWeight="bold" gutterBottom>
        Dashboard
      </Typography>

      {/* KPI Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard title="Total Projects" value={projects.length} />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard title="Active Projects" value={activeProjects.length} color="success.main" />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard title="At-Risk Projects" value={atRisk.length} color="error.main" />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard title="Total People" value={people.length} />
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        {/* RAG Summary */}
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Project Health (RAG)
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1 }}>
                <Chip
                  label={`${greenCount} Green`}
                  color="success"
                  clickable
                  onClick={() => navigate('/projects?health=green')}
                />
                <Chip
                  label={`${amberCount} Amber`}
                  color="warning"
                  clickable
                  onClick={() => navigate('/projects?health=amber')}
                />
                <Chip
                  label={`${redCount} Red`}
                  color="error"
                  clickable
                  onClick={() => navigate('/projects?health=red')}
                />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Overallocated People */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Overallocated People
              </Typography>
              {overallocated.length === 0 ? (
                <Typography color="text.secondary">No overallocated team members.</Typography>
              ) : (
                overallocated.map((p) => (
                  <Box
                    key={p.id}
                    sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 1, mb: 0.5 }}
                  >
                    <Typography sx={{ fontWeight: 500 }}>{p.name}</Typography>
                    <Typography variant="body2" color="error.main">
                      {allocationByPerson[p.id]}h / {p.weekly_hours_capacity}h per week
                    </Typography>
                  </Box>
                ))
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Over Budget Projects */}
        <Grid item xs={12} md={5}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Over Budget Projects
              </Typography>
              {overBudget.length === 0 ? (
                <Typography color="text.secondary">No projects over budget.</Typography>
              ) : (
                overBudget.map((p) => {
                  const planned = Number(p.budget_planned || 0);
                  const consumed = Number(p.budget_consumed || 0);
                  const pct = Math.round((consumed / planned) * 100);
                  return (
                    <Box
                      key={p.id}
                      sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 1, mb: 0.5, cursor: 'pointer' }}
                      onClick={() => navigate(`/projects/${p.id}`)}
                    >
                      <Typography sx={{ fontWeight: 500 }}>{p.title}</Typography>
                      <Typography variant="body2" color="error.main">
                        ${consumed.toLocaleString()} / ${planned.toLocaleString()} ({pct}%)
                      </Typography>
                    </Box>
                  );
                })
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Recent Projects */}
        <Grid item xs={12}>
          <Paper>
            <Box sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Recent Projects
              </Typography>
            </Box>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Title</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Health</TableCell>
                  <TableCell>Budget Used</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {recentProjects.map((p) => {
                  const pct =
                    p.budget_planned > 0
                      ? Math.round((p.budget_consumed / p.budget_planned) * 100)
                      : 0;
                  return (
                    <TableRow
                      key={p.id}
                      hover
                      sx={{ cursor: 'pointer' }}
                      onClick={() => navigate(`/projects/${p.id}`)}
                    >
                      <TableCell>{p.title}</TableCell>
                      <TableCell>
                        <StatusChip status={p.status} />
                      </TableCell>
                      <TableCell>
                        <HealthChip health={p.health} reason={p.health_reason} />
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <LinearProgress
                            variant="determinate"
                            value={Math.min(pct, 100)}
                            color={pct > 95 ? 'error' : pct >= 70 ? 'warning' : 'primary'}
                            sx={{ flexGrow: 1, height: 8, borderRadius: 4 }}
                          />
                          <Typography variant="caption">{pct}%</Typography>
                        </Box>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}

export default DashboardPage;
