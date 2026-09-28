"use client";

import { useEffect, useState, Suspense } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { http, getToken } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Avatar, MarkdownView, TimeAgo } from "@/components/ui";
import { Sidebar } from "@/components/Sidebar";
import { AttachmentList, type AttachmentItem } from "@/components/AttachmentUploader";
import { BytemdEditor } from "@/components/BytemdEditor";

/** 去掉 Markdown 语法符号，取纯文本摘要 */
function stripMd(s: string): string {
  return (s || "")
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^>\s?/gm, "")
    .replace(/[*_~]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function CitationPanel({ citations }: { citations: any[] | null }) {
  const [open, setOpen] = useState(false);
  if (!citations || citations.length === 0) return null;
  return (
    <div className="mt-3">
      <button onClick={() => setOpen(!open)} className="text-[12px] font-medium text-[#0969da] hover:underline">
        {open ? "收起" : "展开"}「为什么这么答？」（{citations.length} 条来源）
      </button>
      {open && (
        <div className="mt-2 space-y-2 rounded-md border border-[#d0d7de] bg-[#f6f8fa] p-3">
          {citations.map((c, i) => (
            <div key={i} className="text-[13px]">
              <div className="font-medium text-[#24292f]">
                [{i + 1}] {c.title || c.doc_id || "文档"}
                <span className="ml-2 text-[11px] text-[#656d76]">chunk #{c.chunk}</span>
              </div>
              <div className="mt-0.5 line-clamp-2 text-[#656d76]">{c.content}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PostInner() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useAuth();
  const [post, setPost] = useState<any>(null);
  const [replies, setReplies] = useState<any[]>([]);
  const [body, setBody] = useState("");
  const [parentReply, setParentReply] = useState<any | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [attachments, setAttachments] = useState<AttachmentItem[]>([]);

  const load = () => {
    http.get(`/posts/${params.id}`).then(setPost).catch(() => router.push("/"));
    http.get(`/posts/${params.id}/replies`).then(setReplies).catch(() => {});
  };

  useEffect(load, [params.id]);

  const submitReply = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!body.trim()) return;
    setSending(true);
    setError("");
    try {
      await http.post(`/posts/${params.id}/replies`, { post_id: Number(params.id), body_md: body, parent_reply_id: parentReply?.id ?? null, at_ai: false, attachments });
      setBody("");
      setParentReply(null);
      setAttachments([]);
      load();
    } catch (err: any) {
      setError(err.message || "回复失败");
    } finally {
      setSending(false);
    }
  };

  const likePost = async () => {
    if (!post) return;
    try {
      await http.post(post.is_liked ? `/posts/${post.id}/unlike` : `/posts/${post.id}/like`);
      load();
    } catch {
      /* ignore */
    }
  };

  const markSolved = async () => {
    if (!post) return;
    await http.post(`/posts/${post.id}/solved?solved=${!post.is_solved}`);
    load();
  };

  if (!post) return <div className="p-10 text-center text-sm text-[#656d76]">加载中…</div>;

  const canManage = user && (user.role === "super_admin");
  const sort = searchParams.get("sort");

  return (
    <div className="mx-auto flex max-w-[1280px] gap-8 px-4 py-6">
      <style>{`
        .reply-row { transition: background-color 0.3s; }
        .reply-row.reply-flash { background-color: #fff8c5; }
      `}</style>
      <Sidebar />
      <main className="min-w-0 flex-1">
        {/* 面包屑 Path */}
        <nav className="mb-3 flex items-center gap-1.5 text-[13px] text-[#656d76]">
          <a href={sort ? `/?sort=${sort}` : "/"} className="hover:text-[#0969da]">首页</a>
          <span>/</span>
          {post.category_name ? (
            <>
              <a href={`/c/${post.category_id}`} className="hover:text-[#0969da]">{post.category_name}</a>
              <span>/</span>
            </>
          ) : null}
          <span className="truncate text-[#24292f]">{post.title}</span>
        </nav>

        <div className="rounded-lg border border-[#d0d7de] bg-white p-6">
          <div className="flex flex-wrap items-center gap-2">
            {post.pinned && <span className="rounded bg-[#fff8c5] px-2 py-0.5 text-[12px] text-[#9a6700]">置顶</span>}
            {post.featured && <span className="rounded bg-[#dafbe1] px-2 py-0.5 text-[12px] text-[#1a7f37]">精华</span>}
            {post.is_solved && <span className="rounded bg-[#dafbe1] px-2 py-0.5 text-[12px] text-[#1a7f37]">已解决</span>}
            {post.locked && <span className="rounded bg-[#ffebe9] px-2 py-0.5 text-[12px] text-[#cf222e]">已锁定</span>}
            {post.status === "pending_review" && <span className="rounded bg-[#fff8c5] px-2 py-0.5 text-[12px] text-[#9a6700]">审核中（仅自己可见）</span>}
            {post.status === "rejected" && <span className="rounded bg-[#ffebe9] px-2 py-0.5 text-[12px] text-[#cf222e]">未通过审核</span>}
            {post.status === "rejected" && post.review_reason && (
              <span className="rounded bg-[#fff1f0] px-2 py-0.5 text-[12px] text-[#cf222e]">
                原因：{post.review_reason}
              </span>
            )}
            <span className="text-[13px] text-[#656d76]">{post.category_name}</span>
          </div>
          <h1 className="mt-2 text-[20px] font-semibold leading-snug text-[#24292f]">{post.title}</h1>
          <div className="mt-3 flex items-center gap-3 text-[13px] text-[#656d76]">
            <span className="flex items-center gap-2">
              <Avatar name={post.author_name} url={post.author_avatar} size={24} isAi={post.author_type === "ai_agent"} />
              <span className="font-medium text-[#24292f]">{post.author_name}</span>
            </span>
            <span>·</span>
            <TimeAgo iso={post.created_at} />
            <span>· 浏览 {post.view_count}</span>
            <span>· 回复 {post.reply_count}</span>
            {post.tags?.map((t: string) => (
              <span key={t} className="rounded bg-[#eaeef2] px-1.5 py-0.5 text-[12px] text-[#656d76]">#{t}</span>
            ))}
          </div>
          <div className="mt-6 border-t border-[#d0d7de]/60 pt-4">
            <MarkdownView content={post.body_md} />
          </div>
          <AttachmentList items={post.attachments} />
          <div className="mt-6 flex items-center gap-3 border-t border-[#d0d7de]/60 pt-4">
            <button onClick={likePost} className={`rounded-md border px-3 py-1.5 text-[13px] ${post.is_liked ? "border-[#0969da] bg-[#0969da]/10 text-[#0969da]" : "border-[#d0d7de] text-[#656d76] hover:bg-[#f3f4f6]"}`}>
              👍 点赞 {post.like_count}
            </button>
            {post.post_type === "question" && post.author_id === user?.id && (
              <button onClick={markSolved} className="rounded-md border border-[#d0d7de] px-3 py-1.5 text-[13px] text-[#1a7f37] hover:bg-[#dafbe1]">
                {post.is_solved ? "取消已解决" : "标记已解决"}
              </button>
            )}
            {canManage && (
              <button
                onClick={async () => {
                  await http.post(`/admin/posts/${post.id}/moderate?action=${post.status === "deleted" ? "restore" : "delete"}`);
                  load();
                }}
                className="ml-auto rounded-md border border-[#d0d7de] px-3 py-1.5 text-[13px] text-[#cf222e] hover:bg-[#ffebe9]"
              >
                {post.status === "deleted" ? "恢复" : "删除"}
              </button>
            )}
          </div>
        </div>

        {/* 回复流：GitHub 风格 */}
        <div className="mt-6">
          <h2 className="mb-2 text-[15px] font-semibold text-[#24292f]">回复（{replies.length}）</h2>
          <div className="rounded-lg border border-[#d0d7de] bg-white">
            {replies.length === 0 && <div className="px-4 py-10 text-center text-[13px] text-[#656d76]">暂无回复{post.human_needed ? " · AI 标记为需要人工介入" : ""}</div>}
            {replies.map((r, idx) => {
              const parent = r.parent_reply_id ? replies.find((x) => x.id === r.parent_reply_id) : null;
              return (
              <div key={r.id} id={`reply-${r.id}`} className={`reply-row flex gap-3 px-4 py-3 ${idx < replies.length - 1 ? "border-b border-[#d0d7de]/50" : ""}`}>
                <div className="flex flex-col items-center">
                  <Avatar name={r.author_name} url={r.author_avatar} size={32} isAi={r.author_type === "ai_admin" || r.author_type === "official"} />
                  {idx < replies.length - 1 && <div className="mt-1 w-px flex-1 bg-[#d0d7de]" />}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 text-[13px]">
                    <span className="font-medium text-[#24292f]">{r.author_name}</span>
                    {r.author_type !== "user" && (
                      <span className="rounded bg-[#0969da]/10 px-1.5 py-0.5 text-[11px] font-medium text-[#0969da]">
                        {r.author_type === "ai_admin" ? "AI 管理员" : "官方"}
                      </span>
                    )}
                    {r.status === "pending_review" && (
                      <span className="rounded bg-[#fff8c5] px-1.5 py-0.5 text-[11px] font-medium text-[#9a6700]">
                        AI 回复审核中
                      </span>
                    )}
                    <span className="text-[#656d76]">·</span>
                    <TimeAgo iso={r.created_at} />
                    <button
                      onClick={() => {
                        setParentReply(r);
                        window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
                      }}
                      className="ml-2 text-[12px] text-[#0969da] hover:underline"
                    >
                      引用
                    </button>
                  </div>
                  {parent && (
                    <button
                      type="button"
                      onClick={() => {
                        const el = document.getElementById(`reply-${parent.id}`);
                        el?.scrollIntoView({ behavior: "smooth", block: "center" });
                        el?.classList.add("reply-flash");
                        setTimeout(() => el?.classList.remove("reply-flash"), 1600);
                      }}
                      className="mb-2 block w-full rounded-md border-l-4 border-[#d0d7de] bg-[#f6f8fa] px-3 py-2 text-left hover:bg-[#eaeef2]"
                    >
                      <div className="text-[12px] text-[#656d76]">回复 @{parent.author_name || `#${parent.id}`}：</div>
                      <div className="mt-0.5 line-clamp-2 text-[13px] text-[#57606a]">{stripMd(parent.body_md) || "…"}</div>
                    </button>
                  )}
                  <div className="mt-1.5">
                    <MarkdownView content={r.body_md} />
                  </div>
                  <AttachmentList items={r.attachments} />
                  {r.author_type !== "user" && <CitationPanel citations={r.citations} />}
                  <div className="mt-2 flex items-center gap-3 text-[12px] text-[#656d76]">
                    <button
                      onClick={async () => {
                        try {
                          await http.post(`/replies/${r.id}/like`);
                          load();
                        } catch {
                          /* ignore */
                        }
                      }}
                      className="hover:text-[#0969da]"
                    >
                      👍 {r.like_count}
                    </button>
                    <button
                      onClick={async () => {
                        const reason = prompt("举报原因：");
                        if (reason) await http.post(`/replies/${r.id}/report?reason=${encodeURIComponent(reason)}`);
                      }}
                      className="hover:text-[#cf222e]"
                    >
                      举报
                    </button>
                  </div>
                </div>
              </div>
              );
            })}
          </div>

          {!post.locked && (
            <form onSubmit={submitReply} className="mt-4 rounded-lg border border-[#d0d7de] bg-white p-4">
              {parentReply && (
                <div className="mb-2 flex items-center justify-between rounded bg-[#eaeef2] px-3 py-1.5 text-[12px] text-[#656d76]">
                  <span className="min-w-0 truncate">
                    引用 @{parentReply.author_name || `#${parentReply.id}`}：{stripMd(parentReply.body_md) || "…"}
                  </span>
                  <button type="button" onClick={() => setParentReply(null)} className="ml-2 shrink-0 text-[#cf222e]">取消</button>
                </div>
              )}
              {user ? (
                <>
                  <BytemdEditor value={body} onChange={setBody} placeholder="写下你的回复…（支持 Markdown；工具栏可直接插入图片 / 附件）" height={180} />
                  {error && <div className="mb-2 rounded bg-[#ffebe9] px-3 py-1.5 text-[13px] text-[#cf222e]">{error}</div>}
                  <div className="flex justify-end">
                    <button disabled={sending} className="rounded-md bg-[#0969da] px-4 py-1.5 text-[13px] font-medium text-white hover:bg-[#0550ae] disabled:opacity-60">
                      {sending ? "回复中…" : "回复"}
                    </button>
                  </div>
                </>
              ) : (
                <div className="py-6 text-center text-[13px] text-[#656d76]">
                  <a href="/login" className="text-[#0969da]">登录</a> 后参与讨论
                </div>
              )}
            </form>
          )}
        </div>
      </main>
      <aside className="hidden w-[280px] shrink-0 space-y-4 lg:block">
        <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
          <div className="mb-2 text-[13px] font-semibold text-[#656d76]">公告</div>
          <p className="text-[13px] text-[#24292f]">欢迎使用 AI 原生开发者社区</p>
        </div>
      </aside>
    </div>
  );
}

export default function PostPage() {
  return (
    <Suspense fallback={<div className="p-10 text-center text-sm text-[#656d76]">加载中…</div>}>
      <PostInner />
    </Suspense>
  );
}
