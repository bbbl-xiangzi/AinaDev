"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { http } from "@/lib/api";
import { startSsoLogin } from "@/lib/sso";

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
  const [branding, setBranding] = useState({
    login_title: "AI 开发者社区",
    login_subtitle: "企业 AI 原生开发者社区 · 内部私有部署",
  });
  const [sso, setSso] = useState<{ enabled: boolean; label: string }>({ enabled: false, label: "企业统一身份登录" });

  useEffect(() => {
    http.get("/admin/site-config-public").then((config: any) => {
      setBranding((current) => ({
        login_title: config.login_title?.trim() || current.login_title,
        login_subtitle: typeof config.login_subtitle === "string" ? config.login_subtitle : current.login_subtitle,
      }));
    }).catch(() => {});
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
    try {
      startSsoLogin();
    } catch {
      setError("无法发起统一登录，请允许浏览器存储后重试。");
    }
  };

  return (
    <div className="mx-auto flex min-h-[76vh] py-8 max-w-[440px] flex-col justify-center px-4">
      <div className="rounded-xl border border-[#d0d7de]/70 bg-white p-6 shadow-sm sm:p-8">
        <h1 className="break-words text-[22px] font-bold text-[#24292f]">{branding.login_title}</h1>
        {branding.login_subtitle && <p className="mt-1 break-words text-[13px] text-[#656d76]">{branding.login_subtitle}</p>}
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
        {sso.enabled && (
          <div className="mt-4">
            <button
              onClick={ssoLogin}
              className="w-full break-words rounded-md border border-[#0969da] bg-[#0969da] px-3 py-2 text-sm font-medium text-white hover:border-[#0550ae] hover:bg-[#0550ae]"
            >
              🔐 {sso.label}
            </button>
          </div>
        )}
        <form onSubmit={submit} className="mt-5 space-y-4">
          <div>
            <label className="mb-1 block text-[13px] font-medium text-[#24292f]">邮箱</label>
            <input aria-label="邮箱" autoComplete="email" placeholder="输入您的邮箱" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="w-full rounded-md border border-[#d0d7de] px-3 py-2.5 text-sm outline-none focus:border-[#0969da]" />
          </div>
          {mode === "register" && (
            <div>
              <label className="mb-1 block text-[13px] font-medium text-[#24292f]">姓名</label>
              <input required value={name} onChange={(e) => setName(e.target.value)} className="w-full rounded-md border border-[#d0d7de] px-3 py-2.5 text-sm outline-none focus:border-[#0969da]" />
            </div>
          )}
          <div>
            <label className="mb-1 block text-[13px] font-medium text-[#24292f]">密码</label>
            <input aria-label="密码" autoComplete={mode === "login" ? "current-password" : "new-password"} placeholder="输入密码" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className="w-full rounded-md border border-[#d0d7de] px-3 py-2.5 text-sm outline-none focus:border-[#0969da]" />
          </div>
          {mode === "register" && (
            <div>
              <label className="mb-1 block text-[13px] font-medium text-[#24292f]">邀请码</label>
              <input required value={invite} onChange={(e) => setInvite(e.target.value)} placeholder="由管理员发放" className="w-full rounded-md border border-[#d0d7de] px-3 py-2.5 text-sm outline-none focus:border-[#0969da]" />
            </div>
          )}
          {error && <div className="rounded-md bg-[#ffebe9] px-3 py-2 text-[13px] text-[#cf222e]">{error}</div>}
          <button disabled={loading} className={`w-full rounded-md py-2.5 text-sm font-medium disabled:opacity-60 ${mode === "login" ? "border border-[#d0d7de] bg-white text-[#24292f] hover:border-[#0969da] hover:text-[#0969da]" : "bg-[#0969da] text-white hover:bg-[#0550ae]"}`}>
            {loading ? "处理中…" : mode === "login" ? "登录" : "注册并登录"}
          </button>
        </form>

      </div>
    </div>
  );
}
