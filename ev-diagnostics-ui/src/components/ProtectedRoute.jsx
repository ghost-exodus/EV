import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

/**
 * ProtectedRoute — guards routes based on authentication and allowed viewModes.
 *
 * @param {React.ReactNode} children
 * @param {string[]} allowedModes - which viewModes can access this route
 * @param {string} redirectTo - where to redirect if the user's viewMode doesn't match
 */
export default function ProtectedRoute({ children, allowedModes, redirectTo }) {
  const { isAuthenticated, viewMode } = useAuth();
  const location = useLocation();

  // Not logged in → go to login
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Logged in but wrong viewMode → redirect to their home
  if (allowedModes && !allowedModes.includes(viewMode)) {
    const home = viewMode === 'customer' ? '/my-battery' : '/dashboard';
    return <Navigate to={redirectTo || home} replace />;
  }

  return children;
}
