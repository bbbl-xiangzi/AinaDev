"use client";

import { useEffect, useState } from "react";
import { http } from "@/lib/api";
import { formatAuditTime } from "@/lib/audit-time";

const PAGE_SIZE = 20;
type AuditRow = { id: number; actor_type: string; actor_id?: number; action: string; created_at: string };

export function AuditPanel() {
  const [logs, setLogs] = useState<AuditRow[]>([]);
  const [page, setPage] = useState(1);
  const [request, setRequest] = useState({ page: 1, action: "" });
  const [keyword, setKeyword] = useState("");
  const [appliedAction, setAppliedAction] = useState("");
  const [jumpPage, setJumpPage] = useState("");
  const [pageMessage, setPageMessage] = useState("");
  const [hasNext, setHasNext] = useState(false);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [runs, setRuns] = useState<any>({ items: [] });
  const [traceId, setTraceId] = useState("");

  function requestPage(page: number, action: string) {
    setLoading(true);
    setPageMessage("");
    setRequest({ page, action });
  }

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setFailed(false);
      setPageMessage("");
      try {
        const filter = `&action=${encodeURIComponent(request.action)}`;
        const rows = await http.get<AuditRow[]>(`/admin/audit-logs?page=${request.page}&page_size=${PAGE_SIZE}${filter}`);
        // The list endpoint returns no total. Check just the first row after a full page.
        const next = rows.length === PAGE_SIZE && (await http.get<AuditRow[]>(
          `/admin/audit-logs?page=${request.page * PAGE_SIZE + 1}&page_size=1${filter}`
        )).length > 0;
        if (active) {
          if (!rows.length && request.page > 1) {
            setPageMessage("该页没有记录，请输入较小的页码");
            return;
          }
          setAppliedAction(request.action);
          setLogs(rows);
          setPage(request.page);
          setHasNext(next);
        }
      } catch {
        if (active) setFailed(true);
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, [request]);

  useEffect(() => {
    http.get("/admin/agent-runs?page_size=15").then(setRuns).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <h3 className="mb-2 text-[15px] font-semibold">Agent 执行记录（流水线全链路审计）</h3>
        <div className="mb-2 flex gap-2">
          <input value={traceId} onChange={(e) => setTraceId(e.target.value)} placeholder="trace_id 查询" className="flex-1 rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
          <button onClick={() => http.get(`/admin/agent-runs?trace_id=${traceId}`).then(setRuns)} className="rounded border border-[#d0d7de] px-2 py-1.5 text-sm">查询</button>
        </div>
        <table className="w-full text-[12px]">
          <thead>
            <tr className="border-b border-[#d0d7de] text-left text-[#656d76]">
              <th className="py-1.5 pr-2">trace</th><th className="py-1.5 pr-2">节点</th><th className="py-1.5 pr-2">决策</th><th className="py-1.5 pr-2">评分</th><th className="py-1.5">耗时</th>
            </tr>
          </thead>
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
        <h3 className="mb-2 text-[15px] font-semibold">操作审计日志</h3>
        <form className="mb-3 flex flex-wrap gap-2" onSubmit={e => {
          e.preventDefault();
          requestPage(1, keyword.trim());
        }}>
          <input type="search" aria-label="搜索操作名称" placeholder="搜索操作名称" value={keyword} onChange={e => setKeyword(e.target.value)} className="min-w-0 rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
          <button className="rounded border border-[#d0d7de] px-3 text-sm">搜索</button>
          {(keyword || appliedAction) && <button type="button" onClick={() => {
            setKeyword("");
            requestPage(1, "");
          }} className="text-sm text-[#0969da]">清除</button>}
        </form>
        <table className="w-full text-[12px]">
          <thead>
            <tr className="border-b border-[#d0d7de] text-left text-[#656d76]">
              <th className="py-1.5 pr-2">操作</th><th className="py-1.5 pr-2">操作用户</th><th className="py-1.5">时间（北京时间）</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((l) => (
              <tr key={l.id} className="border-b border-[#d0d7de]/50">
                <td className="py-1.5">{l.action}</td>
                <td className="py-1.5 text-[#656d76]">{l.actor_type}{l.actor_id ? `#${l.actor_id}` : ""}</td>
                <td className="whitespace-nowrap py-1.5 tabular-nums">{formatAuditTime(l.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {failed && <p role="alert" className="mt-2 text-sm">日志加载失败 <button className="text-[#0969da]" onClick={() => requestPage(request.page, request.action)}>重试</button></p>}
        {!failed && !loading && logs.length === 0 && <p className="py-2 text-sm text-[#656d76]">暂无操作记录</p>}
        <nav aria-label="操作审计日志分页" className="mt-4 flex flex-wrap items-center justify-center gap-4 text-sm">
          <button disabled={loading || page === 1} onClick={() => requestPage(page - 1, appliedAction)} className="text-[#0969da] disabled:opacity-40">上一页</button>
          <span aria-live="polite">{loading ? "加载中…" : `第 ${page} 页`}</span>
          <button disabled={loading || !hasNext} onClick={() => requestPage(page + 1, appliedAction)} className="text-[#0969da] disabled:opacity-40">下一页</button>
          <form className="flex items-center gap-2" onSubmit={e => {
            e.preventDefault();
            const target = Number(jumpPage);
            if (Number.isSafeInteger(target) && target > 0) requestPage(target, appliedAction);
          }}>
            <input type="number" disabled={loading} required min="1" max="2147483647" step="1" aria-label="目标页码" placeholder="页码" value={jumpPage} onChange={e => setJumpPage(e.target.value)} className="w-20 rounded border border-[#d0d7de] px-2 py-1" />
            <button disabled={loading} className="text-[#0969da] disabled:opacity-40">跳转</button>
          </form>
        </nav>
        {pageMessage && <p role="status" className="mt-2 text-center text-sm text-[#656d76]">{pageMessage}</p>}
      </div>
    </div>
  );
}
