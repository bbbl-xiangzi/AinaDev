import { generateHTML } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import Image from "@tiptap/extension-image";
import { Table, TableKit } from "@tiptap/extension-table";
import TaskList from "@tiptap/extension-task-list";
import TaskItem from "@tiptap/extension-task-item";

// GFM cannot represent headerless/merged cells or multiple paragraphs in a cell.
// HTML tables round-trip through Tiptap; the shared viewer sanitizes them.
export const RichEditorTable = Table.extend({
  renderMarkdown(node) {
    return generateHTML({ type: "doc", content: [node] }, [
      StarterKit, Image, TableKit, TaskList, TaskItem.configure({ nested: true }),
    ]);
  },
});
