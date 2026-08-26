import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navbar } from './components/layout/Navbar';
import { Sidebar } from './components/layout/Sidebar';

import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { Dashboard } from './pages/Dashboard';
import { Markets } from './pages/Markets';
import { Patterns } from './pages/Patterns';
import { PatternCreator } from './pages/PatternCreator';
import { PatternDetail } from './pages/PatternDetail';
import { PatternBacktest } from './pages/PatternBacktest';
import { Signals } from './pages/Signals';
import { SignalDetail } from './pages/SignalDetail';
import { Performance } from './pages/Performance';
import { TelegramSettings } from './pages/TelegramSettings';
import { Admin } from './pages/Admin';
import { SettingsPage } from './pages/Settings';

const ProtectedLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center text-primary font-mono text-xs">
        <div className="flex items-center space-x-2">
          <span className="w-2 h-2 rounded-full bg-primary animate-ping" />
          <span>INITIALIZING TRADEPULSE WORKSTATION...</span>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navbar />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 overflow-x-hidden">{children}</main>
      </div>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          <Route
            path="/"
            element={
              <ProtectedLayout>
                <Dashboard />
              </ProtectedLayout>
            }
          />
          <Route
            path="/dashboard"
            element={
              <ProtectedLayout>
                <Dashboard />
              </ProtectedLayout>
            }
          />
          <Route
            path="/markets"
            element={
              <ProtectedLayout>
                <Markets />
              </ProtectedLayout>
            }
          />
          <Route
            path="/patterns"
            element={
              <ProtectedLayout>
                <Patterns />
              </ProtectedLayout>
            }
          />
          <Route
            path="/patterns/new"
            element={
              <ProtectedLayout>
                <PatternCreator />
              </ProtectedLayout>
            }
          />
          <Route
            path="/patterns/:id"
            element={
              <ProtectedLayout>
                <PatternDetail />
              </ProtectedLayout>
            }
          />
          <Route
            path="/patterns/:id/backtest"
            element={
              <ProtectedLayout>
                <PatternBacktest />
              </ProtectedLayout>
            }
          />
          <Route
            path="/signals"
            element={
              <ProtectedLayout>
                <Signals />
              </ProtectedLayout>
            }
          />
          <Route
            path="/signals/:id"
            element={
              <ProtectedLayout>
                <SignalDetail />
              </ProtectedLayout>
            }
          />
          <Route
            path="/performance"
            element={
              <ProtectedLayout>
                <Performance />
              </ProtectedLayout>
            }
          />
          <Route
            path="/settings/telegram"
            element={
              <ProtectedLayout>
                <TelegramSettings />
              </ProtectedLayout>
            }
          />
          <Route
            path="/settings"
            element={
              <ProtectedLayout>
                <SettingsPage />
              </ProtectedLayout>
            }
          />
          <Route
            path="/admin"
            element={
              <ProtectedLayout>
                <Admin />
              </ProtectedLayout>
            }
          />

          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};
