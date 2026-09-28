"use client";

import { useEffect, useState } from "react";
import { http } from "@/lib/api";
import { Modal } from "@/components/ui/Modal";
import { EmojiPicker } from "@/components/EmojiPicker";

type Cat = {
  id: number; slug: string; name: string; description?: string; icon?: string;
  sort_order: number; allow_post: boolean; post_permission: string; auto_reply_enabled: boolean;
  reply_threshold: number; notify_human_on_no_evidence: boolean;
  external_agent_id?: number | null; external_agent_name?: string | null;
  relevance_check_enabled?: boolean; reply_to_author_questions?: boolean;
  post_count?: number; ai_admin?: any; admins?: { user_id: number; name: string; email: string }[];
};

export function CategoryManager() {
  const [cats, setCats] = useState<Cat[]>([]);
  const [editing, setEditing] = useState<Cat | null>(null);
  const [creating, setCreating] = useState<Cat | null>(null);
  const [aiEditing, setAiEditing] = useState<Cat | null>(null);
  const [adminBinding, setAdminBinding] = useState<Cat | null>(null);
  const [iconPickerFor, setIconPickerFor] = useState<"edit" | "create" | null>(null);
  const [externalAgents, setExternalAgents] = useState<any[]>([]);
  const [msg, setMsg] = useState("");

  const reload = async () => {
    const list: Cat[] = await http.get("/admin/categories");
    for (const c of list) {
      c.admins = await http.get(`/admin/categories/${c.id}/admins`).catch(() => []);
    }
    setCats(list);
  };
  useEffect(() => { reload(); }, []);
  useEffect(() => { http.get("/admin/external-agents").then(setExternalAgents).catch(() => {}); }, []);

  const saveCategory = async () => {
    if (!editing) return;
    await http.put(`/admin/categories/${editing.id}`, {
      name: editing.name, description: editing.description || "",
      icon: editing.icon || "📁", allow_post: editing.post_permission !== "closed",
      post_permission: editing.post_permission,
      auto_reply_enabled: editing.auto_reply_enabled, reply_threshold: Number(editing.reply_threshold),
      notify_human_on_no_evidence: editing.notify_human_on_no_evidence,
      external_agent_id: editing.external_agent_id || null,
      relevance_check_enabled: editing.relevance_check_enabled,
      reply_to_author_questions: editing.reply_to_author_questions,
    });
    setEditing(null);
    setMsg("已保存");
    reload();
  };

  const createCategory = async () => {
    if (!creating) return;
    if (!creating.name || !creating.slug) return alert("名称和 slug 必填");
    await http.post("/admin/categories", { ...creating, reply_threshold: Number(creating.reply_threshold) });
    setCreating(null);
    setMsg("已创建");
    reload();
  };

  const saveAiAdmin = async () => {
    if (!aiEditing) return;
    const aa = aiEditing.ai_admin || {};
    await http.post(`/admin/categories/${aiEditing.id}/ai-admin`, {
      persona_name: aa.persona_name || "",
      system_prompt: aa.system_prompt || "",
      style_prompt: aa.style_prompt || "",
      model_config_id: aa.model_config_id || null,
      reply_threshold: aa.reply_threshold != null ? Number(aa.reply_threshold) : aiEditing.reply_threshold,
      self_review_threshold: aa.self_review_threshold != null ? Number(aa.self_review_threshold) : 0.9,
    });
    setAiEditing(null);
    setMsg("AI 管理员已保存");
    reload();
  };

  return (
    <div className="space-y-4">
      {msg && <div className="rounded-md bg-[#dafbe1] px-3 py-2 text-[13px] text-[#1a7f37]">{msg}</div>}

      <div className="flex justify-end">
        <button
          onClick={() => setCreating({ id: 0, slug: "", name: "", description: "", icon: "📁", sort_order: 0, allow_post: true, post_permission: "public", auto_reply_enabled: true, reply_threshold: 0.5, notify_human_on_no_evidence: true })}
          className="rounded-md bg-[#0969da] px-4 py-2 text-[13px] text-white hover:bg-[#0550ae]"
        >
          + 新建栏目
        </button>
      </div>

      <div className="rounded-lg border border-[#d0d7de] bg-white">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-[#d0d7de] text-left text-[#656d76]">
              <th className="px-4 py-2">栏目</th>
              <th className="py-2">帖子</th>
              <th className="py-2">AI 管理员</th>
              <th className="py-2">人工管理员</th>
              <th className="py-2 pr-4">操作</th>
            </tr>
          </thead>
          <tbody>
            {cats.map((c) => (
              <tr key={c.id} className="border-b border-[#d0d7de]/50">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2 font-medium">{c.icon} {c.name}</div>
                  <div className="text-[12px] text-[#656d76]">{c.slug} · {c.description}</div>
                </td>
                <td className="py-3 text-[#656d76]">{c.post_count}</td>
                <td className="py-3">
                  {c.ai_admin ? (
                    <span className="rounded bg-[#0969da]/10 px-1.5 py-0.5 text-[12px] text-[#0969da]">{c.ai_admin.persona_name}</span>
                  ) : c.external_agent_id ? (
                    <span className="rounded bg-[#7c3aed]/10 px-1.5 py-0.5 text-[12px] text-[#7c3aed]">{c.external_agent_name || "外部 Agent"}</span>
                  ) : <span className="text-[#656d76]">未配置</span>}
                </td>
                <td className="py-3 text-[#656d76]">
                  {c.admins?.length ? c.admins.map((a) => a.name).join("、") : "无"}
                </td>
                <td className="py-3 pr-4">
                  <div className="flex gap-1.5">
                    <button onClick={() => setEditing(c)} className="rounded border border-[#d0d7de] px-2 py-1 text-[12px] hover:bg-[#f3f4f6]">编辑</button>
                    <button onClick={() => setAiEditing(c)} className="rounded border border-[#d0d7de] px-2 py-1 text-[12px] hover:bg-[#f3f4f6]">AI 配置</button>
                    <button onClick={() => setAdminBinding(c)} className="rounded border border-[#d0d7de] px-2 py-1 text-[12px] hover:bg-[#f3f4f6]">绑定管理员</button>
                    <button onClick={async () => { if (confirm(`删除栏目「${c.name}」？`)) { await http.del(`/admin/categories/${c.id}`); reload(); } }} className="rounded border border-[#d0d7de] px-2 py-1 text-[12px] text-[#cf222e] hover:bg-[#ffebe9]">删除</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 编辑栏目（模态） */}
      <Modal open={!!editing} title="编辑栏目" width={560} onClose={() => setEditing(null)}>
        {editing && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">名称</label>
                <input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
              </div>
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">图标</label>
                <button
                  type="button"
                  onClick={() => setIconPickerFor("edit")}
                  className="flex h-9 w-full items-center gap-2 rounded border border-[#d0d7de] px-2 text-sm hover:border-[#0969da]"
                >
                  <span className="text-[18px]">{editing.icon || "📁"}</span>
                  <span className="text-[#656d76]">点击选择</span>
                </button>
              </div>
            </div>
            <div>
              <label className="mb-1 block text-[12px] text-[#656d76]">描述</label>
              <textarea value={editing.description || ""} onChange={(e) => setEditing({ ...editing, description: e.target.value })} rows={2} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">发帖权限</label>
                <select
                  value={editing.post_permission || "public"}
                  onChange={(e) => setEditing({ ...editing, post_permission: e.target.value })}
                  className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm"
                >
                  <option value="public">公开（所有成员可发）</option>
                  <option value="staff_only">仅管理员可发</option>
                  <option value="closed">关闭（仅系统/Agent）</option>
                </select>
              </div>
              <label className="flex items-center gap-2 pt-6 text-sm">
                <input type="checkbox" checked={editing.auto_reply_enabled} onChange={(e) => setEditing({ ...editing, auto_reply_enabled: e.target.checked })} /> 自动回复
              </label>
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">回复阈值</label>
                <input type="number" step="0.1" min={0} max={1} value={editing.reply_threshold} onChange={(e) => setEditing({ ...editing, reply_threshold: Number(e.target.value) })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={editing.notify_human_on_no_evidence} onChange={(e) => setEditing({ ...editing, notify_human_on_no_evidence: e.target.checked })} /> 无证据时通知人工
            </label>
            <div>
              <label className="mb-1 block text-[12px] text-[#656d76]">
                外部回帖源（绑定后新帖/楼主追问由第三方 Agent 回复；留空用内置 AI 管理员）
              </label>
              <select
                value={editing.external_agent_id || ""}
                onChange={(e) => setEditing({ ...editing, external_agent_id: e.target.value ? Number(e.target.value) : null })}
                className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm"
              >
                <option value="">（内置 AI 管理员）</option>
                {externalAgents.map((a) => <option key={a.id} value={a.id}>{a.name}（{a.protocol}）</option>)}
              </select>
            </div>
            <div className="flex flex-wrap gap-4">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={editing.relevance_check_enabled} onChange={(e) => setEditing({ ...editing, relevance_check_enabled: e.target.checked })} />
                主题相关性审核（发帖/回复与栏目主题不相关 → 不通过）
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={editing.reply_to_author_questions} onChange={(e) => setEditing({ ...editing, reply_to_author_questions: e.target.checked })} />
                楼主追问自动回复（楼主评论是提问才回复，闲聊不回复）
              </label>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setEditing(null)} className="rounded border border-[#d0d7de] px-3 py-1.5 text-[13px]">取消</button>
              <button onClick={saveCategory} className="rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white">保存</button>
            </div>
          </div>
        )}
      </Modal>

      {/* 新建栏目（模态） */}
      <Modal open={!!creating} title="新建栏目" width={560} onClose={() => setCreating(null)}>
        {creating && (
          <div className="space-y-3">
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">名称</label>
                <input value={creating.name} onChange={(e) => setCreating({ ...creating, name: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
              </div>
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">slug（URL 标识）</label>
                <input value={creating.slug} onChange={(e) => setCreating({ ...creating, slug: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
              </div>
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">图标</label>
                <button
                  type="button"
                  onClick={() => setIconPickerFor("create")}
                  className="flex h-9 w-full items-center gap-2 rounded border border-[#d0d7de] px-2 text-sm hover:border-[#0969da]"
                >
                  <span className="text-[18px]">{creating.icon || "📁"}</span>
                  <span className="text-[#656d76]">点击选择</span>
                </button>
              </div>
            </div>
            <div>
              <label className="mb-1 block text-[12px] text-[#656d76]">描述</label>
              <textarea value={creating.description || ""} onChange={(e) => setCreating({ ...creating, description: e.target.value })} rows={2} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
            </div>
            <div>
              <label className="mb-1 block text-[12px] text-[#656d76]">发帖权限</label>
              <select
                value={creating.post_permission || "public"}
                onChange={(e) => setCreating({ ...creating, post_permission: e.target.value })}
                className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm"
              >
                <option value="public">公开（所有成员可发）</option>
                <option value="staff_only">仅管理员可发</option>
                <option value="closed">关闭（仅系统/Agent）</option>
              </select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setCreating(null)} className="rounded border border-[#d0d7de] px-3 py-1.5 text-[13px]">取消</button>
              <button onClick={createCategory} className="rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white">创建</button>
            </div>
          </div>
        )}
      </Modal>

      {/* AI 管理员配置（模态） */}
      <Modal open={!!aiEditing} title={`AI 管理员配置 · ${aiEditing?.name || ""}`} width={640} onClose={() => setAiEditing(null)}>
        {aiEditing && (
          <div className="space-y-3">
            <AiAdminForm cat={aiEditing} onChange={(aa) => setAiEditing({ ...aiEditing, ai_admin: aa })} />
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setAiEditing(null)} className="rounded border border-[#d0d7de] px-3 py-1.5 text-[13px]">取消</button>
              <button onClick={saveAiAdmin} className="rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white">保存</button>
            </div>
          </div>
        )}
      </Modal>

      {/* 绑定管理员（模态，可搜索） */}
      <Modal open={!!adminBinding} title={`绑定管理员 · ${adminBinding?.name || ""}`} width={520} onClose={() => setAdminBinding(null)}>
        {adminBinding && <AdminPicker cat={adminBinding} onDone={() => { setAdminBinding(null); reload(); }} />}
      </Modal>

      {/* 图标选择器 */}
      <EmojiPicker
        open={!!iconPickerFor}
        value={iconPickerFor === "edit" ? editing?.icon || "" : creating?.icon || ""}
        onClose={() => setIconPickerFor(null)}
        onConfirm={(emoji) => {
          if (iconPickerFor === "edit" && editing) setEditing({ ...editing, icon: emoji });
          if (iconPickerFor === "create" && creating) setCreating({ ...creating, icon: emoji });
          setIconPickerFor(null);
        }}
      />
    </div>
  );
}

function AiAdminForm({ cat, onChange }: { cat: Cat; onChange: (aa: any) => void }) {
  const [models, setModels] = useState<any[]>([]);
  const aa = cat.ai_admin || {};
  useEffect(() => {
    http.get("/admin/model-configs").then(setModels).catch(() => {});
  }, []);
  const set = (k: string, v: any) => onChange({ ...aa, [k]: v });
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="mb-1 block text-[12px] text-[#656d76]">人设名称</label>
          <input value={aa.persona_name || ""} onChange={(e) => set("persona_name", e.target.value)} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
        </div>
        <div>
          <label className="mb-1 block text-[12px] text-[#656d76]">绑定模型</label>
          <select value={aa.model_config_id || ""} onChange={(e) => set("model_config_id", e.target.value ? Number(e.target.value) : null)} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm">
            <option value="">（默认模型）</option>
            {models.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </div>
      </div>
      <div>
        <label className="mb-1 block text-[12px] text-[#656d76]">系统提示词</label>
        <textarea value={aa.system_prompt || ""} onChange={(e) => set("system_prompt", e.target.value)} rows={4} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
      </div>
      <div>
        <label className="mb-1 block text-[12px] text-[#656d76]">回复风格提示词</label>
        <textarea value={aa.style_prompt || ""} onChange={(e) => set("style_prompt", e.target.value)} rows={2} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="mb-1 block text-[12px] text-[#656d76]">回复阈值</label>
          <input type="number" step="0.1" min={0} max={1} value={aa.reply_threshold != null ? aa.reply_threshold : 0.5} onChange={(e) => set("reply_threshold", Number(e.target.value))} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
        </div>
        <div>
          <label className="mb-1 block text-[12px] text-[#656d76]">自审阈值</label>
          <input type="number" step="0.05" min={0} max={1} value={aa.self_review_threshold != null ? aa.self_review_threshold : 0.9} onChange={(e) => set("self_review_threshold", Number(e.target.value))} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
        </div>
      </div>
    </div>
  );
}

function AdminPicker({ cat, onDone }: { cat: Cat; onDone: () => void }) {
  const [q, setQ] = useState("");
  const [users, setUsers] = useState<any[]>([]);
  const [selected, setSelected] = useState<number | null>(null);

  const search = async () => {
    const d: any = await http.get(`/admin/users?q=${encodeURIComponent(q)}&page_size=20`);
    setUsers(d.items);
  };
  useEffect(() => { search(); }, []);

  const bind = async () => {
    if (!selected) return alert("请选择用户");
    await http.post(`/admin/categories/${cat.id}/admins/${selected}`);
    onDone();
  };

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          placeholder="搜索 ID / 邮箱 / 名字"
          className="flex-1 rounded border border-[#d0d7de] px-2 py-1.5 text-sm"
        />
        <button onClick={search} className="rounded-md border border-[#d0d7de] px-3 py-1.5 text-[13px] hover:bg-[#f3f4f6]">搜索</button>
      </div>
      <div className="max-h-[320px] space-y-1 overflow-y-auto">
        {users.map((u) => (
          <label key={u.id} className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm ${selected === u.id ? "border-[#0969da] bg-[#0969da]/5" : "border-[#d0d7de] hover:bg-[#f6f8fa]"}`}>
            <input type="radio" name="admin-user" checked={selected === u.id} onChange={() => setSelected(u.id)} />
            <span className="w-10 text-[#656d76]">#{u.id}</span>
            <span className="font-medium">{u.name}</span>
            <span className="ml-auto text-[#656d76]">{u.email}</span>
          </label>
        ))}
        {users.length === 0 && <div className="py-8 text-center text-[13px] text-[#656d76]">无匹配用户</div>}
      </div>
      <div className="flex justify-end gap-2 pt-2">
        <button onClick={onDone} className="rounded border border-[#d0d7de] px-3 py-1.5 text-[13px]">取消</button>
        <button onClick={bind} className="rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white">确定绑定</button>
      </div>
    </div>
  );
}
