"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { PostCard } from "@/components/PostCard";
import { http } from "@/lib/api";

export default function CategoryPage() {
  const params = useParams<{ id: string }>();
  const [cat, setCat] = useState<any>(null);
  const [data, setData] = useState<any>({ total: 0, items: [] });

  useEffect(() => {
    http.get(`/categories/${params.id}`).then(setCat).catch(() => {});
    http.get(`/posts?category_id=${params.id}&page_size=30`).then(setData).catch(() => {});
  }, [params.id]);

  return (
    <div className="mx-auto flex max-w-[1280px] gap-8 px-4 py-6">
      <Sidebar />
      <main className="min-w-0 flex-1">
        <div className="mb-4 flex items-center gap-3">
          <span className="text-[28px]">{cat?.icon || "📁"}</span>
          <div>
            <h1 className="text-[20px] font-semibold">{cat?.name}</h1>
            <p className="text-[13px] text-[#656d76]">{cat?.description}</p>
          </div>
          {cat?.auto_reply_enabled && cat?.ai_admin?.active && !cat?.external_agent_id && (
            <span className="ml-auto rounded-md border border-[#0969da]/30 bg-[#0969da]/5 px-3 py-1 text-[13px] text-[#0969da]">
              🤖 {cat.ai_admin.persona_name} 自动回帖中
            </span>
          )}
        </div>
        <div className="rounded-lg border border-[#d0d7de] bg-white px-3 py-1">
          {data.items.length === 0 ? (
            <div className="py-16 text-center text-sm text-[#656d76]">该栏目暂无帖子</div>
          ) : (
            data.items.map((p: any) => <PostCard key={p.id} post={p} />)
          )}
        </div>
      </main>
    </div>
  );
}
