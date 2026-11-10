"use client";

import { useEffect, useRef, useState } from "react";
import { http } from "@/lib/api";
import { copyShareText, postShareText, postShareUrl } from "@/lib/post-share";

export function PostShare({ id, title, category }: { id: number; title: string; category: string }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const [url, setUrl] = useState("");
  const [site, setSite] = useState("");
  const [feedback, setFeedback] = useState("");
  const [manual, setManual] = useState("");
  const [busy, setBusy] = useState(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);

  const open = () => {
    setUrl(postShareUrl(window.location.origin, id));
    setFeedback(""); setManual("");
    dialog.current?.showModal();
    http.get("/admin/site-config-public").then((config) => {
      if (mounted.current) setSite(config.site_name || "");
    }).catch(() => {});
  };
  const copy = async (content: string) => {
    setBusy(true);
    const ok = await copyShareText(content);
    if (!mounted.current) return;
    setBusy(false);
    setFeedback(ok ? "已复制" : "自动复制失败，请选中下方内容手动复制。");
    setManual(ok ? "" : content);
  };

  return <>
    <button ref={trigger} type="button" onClick={open} className="ml-auto inline-flex shrink-0 items-center gap-1.5 rounded-md px-2 py-1 text-sm font-medium text-[#0969da] hover:bg-[#0969da]/10">
      <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M14 3h7v7M21 3l-11 11M10 5H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5" /></svg>
      分享
    </button>
    <dialog ref={dialog} aria-labelledby="post-share-title" onClose={() => trigger.current?.focus()} onClick={(e) => { if (e.target === e.currentTarget) dialog.current?.close(); }}
      onKeyDown={(e) => {
        if (e.key !== "Tab") return;
        const nodes = e.currentTarget.querySelectorAll<HTMLElement>("button:not(:disabled), input, textarea");
        const first = nodes[0], last = nodes[nodes.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
      }}
      className="fixed inset-0 m-auto max-h-[90dvh] w-[calc(100%-2rem)] max-w-[580px] overflow-y-auto rounded-xl border border-[#d0d7de] bg-white p-0 text-[#24292f] shadow-2xl backdrop:bg-black/35">
      <div className="p-5 sm:p-7">
        <div className="flex items-center justify-between gap-4">
          <h2 id="post-share-title" className="text-xl font-semibold">分享帖子</h2>
          <button type="button" aria-label="关闭分享弹窗" onClick={() => dialog.current?.close()} className="rounded-md px-2 py-1 text-xl text-[#656d76] hover:bg-[#eaeef2]">×</button>
        </div>
        <p className="mt-2 text-sm text-[#656d76]">复制后发送给同事，一起交流学习</p>
        <div className="mt-5 rounded-lg border border-[#d0d7de]/60 bg-[#f6f8fa] p-5">
          {category && <span className="rounded bg-[#0969da]/10 px-2 py-1 text-xs text-[#0969da]">{category}</span>}
          <p className="mt-3 break-words text-base font-semibold">{title}</p>
          {site && <p className="mt-2 break-words text-sm text-[#656d76]">{site}</p>}
        </div>
        <label htmlFor="post-share-url" className="mb-2 mt-5 block text-sm font-medium">帖子链接</label>
        <div className="flex items-center gap-2 rounded-lg border border-[#d0d7de] bg-[#f6f8fa] px-3">
          <input id="post-share-url" readOnly value={url} onFocus={(e) => e.currentTarget.select()} className="min-w-0 flex-1 bg-transparent py-3 text-sm outline-none" />
          <button type="button" aria-label="复制帖子链接" disabled={busy} onClick={() => void copy(url)} className="rounded p-2 text-[#656d76] hover:bg-[#eaeef2] disabled:opacity-50">
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><rect x="8" y="3" width="12" height="15" rx="2"/><path d="M16 18v2a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1h3"/></svg>
          </button>
        </div>
        <p className="mt-2 text-xs text-[#656d76]">访问权限与原帖一致</p>
        <p role="status" aria-live="polite" className="mt-2 min-h-5 text-sm text-[#656d76]">{feedback}</p>
        {manual && <textarea aria-label="手动复制分享内容" readOnly value={manual} onFocus={(e) => e.currentTarget.select()} className="mt-2 w-full rounded-md border border-[#d0d7de] p-2 text-sm" rows={4} />}
        <div className="mt-5 flex flex-wrap justify-end gap-3">
          <button type="button" disabled={busy} onClick={() => void copy(url)} className="rounded-md border border-[#d0d7de] px-4 py-2 text-sm hover:bg-[#f6f8fa] disabled:opacity-50">仅复制链接</button>
          <button type="button" disabled={busy} onClick={() => void copy(postShareText(title, site, url))} className="rounded-md bg-[#0969da] px-4 py-2 text-sm font-medium text-white hover:bg-[#0550ae] disabled:opacity-50">复制分享内容</button>
        </div>
      </div>
    </dialog>
  </>;
}
