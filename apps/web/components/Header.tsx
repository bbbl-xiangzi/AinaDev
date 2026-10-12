"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { http } from "@/lib/api";
import { newPostHref } from "@/lib/post-category";
import { Avatar } from "./ui";

export function Header() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const [unread, setUnread] = useState(0);
  const [q, setQ] = useState("");

  // 用户或路由变化时重新拉取未读数（进入「我的」后 read-all 会清零）
  useEffect(() => {
    if (!user) {
      setUnread(0);
      return;
    }
    let cancelled = false;
    http.get("/me/notifications?unread_only=true&page_size=1").then((d: any) => {
      if (!cancelled) setUnread(d.unread || 0);
    }).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [user, pathname]);

  return (
    <header className="sticky top-0 z-40 border-b border-[#d0d7de] bg-[#f6f8fa]/95 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-[1280px] items-center gap-4 px-4">
        <Link href="/" className="text-[17px] font-bold text-[#24292f]">
          <span className="text-[#0969da]">◆</span> AI 开发者社区
        </Link>
        <form
          className="ml-2 hidden flex-1 sm:block"
          onSubmit={(e) => {
            e.preventDefault();
            if (q.trim()) window.location.href = `/search?q=${encodeURIComponent(q.trim())}`;
          }}
        >
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="搜索帖子（支持中文分词）"
            className="w-full max-w-sm rounded-md border border-[#d0d7de] bg-white px-3 py-1.5 text-sm outline-none focus:border-[#0969da] focus:ring-2 focus:ring-[#0969da]/20"
          />
        </form>
        <div className="ml-auto flex items-center gap-4">
          {user ? (
            <>
              <Link href={newPostHref(pathname)} className="rounded-md bg-[#0969da] px-3 py-1.5 text-sm font-medium text-white hover:bg-[#0550ae]">
                发帖
              </Link>
              <Link href="/me" className="relative text-sm text-[#24292f] hover:text-[#0969da]">
                我的
                {unread > 0 && (
                  <span className="absolute -right-3 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#cf222e] px-1 text-[10px] font-bold text-white">
                    {unread}
                  </span>
                )}
              </Link>
              {user.role === "super_admin" && (
                <Link href="/admin" className="text-sm text-[#24292f] hover:text-[#0969da]">
                  管理
                </Link>
              )}
              <span className="flex items-center gap-2 text-sm text-[#656d76]">
                <Avatar name={user.name} url={user.avatar_url} size={26} />
                <span className="hidden md:inline">{user.name}</span>
              </span>
              <button onClick={logout} className="text-sm text-[#656d76] hover:text-[#cf222e]">
                退出
              </button>
            </>
          ) : (
            <Link href="/login" className="rounded-md border border-[#d0d7de] bg-white px-3 py-1.5 text-sm font-medium text-[#24292f] hover:bg-[#f3f4f6]">
              登录
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
