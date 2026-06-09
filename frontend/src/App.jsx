import { Routes, Route, Navigate } from 'react-router-dom';
import PropTypes from 'prop-types';

import { useAuth } from './contexts/AuthContext.jsx';
import MainLayout from './layouts/MainLayout.jsx';
import LoginPage from './pages/LoginPage.jsx';
import DashboardPage from './pages/DashboardPage.jsx';
import ProjectsPage from './pages/ProjectsPage.jsx';
import ProjectDetailPage from './pages/ProjectDetailPage.jsx';
import PeoplePage from './pages/PeoplePage.jsx';
import DeliverablesPage from './pages/DeliverablesPage.jsx';
import BudgetsPage from './pages/BudgetsPage.jsx';
import AdminUsersPage from './pages/AdminUsersPage.jsx';

/**
 * Redirects unauthenticated users to the login page.
 * @param {object} props
 * @param {React.ReactNode} props.children
 */
function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return null;
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

ProtectedRoute.propTypes = {
  children: PropTypes.node.isRequired,
};

/**
 * Root application component defining all client-side routes.
 */
function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="projects" element={<ProjectsPage />} />
        <Route path="projects/:id" element={<ProjectDetailPage />} />
        <Route path="people" element={<PeoplePage />} />
        <Route path="deliverables" element={<DeliverablesPage />} />
        <Route path="budgets" element={<BudgetsPage />} />
        <Route path="admin/users" element={<AdminUsersPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
