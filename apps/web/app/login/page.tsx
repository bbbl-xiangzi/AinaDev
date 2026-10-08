"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { http } from "@/lib/api";

export default function LoginPage() {
  const { login, register } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [invite, setInvite] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [sso, setSso] = useState<{ enabled: boolean; label: string }>({ enabled: false, label: "企业统一身份登录" });

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("sso_error") === "1") {
      setError("企业登录结果验证失败，请重新登录或联系管理员。");
    }
    http
      .get("/auth/sso/status")
      .then((r: any) => setSso({ enabled: !!r.enabled, label: r.label || "企业统一身份登录" }))
      .catch(() => {});
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, name, password, invite);
      router.push("/");
    } catch (err: any) {
      setError(err.message || "操作失败");
    } finally {
      setLoading(false);
    }
  };

  const ssoLogin = () => {
    const attempt = window.crypto.randomUUID();
    sessionStorage.setItem("community_sso_attempt", attempt);
    window.location.href = `/api/auth/sso/login?login_attempt=${encodeURIComponent(attempt)}`;
  };

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center px-4">
      <div className="rounded-lg border border-[#d0d7de] bg-white p-8 shadow-sm">
        <h1 className="text-[24px] font-bold text-[#24292f]">AI 开发者社区</h1>
        <p className="mt-1 text-[13px] text-[#656d76]">企业 AI 原生开发者社区 · 内部私有部署</p>
        <div className="mt-6 mb-4 flex gap-1 border-b border-[#d0d7de]">
          {(["login", "register"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`border-b-2 px-3 py-2 text-sm font-medium ${
                mode === m ? "border-[#0969da] text-[#0969da]" : "border-transparent text-[#656d76]"
              }`}
            >
              {m === "login" ? "登录" : "注册"}
            </button>
          ))}
        </div>
        <form onSubmit={submit} className="space-y-3">
          <div>
            <label className="mb-1 block text-[13px] font-medium text-[#24292f]">邮箱</label>
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="w-full rounded-md border border-[#d0d7de] px-3 py-2 text-sm outline-none focus:border-[#0969da]" />
          </div>
          {mode === "register" && (
            <div>
              <label className="mb-1 block text-[13px] font-medium text-[#24292f]">姓名</label>
              <input required value={name} onChange={(e) => setName(e.target.value)} className="w-full rounded-md border border-[#d0d7de] px-3 py-2 text-sm outline-none focus:border-[#0969da]" />
            </div>
          )}
          <div>
            <label className="mb-1 block text-[13px] font-medium text-[#24292f]">密码</label>
            <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className="w-full rounded-md border border-[#d0d7de] px-3 py-2 text-sm outline-none focus:border-[#0969da]" />
          </div>
          {mode === "register" && (
            <div>
              <label className="mb-1 block text-[13px] font-medium text-[#24292f]">邀请码</label>
              <input required value={invite} onChange={(e) => setInvite(e.target.value)} placeholder="由管理员发放" className="w-full rounded-md border border-[#d0d7de] px-3 py-2 text-sm outline-none focus:border-[#0969da]" />
            </div>
          )}
          {error && <div className="rounded-md bg-[#ffebe9] px-3 py-2 text-[13px] text-[#cf222e]">{error}</div>}
          <button disabled={loading} className="w-full rounded-md bg-[#0969da] py-2 text-sm font-medium text-white hover:bg-[#0550ae] disabled:opacity-60">
            {loading ? "处理中…" : mode === "login" ? "登录" : "注册并登录"}
          </button>
        </form>
        {sso.enabled && (
          <div className="mt-4">
            <div className="flex items-center gap-3 text-[12px] text-[#8c959f]">
              <div className="h-px flex-1 bg-[#d0d7de]" />
              <span>或</span>
              <div className="h-px flex-1 bg-[#d0d7de]" />
            </div>
            <button
              onClick={ssoLogin}
              className="mt-4 w-full rounded-md border border-[#d0d7de] bg-white py-2 text-sm font-medium text-[#24292f] hover:border-[#0969da] hover:text-[#0969da]"
            >
              🔐 {sso.label}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
