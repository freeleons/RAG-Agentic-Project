import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api, setOnUnauthorized, setToken } from "../api";

interface AuthValue {
  email: string | null;
  authed: boolean;
  isAdmin: boolean;
  login(email: string, password: string): Promise<void>;
  register(email: string, password: string): Promise<void>;
  logout(): void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [email, setEmail] = useState<string | null>(() =>
    localStorage.getItem("agent_email")
  );
  const [token, setTokenState] = useState<string | null>(() => {
    const t = localStorage.getItem("agent_token");
    setToken(t);
    return t;
  });
  const [isAdmin, setIsAdmin] = useState<boolean>(() =>
    localStorage.getItem("agent_is_admin") === "1"
  );

  useEffect(() => {
    const logoutHandler = () => {
      localStorage.removeItem("agent_token");
      localStorage.removeItem("agent_email");
      localStorage.removeItem("agent_is_admin");
      setToken(null);
      setTokenState(null);
      setEmail(null);
      setIsAdmin(false);
    };
    setOnUnauthorized(logoutHandler);
    return () => setOnUnauthorized(null);
  }, []);

  const value = useMemo<AuthValue>(() => {
    const login = async (em: string, pw: string) => {
      const resp = await api.login(em, pw);
      const { token: t } = resp;
      const admin = resp.is_admin === true;
      localStorage.setItem("agent_token", t);
      localStorage.setItem("agent_email", em);
      localStorage.setItem("agent_is_admin", admin ? "1" : "0");
      setToken(t);
      setTokenState(t);
      setEmail(em);
      setIsAdmin(admin);
    };
    return {
      email,
      authed: token !== null,
      isAdmin,
      login,
      register: async (em: string, pw: string) => {
        await api.register(em, pw);
        await login(em, pw);
      },
      logout: () => {
        localStorage.removeItem("agent_token");
        localStorage.removeItem("agent_email");
        localStorage.removeItem("agent_is_admin");
        setToken(null);
        setTokenState(null);
        setEmail(null);
        setIsAdmin(false);
      },
    };
  }, [email, token, isAdmin]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
