"use client";

import { useEffect, useState, Suspense } from "react";
import { useParams, useRouter } from "next/navigation";
import { http } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Avatar, TimeAgo } from "@/components/ui";
import { Sidebar } from "@/components/Sidebar";
import { PostCard } from "@/components/PostCard";

function UserInner() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const [profile, setProfile] = useState<any>(null);
  const [posts, setPosts] = useState<any[]>([]);
  const [postTotal, setPostTotal] = useState(0);
  const [tab, setTab] = useState<"posts" | "followers" | "followings">("posts");
  const [followers, setFollowers] = useState<any[]>([]);
  const [followings, setFollowings] = useState<any[]>([]);
  const [following, setFollowing] = useState(false);
  const [busy, setBusy] = useState(false);

  const uid = Number(params.id);

  const load = () => {
    http.get(`/users/${uid}`).then((d: any) => {
      setProfile(d);
      setFollowing(d.is_following);
    }).catch(() => router.push("/"));
    http.get(`/users/${uid}/posts?page_size=20`).then((d: any) => {
      setPosts(d.items || []);
      setPostTotal(d.total || 0);
    }).catch(() => {});
    http.get(`/users/${uid}/followers`).then(setFollowers).catch(() => {});
    http.get(`/users/${uid}/followings`).then(setFollowings).catch(() => {});
  };

  useEffect(load, [uid]);

  const toggleFollow = async () => {
    if (!user) {
      router.push("/login");
      return;
    }
    setBusy(true);
    try {
      if (following) await http.del(`/users/${uid}/follow`);
      else await http.post(`/users/${uid}/follow`);
      setFollowing(!following);
      load();
    } catch (err: any) {
      alert(err?.message || "操作失败");
    } finally {
      setBusy(false);
    }
  };

  if (!profile) return <div className="p-10 text-center text-sm text-[#656d76]">加载中…</div>;

  const isAi = profile.account_type === "agent" || profile.account_type === "system";

  return (
    <div className="mx-auto flex max-w-[1012px] gap-8 px-4 py-6">
      <Sidebar />
      <main className="min-w-0 flex-1">
        {/* 资料卡 */}
        <div className="rounded-lg border border-[#d0d7de] bg-white p-6">
          <div className="flex items-start gap-4">
            <Avatar name={profile.name} url={profile.avatar_url} size={72} isAi={isAi} />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-[20px] font-semibold text-[#24292f]">{profile.name}</h1>
                {isAi && (
                  <span className="rounded bg-[#0969da]/10 px-2 py-0.5 text-[12px] font-medium text-[#0969da]">
                    {profile.account_type === "system" ? "官方账号" : "AI 管理员"}
                  </span>
                )}
                {profile.role === "super_admin" && !isAi && (
                  <span className="rounded bg-[#dafbe1] px-2 py-0.5 text-[12px] font-medium text-[#1a7f37]">超级管理员</span>
                )}
              </div>
              <div className="mt-1 text-[13px] text-[#656d76]">
                {profile.department ? `部门：${profile.department}` : "未填写部门"}
                {profile.org_id ? ` · ${profile.org_id}` : ""}
              </div>
              <div className="mt-1 text-[12px] text-[#656d76]">加入于 {new Date(profile.created_at).toLocaleDateString("zh-CN")}</div>
              <div className="mt-3 flex gap-6 text-[13px]">
                <span><b className="text-[16px] text-[#24292f]">{profile.post_count}</b> 发帖</span>
                <span><b className="text-[16px] text-[#24292f]">{profile.reply_count}</b> 回复</span>
                <span><b className="text-[16px] text-[#24292f]">{profile.like_received}</b> 获赞</span>
                <span><b className="text-[16px] text-[#24292f]">{profile.follower_count}</b> 粉丝</span>
                <span><b className="text-[16px] text-[#24292f]">{profile.following_count}</b> 关注</span>
              </div>
            </div>
            <div className="shrink-0">
              {profile.is_self ? (
                <button onClick={() => router.push("/me")} className="rounded-md border border-[#d0d7de] px-4 py-1.5 text-[13px] text-[#24292f] hover:bg-[#f3f4f6]">编辑我的资料</button>
              ) : isAi ? (
                <span className="rounded-md border border-[#d0d7de] px-4 py-1.5 text-[13px] text-[#656d76]">AI / 官方账号</span>
              ) : (
                <button
                  onClick={toggleFollow}
                  disabled={busy}
                  className={`rounded-md border px-4 py-1.5 text-[13px] font-medium ${following ? "border-[#d0d7de] text-[#656d76] hover:bg-[#f3f4f6]" : "border-[#0969da] bg-[#0969da] text-white hover:bg-[#0550ae]"} disabled:opacity-60`}
                >
                  {following ? "已关注" : "+ 关注"}
                </button>
              )}
            </div>
          </div>
        </div>

        {/* 内容区 */}
        <div className="mt-5">
          <div className="mb-3 flex gap-1 border-b border-[#d0d7de]">
            {([
              { key: "posts", label: `TA 的帖子（${postTotal}）` },
              { key: "followers", label: `粉丝（${profile.follower_count}）` },
              { key: "followings", label: `关注（${profile.following_count}）` },
            ] as const).map((t) => (
              <button key={t.key} onClick={() => setTab(t.key)} className={`border-b-2 px-3 py-2 text-sm font-medium ${tab === t.key ? "border-[#0969da] text-[#0969da]" : "border-transparent text-[#656d76]"}`}>
                {t.label}
              </button>
            ))}
          </div>
          <div className="rounded-lg border border-[#d0d7de] bg-white px-3 py-1">
            {tab === "posts" &&
              (posts.length === 0 ? <div className="py-16 text-center text-sm text-[#656d76]">TA 还没有发过帖</div> : posts.map((p: any) => <PostCard key={p.id} post={p} />))}
            {tab === "followers" &&
              (followers.length === 0 ? <div className="py-16 text-center text-sm text-[#656d76]">还没有粉丝</div> : followers.map((u: any) => (
                <a key={u.id} href={`/users/${u.id}`} className="flex items-center gap-3 border-b border-[#d0d7de]/50 px-1 py-3 hover:bg-white/60">
                  <Avatar name={u.name} url={u.avatar_url} size={36} isAi={u.account_type === "agent" || u.account_type === "system"} />
                  <div className="min-w-0">
                    <div className="text-[14px] font-medium text-[#24292f]">{u.name}</div>
                    {u.department && <div className="text-[12px] text-[#656d76]">{u.department}</div>}
                  </div>
                </a>
              )))}
            {tab === "followings" &&
              (followings.length === 0 ? <div className="py-16 text-center text-sm text-[#656d76]">还没有关注任何人</div> : followings.map((u: any) => (
                <a key={u.id} href={`/users/${u.id}`} className="flex items-center gap-3 border-b border-[#d0d7de]/50 px-1 py-3 hover:bg-white/60">
                  <Avatar name={u.name} url={u.avatar_url} size={36} isAi={u.account_type === "agent" || u.account_type === "system"} />
                  <div className="min-w-0">
                    <div className="text-[14px] font-medium text-[#24292f]">{u.name}</div>
                    {u.department && <div className="text-[12px] text-[#656d76]">{u.department}</div>}
                  </div>
                </a>
              )))}
          </div>
        </div>
      </main>
    </div>
  );
}

export default function UserPage() {
  return (
    <Suspense fallback={<div className="p-10 text-center text-sm text-[#656d76]">加载中…</div>}>
      <UserInner />
    </Suspense>
  );
}
