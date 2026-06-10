import { useEffect, useState, useCallback } from 'react';
import PropTypes from 'prop-types';
import Box from '@mui/material/Box';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import Typography from '@mui/material/Typography';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import TextField from '@mui/material/TextField';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import InputAdornment from '@mui/material/InputAdornment';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import RestartAltIcon from '@mui/icons-material/RestartAlt';

import { budgetsApi } from '../services/api.js';
import { useAuth } from '../contexts/AuthContext.jsx';
import { useColorMode } from '../contexts/ColorModeContext.jsx';

function money(n) {
  return `$${Number(n || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/**
 * Editable per-row cell that calls onCommit(value) on blur or Enter.
 * Empty string clears the override (falls back to auto/0).
 */
function MoneyEditCell({ value, overridden, disabled, onCommit }) {
  const [local, setLocal] = useState(value == null ? '' : String(value));
  useEffect(() => { setLocal(value == null ? '' : String(value)); }, [value]);
  const commit = () => {
    const trimmed = local.trim();
    if (trimmed === '' || trimmed === String(value)) {
      onCommit(trimmed === '' ? null : Number(trimmed));
      return;
    }
    const n = Number(trimmed);
    if (Number.isNaN(n) || n < 0) { setLocal(value == null ? '' : String(value)); return; }
    onCommit(n);
  };
  return (
    <TextField
      value={local}
      onChange={(e) => setLocal(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => { if (e.key === 'Enter') e.target.blur(); }}
      disabled={disabled}
      size="small"
      variant="standard"
      inputProps={{ inputMode: 'decimal', style: { textAlign: 'right' } }}
      InputProps={{
        startAdornment: <InputAdornment position="start">$</InputAdornment>,
        sx: overridden ? { fontWeight: 600 } : { color: 'text.secondary' },
      }}
      sx={{ width: 130 }}
    />
  );
}

MoneyEditCell.propTypes = {
  value: PropTypes.number,
  overridden: PropTypes.bool,
  disabled: PropTypes.bool,
  onCommit: PropTypes.func.isRequired,
};
MoneyEditCell.defaultProps = { value: null, overridden: false, disabled: false };

/**
 * Expandable Internal Staff budget section — auto-derives planned cost from
 * assignments × hourly_pay × project weeks; manager can override per row.
 */
function StaffBudgetSection({ projectId, defaultExpanded, onChange }) {
  const { canEdit } = useAuth();
  const { mode } = useColorMode();
  const isDark = mode === 'dark';
  const [data, setData] = useState({ items: [], weeks: 0, total_planned: 0, total_consumed: 0 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchData = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError('');
    try {
      const result = await budgetsApi.getStaff(projectId);
      setData(result?.data ?? result ?? { items: [], total_planned: 0, total_consumed: 0 });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const updateOverride = async (item, patch) => {
    const payload = {
      project_id: projectId,
      person_id: item.person_id,
      amount_planned: 'amount_planned' in patch
        ? patch.amount_planned
        : (item.planned_overridden ? item.amount_planned : null),
      amount_consumed: 'amount_consumed' in patch
        ? patch.amount_consumed
        : (item.consumed_overridden ? item.amount_consumed : null),
    };
    try {
      const result = await budgetsApi.upsertStaffOverride(payload);
      setData(result?.data ?? result ?? data);
      if (onChange) onChange();
    } catch (err) {
      setError(err.message);
    }
  };

  const resetRow = (item) => updateOverride(item, { amount_planned: null, amount_consumed: null });

  return (
    <Accordion defaultExpanded={defaultExpanded} sx={{ bgcolor: 'background.paper' }}>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Box sx={{ display: 'flex', alignItems: 'center', width: '100%', gap: 2 }}>
          <Typography sx={{ fontWeight: 600, flexGrow: 1 }}>Internal Staff</Typography>
          <Typography variant="body2" color="text.secondary">
            {data.items.length} {data.items.length === 1 ? 'person' : 'people'}
            {data.weeks ? ` · ${data.weeks} weeks` : ''}
          </Typography>
          <Typography variant="body2"><strong>Planned:</strong> {money(data.total_planned)}</Typography>
          <Typography variant="body2"><strong>Consumed:</strong> {money(data.total_consumed)}</Typography>
        </Box>
      </AccordionSummary>
      <AccordionDetails sx={{ p: 0 }}>
        {error && <Typography color="error" sx={{ p: 2 }}>{error}</Typography>}
        {!loading && data.items.length === 0 && (
          <Typography color="text.secondary" sx={{ p: 2 }}>
            No people assigned to this project, or no hourly pay set.
          </Typography>
        )}
        {data.items.length > 0 && (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>Role</TableCell>
                <TableCell align="right">Hrs/Wk</TableCell>
                <TableCell align="right">Rate</TableCell>
                <TableCell align="right">Auto Planned</TableCell>
                <TableCell align="right">Planned</TableCell>
                <TableCell align="right">Consumed</TableCell>
                {canEdit() && <TableCell />}
              </TableRow>
            </TableHead>
            <TableBody>
              {data.items.map((item) => (
                <TableRow key={item.person_id} hover>
                  <TableCell>{item.name}</TableCell>
                  <TableCell>{item.role_on_project ?? '—'}</TableCell>
                  <TableCell align="right">{item.hours_per_week}</TableCell>
                  <TableCell align="right">{money(item.hourly_pay)}</TableCell>
                  <TableCell align="right" sx={{ color: 'text.secondary' }}>
                    {money(item.amount_planned_auto)}
                  </TableCell>
                  <TableCell align="right">
                    <MoneyEditCell
                      value={item.planned_overridden ? item.amount_planned : null}
                      overridden={item.planned_overridden}
                      disabled={!canEdit()}
                      onCommit={(v) => updateOverride(item, { amount_planned: v })}
                    />
                  </TableCell>
                  <TableCell align="right">
                    <MoneyEditCell
                      value={item.consumed_overridden ? item.amount_consumed : null}
                      overridden={item.consumed_overridden}
                      disabled={!canEdit()}
                      onCommit={(v) => updateOverride(item, { amount_consumed: v })}
                    />
                  </TableCell>
                  {canEdit() && (
                    <TableCell>
                      {(item.planned_overridden || item.consumed_overridden) && (
                        <Tooltip title="Reset to auto-derived">
                          <IconButton size="small" onClick={() => resetRow(item)}>
                            <RestartAltIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      )}
                    </TableCell>
                  )}
                </TableRow>
              ))}
              <TableRow sx={isDark ? { bgcolor: '#1e1e22', '& .MuiTableCell-root': { color: '#fff' } } : { bgcolor: 'action.hover' }}>
                <TableCell colSpan={5}><strong>Total</strong></TableCell>
                <TableCell align="right"><strong>{money(data.total_planned)}</strong></TableCell>
                <TableCell align="right"><strong>{money(data.total_consumed)}</strong></TableCell>
                {canEdit() && <TableCell />}
              </TableRow>
            </TableBody>
          </Table>
        )}
      </AccordionDetails>
    </Accordion>
  );
}

StaffBudgetSection.propTypes = {
  projectId: PropTypes.string,
  defaultExpanded: PropTypes.bool,
  onChange: PropTypes.func,
};
StaffBudgetSection.defaultProps = { projectId: null, defaultExpanded: false, onChange: null };

export default StaffBudgetSection;
