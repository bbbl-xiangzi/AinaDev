"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Announcement = { id: number; title: string };
type Category = { id: number; slug: string; name: string };

export function AnnouncementCard() {
  const [post, setPost] = useState<Announcement | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    let active = true;
    let pending = false;
    const refresh = async () => {
      if (pending) return;
      pending = true;
      try {
        const categories = await api<Category[]>("/categories", { cache: "no-store" });
        // The built-in slug remains stable when an administrator renames the category.
        const category = categories.find(c => c.slug === "announcements")
          ?? categories.find(c => c.name === "公告" || c.name === "通知公告");
        // The published feed already excludes deleted/hidden/pending posts and
        // orders pinned posts first, then newest creation date.
        const result = category
          ? await api<{ items: Announcement[] }>(`/posts?category_id=${category.id}&sort=latest&page_size=1`, { cache: "no-store" })
          : { items: [] };
        if (active) {
          setPost(result.items[0] ?? null);
          setStatus("ready");
        }
      } catch {
        if (active) {
          setPost(null);
          setStatus("error");
        }
      } finally {
        pending = false;
      }
    };
    const refreshVisible = () => { if (!document.hidden) void refresh(); };
    void refresh();
    const timer = window.setInterval(refreshVisible, 60000);
    window.addEventListener("focus", refreshVisible);
    document.addEventListener("visibilitychange", refreshVisible);
    return () => {
      active = false;
      window.clearInterval(timer);
      window.removeEventListener("focus", refreshVisible);
      document.removeEventListener("visibilitychange", refreshVisible);
    };
  }, []);

  return (
    <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
      <div className="mb-2 text-[13px] font-semibold text-[#656d76]">公告</div>
      {post ? (
        <Link href={`/post/${post.id}`} className="block break-words text-[13px] text-[#24292f] hover:text-[#0969da] hover:underline">
          {post.title}
        </Link>
      ) : (
        <p className="text-[13px] text-[#656d76]">
          {status === "loading" ? "加载中…" : status === "error" ? "公告暂时无法加载" : "暂无公告"}
        </p>
      )}
    </div>
  );
}
