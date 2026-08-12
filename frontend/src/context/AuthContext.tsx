import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api, setCSRFToken } from "../lib/api";
import type { User } from "../types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, displayName: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<{ user: User; csrf_token: string }>("/auth/me")
      .then((data) => {
        setUser(data.user);
        setCSRFToken(data.csrf_token);
      })
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      login: async (email, password) => {
        const data = await api<{ user: User; csrf_token: string }>("/auth/login", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
        setCSRFToken(data.csrf_token);
        setUser(data.user);
      },
      register: async (email, displayName, password) => {
        const data = await api<{ user: User; csrf_token: string }>("/auth/register", {
          method: "POST",
          body: JSON.stringify({ email, display_name: displayName, password }),
        });
        setCSRFToken(data.csrf_token);
        setUser(data.user);
      },
      logout: async () => {
        await api("/auth/logout", { method: "POST" });
        setCSRFToken("");
        setUser(null);
      },
    }),
    [user, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}

