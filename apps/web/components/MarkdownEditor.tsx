"use client";

/**
 * ByteMD 编辑器封装：
 * - 工具栏带「图片上传」「上传附件」两个按钮，均走项目 /api/uploads（登录鉴权）
 * - 完全本地化（npm 打包，无 CDN 依赖）
 * - 内嵌 GitHub 风格 .markdown-body 样式，防止被全局 Tailwind preflight 覆盖
 */

import { useEffect, useMemo, useRef } from "react";
import { Editor } from "@bytemd/react";
import gfm from "@bytemd/plugin-gfm";
import highlight from "@bytemd/plugin-highlight";
import zh_Hans from "bytemd/locales/zh_Hans.json";
import gfmZh from "@bytemd/plugin-gfm/locales/zh_Hans.json";
import "bytemd/dist/index.css";
import { http } from "@/lib/api";
import { isUploadedVideo } from "@/lib/video";

type Props = {
  active?: boolean;
  onBusyChange?: (busy: boolean) => void;
  value?: string;
  onChange?: (md: string) => void;
  placeholder?: string;
  height?: number;
  toolbarConfig?: object; // 兼容旧编辑器接口，ByteMD 无需
  cacheId?: string; // 兼容旧接口；页面已自行处理草稿缓存
};

/** 上传单个文件到 /api/uploads，返回后端元数据。 */
async function uploadFile(file: File): Promise<{ url: string; name: string; size: number; type: string }> {
  const fd = new FormData();
  fd.append("file", file);
  return http.upload<{ url: string; name: string; size: number; type: string }>("/uploads", fd);
}

const IMAGE_EXT = new Set(["png", "jpg", "jpeg", "gif", "webp", "bmp", "svg", "ico"]);

/** GitHub 风格 Markdown 正文样式（覆盖 .markdown-body 内元素，抵御 Tailwind preflight 的 reset） */
const MARKDOWN_BODY_CSS = `
.bytemd-wrap .markdown-body {
  font-size: 15px; line-height: 1.7; color: #24292f; word-break: break-word;
}
.bytemd-wrap .markdown-body h1,.bytemd-wrap .markdown-body h2,.bytemd-wrap .markdown-body h3,
.bytemd-wrap .markdown-body h4,.bytemd-wrap .markdown-body h5,.bytemd-wrap .markdown-body h6 {
  margin: 24px 0 12px; font-weight: 600; line-height: 1.3; color: #1f2328;
}
.bytemd-wrap .markdown-body h1 { font-size: 2em; padding-bottom: 0.3em; border-bottom: 1px solid #d8dee4; }
.bytemd-wrap .markdown-body h2 { font-size: 1.5em; padding-bottom: 0.3em; border-bottom: 1px solid #d8dee4; }
.bytemd-wrap .markdown-body h3 { font-size: 1.25em; }
.bytemd-wrap .markdown-body h4 { font-size: 1em; }
.bytemd-wrap .markdown-body h5 { font-size: 0.875em; }
.bytemd-wrap .markdown-body h6 { font-size: 0.85em; color: #57606a; }
.bytemd-wrap .markdown-body p { margin: 0 0 14px; }
.bytemd-wrap .markdown-body a { color: #0969da; text-decoration: none; }
.bytemd-wrap .markdown-body a:hover { text-decoration: underline; }
.bytemd-wrap .markdown-body ul,.bytemd-wrap .markdown-body ol { padding-left: 2em; margin: 0 0 14px; }
.bytemd-wrap .markdown-body ul { list-style: disc; }
.bytemd-wrap .markdown-body ul ul { list-style: circle; }
.bytemd-wrap .markdown-body ul ul ul { list-style: square; }
.bytemd-wrap .markdown-body ol { list-style: decimal; }
.bytemd-wrap .markdown-body li { margin: 0.25em 0; }
.bytemd-wrap .markdown-body li > p { margin: 0; }
.bytemd-wrap .markdown-body blockquote {
  margin: 0 0 14px; padding: 0 1em; color: #57606a;
  border-left: 0.25em solid #d0d7de;
}
.bytemd-wrap .markdown-body blockquote > :last-child { margin-bottom: 0; }
.bytemd-wrap .markdown-body pre {
  margin: 0 0 14px; padding: 14px 16px; overflow: auto;
  background: #0d1117; color: #e6edf3; border-radius: 6px; font-size: 13px;
}
.bytemd-wrap .markdown-body code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
  font-size: 85%; background: rgba(175,184,193,0.2); padding: 0.2em 0.4em; border-radius: 6px;
}
.bytemd-wrap .markdown-body pre > code { background: transparent; padding: 0; color: inherit; font-size: 100%; }
.bytemd-wrap .markdown-body table {
  margin: 0 0 14px; border-collapse: collapse; width: 100%; display: block; overflow-x: auto;
}
.bytemd-wrap .markdown-body th,.bytemd-wrap .markdown-body td {
  border: 1px solid #d0d7de; padding: 6px 13px; font-size: 14px;
}
.bytemd-wrap .markdown-body th { background: #f6f8fa; font-weight: 600; }
.bytemd-wrap .markdown-body tr:nth-child(2n) { background: #f6f8fa; }
.bytemd-wrap .markdown-body img { max-width: 100%; box-sizing: content-box; }
.bytemd-wrap .markdown-body hr { height: 0.25em; margin: 24px 0; border: 0; background: #d0d7de; }
.bytemd-wrap .markdown-body input[type="checkbox"] { margin-right: 6px; vertical-align: middle; }
.bytemd-wrap .markdown-body .hljs { background: transparent; }
`;

