"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { http } from "@/lib/api";
import { BytemdEditor } from "@/components/BytemdEditor";
import { AttachmentList } from "@/components/AttachmentUploader";

export default function EditPostPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [original, setOriginal] = useState<any>(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);
  const dirty = original && (title !== original.title || body !== original.body_md);
  useEffect(() => {
    let cancelled = false;
    setLoading(true); setOriginal(null); setError("");
    http.get(`/posts/${id}/edit`).then(data => {
      if (cancelled) return;
      setOriginal(data); setTitle(data.title); setBody(data.body_md);
    }).catch(err => { if (!cancelled) setError(err.message || "加载失败"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [id]);
  useEffect(() => {
    const leave = (event: BeforeUnloadEvent) => { if (dirty || uploading) { event.preventDefault(); event.returnValue = ""; } };
    window.addEventListener("beforeunload", leave);
    return () => window.removeEventListener("beforeunload", leave);
  }, [dirty, uploading]);
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (saving || uploading || !original) return;
    if (!title.trim() || !body.trim()) { setError("标题和正文不能为空"); return; }
    setSaving(true); setError("");
    try {
      await http.put(`/posts/${id}`, { title, body_md: body, revision: original.revision });
      setOriginal(null);
      router.push(`/post/${id}`);
    } catch (err: any) { setError(err.message || "保存失败，请重试"); }
    finally { setSaving(false); }
  }
  function cancel() {
    if ((!dirty && !uploading) || window.confirm("放弃未保存的修改和上传？")) router.push(`/post/${id}`);
  }
  return <div className="mx-auto max-w-[920px] px-4 py-6">
    <h1 className="mb-4 text-[28px] font-semibold text-[#24292f]">编辑帖子</h1>
    {loading && <div className="py-10 text-center text-sm text-[#656d76]">加载中…</div>}
    {original && <form onSubmit={save} className="space-y-4" aria-busy={saving}>
      <input aria-label="帖子标题" placeholder="标题" required maxLength={300} disabled={saving} value={title} onChange={e => setTitle(e.target.value)} className="w-full rounded-md border border-[#d0d7de] px-4 py-3 text-[20px] font-medium outline-none focus:border-[#0969da]" />
      <div inert={saving || undefined}><BytemdEditor value={body} onChange={setBody} onBusyChange={setUploading} /></div>
      <AttachmentList items={original.attachments} />
      {error && <div role="alert" className="rounded-md bg-[#ffebe9] px-3 py-2 text-[13px] text-[#cf222e]">{error}</div>}
      <div className="sticky bottom-0 z-20 flex gap-3 border-t border-[#d0d7de] bg-[#f6f8fa] py-3">
        <button type="submit" disabled={saving || uploading || !dirty} className="rounded-md bg-[#0969da] px-5 py-2.5 text-[14px] text-white disabled:opacity-50">{saving ? "审核并保存中…" : "保存修改"}</button>
        <button type="button" disabled={saving} onClick={cancel} className="rounded-md border border-[#d0d7de] px-5 py-2.5 text-[14px] text-[#656d76] hover:bg-[#f3f4f6]">取消</button>
      </div>
    </form>}
    {!original && !loading && <><div role="alert" className="mb-4 text-sm text-[#cf222e]">{error}</div><button onClick={() => router.push(`/post/${id}`)} className="text-sm text-[#0969da]">返回帖子</button></>}
  </div>;
}
