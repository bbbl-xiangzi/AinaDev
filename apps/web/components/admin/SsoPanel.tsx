"use client";

import { useEffect, useState } from "react";
import { http } from "@/lib/api";

/** SSO（企业统一身份登录）配置面板：标准 OIDC 授权码 + PKCE。
 *  社区 = SP，企业客户应用中台 = IDP。一套部署对接一家企业客户。 */
export function SsoPanel() {
  const [cfg, setCfg] = useState<any>(null);
  const [secret, setSecret] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    http.get("/admin/sso/config").then(setCfg).catch((e) => setError(e.message || "加载失败"));
  }, []);

  const set = (patch: any) => setCfg({ ...cfg, ...patch });

  const save = async () => {
    setSaving(true);
    setError("");
    try {
      await http.put("/admin/sso/config", {
        enabled: !!cfg.enabled,
        label: cfg.label || null,
        issuer: cfg.issuer || null,
        client_id: cfg.client_id || null,
        client_secret: secret || null,
        authorization_endpoint: cfg.authorization_endpoint || null,
        token_endpoint: cfg.token_endpoint || null,
        jwks_uri: cfg.jwks_uri || null,
        userinfo_endpoint: cfg.userinfo_endpoint || null,
        scopes: cfg.scopes || null,
        bind_rule: cfg.bind_rule || "email",
        auto_provision: !!cfg.auto_provision,
        extract_employee: !!cfg.extract_employee,
        claim_sub: cfg.claim_sub || null,
        claim_email: cfg.claim_email || null,
        claim_name: cfg.claim_name || null,
      });
      setSecret("");
      alert("SSO 配置已保存");
    } catch (e: any) {
      setError(e.message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const test = async () => {
    setTesting(true);
    setError("");
    try {
      const r: any = await http.post("/admin/sso/config/test", {
        issuer: cfg.issuer || null,
        client_id: cfg.client_id || null,
        client_secret: secret || null,
        authorization_endpoint: cfg.authorization_endpoint || null,
        token_endpoint: cfg.token_endpoint || null,
        jwks_uri: cfg.jwks_uri || null,
        userinfo_endpoint: cfg.userinfo_endpoint || null,
      });
      setTestResult(r);
    } catch (e: any) {
      setTestResult({ ok: false, message: e.message || "测试失败", details: null });
    } finally {
      setTesting(false);
    }
  };

  const copyRedirect = async () => {
    try {
      await navigator.clipboard.writeText(cfg.redirect_uri || "");
      alert("回调地址已复制");
    } catch {
      alert("复制失败，请手动复制");
    }
  };

  if (!cfg) {
    return <div className="rounded-lg border border-[#d0d7de] bg-white p-6 text-[13px] text-[#656d76]">加载中…</div>;
  }

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-[15px] font-semibold">企业统一身份登录（SSO / OIDC）</h3>
          <label className="flex items-center gap-2 text-[13px]">
            <input type="checkbox" checked={!!cfg.enabled} onChange={(e) => set({ enabled: e.target.checked })} className="h-4 w-4" />
            <span className={cfg.enabled ? "font-medium text-[#1a7f37]" : "text-[#656d76]"}>启用（登录页显示企业统一登录入口）</span>
          </label>
        </div>
        <p className="mb-4 text-[12px] leading-relaxed text-[#656d76]">
          社区作为服务提供方（SP），对接企业客户统一身份提供方（IDP），采用标准 OIDC 授权码 + PKCE 流程。
          一套部署只对接一家企业客户。员工通过企业账号首次登录自动开通社区账号（免注册），
          员工扩展信息（部门/职位等）由 SSO 携带的 claims 映射 + 大模型按事实抽取（杜绝猜测，可追溯）。
        </p>

        <div className="mb-3 rounded-md border border-[#d0d7de] bg-[#f6f8fa] px-3 py-2">
          <div className="text-[12px] text-[#656d76]">回调地址 Redirect URI（需配置到企业 IDP 的授权回调白名单）</div>
          <div className="mt-1 flex items-center gap-2">
            <code className="min-w-0 flex-1 truncate font-mono text-[13px] text-[#0969da]">{cfg.redirect_uri}</code>
            <button onClick={copyRedirect} className="shrink-0 rounded-md border border-[#d0d7de] px-2 py-1 text-[12px] text-[#24292f] hover:bg-[#eaeef2]">
              复制
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <label className="mb-1 block text-[12px] text-[#656d76]">IDP Issuer URL（自动发现 OIDC 端点，如 https://sso.corp.com）</label>
            <input value={cfg.issuer || ""} onChange={(e) => set({ issuer: e.target.value })} placeholder="https://企业应用中台地址" className="w-full rounded border border-[#d0d7de] px-2 py-1.5 font-mono text-sm" />
          </div>
          <div>
            <label className="mb-1 block text-[12px] text-[#656d76]">Client ID（企业 IDP 颁发）</label>
            <input value={cfg.client_id || ""} onChange={(e) => set({ client_id: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 font-mono text-sm" />
          </div>
          <div>
            <label className="mb-1 block text-[12px] text-[#656d76]">Client Secret（AES 加密存储，留空保持不变）</label>
            <input type="password" value={secret} onChange={(e) => setSecret(e.target.value)} placeholder={cfg.has_client_secret ? "已配置（如需更换请重新输入）" : "未配置"} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 font-mono text-sm" />
          </div>
          <div>
            <label className="mb-1 block text-[12px] text-[#656d76]">Scopes</label>
            <input value={cfg.scopes || ""} onChange={(e) => set({ scopes: e.target.value })} placeholder="openid profile email" className="w-full rounded border border-[#d0d7de] px-2 py-1.5 font-mono text-sm" />
          </div>
          <div>
            <label className="mb-1 block text-[12px] text-[#656d76]">账号绑定规则</label>
            <select value={cfg.bind_rule || "email"} onChange={(e) => set({ bind_rule: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm">
              <option value="email">按邮箱匹配（email 一致即绑定已有账号）</option>
              <option value="sub">按 IDP 唯一标识匹配（sub）</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-[12px] text-[#656d76]">登录页按钮文案</label>
            <input value={cfg.label || ""} onChange={(e) => set({ label: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
          </div>
          <div className="flex items-end gap-4 pb-1">
            <label className="flex items-center gap-2 text-[13px]">
              <input type="checkbox" checked={!!cfg.auto_provision} onChange={(e) => set({ auto_provision: e.target.checked })} className="h-4 w-4" />
              首登自动开通账号（免注册）
            </label>
            <label className="flex items-center gap-2 text-[13px]">
              <input type="checkbox" checked={!!cfg.extract_employee} onChange={(e) => set({ extract_employee: e.target.checked })} className="h-4 w-4" />
              员工扩展信息 AI 抽取
            </label>
          </div>
          <div>
            <label className="mb-1 block text-[12px] text-[#656d76]">OIDC 端点（可选，不填则由 Issuer 自动发现）</label>
            <div className="grid grid-cols-2 gap-2">
              <input value={cfg.authorization_endpoint || ""} onChange={(e) => set({ authorization_endpoint: e.target.value })} placeholder="authorization_endpoint" className="w-full rounded border border-[#d0d7de] px-2 py-1.5 font-mono text-[12px]" />
              <input value={cfg.token_endpoint || ""} onChange={(e) => set({ token_endpoint: e.target.value })} placeholder="token_endpoint" className="w-full rounded border border-[#d0d7de] px-2 py-1.5 font-mono text-[12px]" />
              <input value={cfg.jwks_uri || ""} onChange={(e) => set({ jwks_uri: e.target.value })} placeholder="jwks_uri" className="w-full rounded border border-[#d0d7de] px-2 py-1.5 font-mono text-[12px]" />
              <input value={cfg.userinfo_endpoint || ""} onChange={(e) => set({ userinfo_endpoint: e.target.value })} placeholder="userinfo_endpoint" className="w-full rounded border border-[#d0d7de] px-2 py-1.5 font-mono text-[12px]" />
            </div>
          </div>
        </div>

        <div className="mt-3 rounded-md border border-[#eaeef2] bg-[#f6f8fa] px-3 py-2">
          <div className="mb-1 text-[12px] text-[#656d76]">claims 字段名映射（不同 IDP 命名可能不同，可调整）</div>
          <div className="grid grid-cols-3 gap-2">
            <input value={cfg.claim_sub || ""} onChange={(e) => set({ claim_sub: e.target.value })} placeholder="sub（唯一标识）" className="w-full rounded border border-[#d0d7de] px-2 py-1 font-mono text-[12px]" />
            <input value={cfg.claim_email || ""} onChange={(e) => set({ claim_email: e.target.value })} placeholder="email（邮箱）" className="w-full rounded border border-[#d0d7de] px-2 py-1 font-mono text-[12px]" />
            <input value={cfg.claim_name || ""} onChange={(e) => set({ claim_name: e.target.value })} placeholder="name（姓名）" className="w-full rounded border border-[#d0d7de] px-2 py-1 font-mono text-[12px]" />
          </div>
        </div>
      </div>

      {error && <div className="rounded-md bg-[#ffebe9] px-3 py-2 text-[13px] text-[#cf222e]">{error}</div>}

      {testResult && (
        <div className={`rounded-lg border px-4 py-3 ${testResult.ok ? "border-[#d0d7de] bg-[#f6f8fa]" : "border-[#ffcecb] bg-[#ffebe9]"}`}>
          <div className={`text-[13px] font-medium ${testResult.ok ? "text-[#1a7f37]" : "text-[#cf222e]"}`}>
            {testResult.ok ? "✅ " : "❌ "}{testResult.message}
          </div>
          {testResult.details && (
            <div className="mt-2 grid grid-cols-2 gap-1 font-mono text-[12px] text-[#57606a]">
              {Object.entries(testResult.details).map(([k, v]) => (
                <div key={k}>
                  <span className="text-[#656d76]">{k}: </span>
                  {String(v)}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="flex gap-3">
        <button onClick={save} disabled={saving || testing} className="rounded-md bg-[#0969da] px-4 py-2 text-sm text-white hover:bg-[#0550ae] disabled:opacity-60">
          {saving ? "保存中…" : "保存配置"}
        </button>
        <button onClick={test} disabled={testing || saving} className="rounded-md border border-[#d0d7de] px-4 py-2 text-sm text-[#24292f] hover:bg-[#eaeef2] disabled:opacity-60">
          {testing ? "测试中…" : "测试连接（不保存）"}
        </button>
      </div>
    </div>
  );
}
