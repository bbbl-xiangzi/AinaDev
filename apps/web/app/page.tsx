"use client";

import { useCallback, useEffect, useRef, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { PostCard } from "@/components/PostCard";
import { http } from "@/lib/api";
import { AnnouncementCard } from "@/components/AnnouncementCard";
import { HomeBanners } from "@/components/HomeBanners";

const PAGE_SIZE = 20;

function HomeInner() {
  const router = useRouter();
  const params = useSearchParams();
  const sort = params.get("sort") || "latest";
  const categoryId = params.get("category") || undefined;
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const generation = useRef(0);
  const pageBusy = useRef(false);

  const loadPage = useCallback(async (p: number, append: boolean, epoch = generation.current) => {
    if (epoch !== generation.current || pageBusy.current) return;
    pageBusy.current = true;
    setLoadError(false);
    if (p === 1) setLoading(true);
    else setLoadingMore(true);
    try {
      const d = await http.get(`/posts?sort=${sort}${categoryId ? `&category_id=${categoryId}` : ""}&page=${p}&page_size=${PAGE_SIZE}`);
      if (epoch !== generation.current) return;
      const rows = Array.isArray(d.items) ? d.items : [];
      setTotal(d.total || 0);
      setItems((prev: any[]) => {
        if (!append) return rows;
        const ids = new Set(prev.map(item => item.id));
        return [...prev, ...rows.filter((item: any) => !ids.has(item.id) && ids.add(item.id))];
      });
      setPage(p);
      setHasMore(rows.length > 0 && p * PAGE_SIZE < (d.total || 0));
    } catch {
      if (epoch !== generation.current) return;
      setLoadError(true);
      if (!append) setItems([]);
    } finally {
      if (epoch === generation.current) {
        pageBusy.current = false;
        setLoading(false);
        setLoadingMore(false);
      }
    }
  }, [sort, categoryId]);

  // sort/category 切换时重置
  useEffect(() => {
    const epoch = ++generation.current;
    pageBusy.current = false;
    setItems([]);
    setTotal(0);
    setPage(1);
    setHasMore(false);
    void loadPage(1, false, epoch);
    return () => { if (generation.current === epoch) generation.current++; };
  }, [loadPage]);

  // 无限滚动
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const epoch = generation.current;
    const io = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && !loading && !loadingMore && !loadError && hasMore) {
        void loadPage(page + 1, true, epoch);
      }
    }, { rootMargin: "400px" });
    io.observe(el);
    return () => io.disconnect();
  }, [loading, loadingMore, loadError, hasMore, page, loadPage]);

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
        {loadError && <p role="alert" className="my-2 text-sm text-[#cf222e]">帖子加载失败 <button onClick={() => void loadPage(items.length ? page + 1 : 1, items.length > 0)} className="text-[#0969da]">重试加载</button></p>}
        <div className="rounded-lg border border-[#d0d7de] bg-white px-3 py-1">
          {loading ? (
            <div className="py-10 text-center text-sm text-[#656d76]">加载中…</div>
          ) : items.length === 0 ? (
            <div className="py-16 text-center text-sm text-[#656d76]">暂无帖子，去发第一帖吧</div>
          ) : (
            <>
              {items.map((p: any) => <PostCard key={p.id} post={p} />)}
              <div ref={sentinelRef} className="py-4 text-center text-[12px] text-[#999]">
                {loadingMore ? "加载更多…" : hasMore ? "↓ 往下滑加载更多" : `— 已全部加载完（共 ${items.length} 条）—`}
              </div>
            </>
          )}
        </div>
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
