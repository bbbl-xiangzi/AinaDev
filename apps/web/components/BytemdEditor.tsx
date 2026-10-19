"use client";
import { useEffect, useState } from "react";
import dynamic from "next/dynamic";

const MarkdownEditor = dynamic(() => import("./MarkdownEditor").then(m => m.MarkdownEditor), { ssr: false });
const RichTextEditor = dynamic(() => import("./RichTextEditor").then(m => m.RichTextEditor), { ssr: false });
type Props = {
  value?: string; onChange?: (markdown: string) => void; placeholder?: string;
  height?: number; toolbarConfig?: object; cacheId?: string;
};

/** Both editors retain the existing Markdown persistence and draft contract. */
export function BytemdEditor(props: Props) {
  const [mode, setMode] = useState<"markdown" | "rich">("markdown");
  const [value, setValue] = useState(props.value || "");
  useEffect(() => { setValue(props.value || ""); }, [props.value]);
  const shared = { ...props, value, onChange: (next: string) => { setValue(next); props.onChange?.(next); } };
  return <div>
    <div className="mb-2 flex flex-wrap items-center gap-2 text-sm" role="group" aria-label="编辑模式">
      {([['markdown', 'Markdown'], ['rich', '富文本']] as const).map(([key, label]) => <button key={key} type="button" aria-pressed={mode === key} onClick={() => setMode(key)} className={`rounded border border-[#d0d7de] px-3 py-1.5 ${mode === key ? "bg-[#0969da]/10 text-[#0969da]" : "bg-white text-[#656d76]"}`}>{label}</button>)}
      <span className="text-xs text-[#656d76]">富文本支持常用排版；复杂 Markdown 建议使用源码模式</span>
    </div>
    {mode === "rich" ? <RichTextEditor {...shared} /> : <MarkdownEditor {...shared} />}
  </div>;
}
