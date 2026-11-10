"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { clearAuth, getToken } from "@/lib/api";
import { resolveSsoEntry, startSsoLogin } from "@/lib/sso";

export default function SsoEntryPage() {
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 15000);
    let active = true;
    setError("");
    void (async () => {
      try {
        const destination = await resolveSsoEntry(getToken(), fetch, clearAuth, controller.signal);
        if (!active) return;
        if (destination === "home") window.location.replace("/");
        else startSsoLogin();
      } catch (err) {
        if (active) setError(controller.signal.aborted
          ? "连接超时，请重试"
          : err instanceof Error && !/fetch|storage|quota/i.test(err.message)
            ? err.message : "无法完成统一登录，请重试或使用账号登录");
      } finally {
        window.clearTimeout(timeout);
      }
    })();
    return () => {
      active = false;
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [retry]);

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center px-4">
      <div className="rounded-lg border border-[#d0d7de] bg-white p-8 shadow-sm">
        <h1 className="text-[24px] font-bold text-[#24292f]">统一登录</h1>
        {error ? (
          <>
            <p role="alert" className="mt-4 rounded-md bg-[#ffebe9] px-3 py-2 text-[13px] text-[#cf222e]">{error}</p>
            <button onClick={() => setRetry(value => value + 1)} className="mt-4 w-full rounded-md bg-[#0969da] py-2 text-sm font-medium text-white hover:bg-[#0550ae]">重试</button>
          </>
        ) : <p role="status" className="mt-4 text-sm text-[#656d76]">正在登录…</p>}
        <Link href="/login?local=1" className="mt-4 block text-center text-sm text-[#0969da] hover:underline">账号登录</Link>
      </div>
    </div>
  );
}
