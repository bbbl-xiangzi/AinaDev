export function postShareUrl(origin: string, id: number | string): string {
  if (!/^[1-9]\d*$/.test(String(id))) throw new Error("Invalid post ID");
  const url = new URL(origin);
  if (url.protocol !== "http:" && url.protocol !== "https:") throw new Error("Invalid site URL");
  return `${url.origin}/post/${id}`;
}

export function postShareText(title: string, site: string, url: string): string {
  return [`推荐阅读：${title}`, site ? `来自：${site}` : "", url].filter(Boolean).join("\n");
}

/** HTTP intranet sites may not expose the Clipboard API. */
export async function copyShareText(text: string): Promise<boolean> {
  if (window.isSecureContext && navigator.clipboard?.writeText) {
    try { await navigator.clipboard.writeText(text); return true; } catch { /* Fall back to selection copy. */ }
  }
  const focused = document.activeElement as HTMLElement | null;
  const input = document.createElement("textarea");
  input.value = text;
  input.readOnly = true;
  input.style.cssText = "position:fixed;left:0;top:0;opacity:0;font-size:16px;";
  // Keep the selection inside the active modal (the rest of the page is inert).
  (document.querySelector("dialog[open]") || document.body).appendChild(input);
  try {
    input.focus(); input.select(); input.setSelectionRange(0, text.length);
    return document.execCommand("copy");
  } catch { return false; }
  finally { input.remove(); focused?.focus({ preventScroll: true }); }
}
