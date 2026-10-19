"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { http } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { canPostInCategory, initialPostCategory } from "@/lib/post-category";
import { BytemdEditor } from "@/components/BytemdEditor";

export default function NewPostPage() {
  return <Suspense fallback={null}><NewPostForm /></Suspense>;
}

function NewPostForm() {
  const { user } = useAuth();
  const router = useRouter();
  const requestedCategory = useSearchParams().get("category_id");
  const [cats, setCats] = useState<any[]>([]);
  const [categoryId, setCategoryId] = useState<number>(0);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState(() => {
    if (typeof window === "undefined") return "";
    try {
      return JSON.parse(localStorage.getItem("post_draft") || "{}").body || "";
    } catch {
      return "";
    }
  });
  const [postType, setPostType] = useState("discussion");
  const [atAi, setAtAi] = useState(true);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!user) {
      router.push("/login");
      return;
    }
    let cancelled = false;
    http.get("/categories").then((d) => {
      if (cancelled) return;
      setCats(d);
      setCategoryId(initialPostCategory(d, requestedCategory, user.role));
    }).catch((err) => { if (!cancelled) setError(err.message || "栏目加载失败"); });
    return () => { cancelled = true; };
  }, [user, router, requestedCategory]);

  useEffect(() => {
    if (title || body) {
      localStorage.setItem("post_draft", JSON.stringify({ title, body }));
    }
  }, [title, body]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!categoryId) return setError("请选择栏目");
    if (!title.trim()) return setError("请输入标题");
    if (!body.trim()) return setError("正文不能为空");
    setLoading(true);
    try {
      const post = await http.post("/posts", { category_id: Number(categoryId), title, body_md: body, post_type: postType, at_ai: atAi, attachments: [] });
      localStorage.removeItem("post_draft");
      router.push(`/post/${post.id}`);
    } catch (err: any) {
      setError(err.message || "发帖失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-[920px] px-4 py-6">
      <h1 className="mb-4 text-[28px] font-semibold text-[#24292f]">发帖</h1>
      <form onSubmit={submit} className="space-y-4">
        <div className="flex gap-3">
          <select value={categoryId} onChange={(e) => setCategoryId(Number(e.target.value))} className="rounded-md border border-[#d0d7de] bg-white px-3 py-2 text-sm outline-none focus:border-[#0969da]">
            {!categoryId && <option value={0} disabled>请选择栏目</option>}
            {cats.map((c) => {
              const perm = c.post_permission || (c.allow_post ? "public" : "closed");
              const disabled = !canPostInCategory(c, user?.role);
              const suffix = perm === "staff_only" ? "（仅管理员）" : perm === "closed" ? "（关闭）" : "";
              return (
                <option key={c.id} value={c.id} disabled={disabled}>
                  {c.icon} {c.name}{suffix}
                </option>
              );
            })}
          </select>
          <select value={postType} onChange={(e) => setPostType(e.target.value)} className="rounded-md border border-[#d0d7de] bg-white px-3 py-2 text-sm outline-none">
            <option value="discussion">讨论</option>
            <option value="question">问答</option>
          </select>
          <label className="flex items-center gap-2 text-sm text-[#656d76]">
            <input type="checkbox" checked={atAi} onChange={(e) => setAtAi(e.target.checked)} />
            @ 栏目 AI 管理员
          </label>
        </div>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="标题"
          required
          className="w-full rounded-md border border-[#d0d7de] px-4 py-3 text-[20px] font-medium outline-none focus:border-[#0969da]"
        />
        <BytemdEditor value={body} onChange={setBody} />
        {error && <div className="rounded-md bg-[#ffebe9] px-3 py-2 text-[13px] text-[#cf222e]">{error}</div>}
        <button type="submit" disabled={loading} className="rounded-md bg-[#0969da] px-5 py-2.5 text-[14px] text-white disabled:opacity-50">
          {loading ? "发布中…" : "发布"}
        </button>
      </form>
    </div>
  );
}
