"use client";

import { useEffect, useState } from "react";
import { http } from "@/lib/api";
import { Modal } from "@/components/ui/Modal";

export function UsersPanel() {
  const [users, setUsers] = useState<any[]>([]);
  const [invites, setInvites] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [editUser, setEditUser] = useState<any>(null);
  const [empUser, setEmpUser] = useState<any>(null); // 员工信息弹窗目标
  const [emp, setEmp] = useState<any>(null); // 员工扩展值 {key: value}
  const [empLoading, setEmpLoading] = useState(false);
  const [empMsg, setEmpMsg] = useState("");
  const [fieldDefs, setFieldDefs] = useState<any[]>([]);
  const [editField, setEditField] = useState<any>(null); // 编辑字段定义
  const [newField, setNewField] = useState<any>(null); // 新增字段弹窗
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteNote, setInviteNote] = useState("");
  const [msg, setMsg] = useState("");

  const reload = () => {
    http.get(`/admin/users?q=${encodeURIComponent(q)}&page_size=50`).then((d: any) => setUsers(d.items)).catch(() => {});
    http.get("/admin/invitations").then(setInvites).catch(() => {});
    http.get("/admin/employee-fields").then(setFieldDefs).catch(() => {});
  };
  useEffect(reload, []);

  const saveUser = async () => {
    if (!editUser) return;
    await http.put(`/admin/users/${editUser.id}`, { name: editUser.name, role: editUser.role, status: editUser.status });
    setEditUser(null);
    setMsg("已保存");
    reload();
  };

  const createInvite = async () => {
    if (!inviteEmail) return;
    await http.post("/admin/invitations", { email: inviteEmail, note: inviteNote || null });
    setInviteEmail("");
    setInviteNote("");
    reload();
  };

  // ---- 员工扩展信息（按字段定义动态渲染） ----
  const openEmp = async (u: any) => {
    setEmpUser(u);
    setEmp({});
    setEmpMsg("");
    setEmpLoading(true);
    try {
      const ep: any = await http.get(`/admin/users/${u.id}/employee`);
      const values: any = { department: u.department || "", org_id: u.org_id || "" };
      // 内置 employee 列
      ["employee_no", "position", "org_path", "mobile", "gender", "birth_date",
        "join_date", "manager", "location", "employee_type", "job_level", "cost_center",
      ].forEach((k) => { if (ep[k]) values[k] = ep[k]; });
      // 自定义字段（extras）
      if (ep.extras && typeof ep.extras === "object") {
        Object.keys(ep.extras).forEach((k) => { values[k] = ep.extras[k] || ""; });
      }
      values.__sso_sub = ep.sso_sub || null;
      values.__source = ep.source || "manual";
      values.__raw_claims = ep.raw_claims || null;
      setEmp(values);
    } catch {
      /* 读取失败不阻塞 */
    } finally {
      setEmpLoading(false);
    }
  };

  const saveEmp = async () => {
    setEmpMsg("");
    const body: any = {};
    const extras: any = {};
    fieldDefs.filter((d) => d.enabled).forEach((d: any) => {
      const v = emp[d.field_key] ?? "";
      if (d.target === "custom") extras[d.field_key] = v;
      else body[d.field_key] = v;
    });
    body.extras = extras;
    try {
      await http.put(`/admin/users/${empUser.id}/employee`, body);
      setEmpMsg("✓ 已保存");
      setTimeout(() => { setEmpUser(null); }, 800);
      reload();
    } catch (err: any) {
      setEmpMsg(err?.message || "保存失败");
    }
  };

  // ---- 员工字段定义管理 ----
  const saveFieldDef = async () => {
    if (!editField) return;
    await http.put(`/admin/employee-fields/${editField.id}`, {
      field_name: editField.field_name,
      hint: editField.hint || null,
      user_editable: editField.user_editable,
    });
    setEditField(null);
    reload();
  };

  const toggleField = async (d: any) => {
    await http.put(`/admin/employee-fields/${d.id}`, { enabled: !d.enabled });
    reload();
  };

  const createField = async () => {
    if (!newField?.field_name?.trim()) return;
    await http.post("/admin/employee-fields", { field_name: newField.field_name.trim(), hint: newField.hint || null });
    setNewField(null);
    reload();
  };

  const deleteField = async (d: any) => {
    if (!confirm(`确定删除自定义字段「${d.field_name}」？历史数据将不再展示。`)) return;
    await http.del(`/admin/employee-fields/${d.id}`);
    reload();
  };

  return (
    <div className="space-y-4">
      {msg && <div className="rounded-md bg-[#dafbe1] px-3 py-2 text-[13px] text-[#1a7f37]">{msg}</div>}
      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <h3 className="mb-2 text-[15px] font-semibold">用户管理</h3>
        <div className="mb-3 flex gap-2">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && reload()}
            placeholder="搜索姓名 / 邮箱"
            className="w-64 rounded border border-[#d0d7de] px-2 py-1.5 text-sm"
          />
          <button onClick={reload} className="rounded-md border border-[#d0d7de] px-3 py-1.5 text-[13px] hover:bg-[#f3f4f6]">搜索</button>
        </div>
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-[#d0d7de] text-left text-[#656d76]">
              <th className="py-2 pr-2">ID</th><th className="py-2 pr-2">姓名</th><th className="py-2 pr-2">邮箱</th><th className="py-2 pr-2">角色</th><th className="py-2 pr-2">职位</th><th className="py-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-[#d0d7de]/50">
                <td className="py-2 text-[#656d76]">{u.id}</td>
                <td className="py-2 font-medium">{u.name}</td>
                <td className="py-2 text-[#656d76]">{u.email}</td>
                <td className="py-2">{u.role === "super_admin" ? "管理员" : "成员"}</td>
                <td className="py-2 text-[#656d76]">{u.employee?.position || "—"}</td>
                <td className="py-2">
                  <button onClick={() => setEditUser(u)} className="mr-3 text-[#0969da] hover:underline">编辑</button>
                  <button onClick={() => openEmp(u)} className="text-[#0969da] hover:underline">员工信息</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 员工字段配置 */}
      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-[15px] font-semibold">员工字段配置</h3>
          <button onClick={() => setNewField({ field_name: "", hint: "" })} className="rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white">新增字段</button>
        </div>
        <p className="mb-3 text-[12px] text-[#656d76]">
          停用的字段将不再展示、不再由 SSO 抽取；内置字段不可删除，自定义字段可按客户需求添加。
        </p>
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-[#d0d7de] text-left text-[#656d76]">
              <th className="py-2 pr-2">字段名</th><th className="py-2 pr-2">标识 key</th><th className="py-2 pr-2">来源</th><th className="py-2 pr-2">状态</th><th className="py-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {fieldDefs.map((d) => (
              <tr key={d.id} className="border-b border-[#d0d7de]/50">
                <td className="py-2 font-medium">{d.field_name}</td>
                <td className="py-2 font-mono text-[12px] text-[#656d76]">{d.field_key}</td>
                <td className="py-2 text-[#656d76]">{d.builtin ? "内置" : "自定义"}</td>
                <td className="py-2">
                  <span className={`rounded-full px-2 py-0.5 text-[12px] ${d.enabled ? "bg-[#dafbe1] text-[#1a7f37]" : "bg-[#f3f4f6] text-[#656d76]"}`}>
                    {d.enabled ? "启用" : "停用"}
                  </span>
                </td>
                <td className="py-2">
                  <button onClick={() => toggleField(d)} className="mr-3 text-[#0969da] hover:underline">{d.enabled ? "停用" : "启用"}</button>
                  <button onClick={() => setEditField(d)} className="mr-3 text-[#0969da] hover:underline">编辑</button>
                  {!d.builtin && <button onClick={() => deleteField(d)} className="text-[#cf222e] hover:underline">删除</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <h3 className="mb-2 text-[15px] font-semibold">邀请码</h3>
        <div className="mb-3 flex gap-2">
          <input value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} placeholder="受邀人邮箱" className="w-64 rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
          <input value={inviteNote} onChange={(e) => setInviteNote(e.target.value)} placeholder="备注（可选）" className="w-40 rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
          <button onClick={createInvite} className="rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white">生成邀请码</button>
        </div>
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-[#d0d7de] text-left text-[#656d76]">
              <th className="py-2 pr-2">邀请码</th><th className="py-2 pr-2">受邀邮箱</th><th className="py-2 pr-2">状态</th><th className="py-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {invites.map((i) => (
              <tr key={i.id} className="border-b border-[#d0d7de]/50">
                <td className="py-2 font-mono text-[12px]">{i.code}</td>
                <td className="py-2 text-[#656d76]">{i.email}</td>
                <td className="py-2">{i.status === "active" ? "有效" : i.status}</td>
                <td className="py-2">
                  {i.status === "active" && (
                    <button onClick={async () => { await http.del(`/admin/invitations/${i.id}`); reload(); }} className="text-[#cf222e] hover:underline">作废</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Modal open={!!editUser} title="编辑用户" width={480} onClose={() => setEditUser(null)}>
        {editUser && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">姓名</label>
                <input value={editUser.name} onChange={(e) => setEditUser({ ...editUser, name: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
              </div>
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">角色</label>
                <select value={editUser.role} onChange={(e) => setEditUser({ ...editUser, role: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm">
                  <option value="member">成员</option>
                  <option value="super_admin">管理员</option>
                </select>
              </div>
            </div>
            <div>
              <label className="mb-1 block text-[12px] text-[#656d76]">状态</label>
              <select value={editUser.status} onChange={(e) => setEditUser({ ...editUser, status: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm">
                <option value="active">正常</option>
                <option value="disabled">禁用</option>
              </select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setEditUser(null)} className="rounded border border-[#d0d7de] px-3 py-1.5 text-[13px]">取消</button>
              <button onClick={saveUser} className="rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white">保存</button>
            </div>
          </div>
        )}
      </Modal>

      {/* 员工扩展信息弹窗（动态字段） */}
      <Modal open={!!empUser} title={`员工信息 · ${empUser?.name || ""}`} width={620} onClose={() => setEmpUser(null)}>
        {empUser && (
          <div className="space-y-3">
            {empLoading ? (
              <div className="text-[13px] text-[#8c959f]">加载中…</div>
            ) : (
              <>
                <div className="flex items-center gap-3 text-[12px] text-[#656d76]">
                  <span>数据来源：<b className="text-[#24292f]">{emp.__source === "sso" ? "企业 SSO 同步 / AI 抽取" : emp.__source === "admin" ? "管理员维护" : "用户自行填写"}</b></span>
                  {emp.__sso_sub && <span>SSO 标识：<code className="font-mono">{emp.__sso_sub}</code></span>}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  {fieldDefs.filter((d: any) => d.enabled).map((d: any) => (
                    <div key={d.field_key}>
                      <label className="mb-1 block text-[12px] text-[#656d76]">
                        {d.field_name}
                        {d.target === "custom" && <span className="ml-1 rounded bg-[#fff1c9] px-1 text-[11px] text-[#9a6700]">自定义</span>}
                      </label>
                      <input
                        type={d.input_type === "number" ? "number" : "text"}
                        value={emp[d.field_key] ?? ""}
                        onChange={(e) => setEmp({ ...emp, [d.field_key]: e.target.value })}
                        placeholder={d.hint || ""}
                        className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm"
                      />
                    </div>
                  ))}
                </div>
                {emp.__raw_claims && (
                  <details className="rounded border border-[#eaeef2] bg-[#f6f8fa] px-3 py-2">
                    <summary className="cursor-pointer text-[12px] text-[#656d76]">SSO 原始 Claims（只读，可追溯）</summary>
                    <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap break-all font-mono text-[11px] text-[#57606a]">{JSON.stringify(emp.__raw_claims, null, 2)}</pre>
                  </details>
                )}
                {empMsg && <div className={`text-[13px] ${empMsg.startsWith("✓") ? "text-[#1a7f37]" : "text-[#cf222e]"}`}>{empMsg}</div>}
                <div className="flex justify-end gap-2 pt-1">
                  <button onClick={() => setEmpUser(null)} className="rounded border border-[#d0d7de] px-3 py-1.5 text-[13px]">取消</button>
                  <button onClick={saveEmp} className="rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white">保存</button>
                </div>
              </>
            )}
          </div>
        )}
      </Modal>

      {/* 编辑字段定义 */}
      <Modal open={!!editField} title={`编辑字段 · ${editField?.field_name || ""}`} width={460} onClose={() => setEditField(null)}>
        {editField && (
          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-[12px] text-[#656d76]">字段名（中文显示名）</label>
              <input value={editField.field_name} onChange={(e) => setEditField({ ...editField, field_name: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
            </div>
            <div>
              <label className="mb-1 block text-[12px] text-[#656d76]">占位提示（可选）</label>
              <input value={editField.hint || ""} onChange={(e) => setEditField({ ...editField, hint: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
            </div>
            <div className="flex items-center gap-2">
              <input type="checkbox" checked={!!editField.user_editable} onChange={(e) => setEditField({ ...editField, user_editable: e.target.checked })} />
              <span className="text-[13px]">允许用户本人在「我的 - 编辑资料」修改此字段</span>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setEditField(null)} className="rounded border border-[#d0d7de] px-3 py-1.5 text-[13px]">取消</button>
              <button onClick={saveFieldDef} className="rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white">保存</button>
            </div>
          </div>
        )}
      </Modal>

      {/* 新增自定义字段 */}
      <Modal open={!!newField} title="新增员工字段" width={460} onClose={() => setNewField(null)}>
        {newField && (
          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-[12px] text-[#656d76]">字段名（如「内部职称」「所在园区」）</label>
              <input value={newField.field_name} onChange={(e) => setNewField({ ...newField, field_name: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
            </div>
            <div>
              <label className="mb-1 block text-[12px] text-[#656d76]">占位提示（可选）</label>
              <input value={newField.hint || ""} onChange={(e) => setNewField({ ...newField, hint: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
            </div>
            <p className="text-[12px] text-[#656d76]">新增后：管理员可在「员工信息」里维护该字段；SSO 登录时 AI 会按此字段名从原始 claims 中抽取（有则填、无则留空，杜绝猜测）。</p>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setNewField(null)} className="rounded border border-[#d0d7de] px-3 py-1.5 text-[13px]">取消</button>
              <button onClick={createField} className="rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white">创建</button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
