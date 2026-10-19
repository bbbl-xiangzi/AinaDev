"use client";
import { AnnouncementCard } from "@/components/AnnouncementCard";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { PostCard } from "@/components/PostCard";
import { http } from "@/lib/api";
import { HomeBanners } from "@/components/HomeBanners";

function HomeInner() {
  const router = useRouter();
  const params = useSearchParams();
  const sort = params.get("sort") || "latest";
  const categoryId = params.get("category") || undefined;
  const [data, setData] = useState<any>({ total: 0, items: [] });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    http
      .get(`/posts?sort=${sort}${categoryId ? `&category_id=${categoryId}` : ""}&page_size=20`)
      .then(setData)
      .catch(() => setData({ total: 0, items: [] }))
      .finally(() => setLoading(false));
  }, [sort, categoryId]);

  const tabs = [
    { key: "latest", label: "最新" },
    { key: "hot", label: "热门" },
    { key: "unanswered", label: "未回答" },
    { key: "following", label: "我关注的" },
  ];

  return (
    <div className="mx-auto flex max-w-[1280px] gap-8 px-4 py-6">
      <Sidebar />
      <main className="min-w-0 flex-1">
        <HomeBanners />
        <div className="mb-4 flex items-center gap-1 border-b border-[#d0d7de]">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => router.replace(t.key === "latest" ? "/" : `/?sort=${t.key}`)}
              className={`border-b-2 px-3 py-2 text-sm font-medium ${
                sort === t.key ? "border-[#0969da] text-[#0969da]" : "border-transparent text-[#656d76] hover:text-[#24292f]"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="rounded-lg border border-[#d0d7de] bg-white px-3 py-1">
          {loading ? (
            <div className="py-10 text-center text-sm text-[#656d76]">加载中…</div>
          ) : data.items.length === 0 ? (
            <div className="py-16 text-center text-sm text-[#656d76]">暂无帖子，去发第一帖吧</div>
          ) : (
            data.items.map((p: any) => <PostCard key={p.id} post={p} />)
          )}
        </div>
        <div className="mt-3 text-[12px] text-[#656d76]">共 {data.total} 条</div>
      </main>
      <aside className="hidden w-[280px] shrink-0 space-y-4 lg:block">
        <AnnouncementCard />
      </aside>
    </div>
  );
}

export default function Home() {
  return (
    <Suspense fallback={<div className="p-10 text-center text-sm text-[#656d76]">加载中…</div>}>
      <HomeInner />
    </Suspense>
  );
}
