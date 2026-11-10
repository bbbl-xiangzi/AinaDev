export const AUTO_SSO_ATTEMPTED = "community_auto_sso_attempted";

/** One automatic attempt per tab; explicit account login is always available. */
export async function resolveAutoSso(
  href: string,
  token: string | null,
  storage: Pick<Storage, "getItem" | "setItem">,
  request: typeof fetch,
  clearSession: () => void,
): Promise<"stay" | "sso"> {
  try {
    const url = new URL(href);
    if (url.pathname === "/sso-entry" || url.searchParams.has("sso_ok")) return "stay";
    if (url.searchParams.get("local") === "1" || url.searchParams.has("sso_error")) {
      storage.setItem(AUTO_SSO_ATTEMPTED, "1");
      return "stay";
    }
    if (storage.getItem(AUTO_SSO_ATTEMPTED)) return "stay";
    const signal = AbortSignal.timeout(5000);
    const config = await request("/api/admin/site-config-public", { cache: "no-store", signal });
    if (!config.ok || (await config.json()).auto_sso_login !== true) return "stay";
    if (token) {
      const me = await request("/api/auth/me", { headers: { Authorization: `Bearer ${token}` }, cache: "no-store", signal });
      if (me.status !== 401) return "stay";
      clearSession();
    }
    const status = await request("/api/auth/sso/status", { cache: "no-store", signal });
    if (!status.ok || (await status.json()).enabled !== true) return "stay";
    storage.setItem(AUTO_SSO_ATTEMPTED, "1");
    return "sso";
  } catch {
    // Network/storage errors must never lock users out of account login.
    return "stay";
  }
}
