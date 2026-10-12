"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { http } from "@/lib/api";

type Banner = { id: string; image_url: string; post_id: number; post_title: string };

export function HomeBanners() {
  const [items, setItems] = useState<Banner[]>([]);
  const [index, setIndex] = useState(0);
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const [paused, setPaused] = useState(false);
  useEffect(() => {
    let active = true;
    const refresh = () => http.get<{items: Banner[]}>("/banners").then(r => { if (active) { setItems(r.items); setIndex(i => r.items.length ? i % r.items.length : 0); } }).catch(() => { if(active) setItems([]); });
    refresh();
    const timer = window.setInterval(refresh, 60000);
    const onVisibility = () => { if (!document.hidden) refresh(); };
    document.addEventListener("visibilitychange", onVisibility);
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) setPaused(true);
    return () => { active = false; clearInterval(timer); document.removeEventListener("visibilitychange", onVisibility); };
  }, []);
  useEffect(() => {
    if (items.length < 2 || hovered || focused || paused) return;
    const timer = window.setInterval(() => { if (!document.hidden) setIndex(i => (i + 1) % items.length); }, 5000);
    return () => clearInterval(timer);
  }, [items.length, hovered, focused, paused]);
  if (!items.length) return null;
  const current = items[index % items.length];
  const move = (delta: number) => setIndex(i => (i + delta + items.length) % items.length);
  return (
    <section aria-label="首页轮播图" aria-roledescription="轮播" className="relative mb-4 aspect-[3/1] w-full overflow-hidden rounded-lg border border-[#d0d7de] bg-white"
      onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}
      onFocusCapture={() => setFocused(true)} onBlurCapture={e => { if (!e.currentTarget.contains(e.relatedTarget)) setFocused(false); }}>
      <Link href={`/post/${current.post_id}`} className="block h-full w-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#0969da]">
        <img src={current.image_url} alt={current.post_title} className="h-full w-full object-cover" />
        <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent px-4 pb-7 pt-7 text-sm font-medium text-white truncate">{current.post_title}</span>
      </Link>
      {items.length > 1 && <>
        <button type="button" aria-label="上一张" onClick={() => move(-1)} className="absolute left-2 top-1/2 -translate-y-1/2 rounded-md bg-black/40 px-2 py-1 text-white hover:bg-black/60">‹</button>
        <button type="button" aria-label="下一张" onClick={() => move(1)} className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md bg-black/40 px-2 py-1 text-white hover:bg-black/60">›</button>
        <div className="absolute bottom-2 left-1/2 flex -translate-x-1/2 gap-2">{items.map((item,i) => <button type="button" key={item.id} aria-label={`第 ${i+1} 张`} aria-current={index % items.length === i ? "true" : undefined} onClick={() => setIndex(i)} className={`h-2 w-2 rounded-full ${index % items.length === i ? "bg-white" : "bg-white/50"}`} />)}</div>
        <button type="button" aria-label={paused ? "播放轮播" : "暂停轮播"} onClick={() => setPaused(!paused)} className="absolute right-2 bottom-1 rounded px-2 py-1 text-xs text-white hover:bg-black/40">{paused ? "播放" : "暂停"}</button>
      </>}
    </section>
  );
}
