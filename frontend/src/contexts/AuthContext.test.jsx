import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, waitFor } from '@testing-library/react';
import { AuthProvider, useAuth } from './AuthContext';
import { authApi } from '../services/api.js';

vi.mock('../services/api.js', () => ({
  authApi: {
    me: vi.fn(),
    login: vi.fn(),
  },
}));

function Probe() {
  const { user, isAuthenticated, loading, canEdit, canDelete, isAdmin, loginWithPassword, logout } = useAuth();
  return (
    <div>
      <div data-testid="loading">{String(loading)}</div>
      <div data-testid="auth">{String(isAuthenticated)}</div>
      <div data-testid="role">{user?.role ?? 'none'}</div>
      <div data-testid="canEdit">{String(canEdit())}</div>
      <div data-testid="canDelete">{String(canDelete())}</div>
      <div data-testid="isAdmin">{String(isAdmin())}</div>
      <button onClick={() => loginWithPassword('u', 'p')}>login</button>
      <button onClick={logout}>logout</button>
    </div>
  );
}

function renderWithProvider() {
  return render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
}

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });
  afterEach(() => {
    localStorage.clear();
  });

  it('starts unauthenticated and not loading when no token is stored', async () => {
    renderWithProvider();
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('false'));
    expect(screen.getByTestId('auth').textContent).toBe('false');
    expect(authApi.me).not.toHaveBeenCalled();
  });

  it('validates stored token via /me on mount', async () => {
    localStorage.setItem('acme_jwt', 'stored-jwt');
    authApi.me.mockResolvedValueOnce({ id: '1', user_role: 'admin', email: 'a@x.com' });
    renderWithProvider();
    await waitFor(() => expect(screen.getByTestId('auth').textContent).toBe('true'));
    expect(screen.getByTestId('role').textContent).toBe('admin');
  });

  it('logs out if /me fails on mount', async () => {
    localStorage.setItem('acme_jwt', 'bad-jwt');
    authApi.me.mockRejectedValueOnce(new Error('401'));
    renderWithProvider();
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('false'));
    expect(screen.getByTestId('auth').textContent).toBe('false');
    expect(localStorage.getItem('acme_jwt')).toBeNull();
  });

  it('loginWithPassword stores token + user and skips /me', async () => {
    authApi.login.mockResolvedValueOnce({
      token: 'new-jwt',
      user: { id: '1', user_role: 'manager', email: 'm@x.com' },
    });
    renderWithProvider();
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('false'));
    await act(async () => {
      screen.getByText('login').click();
    });
    await waitFor(() => expect(screen.getByTestId('auth').textContent).toBe('true'));
    expect(localStorage.getItem('acme_jwt')).toBe('new-jwt');
    expect(screen.getByTestId('role').textContent).toBe('manager');
    expect(authApi.me).not.toHaveBeenCalled();
  });

  it('logout clears token and user', async () => {
    localStorage.setItem('acme_jwt', 'stored-jwt');
    authApi.me.mockResolvedValueOnce({ id: '1', user_role: 'admin' });
    renderWithProvider();
    await waitFor(() => expect(screen.getByTestId('auth').textContent).toBe('true'));
    await act(async () => {
      screen.getByText('logout').click();
    });
    expect(screen.getByTestId('auth').textContent).toBe('false');
    expect(localStorage.getItem('acme_jwt')).toBeNull();
  });

  describe('permission helpers', () => {
    const cases = [
      { role: 'admin', canEdit: 'true', canDelete: 'true', isAdmin: 'true' },
      { role: 'manager', canEdit: 'true', canDelete: 'true', isAdmin: 'false' },
      { role: 'contributor', canEdit: 'true', canDelete: 'false', isAdmin: 'false' },
      { role: 'viewer', canEdit: 'false', canDelete: 'false', isAdmin: 'false' },
    ];
    for (const c of cases) {
      it(`role=${c.role} → edit=${c.canEdit} delete=${c.canDelete} admin=${c.isAdmin}`, async () => {
        localStorage.setItem('acme_jwt', 'jwt');
        authApi.me.mockResolvedValueOnce({ id: '1', user_role: c.role });
        renderWithProvider();
        await waitFor(() => expect(screen.getByTestId('role').textContent).toBe(c.role));
        expect(screen.getByTestId('canEdit').textContent).toBe(c.canEdit);
        expect(screen.getByTestId('canDelete').textContent).toBe(c.canDelete);
        expect(screen.getByTestId('isAdmin').textContent).toBe(c.isAdmin);
      });
    }
  });

  it('useAuth throws outside provider', () => {
    const Bad = () => {
      useAuth();
      return null;
    };
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<Bad />)).toThrow(/useAuth must be used inside AuthProvider/);
    spy.mockRestore();
  });
});
