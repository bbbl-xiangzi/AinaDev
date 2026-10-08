"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";

export function MarkdownView({ content, className = "" }: { content: string; className?: string }) {
  return (
    <div className={`md-body ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeHighlight, { ignoreMissing: true }]]}
        components={{
          a: ({ href, children }) => {
            const isExternal = href && /^https?:\/\//i.test(href);
            return (
              <a href={href} {...(isExternal ? { target: "_blank", rel: "noopener noreferrer" } : {})}>
                {children}
              </a>
            );
          },
          img: ({ src, alt }) => (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={src} alt={alt || ""} className="my-2 rounded-md border border-[#d0d7de]" loading="lazy" />
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

// Restore shared components used by existing pages (original implementation: f515b72).
export function Avatar({ name, url, size = 32, isAi = false }: { name?: string; url?: string | null; size?: number; isAi?: boolean }) {
  const initial = (name || "?").slice(0, 1).toUpperCase();
  return (
    <span className="relative inline-flex shrink-0 items-center justify-center rounded-full bg-[#d0d7de] text-[#24292f] font-semibold" style={{ width: size, height: size, fontSize: size * 0.45 }}>
      {url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={url} alt={name || ""} className="h-full w-full rounded-full object-cover" />
      ) : (
        initial
      )}
      {isAi && (
        <span className="absolute -bottom-0.5 -right-0.5 flex h-[14px] w-[14px] items-center justify-center rounded-full bg-[#0969da] text-[8px] font-bold text-white ring-2 ring-white">
          AI
        </span>
      )}
    </span>
  );
}

export function TimeAgo({ iso }: { iso?: string }) {
  if (!iso) return null;
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return <span>{Math.max(0, Math.floor(diff))} 秒前</span>;
  if (diff < 3600) return <span>{Math.floor(diff / 60)} 分钟前</span>;
  if (diff < 86400) return <span>{Math.floor(diff / 3600)} 小时前</span>;
  if (diff < 86400 * 7) return <span>{Math.floor(diff / 86400)} 天前</span>;
  return <span>{d.toLocaleDateString("zh-CN")}</span>;
}
