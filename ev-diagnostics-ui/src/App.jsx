import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './contexts/AuthContext';

import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import BatteryDetailPage from './pages/BatteryDetailPage';
import AnalyticsPage from './pages/AnalyticsPage';
import MyBatteryPage from './pages/MyBatteryPage';

/**
 * App — top-level routing configuration.
 *
 * Route structure:
 *   /login        — public, 3-button login
 *   /dashboard    — admin + operator only
 *   /battery/:id  — admin + operator only
 *   /analytics    — admin + operator only
 *   /my-battery   — customer only
 */
export default function App() {
  const { isAuthenticated, viewMode } = useAuth();

  return (
    <Routes>
      {/* Public: Login */}
      <Route
        path="/login"
        element={
          isAuthenticated
            ? <Navigate to={viewMode === 'customer' ? '/my-battery' : '/dashboard'} replace />
            : <LoginPage />
        }
      />

      {/* Protected routes inside Layout shell */}
      <Route element={
        <ProtectedRoute allowedModes={['admin', 'operator', 'customer']}>
          <Layout />
        </ProtectedRoute>
      }>
        {/* Admin + Operator routes */}
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute allowedModes={['admin', 'operator']} redirectTo="/my-battery">
              <DashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/battery/:batteryId"
          element={
            <ProtectedRoute allowedModes={['admin', 'operator']} redirectTo="/my-battery">
              <BatteryDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/analytics"
          element={
            <ProtectedRoute allowedModes={['admin', 'operator']} redirectTo="/my-battery">
              <AnalyticsPage />
            </ProtectedRoute>
          }
        />

        {/* Customer route */}
        <Route
          path="/my-battery"
          element={
            <ProtectedRoute allowedModes={['customer']} redirectTo="/dashboard">
              <MyBatteryPage />
            </ProtectedRoute>
          }
        />
      </Route>

      {/* Catch-all: redirect to appropriate home */}
      <Route
        path="*"
        element={
          isAuthenticated
            ? <Navigate to={viewMode === 'customer' ? '/my-battery' : '/dashboard'} replace />
            : <Navigate to="/login" replace />
        }
      />
    </Routes>
  );
}