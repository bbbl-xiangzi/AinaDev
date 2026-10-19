"use client";

import { createContext, useContext, useEffect, useRef, useState } from "react";
import { clearAuth, getStoredUser, http, setAuth } from "./api";
import { consumeSsoResult, safeSsoLogoutUrl } from "./sso";

interface AuthCtx {
  user: any | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, name: string, password: string, inviteCode: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const Ctx = createContext<AuthCtx>(null as any);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<any | null>(null);
  const [ready, setReady] = useState(false);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void (async () => {
      try {
        const attempt = sessionStorage.getItem("community_sso_attempt");
        const result = await consumeSsoResult(window.location.href, () => {
          window.history.replaceState(null, "", "/login");
          sessionStorage.removeItem("community_sso_attempt");
          clearAuth();
        }, async (token) => {
          const response = await fetch("/api/auth/me", {
            headers: { Authorization: `Bearer ${token}` }, cache: "no-store",
          });
          if (!response.ok) throw new Error("SSO 用户验证失败");
          return response.json();
        }, attempt);
        if (result) {
          setAuth(result.token, result.user);
          localStorage.setItem("community_auth_source", "sso");
          setUser(result.user);
          window.location.replace("/");
          return;
        }
        const stored = getStoredUser();
        if (stored) setUser(stored);
      } catch {
        clearAuth();
        window.location.replace("/login?sso_error=1");
      } finally {
        setReady(true);
      }
    })();
  }, []);

  const login = async (email: string, password: string) => {
    const data = await http.post("/auth/login", { email, password });
    setAuth(data.access_token, data.user);
    setUser(data.user);
  };

  const register = async (email: string, name: string, password: string, inviteCode: string) => {
    const data = await http.post("/auth/register", { email, name, password, invite_code: inviteCode });
    setAuth(data.access_token, data.user);
    setUser(data.user);
  };

  const logout = async () => {
    const wasSso = localStorage.getItem("community_auth_source") === "sso";
    clearAuth();
    setUser(null);
    let destination = "/login";
    if (wasSso) {
      try {
        const response = await fetch("/api/auth/sso/status", { signal: AbortSignal.timeout(3000), cache: "no-store" });
        if (response.ok) destination = safeSsoLogoutUrl((await response.json()).logout_url);
      } catch { /* Local logout still succeeds if the status endpoint is unavailable. */ }
    }
    window.location.href = destination;
  };

  const refreshUser = async () => {
    try {
      const me = await http.get("/auth/me");
      setUser(me);
      localStorage.setItem("community_user", JSON.stringify(me));
    } catch {
      /* ignore */
    }
  };

  return <Ctx.Provider value={{ user, login, register, logout, refreshUser }}>{ready ? children : null}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
