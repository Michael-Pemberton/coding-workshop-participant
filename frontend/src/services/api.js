import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:3001';

const client = axios.create({ baseURL: BASE_URL });

// Attach stored JWT to every request.
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('acme_jwt');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`; // eslint-disable-line no-param-reassign
  }
  return config;
});

// Unwrap the {data, success} envelope on success; surface error messages.
// On 401, clear the stored token so the AuthContext will redirect to login.
client.interceptors.response.use(
  (res) => (res.data && Object.prototype.hasOwnProperty.call(res.data, 'data') ? res.data.data : res.data),
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('acme_jwt');
      // Reload so AuthContext re-evaluates and redirects to /login.
      window.location.href = '/login';
    }
    const message =
      err.response?.data?.error || err.message || 'An unexpected error occurred';
    return Promise.reject(new Error(message));
  },
);

// ---------------------------------------------------------------------------
// Generic CRUD factory
// ---------------------------------------------------------------------------

/**
 * Creates a standard set of CRUD functions for a given API resource.
 * @param {string} resource - URL segment (e.g. 'projects').
 * @returns {object} Object with getAll, getById, create, update, remove.
 */
function crudFor(resource) {
  return {
    /** @param {object} [params] - Query parameters for filtering. */
    getAll: (params) => client.get(`/api/${resource}`, { params }),
    /** @param {string} id */
    getById: (id) => client.get(`/api/${resource}/${id}`),
    /** @param {object} data */
    create: (data) => client.post(`/api/${resource}`, data),
    /** @param {string} id @param {object} data */
    update: (id, data) => client.put(`/api/${resource}/${id}`, data),
    /** @param {string} id */
    remove: (id) => client.delete(`/api/${resource}/${id}`),
  };
}

export const projectsApi = {
  ...crudFor('projects'),
};

export const peopleApi = {
  ...crudFor('people'),
  /** @param {string} id - Person ID. */
  getAllocation: (id) => client.get(`/api/people/${id}/allocation`),
};

export const deliverablesApi = crudFor('deliverables');

export const assignmentsApi = crudFor('assignments');

export const budgetsApi = {
  ...crudFor('budgets'),
  /** @param {string} projectId */
  getStaff: (projectId) => client.get('/api/budgets/staff', { params: { project_id: projectId } }),
  /** @param {object} body - {project_id, person_id, amount_planned, amount_consumed} */
  upsertStaffOverride: (body) => client.put('/api/budgets/staff/override', body),
};

export const authApi = {
  /**
   * Verifies a Google ID token and returns {token, user}.
   * @param {string} credential - Google ID token.
   */
  verify: (credential) => client.post('/api/auth/verify', { credential }),

  /**
   * Logs in with username + password.
   * @param {string} username @param {string} password
   */
  login: (username, password) =>
    client.post('/api/auth/login', { username, password }),

  /** Developer login bypass (IS_LOCAL=true only). */
  devLogin: () =>
    client.post('/api/auth/verify', {
      dev_login: true,
      email: 'admin@acme.com',
      name: 'Dev Admin',
    }),

  /** Returns current user from JWT. */
  me: () => client.get('/api/auth/me'),

  /** Returns all users (admin only). */
  getUsers: () => client.get('/api/auth/users'),

  /** Creates a new user (admin only). */
  createUser: (data) => client.post('/api/auth/users', data),

  /** Updates a user (admin only). */
  updateUser: (id, data) => client.put(`/api/auth/users/${id}`, data),

  /** Deactivates a user (admin only). */
  deleteUser: (id) => client.delete(`/api/auth/users/${id}`),

  /**
   * Updates a user's role (admin only).
   * @param {string} id @param {string} role
   */
  updateRole: (id, role) => client.put(`/api/auth/users/${id}/role`, { role }),
};
