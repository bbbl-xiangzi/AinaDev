"use client";
import { useEffect, useState } from "react";
import { http } from "@/lib/api";
import type { SdkPageConfig } from "@/lib/sdk-pages";

export function SdkPagesPanel() {
  const [pages, setPages] = useState<SdkPageConfig[]>([]);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  useEffect(() => { http.get("/admin/sdk-pages").then(d => { setPages(d.pages); setReady(true); }).catch(() => setMessage("加载失败，请刷新重试")); }, []);
  function update(index: number, change: Partial<SdkPageConfig>) {
    setPages(old => old.map((page, i) => i === index ? { ...page, ...change } : page));
  }
  return <form onSubmit={async e => {
    e.preventDefault(); setBusy(true); setMessage("");
    try { const d = await http.put("/admin/sdk-pages", { pages }); setPages(d.pages); setMessage("已保存，刷新社区导航后生效"); }
    catch (e) { setMessage(e instanceof Error ? e.message : "保存失败"); }
    finally { setBusy(false); }
  }} className="space-y-4">
    <p className="text-sm text-[#656d76]">添加 SDK 页面并显示在社区导航中。当前支持 HiAgent Web SDK；地址由用户浏览器访问。AppKey 必须是可公开的浏览器端应用标识，请勿填写服务端密钥。</p>
    <fieldset disabled={!ready || busy} className="space-y-4">
      {pages.map((p, i) => <section key={i} className="space-y-3 rounded-lg border border-[#d0d7de] bg-white p-4">
        <div className="flex items-center justify-between"><strong>页面 {i + 1} · HiAgent SDK</strong><button type="button" onClick={() => setPages(old => old.filter((_, n) => n !== i))} className="text-sm text-[#cf222e]">移除页面</button></div>
        <div className="grid gap-3 md:grid-cols-2">
          {([
            ["title", "页面名称", "智能问答"], ["slug", "页面标识（小写字母开头）", "assistant"],
            ["base_url", "平台地址", "https://agent.example.com"], ["sdk_url", "SDK 脚本地址", "https://agent.example.com/resources/product/llm/public/sdk/embedFull.js"],
            ["app_key", "浏览器端 AppKey", "应用公开标识"],
          ] as const).map(([key, label, placeholder]) => <label key={key} className="text-sm">{label}<input required maxLength={key === "title" ? 60 : key === "slug" ? 48 : key === "app_key" ? 256 : 2048} pattern={key === "slug" ? "[a-z][a-z0-9-]{0,47}" : undefined} type={key.endsWith("url") ? "url" : "text"} value={p[key]} placeholder={placeholder} onChange={e => update(i, { [key]: e.target.value })} className="mt-1 w-full rounded border border-[#d0d7de] px-3 py-2" /></label>)}
        </div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={p.enabled} onChange={e => update(i, { enabled: e.target.checked })} />启用页面</label>
        <p className="text-xs text-[#656d76]">入口：/sdk/{p.slug || "页面标识"}。SDK 在隔离框架运行，需支持跨域请求；不兼容的 SDK 请通过平台原站使用。</p>
      </section>)}
      <div className="flex gap-3"><button type="button" disabled={pages.length >= 20} onClick={() => setPages(old => [...old, { slug: "", title: "", provider: "hiagent", enabled: false, base_url: "", sdk_url: "", app_key: "" }])} className="rounded border border-[#d0d7de] px-4 py-2 text-sm">添加页面</button><button className="rounded bg-[#0969da] px-4 py-2 text-sm text-white">{busy ? "保存中…" : "保存配置"}</button></div>
    </fieldset>
    <p role="status" className="text-sm">{message}</p>
  </form>;
}
