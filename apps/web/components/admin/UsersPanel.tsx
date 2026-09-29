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
  const [emp, setEmp] = useState<any>(null); // 员工扩展数据
  const [empLoading, setEmpLoading] = useState(false);
  const [empMsg, setEmpMsg] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteNote, setInviteNote] = useState("");
  const [msg, setMsg] = useState("");

  const reload = () => {
    http.get(`/admin/users?q=${encodeURIComponent(q)}&page_size=50`).then((d: any) => setUsers(d.items)).catch(() => {});
    http.get("/admin/invitations").then(setInvites).catch(() => {});
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

  // ---- 员工扩展信息 ----
  const openEmp = async (u: any) => {
    setEmpUser(u);
    setEmp({
      department: u.department || "", org_id: u.org_id || "",
      employee_no: "", position: "", org_path: "", mobile: "", gender: "",
      birth_date: "", join_date: "", manager: "", location: "",
      employee_type: "", job_level: "", cost_center: "",
    });
    setEmpMsg("");
    setEmpLoading(true);
    try {
      const ep: any = await http.get(`/admin/users/${u.id}/employee`);
      setEmp((prev: any) => {
        const next = { ...prev };
        [
          "employee_no", "position", "org_path", "mobile", "gender", "birth_date",
          "join_date", "manager", "location", "employee_type", "job_level", "cost_center",
        ].forEach((k) => { if (ep[k]) next[k] = ep[k]; });
        next.sso_sub = ep.sso_sub || null;
        next.source = ep.source || "manual";
        next.raw_claims = ep.raw_claims || null;
        return next;
      });
    } catch {
      /* 读取失败不阻塞 */
    } finally {
      setEmpLoading(false);
    }
  };

  const saveEmp = async () => {
    setEmpMsg("");
    try {
      const r = await http.put(`/admin/users/${empUser.id}/employee`, {
        department: emp.department || null, org_id: emp.org_id || null,
        employee_no: emp.employee_no || null, position: emp.position || null,
        org_path: emp.org_path || null, mobile: emp.mobile || null,
        gender: emp.gender || null, birth_date: emp.birth_date || null,
        join_date: emp.join_date || null, manager: emp.manager || null,
        location: emp.location || null, employee_type: emp.employee_type || null,
        job_level: emp.job_level || null, cost_center: emp.cost_center || null,
      });
      setEmpMsg("✓ 已保存");
      setTimeout(() => { setEmpUser(null); }, 800);
      reload();
    } catch (err: any) {
      setEmpMsg(err?.message || "保存失败");
    }
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

      {/* 员工扩展信息弹窗 */}
      <Modal open={!!empUser} title={`员工信息 · ${empUser?.name || ""}`} width={560} onClose={() => setEmpUser(null)}>
        {empUser && (
          <div className="space-y-3">
            {empLoading ? (
              <div className="text-[13px] text-[#8c959f]">加载中…</div>
            ) : (
              <>
                <div className="flex items-center gap-3 text-[12px] text-[#656d76]">
                  <span>数据来源：<b className="text-[#24292f]">{emp.source === "sso" ? "企业 SSO 同步 / AI 抽取" : emp.source === "admin" ? "管理员维护" : "用户自行填写"}</b></span>
                  {emp.sso_sub && <span>SSO 标识：<code className="font-mono">{emp.sso_sub}</code></span>}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="mb-1 block text-[12px] text-[#656d76]">部门</label>
                    <input value={emp.department || ""} onChange={(e) => setEmp({ ...emp, department: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
                  </div>
                  <div>
                    <label className="mb-1 block text-[12px] text-[#656d76]">所属组织 / 单位</label>
                    <input value={emp.org_id || ""} onChange={(e) => setEmp({ ...emp, org_id: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
                  </div>
                  <div>
                    <label className="mb-1 block text-[12px] text-[#656d76]">工号</label>
                    <input value={emp.employee_no || ""} onChange={(e) => setEmp({ ...emp, employee_no: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
                  </div>
                  <div>
                    <label className="mb-1 block text-[12px] text-[#656d76]">职位</label>
                    <input value={emp.position || ""} onChange={(e) => setEmp({ ...emp, position: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
                  </div>
                  <div>
                    <label className="mb-1 block text-[12px] text-[#656d76]">手机号</label>
                    <input value={emp.mobile || ""} onChange={(e) => setEmp({ ...emp, mobile: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
                  </div>
                  <div>
                    <label className="mb-1 block text-[12px] text-[#656d76]">性别</label>
                    <input value={emp.gender || ""} onChange={(e) => setEmp({ ...emp, gender: e.target.value })} placeholder="男 / 女" className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
                  </div>
                  <div>
                    <label className="mb-1 block text-[12px] text-[#656d76]">入职日期</label>
                    <input value={emp.join_date || ""} onChange={(e) => setEmp({ ...emp, join_date: e.target.value })} placeholder="2024-03-01" className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
                  </div>
                  <div>
                    <label className="mb-1 block text-[12px] text-[#656d76]">直属上级</label>
                    <input value={emp.manager || ""} onChange={(e) => setEmp({ ...emp, manager: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
                  </div>
                  <div>
                    <label className="mb-1 block text-[12px] text-[#656d76]">办公地点</label>
                    <input value={emp.location || ""} onChange={(e) => setEmp({ ...emp, location: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
                  </div>
                  <div>
                    <label className="mb-1 block text-[12px] text-[#656d76]">员工类型</label>
                    <input value={emp.employee_type || ""} onChange={(e) => setEmp({ ...emp, employee_type: e.target.value })} placeholder="正式 / 实习 / 外包" className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
                  </div>
                  <div>
                    <label className="mb-1 block text-[12px] text-[#656d76]">职级</label>
                    <input value={emp.job_level || ""} onChange={(e) => setEmp({ ...emp, job_level: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
                  </div>
                  <div>
                    <label className="mb-1 block text-[12px] text-[#656d76]">成本中心</label>
                    <input value={emp.cost_center || ""} onChange={(e) => setEmp({ ...emp, cost_center: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
                  </div>
                  <div className="col-span-2">
                    <label className="mb-1 block text-[12px] text-[#656d76]">组织架构路径</label>
                    <input value={emp.org_path || ""} onChange={(e) => setEmp({ ...emp, org_path: e.target.value })} placeholder="集团 / 事业部 / 部门" className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
                  </div>
                </div>
                {emp.raw_claims && (
                  <details className="rounded border border-[#eaeef2] bg-[#f6f8fa] px-3 py-2">
                    <summary className="cursor-pointer text-[12px] text-[#656d76]">SSO 原始 Claims（只读，可追溯）</summary>
                    <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap break-all font-mono text-[11px] text-[#57606a]">{JSON.stringify(emp.raw_claims, null, 2)}</pre>
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
    </div>
  );
}
