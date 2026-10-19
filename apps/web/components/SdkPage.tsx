"use client";
import { useEffect, useState, Suspense } from "react";
import { useParams } from "next/navigation";
import { http } from "@/lib/api";
import { sdkDocument, SdkPageConfig } from "@/lib/sdk-pages";
import { Sidebar } from "./Sidebar";

export function SdkPage() {
  const { slug } = useParams<{ slug: string }>();
  const [page, setPage] = useState<SdkPageConfig | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true; setPage(null); setError("");
    http.get<SdkPageConfig>(`/sdk-pages/${encodeURIComponent(slug)}`).then(p => { if (active) setPage(p); }).catch(e => { if (active) setError(e.message || "加载失败"); });
    return () => { active = false; };
  }, [slug, attempt]);
  return <div className="mx-auto flex max-w-[1280px] gap-8 px-4 py-6">
    <aside className="hidden md:block"><Suspense fallback={null}><Sidebar /></Suspense></aside>
    <main className="min-w-0 flex-1"><div className="mb-4 flex flex-wrap items-center justify-between gap-3">
      <h1 className="text-xl font-semibold">{page?.title || "SDK 页面"}</h1>
      <div className="flex gap-3 text-sm">{page && <a href={page.base_url} target="_blank" rel="noopener noreferrer" className="text-[#0969da]">打开平台 ↗</a>}<button onClick={() => setAttempt(n => n + 1)} className="rounded border border-[#d0d7de] px-3 py-1.5">重新加载</button></div>
    </div>
    {error ? <p role="alert">{error}</p> : !page ? <p role="status">加载中…</p> : <iframe key={`${slug}-${attempt}`} title={page.title} srcDoc={sdkDocument(page)} sandbox="allow-scripts allow-forms allow-popups allow-popups-to-escape-sandbox allow-downloads" referrerPolicy="no-referrer" className="block h-[calc(100dvh-160px)] min-h-[400px] w-full rounded-lg border border-[#d0d7de] bg-white" />}
    </main>
  </div>;
}
