import { createContext, useContext, useMemo, useState, useCallback } from 'react';
import PropTypes from 'prop-types';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';

const STORAGE_KEY = 'color-mode';
const ColorModeContext = createContext({ mode: 'light', toggle: () => {} });

export function ColorModeProvider({ children }) {
  const [mode, setMode] = useState(() => localStorage.getItem(STORAGE_KEY) || 'light');

  const toggle = useCallback(() => {
    setMode((prev) => {
      const next = prev === 'light' ? 'dark' : 'light';
      localStorage.setItem(STORAGE_KEY, next);
      return next;
    });
  }, []);

  const theme = useMemo(() => {
    const navy = mode === 'dark' ? '#1a237e' : '#1976d2';
    const headerGrey = '#1e1e22';
    const isDark = mode === 'dark';
    return createTheme({
      palette: {
        mode,
        primary: { main: navy },
        secondary: { main: '#dc004e' },
        ...(isDark && {
          background: { default: '#2a2a2e', paper: '#1e1e22' },
        }),
      },
      components: {
        MuiAppBar: {
          defaultProps: { enableColorOnDark: true, color: 'primary' },
        },
        MuiPaper: {
          styleOverrides: {
            root: { backgroundImage: 'none' },
          },
        },
        ...(isDark && {
          MuiTab: {
            styleOverrides: {
              root: {
                backgroundColor: '#1e1e22',
                borderRadius: 1,
                marginRight: 4,
                color: 'rgba(255,255,255,0.7)',
                '&.Mui-selected': {
                  backgroundColor: navy,
                  color: '#fff',
                },
              },
            },
          },
          MuiDialog: {
            styleOverrides: {
              paper: { backgroundColor: '#2a2a2e' },
            },
          },
          MuiDialogActions: {
            styleOverrides: {
              root: {
                '& .MuiButton-text': { color: '#fff' },
              },
            },
          },
          MuiOutlinedInput: {
            styleOverrides: {
              root: {
                backgroundColor: headerGrey,
                color: '#fff',
                '& .MuiOutlinedInput-notchedOutline': { borderColor: headerGrey },
                '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: '#3a3a3f' },
                '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: '#5a5a60' },
                '& .MuiSelect-icon': { color: '#fff' },
              },
              input: {
                color: '#fff',
                '&::placeholder': { color: 'rgba(255,255,255,0.6)', opacity: 1 },
              },
            },
          },
          MuiInputLabel: {
            styleOverrides: {
              root: {
                color: 'rgba(255,255,255,0.7)',
                '&.Mui-focused': { color: '#fff' },
              },
            },
          },
          MuiTableHead: {
            styleOverrides: {
              root: {
                backgroundColor: headerGrey,
                '& .MuiTableCell-head': {
                  backgroundColor: headerGrey,
                  color: '#fff',
                  fontWeight: 600,
                },
              },
            },
          },
          MuiDataGrid: {
            styleOverrides: {
              root: {
                '& .MuiDataGrid-columnHeaders': {
                  backgroundColor: headerGrey,
                  color: '#fff',
                },
                '& .MuiDataGrid-columnHeader': {
                  backgroundColor: headerGrey,
                  color: '#fff',
                },
                '& .MuiDataGrid-columnHeaderTitle': {
                  fontWeight: 600,
                  color: '#fff',
                },
                '& .MuiDataGrid-sortIcon, & .MuiDataGrid-menuIconButton, & .MuiDataGrid-iconButtonContainer': {
                  color: '#fff',
                },
              },
            },
          },
        }),
      },
    });
  }, [mode]);

  const value = useMemo(() => ({ mode, toggle }), [mode, toggle]);

  return (
    <ColorModeContext.Provider value={value}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ColorModeContext.Provider>
  );
}

ColorModeProvider.propTypes = { children: PropTypes.node.isRequired };

export const useColorMode = () => useContext(ColorModeContext);
