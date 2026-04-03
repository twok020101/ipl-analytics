"use client";
import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from "react";
import { BASE_URL } from "@/lib/api";
import type { AppUser as User, UserRole } from "@/lib/types";

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string, organization?: string) => Promise<void>;
  logout: () => void;
  /** Check if user has at least the given role level */
  hasRole: (minimum: UserRole) => boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for stored token on mount
    const stored = localStorage.getItem("ipl_token");
    if (stored) {
      setToken(stored);
      // Verify token
      fetch(`${BASE_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${stored}` },
      })
        .then((r) => (r.ok ? r.json() : Promise.reject()))
        .then((data) => setUser(data))
        .catch(() => {
          localStorage.removeItem("ipl_token");
          setToken(null);
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (email: string, password: string) => {
    const res = await fetch(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Login failed");
    }
    const data = await res.json();
    localStorage.setItem("ipl_token", data.token);
    setToken(data.token);
    setUser(data.user);
  };

  const register = async (email: string, password: string, name: string, organization?: string) => {
    const res = await fetch(`${BASE_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name, organization }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Registration failed");
    }
    const data = await res.json();
    localStorage.setItem("ipl_token", data.token);
    setToken(data.token);
    setUser(data.user);
  };

  const logout = () => {
    localStorage.removeItem("ipl_token");
    setToken(null);
    setUser(null);
  };

  /** Role hierarchy check: viewer < analyst < admin */
  const hasRole = useCallback(
    (minimum: UserRole): boolean => {
      if (!user) return false;
      const rank: Record<string, number> = { viewer: 0, analyst: 1, admin: 2 };
      return (rank[user.role] ?? -1) >= (rank[minimum] ?? 99);
    },
    [user],
  );

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout, hasRole }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