export function MarkdownEditor({ value = "", onChange, placeholder = "内容…", height = 360, cacheId, onBusyChange, active = true }: Props) {
  const editorRef = useRef<any>(null);
  useEffect(() => {
    if (!active) return;
    // CodeMirror skips measurement while hidden; refresh after it is shown.
    const frame = requestAnimationFrame(() => editorRef.current?.refresh());
    return () => cancelAnimationFrame(frame);
  }, [active, value]);
  // 插件实例保持稳定，避免每次渲染重建导致 @bytemd/react $set 抖动
  const plugins = useMemo(
    () => [
      { editorEffect({ editor }: { editor: any }) {
          editorRef.current = editor;
          return () => { if (editorRef.current === editor) editorRef.current = null; };
      } },
      gfm({ locale: gfmZh }),
      highlight(),
      {
        viewerEffect({ markdownBody }: { markdownBody: HTMLElement }) {
          markdownBody.querySelectorAll("a").forEach((link) => {
            const url = link.getAttribute("href") || "";
            if (!isUploadedVideo(url)) return;
            const video = document.createElement("video");
            video.src = url;
            video.controls = true;
            video.playsInline = true;
            video.preload = "metadata";
            video.setAttribute("aria-label", link.textContent || "视频");
            video.style.cssText = "display:block;max-width:100%;max-height:480px;border:1px solid #d0d7de;border-radius:8px;background:black;margin:8px 0";
            link.replaceWith(video);
          });
        },
      },
      {
        actions: [
          {
            title: "上传附件",
            icon: '<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M8.5 1.5a2.5 2.5 0 0 1 5 0V9a4 4 0 0 1-8 0V3.5a.75.75 0 0 1 1.5 0V9a2.5 2.5 0 0 0 5 0V1.5a1 1 0 0 0-2 0V8a.75.75 0 0 1-1.5 0V1.5Z"/><path fill="currentColor" d="M2 6.25a.75.75 0 0 1 1.5 0v2.75a4.5 4.5 0 0 0 9 0V6.25a.75.75 0 0 1 1.5 0v2.75a6 6 0 0 1-12 0V6.25Z"/></svg>',
            handler: {
              type: "action" as const,
              click: async (ctx: any) => {
                // 隐藏 input 选择任意类型文件，上传后在光标处插入 Markdown 链接
                const input = document.createElement("input");
                input.type = "file";
                input.accept = ".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.md,.csv,.zip,.rar,.7z,.png,.jpg,.jpeg,.gif,.webp,.mp4,.webm";
                input.onchange = async () => {
                  const file = input.files?.[0];
                  if (!file) return;
                  onBusyChange?.(true);
                  try {
                    const r = await uploadFile(file);
                    const editor = ctx.editor;
                    if (editor) {
                      const ext = file.name.split(".").pop()?.toLowerCase() || "";
                      const text = IMAGE_EXT.has(ext)
                        ? `![${file.name}](${r.url})`
                        : `[${file.name}](${r.url})`;
                      editor.replaceSelection(text);
                    }
                  } catch (e: any) {
                    alert(e.message || "上传失败");
                  } finally { onBusyChange?.(false); }
                };
                input.click();
              },
            },
          },
        ],
      },
    ],
    [onBusyChange]
  );

  return (
    <div style={{ height }} className="bytemd-wrap overflow-hidden rounded-lg">
      <style>{`
        .bytemd-wrap > div { height: 100%; }
        .bytemd-wrap .bytemd { height: 100% !important; }
        .bytemd-wrap .bytemd-body { height: calc(100% - 58px); }
        ${MARKDOWN_BODY_CSS}
      `}</style>
      <Editor
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        mode="split"
        plugins={plugins}
        locale={zh_Hans}
        uploadImages={async (files: File[]) => {
          const results = [];
          onBusyChange?.(true);
          try {
          for (const f of files) {
            try {
              const r = await uploadFile(f);
              results.push({ url: r.url, alt: f.name, title: f.name });
            } catch {
              /* 单文件失败跳过，其余继续 */
            }
          }
          return results;
          } finally { onBusyChange?.(false); }
        }}
      />
    </div>
  );
}
