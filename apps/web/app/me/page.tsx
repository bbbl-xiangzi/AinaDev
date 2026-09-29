"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { http } from "@/lib/api";
import { PostCard } from "@/components/PostCard";
import { Avatar, MarkdownView, TimeAgo } from "@/components/ui";
import { Modal } from "@/components/ui/Modal";

export default function MePage() {
  const { user, logout, refreshUser } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<"posts" | "favorites" | "notifications" | "tickets">("posts");
  const [posts, setPosts] = useState<any[]>([]);
  const [favs, setFavs] = useState<any[]>([]);
  const [notifs, setNotifs] = useState<any>({ items: [], unread: 0 });
  const [tickets, setTickets] = useState<any>({ balance: 0, total_earned: 0, items: [] });
  const [wallet, setWallet] = useState<{ balance: number; total_earned: number }>({ balance: 0, total_earned: 0 });
  const [empInfo, setEmpInfo] = useState<{ department?: string; position?: string; employee_no?: string }>({});
  const fileRef = useRef<HTMLInputElement>(null);

  // 编辑资料
  const [profileOpen, setProfileOpen] = useState(false);
  const [pfName, setPfName] = useState("");
  const [pfDept, setPfDept] = useState("");
  const [pfOrg, setPfOrg] = useState("");
  const [pfEmp, setPfEmp] = useState<Record<string, string>>({}); // 员工扩展字段
  const [profileMsg, setProfileMsg] = useState("");
  const [profileLoading, setProfileLoading] = useState(false);
  // 修改密码
  const [passOpen, setPassOpen] = useState(false);
  const [oldPwd, setOldPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [newPwd2, setNewPwd2] = useState("");
  const [passMsg, setPassMsg] = useState("");

  const openProfile = async () => {
    setPfName(user?.name || "");
    setPfDept(user?.department || "");
    setPfOrg(user?.org_id || "");
    setPfEmp({});
    setProfileMsg("");
    setProfileOpen(true);
    setProfileLoading(true);
    try {
      const ep: any = await http.get("/me/employee");
      const pick: Record<string, string> = {};
      [
        "employee_no", "position", "org_path", "mobile", "gender", "birth_date",
        "join_date", "manager", "location", "employee_type", "job_level", "cost_center",
      ].forEach((k) => {
        if (ep[k]) pick[k] = ep[k];
      });
      setPfEmp(pick);
    } catch {
      /* 员工扩展信息读取失败不阻塞 */
    } finally {
      setProfileLoading(false);
    }
  };

  const saveProfile = async () => {
    setProfileMsg("");
    try {
      const updated = await http.patch("/me/profile", {
        name: pfName, department: pfDept, org_id: pfOrg,
        employee_no: pfEmp.employee_no || null, position: pfEmp.position || null,
        org_path: pfEmp.org_path || null, mobile: pfEmp.mobile || null,
        gender: pfEmp.gender || null, birth_date: pfEmp.birth_date || null,
        join_date: pfEmp.join_date || null, manager: pfEmp.manager || null,
        location: pfEmp.location || null, employee_type: pfEmp.employee_type || null,
        job_level: pfEmp.job_level || null, cost_center: pfEmp.cost_center || null,
      });
      refreshUser?.();
      setProfileMsg("✓ 已保存");
      setTimeout(() => setProfileOpen(false), 800);
    } catch (err: any) {
      setProfileMsg(err?.message || "保存失败");
    }
  };

  const savePassword = async () => {
    setPassMsg("");
    if (newPwd.length < 6) {
      setPassMsg("新密码至少 6 位");
      return;
    }
    if (newPwd !== newPwd2) {
      setPassMsg("两次输入的新密码不一致");
      return;
    }
    try {
      await http.post("/auth/change-password", { old_password: oldPwd, new_password: newPwd });
      setPassMsg("✓ 密码已修改，下次登录请使用新密码");
      setOldPwd("");
      setNewPwd("");
      setNewPwd2("");
      setTimeout(() => setPassOpen(false), 1200);
    } catch (err: any) {
      setPassMsg(err?.message || "修改失败");
    }
  };

  const onAvatarChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const fd = new FormData();
    fd.append("file", f);
    try {
      const res = await http.upload("/me/avatar", fd);
      refreshUser?.();
    } catch (err: any) {
      alert(err?.message || "上传失败");
    }
  };

  useEffect(() => {
    if (!user) {
      router.push("/login");
      return;
    }
    http.post("/me/notifications/read-all").catch(() => {});
    // 进入页面就拉余额（左侧卡片显示）——只取余额字段，不拉明细避免竞争
    http.get("/me/tickets?page_size=1").then((d: any) => {
      setWallet({ balance: d.balance || 0, total_earned: d.total_earned || 0 });
    }).catch(() => {});
    // 员工扩展信息（部门/职位展示）
    http.get("/me/employee").then((ep: any) => {
      setEmpInfo({ department: ep.department || user?.department, position: ep.position || "", employee_no: ep.employee_no || "" });
    }).catch(() => setEmpInfo({ department: user?.department }));
    loadTab(tab);
  }, [user, tab]);

  const loadTab = (t: string) => {
    if (t === "posts") http.get("/me/posts?page_size=50").then((d: any) => setPosts(d.items || []));
    if (t === "favorites") http.get("/me/favorites").then(setFavs);
    if (t === "notifications") http.get("/me/notifications?page_size=50").then(setNotifs);
    if (t === "tickets") http.get("/me/tickets?page_size=50").then((d: any) => {
      setTickets(d);
      setWallet({ balance: d.balance || 0, total_earned: d.total_earned || 0 });
    });
  };

  if (!user) return null;

  return (
    <div className="mx-auto flex max-w-[1012px] gap-8 px-4 py-6">
      <div className="w-[220px] shrink-0">
        <div className="rounded-lg border border-[#d0d7de] bg-white p-6 text-center">
          <div className="flex justify-center">
            <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={onAvatarChange} />
            <button onClick={() => fileRef.current?.click()} title="点击更换头像" className="rounded-full hover:opacity-80">
              <Avatar name={user.name} url={user.avatar_url} size={64} />
            </button>
          </div>
          <div className="mt-3 text-[16px] font-semibold">{user.name}</div>
          <div className="text-[13px] text-[#656d76]">{user.email}</div>
          {(empInfo.position || empInfo.department) && (
            <div className="mt-1 text-[12px] text-[#656d76]">
              {[empInfo.position, empInfo.department, empInfo.employee_no ? `工号 ${empInfo.employee_no}` : ""].filter(Boolean).join(" · ")}
            </div>
          )}
          <div className="mt-1 text-[12px] text-[#656d76]">{user.role === "super_admin" ? "超级管理员" : "成员"} · 加入于 {new Date(user.created_at).toLocaleDateString("zh-CN")}</div>

          {/* Ticket 余额卡片 */}
          <div className="mt-4 rounded-lg bg-gradient-to-br from-amber-50 to-amber-100/50 p-3">
            <div className="text-[12px] text-[#9a6700]">我的 ⭐ Ticket</div>
            <div className="mt-1 text-[28px] font-bold leading-none text-[#b45309]">{wallet.balance.toFixed(1)}</div>
            <div className="mt-1 text-[11px] text-[#9a6700]/80">累计获得 {wallet.total_earned.toFixed(1)}</div>
          </div>

          <div className="mt-4 flex flex-col gap-2">
            <button onClick={() => router.push(`/users/${user.id}`)} className="rounded-md border border-[#d0d7de] px-3 py-1.5 text-[13px] text-[#24292f] hover:bg-[#f3f4f6]">我的主页</button>
            <button onClick={openProfile} className="rounded-md border border-[#d0d7de] px-3 py-1.5 text-[13px] text-[#24292f] hover:bg-[#f3f4f6]">编辑资料</button>
            <button onClick={() => { setPassMsg(""); setOldPwd(""); setNewPwd(""); setNewPwd2(""); setPassOpen(true); }} className="rounded-md border border-[#d0d7de] px-3 py-1.5 text-[13px] text-[#24292f] hover:bg-[#f3f4f6]">修改密码</button>
          </div>
          <div className="mt-2 flex justify-center gap-2">
            <button onClick={logout} className="rounded-md border border-[#d0d7de] px-3 py-1.5 text-[13px] text-[#656d76] hover:bg-[#f3f4f6]">退出登录</button>
            {user.role === "super_admin" && <button onClick={() => router.push("/admin")} className="rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white">管理后台</button>}
          </div>
        </div>
      </div>
      <main className="min-w-0 flex-1">
        <div className="mb-4 flex gap-1 border-b border-[#d0d7de]">
          {([
            { key: "posts", label: "我发的" },
            { key: "favorites", label: "我赞过的" },
            { key: "notifications", label: `通知${notifs.unread ? `（${notifs.unread}）` : ""}` },
            { key: "tickets", label: "⭐ Ticket 明细" },
          ] as const).map((t) => (
            <button key={t.key} onClick={() => setTab(t.key)} className={`border-b-2 px-3 py-2 text-sm font-medium ${tab === t.key ? "border-[#0969da] text-[#0969da]" : "border-transparent text-[#656d76]"}`}>
              {t.label}
            </button>
          ))}
        </div>
        <div className="rounded-lg border border-[#d0d7de] bg-white px-3 py-1">
          {tab === "posts" &&
            (posts.length === 0 ? <div className="py-16 text-center text-sm text-[#656d76]">还没有发过帖</div> : posts.map((p: any) => <PostCard key={p.id} post={p} />))}
          {tab === "favorites" &&
            (favs.length === 0 ? <div className="py-16 text-center text-sm text-[#656d76]">还没有赞过的帖子</div> : favs.map((p: any) => <PostCard key={p.id} post={p} />))}
          {tab === "notifications" && (
            <div>
              {notifs.items.length === 0 && <div className="py-16 text-center text-sm text-[#656d76]">暂无通知</div>}
              {notifs.items.map((n: any) => (
                <div key={n.id} className={`flex gap-3 border-b border-[#d0d7de]/50 px-1 py-3 ${n.is_read ? "opacity-60" : ""}`}>
                  <div className="min-w-0 flex-1">
                    <a href={n.link_url || undefined} className="text-[14px] font-medium text-[#24292f] hover:text-[#0969da]">{n.title}</a>
                    {n.body && <div className="mt-0.5 line-clamp-2 text-[13px] text-[#656d76]">{n.body}</div>}
                    <div className="mt-1 text-[12px] text-[#656d76]"><TimeAgo iso={n.created_at} /></div>
                  </div>
                </div>
              ))}
              {notifs.unread > 0 && (
                <div className="p-2 text-center">
                  <button onClick={() => http.post("/me/notifications/read-all").then(() => loadTab("notifications"))} className="text-[13px] text-[#0969da] hover:underline">
                    全部标为已读
                  </button>
                </div>
              )}
            </div>
          )}
          {tab === "tickets" && (
            <div>
              {tickets.items.length === 0 && <div className="py-16 text-center text-sm text-[#656d76]">还没有 Ticket 流水，去发帖/回帖/点赞赚星星吧</div>}
              {tickets.items.map((t: any) => (
                <div key={t.id} className="flex items-center justify-between border-b border-[#d0d7de]/50 px-1 py-3">
                  <div className="min-w-0 flex-1">
                    <div className="text-[14px] font-medium text-[#24292f]">{t.note || t.action_key}</div>
                    <div className="mt-0.5 text-[12px] text-[#656d76]"><TimeAgo iso={t.created_at} /></div>
                  </div>
                  <div className={`text-[15px] font-semibold ${t.amount > 0 ? "text-[#1a7f37]" : "text-[#cf222e]"}`}>
                    {t.amount > 0 ? "+" : ""}{t.amount.toFixed(1)} ⭐
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 编辑资料弹窗 */}
        <Modal open={profileOpen} title="编辑个人资料" width={460} onClose={() => setProfileOpen(false)}>
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-[13px] font-medium text-[#24292f]">昵称</label>
              <input value={pfName} onChange={(e) => setPfName(e.target.value)} maxLength={50} className="w-full rounded-md border border-[#d0d7de] px-3 py-2 text-[14px] outline-none focus:border-[#0969da]" />
            </div>
            <div>
              <label className="mb-1 block text-[13px] font-medium text-[#24292f]">部门</label>
              <input value={pfDept} onChange={(e) => setPfDept(e.target.value)} maxLength={100} placeholder="如：基础架构部" className="w-full rounded-md border border-[#d0d7de] px-3 py-2 text-[14px] outline-none focus:border-[#0969da]" />
            </div>
            <div>
              <label className="mb-1 block text-[13px] font-medium text-[#24292f]">所属组织 / 单位</label>
              <input value={pfOrg} onChange={(e) => setPfOrg(e.target.value)} maxLength={100} placeholder="如：XX 集团" className="w-full rounded-md border border-[#d0d7de] px-3 py-2 text-[14px] outline-none focus:border-[#0969da]" />
            </div>

            {/* 员工扩展信息（SSO 同步 / AI 抽取后可自行修改） */}
            <div className="border-t border-[#eaeef2] pt-3">
              <div className="mb-2 text-[12px] font-medium text-[#656d76]">员工信息（企业身份同步 / AI 抽取，可自行修改）</div>
              {profileLoading ? (
                <div className="text-[12px] text-[#8c959f]">加载中…</div>
              ) : (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="mb-1 block text-[12px] text-[#656d76]">工号</label>
                    <input value={pfEmp.employee_no || ""} onChange={(e) => setPfEmp({ ...pfEmp, employee_no: e.target.value })} maxLength={100} className="w-full rounded-md border border-[#d0d7de] px-2 py-1.5 text-[13px] outline-none focus:border-[#0969da]" />
                  </div>
                  <div>
                    <label className="mb-1 block text-[12px] text-[#656d76]">职位</label>
                    <input value={pfEmp.position || ""} onChange={(e) => setPfEmp({ ...pfEmp, position: e.target.value })} maxLength={100} className="w-full rounded-md border border-[#d0d7de] px-2 py-1.5 text-[13px] outline-none focus:border-[#0969da]" />
                  </div>
                  <div>
                    <label className="mb-1 block text-[12px] text-[#656d76]">手机号</label>
                    <input value={pfEmp.mobile || ""} onChange={(e) => setPfEmp({ ...pfEmp, mobile: e.target.value })} maxLength={50} className="w-full rounded-md border border-[#d0d7de] px-2 py-1.5 text-[13px] outline-none focus:border-[#0969da]" />
                  </div>
                  <div>
                    <label className="mb-1 block text-[12px] text-[#656d76]">性别</label>
                    <input value={pfEmp.gender || ""} onChange={(e) => setPfEmp({ ...pfEmp, gender: e.target.value })} maxLength={20} placeholder="男 / 女" className="w-full rounded-md border border-[#d0d7de] px-2 py-1.5 text-[13px] outline-none focus:border-[#0969da]" />
                  </div>
                  <div>
                    <label className="mb-1 block text-[12px] text-[#656d76]">入职日期</label>
                    <input value={pfEmp.join_date || ""} onChange={(e) => setPfEmp({ ...pfEmp, join_date: e.target.value })} maxLength={20} placeholder="2024-03-01" className="w-full rounded-md border border-[#d0d7de] px-2 py-1.5 text-[13px] outline-none focus:border-[#0969da]" />
                  </div>
                  <div>
                    <label className="mb-1 block text-[12px] text-[#656d76]">直属上级</label>
                    <input value={pfEmp.manager || ""} onChange={(e) => setPfEmp({ ...pfEmp, manager: e.target.value })} maxLength={100} className="w-full rounded-md border border-[#d0d7de] px-2 py-1.5 text-[13px] outline-none focus:border-[#0969da]" />
                  </div>
                  <div>
                    <label className="mb-1 block text-[12px] text-[#656d76]">办公地点</label>
                    <input value={pfEmp.location || ""} onChange={(e) => setPfEmp({ ...pfEmp, location: e.target.value })} maxLength={100} className="w-full rounded-md border border-[#d0d7de] px-2 py-1.5 text-[13px] outline-none focus:border-[#0969da]" />
                  </div>
                  <div>
                    <label className="mb-1 block text-[12px] text-[#656d76]">员工类型</label>
                    <input value={pfEmp.employee_type || ""} onChange={(e) => setPfEmp({ ...pfEmp, employee_type: e.target.value })} maxLength={50} placeholder="正式 / 实习 / 外包" className="w-full rounded-md border border-[#d0d7de] px-2 py-1.5 text-[13px] outline-none focus:border-[#0969da]" />
                  </div>
                  <div>
                    <label className="mb-1 block text-[12px] text-[#656d76]">职级</label>
                    <input value={pfEmp.job_level || ""} onChange={(e) => setPfEmp({ ...pfEmp, job_level: e.target.value })} maxLength={50} className="w-full rounded-md border border-[#d0d7de] px-2 py-1.5 text-[13px] outline-none focus:border-[#0969da]" />
                  </div>
                  <div>
                    <label className="mb-1 block text-[12px] text-[#656d76]">成本中心</label>
                    <input value={pfEmp.cost_center || ""} onChange={(e) => setPfEmp({ ...pfEmp, cost_center: e.target.value })} maxLength={100} className="w-full rounded-md border border-[#d0d7de] px-2 py-1.5 text-[13px] outline-none focus:border-[#0969da]" />
                  </div>
                  <div className="col-span-2">
                    <label className="mb-1 block text-[12px] text-[#656d76]">组织架构路径</label>
                    <input value={pfEmp.org_path || ""} onChange={(e) => setPfEmp({ ...pfEmp, org_path: e.target.value })} maxLength={500} placeholder="集团 / 事业部 / 部门" className="w-full rounded-md border border-[#d0d7de] px-2 py-1.5 text-[13px] outline-none focus:border-[#0969da]" />
                  </div>
                </div>
              )}
            </div>
            {profileMsg && <div className={`text-[13px] ${profileMsg.startsWith("✓") ? "text-[#1a7f37]" : "text-[#cf222e]"}`}>{profileMsg}</div>}
            <div className="flex justify-end gap-2">
              <button onClick={() => setProfileOpen(false)} className="rounded-md border border-[#d0d7de] px-4 py-1.5 text-[13px] text-[#656d76] hover:bg-[#f3f4f6]">取消</button>
              <button onClick={saveProfile} className="rounded-md bg-[#0969da] px-4 py-1.5 text-[13px] font-medium text-white hover:bg-[#0550ae]">保存</button>
            </div>
          </div>
        </Modal>

        {/* 修改密码弹窗 */}
        <Modal open={passOpen} title="修改密码" width={420} onClose={() => setPassOpen(false)}>
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-[13px] font-medium text-[#24292f]">当前密码</label>
              <input type="password" value={oldPwd} onChange={(e) => setOldPwd(e.target.value)} className="w-full rounded-md border border-[#d0d7de] px-3 py-2 text-[14px] outline-none focus:border-[#0969da]" />
            </div>
            <div>
              <label className="mb-1 block text-[13px] font-medium text-[#24292f]">新密码</label>
              <input type="password" value={newPwd} onChange={(e) => setNewPwd(e.target.value)} className="w-full rounded-md border border-[#d0d7de] px-3 py-2 text-[14px] outline-none focus:border-[#0969da]" />
            </div>
            <div>
              <label className="mb-1 block text-[13px] font-medium text-[#24292f]">确认新密码</label>
              <input type="password" value={newPwd2} onChange={(e) => setNewPwd2(e.target.value)} className="w-full rounded-md border border-[#d0d7de] px-3 py-2 text-[14px] outline-none focus:border-[#0969da]" />
            </div>
            {passMsg && <div className={`text-[13px] ${passMsg.startsWith("✓") ? "text-[#1a7f37]" : "text-[#cf222e]"}`}>{passMsg}</div>}
            <div className="flex justify-end gap-2">
              <button onClick={() => setPassOpen(false)} className="rounded-md border border-[#d0d7de] px-4 py-1.5 text-[13px] text-[#656d76] hover:bg-[#f3f4f6]">取消</button>
              <button onClick={savePassword} className="rounded-md bg-[#0969da] px-4 py-1.5 text-[13px] font-medium text-white hover:bg-[#0550ae]">确认修改</button>
            </div>
          </div>
        </Modal>
      </main>
    </div>
  );
}
