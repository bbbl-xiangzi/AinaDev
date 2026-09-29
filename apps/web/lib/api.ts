"use client";

/** API 客户端：token 管理 + fetch 封装。 */

export const API_BASE = "";

const TOKEN_KEY = "community_token";
const USER_KEY = "community_user";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setAuth(token: string, user: any) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getStoredUser(): any | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  try {
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const resp = await fetch(`${API_BASE}/api${path}`, { ...options, headers });
  if (resp.status === 401 && !path.startsWith("/auth/login") && !path.startsWith("/auth/refresh")) {
    clearAuth();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
    throw new ApiError(401, "未登录");
  }
  if (!resp.ok) {
    let detail = `请求失败 (${resp.status})`;
    try {
      const data = await resp.json();
      if (data.detail) detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      /* ignore */
    }
    throw new ApiError(resp.status, detail);
  }
  return resp.json() as Promise<T>;
}

export const http = {
  get: <T = any>(path: string) => api<T>(path),
  post: <T = any>(path: string, body?: any) =>
    api<T>(path, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined }),
  put: <T = any>(path: string, body?: any) => api<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  patch: <T = any>(path: string, body?: any) => api<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  del: <T = any>(path: string) => api<T>(path, { method: "DELETE" }),
  upload: <T = any>(path: string, formData: FormData) => {
    const headers: Record<string, string> = {};
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return fetch(`${API_BASE}/api${path}`, { method: "POST", headers, body: formData }).then(async (r) => {
      if (!r.ok) throw new ApiError(r.status, (await r.json().catch(() => ({}))).detail || "上传失败");
      return r.json() as Promise<T>;
    });
  },
};
