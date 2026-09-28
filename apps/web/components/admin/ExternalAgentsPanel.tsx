"use client";

import { useEffect, useState } from "react";
import { http } from "@/lib/api";
import { Modal } from "@/components/ui/Modal";

type Agent = {
  id: number; name: string; protocol: string; api_url: string;
  model?: string; headers_json?: any; request_template?: string;
  response_path?: string; timeout_seconds: number; enabled: boolean; has_api_key?: boolean;
};

const PROTOCOLS: { value: string; label: string; hint: string }[] = [
  { value: "openai_compatible", label: "OpenAI 兼容（HiAgent / 方舟 / 大多数平台）", hint: "API URL 填 /chat/completions 完整地址，如 https://ark.cn-beijing.volces.com/api/v3/chat/completions" },
  { value: "dify_chatflow", label: "Dify 对话型应用（Chatflow）", hint: "API URL 填应用 API 基础地址，如 https://api.dify.ai/v1；回复取响应 answer 字段" },
  { value: "dify_workflow", label: "Dify 工作流（Workflow）", hint: "API URL 填应用 API 基础地址，如 https://api.dify.ai/v1；回复默认取 data.outputs.text" },
  { value: "custom_http", label: "自定义 HTTP（通用兜底）", hint: "请求体用 JSON 模板（支持 {title} {body} {author_name} {category_name}），响应用点分路径提取文本" },
];

const empty = (): Agent => ({
  id: 0, name: "", protocol: "openai_compatible", api_url: "", model: "",
  headers_json: undefined, request_template: "", response_path: "", timeout_seconds: 60, enabled: true,
});

