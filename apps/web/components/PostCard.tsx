"use client";

import Link from "next/link";
import { Avatar, TimeAgo } from "./ui";

const TYPE_LABEL: Record<string, string> = {
  question: "问答",
  discussion: "讨论",
  announcement: "公告",
  news: "资讯",
};

export function PostCard({ post }: { post: any }) {
  return (
    <div className="flex gap-3 border-b border-[#d0d7de]/60 px-1 py-3 hover:bg-white/60">
      <div className="flex w-14 shrink-0 flex-col items-center gap-0.5 pt-0.5">
        <span className="text-[13px] font-semibold text-[#24292f]">{post.reply_count}</span>
        <span className="text-[11px] text-[#656d76]">回复</span>
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {post.pinned && <span className="rounded bg-[#fff8c5] px-1.5 py-0.5 text-[11px] font-medium text-[#9a6700]">置顶</span>}
          {post.featured && <span className="rounded bg-[#dafbe1] px-1.5 py-0.5 text-[11px] font-medium text-[#1a7f37]">精华</span>}
          {post.is_solved && <span className="rounded bg-[#dafbe1] px-1.5 py-0.5 text-[11px] font-medium text-[#1a7f37]">已解决</span>}
          {post.status === "rejected" && <span className="rounded bg-[#ffebe9] px-1.5 py-0.5 text-[11px] font-medium text-[#cf222e]">审核未通过</span>}
          {post.status === "pending_review" && <span className="rounded bg-[#fff8c5] px-1.5 py-0.5 text-[11px] font-medium text-[#9a6700]">审核中</span>}
          {post.post_type !== "discussion" && (
            <span className="rounded bg-[#ddf4ff] px-1.5 py-0.5 text-[11px] font-medium text-[#0969da]">{TYPE_LABEL[post.post_type] || post.post_type}</span>
          )}
          {post.author_type === "ai_agent" && <span className="rounded bg-[#0969da]/10 px-1.5 py-0.5 text-[11px] font-medium text-[#0969da]">官方/AI</span>}
        </div>
        <Link href={`/post/${post.id}`} className="mt-0.5 block truncate text-[16px] font-medium text-[#24292f] hover:text-[#0969da]">
          {post.title}
        </Link>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-[12px] text-[#656d76]">
          <span className="flex items-center gap-1">
            <Avatar name={post.author_name} url={post.author_avatar} size={16} isAi={post.author_type === "ai_agent"} />
            {post.author_name}
          </span>
          <span>·</span>
          <span>{post.category_name}</span>
          <span>·</span>
          <TimeAgo iso={post.created_at} />
          {post.ai_handled && <span className="rounded bg-[#0969da]/10 px-1.5 py-0.5 text-[11px] text-[#0969da]">AI 已回复</span>}
          {post.status === "rejected" && post.review_reason && (
            <span className="text-[11px] text-[#cf222e]" title={post.review_reason}>未通过原因：{post.review_reason}</span>
          )}
          {post.tags?.slice(0, 3).map((t: string) => (
            <span key={t} className="rounded bg-[#eaeef2] px-1.5 py-0.5 text-[11px] text-[#656d76]">
              {t}
            </span>
          ))}
        </div>
      </div>
      <div className="hidden shrink-0 items-center gap-2 text-[12px] text-[#656d76] sm:flex">
        <span>👁 {post.view_count}</span>
        <span>👍 {post.like_count}</span>
      </div>
    </div>
  );
}
