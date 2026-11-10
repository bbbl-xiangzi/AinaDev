/** Receive only a locally issued token; identity always comes from /auth/me. */
export function newSsoAttempt(source: Pick<Crypto, "getRandomValues"> = crypto): string {
  return Array.from(source.getRandomValues(new Uint8Array(24)), byte => byte.toString(16).padStart(2, "0")).join("");
}

export function startSsoLogin() {
  const attempt = newSsoAttempt();
  sessionStorage.setItem("community_sso_attempt", attempt);
  window.location.replace(`/api/auth/sso/login?login_attempt=${encodeURIComponent(attempt)}`);
}

/** Validate cached authentication before choosing the portal entry destination. */
export async function resolveSsoEntry(
  token: string | null,
  request: typeof fetch,
  clearSession: () => void,
  signal?: AbortSignal,
): Promise<"home" | "sso"> {
  if (token) {
    const me = await request("/api/auth/me", {
      headers: { Authorization: `Bearer ${token}` }, cache: "no-store", signal,
    });
    signal?.throwIfAborted();
    if (me.ok) {
      const user = await me.json();
      signal?.throwIfAborted();
      if (!Number.isInteger(user?.id)) throw new Error("登录状态验证失败，请重试");
      return "home";
    }
    if (me.status !== 401) throw new Error("登录状态验证失败，请重试");
    clearSession();
  }
  const response = await request("/api/auth/sso/status", { cache: "no-store", signal });
  if (!response.ok) throw new Error("统一登录暂时不可用，请重试");
  const status = await response.json();
  signal?.throwIfAborted();
  if (status.enabled !== true) throw new Error("统一登录尚未启用");
  return "sso";
}

export async function consumeSsoResult(
  href: string,
  clearLocation: () => void,
  verify: (token: string) => Promise<any>,
  expectedAttempt: string | null = null,
): Promise<{ token: string; user: any } | null> {
  const url = new URL(href);
  if (url.pathname !== "/login" || url.searchParams.get("sso_ok") !== "1") return null;
  clearLocation();
  const fragment = new URLSearchParams(url.hash.slice(1));
  if (!expectedAttempt || fragment.getAll("attempt").length !== 1 || fragment.get("attempt") !== expectedAttempt) {
    throw new Error("SSO 登录不是由当前浏览器发起");
  }
  const tokens = fragment.getAll("token");
  if (tokens.length !== 1 || !tokens[0]) throw new Error("缺少有效 SSO 登录结果");
  const user = await verify(tokens[0]);
  if (!user || !Number.isInteger(user.id)) throw new Error("SSO 用户验证失败");
  return { token: tokens[0], user };
}

export function safeSsoLogoutUrl(value: unknown): string {
  try {
    if (typeof value !== "string") return "/login";
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password ? url.href : "/login";
  } catch {
    return "/login";
  }
}