export function ExternalAgentsPanel() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [editing, setEditing] = useState<Agent | null>(null);
  const [creating, setCreating] = useState<Agent | null>(null);
  const [msg, setMsg] = useState("");

  const reload = () => http.get("/admin/external-agents").then(setAgents).catch(() => {});
  useEffect(() => { reload(); }, []);

  const save = async () => {
    const a = editing || creating;
    if (!a || !a.name || !a.api_url) return alert("名称和 API URL 必填");
    if (a.protocol === "custom_http" && !a.request_template) return alert("自定义 HTTP 需要填写请求体 JSON 模板");
    const payload: any = {
      name: a.name, protocol: a.protocol, api_url: a.api_url,
      model: a.model || null, headers_json: a.headers_json || null,
      request_template: a.request_template || null, response_path: a.response_path || null,
      timeout_seconds: Number(a.timeout_seconds) || 60, enabled: a.enabled,
    };
    try {
      if (editing) {
        await http.put(`/admin/external-agents/${editing.id}`, payload);
        setMsg("已保存");
      } else {
        await http.post("/admin/external-agents", payload);
        setMsg("已创建");
      }
      setEditing(null); setCreating(null);
      reload();
    } catch (e: any) {
      alert(e.message || "保存失败");
    }
  };

  const remove = async (a: Agent) => {
    if (!confirm(`删除外部回帖源「${a.name}」？绑定它的栏目将恢复为内置 AI 管理员。`)) return;
    await http.del(`/admin/external-agents/${a.id}`);
    reload();
  };

  return (
    <div className="space-y-4">
      {msg && <div className="rounded-md bg-[#dafbe1] px-3 py-2 text-[13px] text-[#1a7f37]">{msg}</div>}

      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h3 className="text-[15px] font-semibold">外部回帖源（第三方 Agent）</h3>
            <p className="mt-1 text-[12px] text-[#656d76]">
              在栏目「AI 配置」中绑定外部回帖源后，新帖发布 / 楼主追问会自动调用该 Agent 回帖；回复内容会先经过 AI 审核（违规 + 主题相关性）。
              外部调用失败时不会回退内置 AI，会通知管理员人工回复并给出失败码。
            </p>
          </div>
          <button
            onClick={() => setCreating(empty())}
            className="rounded-md bg-[#0969da] px-4 py-2 text-[13px] text-white hover:bg-[#0550ae]"
          >
            + 新建回帖源
          </button>
        </div>

        {agents.length === 0 ? (
          <div className="py-10 text-center text-[13px] text-[#656d76]">暂无外部回帖源 · 点击右上角新建</div>
        ) : (
          <div className="space-y-2">
            {agents.map((a) => {
              const p = PROTOCOLS.find((x) => x.value === a.protocol);
              return (
                <div key={a.id} className="flex items-center gap-3 rounded-md border border-[#d0d7de]/60 p-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[13px] font-medium">{a.name}</span>
                      <span className="rounded bg-[#eaeef2] px-1.5 py-0.5 text-[11px] text-[#656d76]">{p?.label.split("（")[0] || a.protocol}</span>
                      {!a.enabled && <span className="rounded bg-[#ffebe9] px-1.5 py-0.5 text-[11px] text-[#cf222e]">已停用</span>}
                    </div>
                    <div className="mt-0.5 truncate text-[12px] text-[#656d76]">{a.api_url}</div>
                  </div>
                  <div className="shrink-0 text-[12px] text-[#656d76]">{a.has_api_key ? "已配置 Key" : "无 Key"}</div>
                  <div className="flex shrink-0 gap-1.5">
                    <button onClick={() => setEditing({ ...a })} className="rounded border border-[#d0d7de] px-2 py-1 text-[12px] hover:bg-[#f3f4f6]">编辑</button>
                    <button onClick={() => remove(a)} className="rounded border border-[#d0d7de] px-2 py-1 text-[12px] text-[#cf222e] hover:bg-[#ffebe9]">删除</button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 新建 / 编辑（模态） */}
      <Modal open={!!(creating || editing)} title={creating ? "新建外部回帖源" : "编辑外部回帖源"} width={680} onClose={() => { setCreating(null); setEditing(null); }}>
        {(creating || editing) && (
          <AgentForm
            agent={creating || editing!}
            onChange={(a) => (creating ? setCreating(a) : setEditing(a))}
            onSave={save}
            onCancel={() => { setCreating(null); setEditing(null); }}
          />
        )}
      </Modal>
    </div>
  );
}

function AgentForm({ agent, onChange, onSave, onCancel }: { agent: Agent; onChange: (a: Agent) => void; onSave: () => void; onCancel: () => void }) {
  const p = PROTOCOLS.find((x) => x.value === agent.protocol);
  const set = (k: string, v: any) => onChange({ ...agent, [k]: v });
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="mb-1 block text-[12px] text-[#656d76]">名称</label>
          <input value={agent.name} onChange={(e) => set("name", e.target.value)} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" placeholder="如：Dify 技术答疑 Agent" />
        </div>
        <div>
          <label className="mb-1 block text-[12px] text-[#656d76]">协议类型</label>
          <select value={agent.protocol} onChange={(e) => set("protocol", e.target.value)} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm">
            {PROTOCOLS.map((x) => <option key={x.value} value={x.value}>{x.label}</option>)}
          </select>
        </div>
      </div>
      {p && <div className="rounded-md bg-[#ddf4ff] px-3 py-2 text-[12px] text-[#0969da]">{p.hint}</div>}

      <div>
        <label className="mb-1 block text-[12px] text-[#656d76]">API URL（完整端点地址）</label>
        <input value={agent.api_url} onChange={(e) => set("api_url", e.target.value)} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" placeholder="https://..." />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="mb-1 block text-[12px] text-[#656d76]">API Key（留空保持原值）</label>
          <input type="password" placeholder={agent.has_api_key ? "已配置（留空不修改）" : "sk-..."} onChange={(e) => set("api_key", e.target.value)} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
        </div>
        <div>
          <label className="mb-1 block text-[12px] text-[#656d76]">模型名（OpenAI 兼容用）</label>
          <input value={agent.model || ""} onChange={(e) => set("model", e.target.value)} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" placeholder="如 deepseek-chat" />
        </div>
      </div>

      {agent.protocol === "custom_http" && (
        <div>
          <label className="mb-1 block text-[12px] text-[#656d76]">
            请求体 JSON 模板（支持 {"{title}"} {"{body}"} {"{author_name}"} {"{category_name}"} 变量）
          </label>
          <textarea
            value={agent.request_template || ""}
            onChange={(e) => set("request_template", e.target.value)}
            rows={4}
            className="w-full rounded border border-[#d0d7de] px-2 py-1.5 font-mono text-[12px]"
            placeholder={'{"query": "{title}\n{body}", "user": "community"}'}
          />
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="mb-1 block text-[12px] text-[#656d76]">响应文本提取路径（点分，可空用默认）</label>
          <input value={agent.response_path || ""} onChange={(e) => set("response_path", e.target.value)} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" placeholder="如 data.outputs.text / choices.0.message.content" />
        </div>
        <div>
          <label className="mb-1 block text-[12px] text-[#656d76]">超时（秒）</label>
          <input type="number" min={5} max={300} value={agent.timeout_seconds} onChange={(e) => set("timeout_seconds", Number(e.target.value))} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
        </div>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={agent.enabled} onChange={(e) => set("enabled", e.target.checked)} /> 启用
      </label>
      <div className="flex justify-end gap-2 pt-2">
        <button onClick={onCancel} className="rounded border border-[#d0d7de] px-3 py-1.5 text-[13px]">取消</button>
        <button onClick={onSave} className="rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white">保存</button>
      </div>
    </div>
  );
}
