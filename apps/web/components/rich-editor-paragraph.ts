import Paragraph from "@tiptap/extension-paragraph";
import type { JSONContent } from "@tiptap/core";

// Use real non-breaking spaces, not entity strings that reappear as literal text.
export function preserveTextSpacing(nodes: JSONContent[]): JSONContent[] {
  return nodes.map(node => node.type === "text" && !node.marks?.some(mark => mark.type === "code")
    ? { ...node, text: node.text?.replace(/ {2,}|\t/g, spaces => spaces.replace(/ /g, "\u00a0").replace(/\t/g, "\u00a0\u00a0\u00a0\u00a0")) }
    : node);
}

/** Keep visual paragraph indentation from becoming Markdown's indented code syntax. */
export const RichEditorParagraph = Paragraph.extend({
  renderMarkdown(node, helpers) {
    const content = Array.isArray(node?.content) ? node.content : [];
    if (!content.length) {
      return "\u00a0";
    }
    return helpers.renderChildren(preserveTextSpacing(content))
      .replace(/^[ \t]+/gm, indentation =>
        indentation.replace(/ /g, "\u00a0").replace(/\t/g, "\u00a0\u00a0\u00a0\u00a0")
      )
      .replace(/^(#{1,6})(?=\s|$)/gm, "\\$1")
      .replace(/^([-+])(?=\s|$)/gm, "\\$1")
      .replace(/^(\d{1,9})([.)])(?=\s|$)/gm, "$1\\$2")
      .replace(/^(-{3,})(?=\s*$)/gm, "\\$1")
      .replace(/^([|:\-][|:\- \t]*\|[|:\- \t]*)$/gm, "\\$1")
      .replace(/^(=+)(?=\s*$)/gm, "\\$1");
  },
});
