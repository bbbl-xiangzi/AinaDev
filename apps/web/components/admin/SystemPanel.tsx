"use client";

import { useEffect, useState } from "react";
import { http } from "@/lib/api";
import { formatAuditTime } from "@/lib/audit-time";
import { LoginCardFields } from "./LoginCardFields";

export function SystemPanel() {
  const [stats, setStats] = useState<any>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [runs, setRuns] = useState<any>({ items: [] });
  const [site, setSite] = useState<any>({});
  const [traceId, setTraceId] = useState("");

  const reload = () => {
    http.get("/admin/stats").then(setStats).catch(() => {});
    http.get("/admin/audit-logs?page_size=20").then(setLogs).catch(() => {});
    http.get("/admin/agent-runs?page_size=15").then(setRuns).catch(() => {});
    http.get("/admin/site-config").then(setSite).catch(() => {});
  };
  useEffect(reload, []);

  const saveSite = async () => {
    await http.put("/admin/site-config", {
      site_name: site.site_name || null,
      login_title: site.login_title,
      auto_sso_login: String(site.auto_sso_login).toLowerCase() === "true",
      login_subtitle: site.login_subtitle,
      site_description: site.site_description || null,
      mcp_api_key: site.mcp_api_key || null,
      upload_allowed_types: site.upload_allowed_types || null,
      upload_max_size_mb: site.upload_max_size_mb ? Number(site.upload_max_size_mb) : null,
    });
    alert("已保存（MCP 令牌修改后需更新豆包工作配置）");
  };

  return (
    <div className="space-y-6">
      {stats && (
        <div className="grid grid-cols-4 gap-3">
          {[
            ["用户", stats.user_count], ["帖子", stats.post_count], ["回复", stats.reply_count], ["今日新帖", stats.today_posts],
            ["待审", stats.pending_reviews], ["举报", stats.open_reports], ["AI 回复", stats.ai_replies], ["知识文档", stats.doc_count],
          ].map(([label, value]) => (
            <div key={label as string} className="rounded-lg border border-[#d0d7de] bg-white p-4">
              <div className="text-[12px] text-[#656d76]">{label}</div>
              <div className="mt-1 text-[24px] font-semibold">{value}</div>
            </div>
          ))}
        </div>
      )}

      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <h3 className="mb-2 text-[15px] font-semibold">MCP 接入信息（供豆包工作配置）</h3>
        <div className="space-y-1 rounded-md bg-[#f6f8fa] p-3 font-mono text-[13px]">
          <div>服务器 URL：<span className="text-[#0969da]">{window.location.origin}/mcp</span></div>
          <div>传输类型：<span className="text-[#0969da]">HTTP（Streamable）</span></div>
          <div>Authorization：<span className="text-[#0969da]">Bearer {site.mcp_api_key || "（未设置）"}</span></div>
        </div>
        <p className="mt-2 text-[12px] text-[#656d76]">同事可在豆包工作中添加 MCP 服务器，接入后即可调用：合规审查、知识库检索、帖子/栏目管理、审核处置、每日资讯、周报、系统统计等工具。</p>
      </div>

      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <h3 className="mb-3 text-[15px] font-semibold">站点配置</h3>
        <div className="grid grid-cols-2 gap-3">
          <LoginCardFields site={site} onChange={(patch) => setSite({ ...site, ...patch })} />
          <div>
            <label className="mb-1 block text-[12px] text-[#656d76]">站点名称</label>
            <input value={site.site_name || ""} onChange={(e) => setSite({ ...site, site_name: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
          </div>
          <div>
            <label className="mb-1 block text-[12px] text-[#656d76]">站点描述</label>
            <input value={site.site_description || ""} onChange={(e) => setSite({ ...site, site_description: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
          </div>
          <div>
            <label className="mb-1 block text-[12px] text-[#656d76]">MCP 访问令牌</label>
            <input value={site.mcp_api_key || ""} onChange={(e) => setSite({ ...site, mcp_api_key: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 font-mono text-sm" />
          </div>
          <div>
            <label className="mb-1 block text-[12px] text-[#656d76]">附件允许格式（逗号分隔）</label>
            <input value={site.upload_allowed_types || ""} onChange={(e) => setSite({ ...site, upload_allowed_types: e.target.value })} placeholder="png,jpg,jpeg,gif,webp,pdf,doc,docx,xls,xlsx,txt,md,csv,zip" className="w-full rounded border border-[#d0d7de] px-2 py-1.5 font-mono text-sm" />
          </div>
          <div>
            <label className="mb-1 block text-[12px] text-[#656d76]">单文件大小上限（MB）</label>
            <input type="number" min={1} max={100} value={site.upload_max_size_mb || ""} onChange={(e) => setSite({ ...site, upload_max_size_mb: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
          </div>
        </div>
        <button onClick={saveSite} className="mt-3 rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white">保存配置</button>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
          <h3 className="mb-2 text-[15px] font-semibold">Agent 执行记录（审计）</h3>
          <div className="mb-2 flex gap-2">
            <input value={traceId} onChange={(e) => setTraceId(e.target.value)} placeholder="trace_id 查询" className="flex-1 rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
            <button onClick={() => http.get(`/admin/agent-runs?trace_id=${traceId}`).then(setRuns)} className="rounded border border-[#d0d7de] px-2 py-1.5 text-sm">查询</button>
          </div>
          <table className="w-full text-[12px]">
            <tbody>
              {runs.items.map((r: any) => (
                <tr key={r.id} className="border-b border-[#d0d7de]/50">
                  <td className="py-1.5 font-mono">{r.trace_id.slice(0, 8)}</td>
                  <td className="py-1.5">{r.node}</td>
                  <td className="py-1.5">{r.decision}</td>
                  <td className="py-1.5">{r.score ?? "-"}</td>
                  <td className="py-1.5 text-[#656d76]">{r.latency_ms}ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
          <h3 className="mb-2 text-[15px] font-semibold">操作审计日志（北京时间）</h3>
          <table className="w-full text-[12px]">
            <tbody>
              {logs.map((l) => (
                <tr key={l.id} className="border-b border-[#d0d7de]/50">
                  <td className="py-1.5">{l.action}</td>
                  <td className="py-1.5 text-[#656d76]">{l.actor_type}{l.actor_id ? `#${l.actor_id}` : ""}</td>
                  <td className="py-1.5 font-mono text-[11px]">{formatAuditTime(l.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
