import Image from "@tiptap/extension-image";

/** Preserve image attributes when converting pasted HTML into Markdown. */
export const RichEditorImage = Image.extend({
  renderMarkdown(node) {
    const attrs = node.attrs || {};
    const src = String(attrs.src || "").replace(/[\s<>\\]/g, char => encodeURIComponent(char));
    const alt = String(attrs.alt || "").replace(/\\/g, "\\\\").replace(/[\[\]]/g, char => `\\${char}`).replace(/[\r\n]+/g, " ");
    const title = String(attrs.title || "").replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/[\r\n]+/g, " ");
    return `![${alt}](<${src}>${title ? ` "${title}"` : ""})`;
  },
});
