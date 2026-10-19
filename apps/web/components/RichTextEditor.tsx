"use client";

import { useEffect, useRef, useState } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Heading from "@tiptap/extension-heading";
import { generateHTML } from "@tiptap/core";
import Image from "@tiptap/extension-image";
import { TableKit } from "@tiptap/extension-table";
import { Markdown } from "@tiptap/markdown";
import TaskList from "@tiptap/extension-task-list";
import TaskItem from "@tiptap/extension-task-item";
import { http } from "@/lib/api";
import { MarkdownView } from "./ui";
import { richEditorIcons } from "./rich-editor-icons";
import { RichEditorParagraph, preserveTextSpacing } from "./rich-editor-paragraph";
import { RichEditorTable } from "./rich-editor-table";
import "./rich-editor.css";

type Props = {
  value?: string;
  onChange?: (markdown: string) => void;
  placeholder?: string;
  height?: number;
  toolbarConfig?: object;
  cacheId?: string;
};

/** Visual editing with the existing Markdown API, search and Agent storage contract. */
export function RichTextEditor({ value = "", onChange, placeholder = "请输入正文…", height = 480 }: Props) {
  const latest = useRef({ value, onChange });
  latest.current = { value, onChange };
  const emitted = useRef(value);
  const input = useRef<HTMLInputElement>(null);
  const imageInput = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [pane, setPane] = useState("edit");
  const [preview, setPreview] = useState(value);
  const [linkOpen, setLinkOpen] = useState(false);
  const [linkUrl, setLinkUrl] = useState("");
  const [linkText, setLinkText] = useState("");
  const [, refreshToolbar] = useState(0);
  const editor = useEditor({
    immediatelyRender: false,
    enableInputRules: false,
    enablePasteRules: false,
    extensions: [
      StarterKit.configure({ paragraph: false, heading: false, underline: false, link: { openOnClick: false, autolink: false } }),
      RichEditorParagraph,
      Heading.extend({ renderMarkdown: (node, helpers) => {
        const content = preserveTextSpacing(node.content || []);
        if (content[0]?.text && /^[\s\u00a0]/.test(content[0].text)) {
          content[0] = { ...content[0], text: content[0].text.replace(/^[ \t]+/, spaces => spaces.replace(/ /g, "\u00a0").replace(/\t/g, "\u00a0\u00a0\u00a0\u00a0")) };
          return generateHTML({ type: "doc", content: [{ ...node, content }] }, [StarterKit, Image]);
        }
        return `${"#".repeat(node.attrs?.level || 1)} ${helpers.renderChildren(content).replace(/(\s)(#+)(\s*)$/, "$1\\$2$3")}`;
      } }),
      Image.configure({ allowBase64: false }),
      TaskList,
      TaskItem.configure({ nested: true }),
      TableKit.configure({ table: false }),
      RichEditorTable.configure({ resizable: false }),
      Markdown.configure({ markedOptions: { gfm: true } }),
    ],
    content: value,
    contentType: "markdown",
    editorProps: {
      attributes: { class: "md-body rich-editor-input", "aria-label": "正文富文本编辑", "data-placeholder": placeholder },
      handlePaste: (view, event) => {
        const files = Array.from(event.clipboardData?.files || []);
        if (!files.length) {
          // Preserve blank lines in plain-text paste. Rich HTML retains supported formatting.
          const text = event.clipboardData?.getData("text/plain");
          if (!text || event.clipboardData?.getData("text/html") || view.state.selection.$from.parent.type.spec.code) return false;
          event.preventDefault();
          editor?.commands.insertContent(text.replace(/\r\n?/g, "\n").split("\n").map(line => ({
            type: "paragraph", content: line ? [{ type: "text", text: line }] : [],
          })));
          return true;
        }
        event.preventDefault();
        void uploadFiles(files);
        return true;
      },
      handleDrop: (_view, event, _slice, moved) => {
        if (moved || !event.dataTransfer?.files.length) return false;
        event.preventDefault();
        void uploadFiles(Array.from(event.dataTransfer.files));
        return true;
      },
    },
    onUpdate: ({ editor: current }) => {
      const markdown = current.getMarkdown();
      emitted.current = markdown;
      setPreview(markdown);
      latest.current.onChange?.(markdown);
    },
    onSelectionUpdate: () => refreshToolbar(n => n + 1),
    onTransaction: () => refreshToolbar(n => n + 1),
  });

  useEffect(() => {
    setPreview(value);
    if (editor && value !== emitted.current) {
      editor.commands.setContent(value, { contentType: "markdown", emitUpdate: false });
      emitted.current = value;
    }
  }, [value, editor]);

  async function uploadFiles(files: File[]) {
    if (!editor || busy) return;
    setBusy(true);
    setError("");
    try {
      for (const file of files) {
        const data = new FormData();
        data.append("file", file);
        const result = await http.upload<{ url: string; name: string }>("/uploads", data);
        if (editor.isDestroyed) return;
        if (/^image\//.test(file.type)) {
          editor.chain().focus().setImage({ src: result.url, alt: result.name || file.name }).run();
        } else {
          editor.chain().focus().insertContent({ type: "text", text: result.name || file.name, marks: [{ type: "link", attrs: { href: result.url } }] }).run();
          editor.chain().command(({ tr }) => { tr.setStoredMarks([]); return true; }).insertContent(" ").run();
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "上传失败，请重试");
    } finally {
      setBusy(false);
    }
  }

  function insertLink() {
    const url = linkUrl.trim();
    if (!/^(https?:\/\/|mailto:|\/(?!\/)|#)/i.test(url)) {
      setError("请输入 http://、https:// 或站内链接");
      return;
    }
    editor?.chain().focus().insertContent({ type: "text", text: linkText.trim() || url, marks: [{ type: "link", attrs: { href: url } }] }).command(({ tr }) => { tr.setStoredMarks([]); return true; }).run();
    setLinkOpen(false);
    setError("");
  }

  const button = (label: string, action: () => void, active = false, disabled = false) => (
    <button key={label} type="button" title={label} aria-label={label} aria-pressed={active} disabled={!editor || disabled}
      onMouseDown={event => event.preventDefault()} onClick={action}
      className={`rich-tool ${richEditorIcons[label] ? "rich-icon-tool" : ""} ${active ? "rich-tool-active" : ""}`}>
      {richEditorIcons[label] ? <span aria-hidden="true" dangerouslySetInnerHTML={{ __html: richEditorIcons[label] }} /> : label}
    </button>
  );
  const heading = [1, 2, 3].find(level => editor?.isActive("heading", { level })) || 0;
  return (
    <div className="rich-editor rounded-lg border border-[#d0d7de] bg-white">
      <div className="rich-toolbar" role="toolbar" aria-label="正文格式">
        <select aria-label="段落样式" value={heading} disabled={!editor} onChange={event => {
          const level = Number(event.target.value) as 1 | 2 | 3;
          if (level) editor?.chain().focus().setHeading({ level }).run();
          else editor?.chain().focus().setParagraph().run();
        }} className="rounded border border-[#d0d7de] bg-white px-2 py-1">
          <option value={0}>正文</option><option value={1}>一级标题</option><option value={2}>二级标题</option><option value={3}>三级标题</option>
        </select>
        {button("加粗", () => editor?.chain().focus().toggleBold().run(), editor?.isActive("bold"))}
        {button("斜体", () => editor?.chain().focus().toggleItalic().run(), editor?.isActive("italic"))}
        {button("删除线", () => editor?.chain().focus().toggleStrike().run(), editor?.isActive("strike"))}
        {button("无序列表", () => editor?.chain().focus().toggleBulletList().run(), editor?.isActive("bulletList"))}
        {button("有序列表", () => editor?.chain().focus().toggleOrderedList().run(), editor?.isActive("orderedList"))}
        {button("引用", () => editor?.chain().focus().toggleBlockquote().run(), editor?.isActive("blockquote"))}
        {button("代码块", () => editor?.chain().focus().toggleCodeBlock().run(), editor?.isActive("codeBlock"))}
        {button("行内代码", () => editor?.chain().focus().toggleCode().run(), editor?.isActive("code"))}
        {button("任务列表", () => editor?.chain().focus().toggleTaskList().run(), editor?.isActive("taskList"))}
        {button("链接", () => { setLinkUrl(editor?.getAttributes("link").href || ""); setLinkText(editor?.state.doc.textBetween(editor.state.selection.from, editor.state.selection.to) || ""); setLinkOpen(!linkOpen); })}
        {button("图片", () => imageInput.current?.click(), false, busy)}
        {button(busy ? "上传中…" : "视频 / 附件", () => input.current?.click(), false, busy)}
        {button("表格", () => editor?.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run())}
        {button("撤销", () => editor?.chain().focus().undo().run(), false, !editor?.can().undo())}
        {button("重做", () => editor?.chain().focus().redo().run(), false, !editor?.can().redo())}
      </div>
      {editor?.isActive("table") && <div className="rich-toolbar" aria-label="表格操作">
        {button("添加行", () => editor.chain().focus().addRowAfter().run())}
        {button("添加列", () => editor.chain().focus().addColumnAfter().run())}
        {button("删除行", () => editor.chain().focus().deleteRow().run())}
        {button("删除列", () => editor.chain().focus().deleteColumn().run())}
        {button("删除表格", () => editor.chain().focus().deleteTable().run())}
      </div>}
      {linkOpen && <div className="flex flex-wrap gap-2 border-b border-[#d0d7de] p-2">
        <input aria-label="链接文字" placeholder="链接文字" value={linkText} onChange={e => setLinkText(e.target.value)} className="min-w-0 rounded border border-[#d0d7de] px-2 py-1 text-sm" />
        <input aria-label="链接地址" placeholder="https://" value={linkUrl} onChange={e => setLinkUrl(e.target.value)} className="min-w-0 flex-1 rounded border border-[#d0d7de] px-2 py-1 text-sm" />
        <button type="button" onClick={insertLink} className="rich-tool">插入</button>
        <button type="button" onClick={() => setLinkOpen(false)} className="rich-tool">取消</button>
      </div>}
      <input ref={input} type="file" className="hidden" aria-label="上传视频或附件" onChange={e => { const files = Array.from(e.target.files || []); e.target.value = ""; void uploadFiles(files); }} />
      <input ref={imageInput} type="file" accept="image/png,image/jpeg,image/gif,image/webp" className="hidden" aria-label="上传图片" onChange={e => { const files = Array.from(e.target.files || []); e.target.value = ""; void uploadFiles(files); }} />
      {error && <div role="alert" className="border-b border-[#d0d7de] bg-[#ffebe9] px-3 py-2 text-sm text-[#cf222e]">{error}</div>}
      <div className="flex border-b border-[#d0d7de] md:hidden" role="tablist" aria-label="正文视图">
        {[["edit", "编辑"], ["preview", "预览"]].map(([id, name]) => <button type="button" role="tab" aria-selected={pane === id} key={id} onClick={() => setPane(id)} className={`flex-1 px-3 py-2 text-sm ${pane === id ? "border-b-2 border-[#0969da] text-[#0969da]" : "text-[#656d76]"}`}>{name}</button>)}
      </div>
      <div className="grid min-w-0 md:grid-cols-2" style={{ height: Math.max(height, 280) }}>
        <div className={`${pane === "edit" ? "block" : "hidden"} min-h-0 min-w-0 overflow-auto p-5 md:block md:border-r md:border-[#d0d7de]`}>
          <EditorContent editor={editor} />
        </div>
        <section aria-label="帖子实时预览" className={`${pane === "preview" ? "block" : "hidden"} min-h-0 overflow-auto p-5 md:block`}>
          <div className="mb-3 text-xs text-[#656d76]">预览</div>
          <MarkdownView content={preview} />
        </section>
      </div>
    </div>
  );
}
