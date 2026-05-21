import React, { useEffect } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { Markdown } from '@tiptap/markdown';
import Placeholder from '@tiptap/extension-placeholder';
import TaskList from '@tiptap/extension-task-list';
import TaskItem from '@tiptap/extension-task-item';
import styles from './MarkdownEditor.module.css';

export default function MarkdownEditor({
  value = '',
  onChange,
  placeholder,
  minRows = 4,
  autoFocus = false,
  className,
  onBlur,
}) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Markdown.configure({ html: false, transformPastedText: true }),
      Placeholder.configure({ placeholder: placeholder || 'Write something…' }),
      TaskList,
      TaskItem.configure({ nested: true }),
    ],
    content: value,
    contentType: 'markdown',
    autofocus: autoFocus,
    onUpdate({ editor: e }) {
      onChange?.(e.getMarkdown());
    },
    onBlur({ editor: e }) {
      onBlur?.(e.getMarkdown());
    },
    editorProps: {
      attributes: {
        class: styles.prosemirror,
        style: `--min-rows: ${minRows}`,
      },
    },
  });

  // Sync external value resets (e.g. clear after submit)
  useEffect(() => {
    if (!editor) return;
    const current = editor.getMarkdown();
    if (value !== current) {
      editor.commands.setContent(value, false, { contentType: 'markdown' });
    }
  }, [value, editor]);

  return (
    <div className={`${styles.editor} ${className || ''}`}>
      <EditorContent editor={editor} />
    </div>
  );
}
