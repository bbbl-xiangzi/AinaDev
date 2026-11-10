"use client";

/** 通用模态弹窗：白色磨砂玻璃遮罩 + 居中卡片。 */

import { useEffect, useRef } from "react";

const modalStack: symbol[] = [];
let initialOverflow: string | undefined;

type Props = {
  open: boolean;
  title: string;
  width?: number;
  onClose: () => void;
  children: React.ReactNode;
};

export function Modal({ open, title, width = 640, onClose, children }: Props) {
  const content = useRef<HTMLDivElement>(null);
  const modalId = useRef(Symbol("modal"));
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    if (!open) return;
    const id = modalId.current;
    if (!modalStack.length) initialOverflow = document.body.style.overflow;
    modalStack.push(id);
    const isTop = () => modalStack[modalStack.length - 1] === id;
    const previous = document.activeElement as HTMLElement | null;
    document.body.style.overflow = "hidden";
    const controls = () => Array.from(content.current?.querySelectorAll<HTMLElement>(
      'button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select:not(:disabled), a[href], [tabindex="0"], [contenteditable="true"]'
    ) || []).filter(element => element.getClientRects().length > 0);
    const focusFirst = () => (controls()[0] || content.current)?.focus();
    focusFirst();
    const onKey = (e: KeyboardEvent) => {
      if (!isTop()) return;
      if (e.key === "Escape") { e.preventDefault(); e.stopImmediatePropagation(); close.current(); }
      if (e.key !== "Tab") return;
      const items = controls(), first = items[0], last = items[items.length - 1];
      if (!first) { e.preventDefault(); content.current?.focus(); }
      else if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    const containFocus = (e: FocusEvent) => { if (isTop() && e.target instanceof Node && !content.current?.contains(e.target)) focusFirst(); };
    document.addEventListener("keydown", onKey);
    document.addEventListener("focusin", containFocus);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("focusin", containFocus);
      const wasTop = isTop();
      const index = modalStack.indexOf(id);
      if (index >= 0) modalStack.splice(index, 1);
      document.body.style.overflow = modalStack.length ? "hidden" : initialOverflow || "";
      if (!modalStack.length) initialOverflow = undefined;
      if (wasTop && previous?.isConnected) previous.focus();
    };
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-white/60 p-4 backdrop-blur-md"
      onClick={onClose}
    >
      <div
        ref={content}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="max-h-[85vh] w-full overflow-y-auto rounded-xl border border-white/60 bg-white p-6 shadow-2xl shadow-black/10"
        style={{ maxWidth: width }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-[16px] font-semibold text-[#24292f]">{title}</h3>
          <button
            type="button"
            aria-label={`关闭${title}`}
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded-md text-[#656d76] hover:bg-[#eaeef2] hover:text-[#24292f]"
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
