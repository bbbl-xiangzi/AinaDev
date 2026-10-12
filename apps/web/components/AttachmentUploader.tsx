"use client";

import { useRef, useState } from "react";
import { http } from "@/lib/api";
import { VideoPlayer } from "./VideoPlayer";
import { isUploadedVideo } from "@/lib/video";

export type AttachmentItem = {
  name: string;
  url: string;
  size: number;
  type: string;
};

/**
 * 通用附件上传：上传到 /api/uploads，返回附件元数据列表。
 * 父组件把 attachments 随帖子/回复一起提交。
 */
export function AttachmentUploader({
  attachments,
  onChange,
  max = 9,
  accept = ".png,.jpg,.jpeg,.gif,.webp,.pdf,.doc,.docx,.xls,.xlsx,.txt,.md,.csv,.zip,.mp4,.webm",
}: {
  attachments: AttachmentItem[];
  onChange: (list: AttachmentItem[]) => void;
  max?: number;
  accept?: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [err, setErr] = useState("");

  const pick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    e.target.value = "";
    if (files.length === 0) return;
    if (attachments.length + files.length > max) {
      setErr(`最多 ${max} 个附件`);
      return;
    }
    setErr("");
    setUploading(true);
    try {
      const added: AttachmentItem[] = [];
      for (const f of files) {
        const fd = new FormData();
        fd.append("file", f);
        const r = await http.upload<AttachmentItem>("/uploads", fd);
        added.push(r);
      }
      onChange([...attachments, ...added]);
    } catch (e: any) {
      setErr(e.message || "上传失败");
    } finally {
      setUploading(false);
    }
  };

  const remove = (url: string) => onChange(attachments.filter((a) => a.url !== url));

  const fmtSize = (n: number) => (n >= 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)}MB` : `${Math.max(1, Math.round(n / 1024))}KB`);

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
          className="rounded-md border border-[#d0d7de] px-3 py-1.5 text-[13px] hover:bg-[#f6f8fa] disabled:opacity-60"
        >
          {uploading ? "上传中…" : "+ 添加附件"}
        </button>
        <input ref={inputRef} type="file" multiple accept={accept} className="hidden" onChange={pick} />
        <span className="text-[12px] text-[#656d76]">{attachments.length}/{max} · 支持图片/视频/文档/压缩包</span>
      </div>

      {attachments.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {attachments.map((a) => (
            <div key={a.url} className="flex items-center gap-2 rounded-md border border-[#d0d7de] bg-[#f6f8fa] px-2 py-1 text-[12px]">
              {a.type === "image" ? (
                <img src={a.url} alt={a.name} className="h-6 w-6 rounded object-cover" />
              ) : (
                <span className="text-[#656d76]">📎</span>
              )}
              <span className="max-w-[160px] truncate" title={a.name}>{a.name}</span>
              <span className="text-[#656d76]">{fmtSize(a.size)}</span>
              <button type="button" onClick={() => remove(a.url)} className="text-[#cf222e] hover:underline">移除</button>
            </div>
          ))}
        </div>
      )}
      {err && <p className="mt-1 text-[12px] text-[#cf222e]">{err}</p>}
    </div>
  );
}

/** 渲染附件列表（帖子详情/回复中使用）。 */
export function AttachmentList({ items }: { items: AttachmentItem[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {items.map((a, i) =>
        isUploadedVideo(a.url) ? (
          <VideoPlayer key={i} url={a.url} name={a.name} />
        ) : a.type === "image" ? (
          <a key={i} href={a.url} target="_blank" rel="noreferrer" className="block">
            <img src={a.url} alt={a.name} className="max-h-48 rounded-lg border border-[#d0d7de] object-contain" />
          </a>
        ) : (
          <a
            key={i}
            href={a.url}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2 rounded-md border border-[#d0d7de] bg-[#f6f8fa] px-3 py-2 text-[13px] hover:bg-white"
          >
            <span>📎</span>
            <span className="max-w-[240px] truncate">{a.name}</span>
            <span className="text-[12px] text-[#656d76]">{(a.size / 1024).toFixed(0)}KB</span>
          </a>
        )
      )}
    </div>
  );
}
