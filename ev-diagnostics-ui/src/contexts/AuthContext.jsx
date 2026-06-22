import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { loginApi } from '../api/client';

/**
 * AuthContext — manages JWT token, backend role, and UI-only viewMode.
 *
 * viewMode values: "admin" | "operator" | "customer" | null
 * - "admin" and "operator" map 1:1 to backend roles
 * - "customer" uses the operator backend credentials but renders a simplified UI
 *
 * Persists to localStorage so page refresh doesn't log the user out.
 */

const AuthContext = createContext(null);

// Demo credentials mapping
const CREDENTIALS = {
  admin:    { username: 'admin',    password: 'secret' },
  operator: { username: 'operator', password: 'secret' },
  customer: { username: 'operator', password: 'secret' }, // same backend creds as operator
};

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('ev_token'));
  const [role, setRole] = useState(() => localStorage.getItem('ev_role'));
  const [viewMode, setViewMode] = useState(() => localStorage.getItem('ev_viewMode'));
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // Sync state → localStorage
  useEffect(() => {
    if (token) {
      localStorage.setItem('ev_token', token);
      localStorage.setItem('ev_role', role);
      localStorage.setItem('ev_viewMode', viewMode);
    } else {
      localStorage.removeItem('ev_token');
      localStorage.removeItem('ev_role');
      localStorage.removeItem('ev_viewMode');
    }
  }, [token, role, viewMode]);

  /**
   * Login with one of the preset roles: "admin" | "operator" | "customer"
   * @param {"admin"|"operator"|"customer"} presetRole
   */
  const login = useCallback(async (presetRole) => {
    setIsLoading(true);
    setError(null);

    const creds = CREDENTIALS[presetRole];
    if (!creds) {
      setError(`Unknown role: ${presetRole}`);
      setIsLoading(false);
      return false;
    }

    try {
      const data = await loginApi(creds.username, creds.password);

      setToken(data.access_token);
      setRole(data.role); // backend role: "fleet_admin" or "operator"

      // viewMode: for customer, override to "customer" even though backend role is "operator"
      if (presetRole === 'customer') {
        setViewMode('customer');
      } else if (data.role === 'fleet_admin') {
        setViewMode('admin');
      } else {
        setViewMode('operator');
      }

      setIsLoading(false);
      return true;
    } catch (err) {
      setError(err.message || 'Login failed');
      setIsLoading(false);
      return false;
    }
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setRole(null);
    setViewMode(null);
    setError(null);
  }, []);

  const value = {
    token,
    role,         // backend role: "fleet_admin" | "operator" | null
    viewMode,     // UI mode: "admin" | "operator" | "customer" | null
    isLoading,
    error,
    login,
    logout,
    isAuthenticated: !!token,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
