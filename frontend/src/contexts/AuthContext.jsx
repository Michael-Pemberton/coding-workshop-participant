import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import { authApi } from '../services/api.js';

/** @type {React.Context} */
const AuthContext = createContext(null);

const TOKEN_KEY = 'acme_jwt';

/** Ensures both `role` (frontend) and `user_role` (DB) fields exist on the user. */
function normalizeUser(u) {
  if (!u) return u;
  return { ...u, role: u.role ?? u.user_role, user_role: u.user_role ?? u.role };
}

/**
 * Provides authentication state and helpers to the component tree.
 * @param {object} props
 * @param {React.ReactNode} props.children
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [loading, setLoading] = useState(true);

  const applyToken = useCallback((jwt, userData) => {
    localStorage.setItem(TOKEN_KEY, jwt);
    setToken(jwt);
    setUser(normalizeUser(userData));
    setLoading(false);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }, []);

  // Validate stored token whenever it changes (mount or after login).
  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    if (user) {
      // Token was just applied via login; user is already populated.
      setLoading(false);
      return;
    }
    authApi
      .me()
      .then((data) => setUser(normalizeUser(data)))
      .catch(() => logout())
      .finally(() => setLoading(false));
  }, [token, user, logout]);

  /**
   * Logs in with username + password.
   * @param {string} username
   * @param {string} password
   */
  const loginWithPassword = useCallback(async (username, password) => {
    const result = await authApi.login(username, password);
    applyToken(result.token, result.user);
  }, [applyToken]);

  /** @returns {boolean} True if user can create or update records. */
  const canEdit = useCallback(
    () => ['admin', 'manager', 'contributor'].includes(user?.role),
    [user],
  );

  /** @returns {boolean} True if user can delete records. */
  const canDelete = useCallback(
    () => ['admin', 'manager'].includes(user?.role),
    [user],
  );

  /** @returns {boolean} True if user is an administrator. */
  const isAdmin = useCallback(() => user?.role === 'admin', [user]);

  const value = {
    user,
    token,
    isAuthenticated: !!user,
    loading,
    loginWithPassword,
    logout,
    canEdit,
    canDelete,
    isAdmin,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

AuthProvider.propTypes = {
  children: PropTypes.node.isRequired,
};

/**
 * Returns the authentication context.
 * Must be used within an AuthProvider.
 * @returns {object} Auth context value.
 */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
