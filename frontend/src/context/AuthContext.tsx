import React, { createContext, useContext, useState, useEffect } from 'react';
import { User, AuthResponse } from '../types';
import { authApi } from '../services/api';

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, pass: string) => Promise<void>;
  register: (email: string, pass: string, name?: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('tradepulse_token'));
  const [loading, setLoading] = useState<boolean>(true);

  const refreshUser = async () => {
    try {
      if (token) {
        const u = await authApi.getMe();
        setUser(u);
      } else {
        setUser(null);
      }
    } catch (e) {
      console.error('Failed to load current user', e);
      localStorage.removeItem('tradepulse_token');
      setToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshUser();
  }, [token]);

  const login = async (email: string, pass: string) => {
    const formData = new FormData();
    formData.append('username', email);
    formData.append('password', pass);
    const res: AuthResponse = await authApi.login(formData);
    localStorage.setItem('tradepulse_token', res.access_token);
    setToken(res.access_token);
    setUser(res.user);
  };

  const register = async (email: string, pass: string, name?: string) => {
    const res: AuthResponse = await authApi.register({
      email,
      password: pass,
      full_name: name
    });
    localStorage.setItem('tradepulse_token', res.access_token);
    setToken(res.access_token);
    setUser(res.user);
  };

  const logout = () => {
    localStorage.removeItem('tradepulse_token');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
