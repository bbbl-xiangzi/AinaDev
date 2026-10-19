/** Receive only a locally issued token; identity always comes from /auth/me. */
export function newSsoAttempt(source: Pick<Crypto, "getRandomValues"> = crypto): string {
  return Array.from(source.getRandomValues(new Uint8Array(24)), byte => byte.toString(16).padStart(2, "0")).join("");
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
