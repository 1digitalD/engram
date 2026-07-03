import { useEffect, useMemo, useRef } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { Markdown } from '@tiptap/markdown';
import Placeholder from '@tiptap/extension-placeholder';
import TaskList from '@tiptap/extension-task-list';
import TaskItem from '@tiptap/extension-task-item';
import { createMentionExtension } from './mentionExtension';
import styles from './MarkdownEditor.module.css';

export default function MarkdownEditor({
  value = '',
  onChange,
  placeholder,
  ariaLabel,
  minRows = 4,
  autoFocus = false,
  className,
  onBlur,
  editable = true,
}) {
  const extensions = useMemo(() => [
    StarterKit.configure({ link: { openOnClick: false, autolink: false } }),
    Markdown.configure({ html: false, transformPastedText: true }),
    Placeholder.configure({ placeholder: placeholder || 'Write something…' }),
    TaskList,
    TaskItem.configure({ nested: true }),
    createMentionExtension({ name: 'personMention', char: '@', types: ['person'] }),
    createMentionExtension({ name: 'entityMention', char: '[[' }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
  ], []);

  // Tracks every markdown string this editor itself emitted via onChange
  // since the last externally-applied value, so the sync effect below can
  // tell "value is an echo of our own typing" (skip it — a render can carry
  // a value that is several keystrokes stale, and applying it would clobber
  // the newer keystrokes) apart from "value changed externally" (apply it,
  // e.g. initial content from voice capture, or a reset after submit).
  const emittedValuesRef = useRef(new Set([value]));

  const editor = useEditor({
    extensions,
    content: value,
    contentType: 'markdown',
    // Deliberately not using Tiptap's `autofocus` option here: it defers the
    // actual focus() call via `window.setTimeout(0)` (see @tiptap/core
    // Editor#mount), which can land *after* a caller has already started
    // typing (e.g. fast synthetic input in tests, or a very fast typist),
    // resetting the selection mid-stream and scrambling what's been typed
    // so far. We drive focus ourselves, once, in the effect below instead.
    editable,
    onUpdate({ editor: e }) {
      const markdown = e.getMarkdown();
      emittedValuesRef.current.add(markdown);
      onChange?.(markdown);
    },
    onBlur({ editor: e }) {
      onBlur?.(e.getMarkdown());
    },
    editorProps: {
      attributes: {
        class: styles.prosemirror,
        'aria-label': ariaLabel,
        style: `--min-rows: ${minRows}`,
      },
    },
  });

  // Sync external value changes (e.g. seeded initial content, clear after
  // submit) into the editor. Skipped when `value` merely echoes back
  // something this editor emitted itself (the normal typing round trip).
  useEffect(() => {
    if (!editor) return;
    const current = editor.getMarkdown();
    if (value === current) {
      // Caught up with the editor; older echoes can no longer arrive with a
      // value we haven't seen, so reset the tracking set to stay bounded.
      emittedValuesRef.current = new Set([value]);
      return;
    }
    if (emittedValuesRef.current.has(value)) return; // stale echo of our own typing
    editor.commands.setContent(value, { emitUpdate: false, contentType: 'markdown' });
    emittedValuesRef.current = new Set([value]);
  }, [value, editor]);

  useEffect(() => {
    if (!editor) return;
    if (editor.isEditable !== editable) editor.setEditable(editable);
  }, [editable, editor]);

  // Focus once, synchronously with editor availability, instead of via
  // Tiptap's deferred `autofocus` option (see comment above).
  const didAutoFocusRef = useRef(false);
  useEffect(() => {
    if (!editor || !autoFocus || didAutoFocusRef.current) return;
    didAutoFocusRef.current = true;
    editor.commands.focus('end');
    // focus('end') sets the selection synchronously but defers the actual
    // DOM focus a frame (requestAnimationFrame). Focus the view now so
    // keystrokes landing immediately after mount are not lost.
    editor.view.focus();
  }, [editor, autoFocus]);

  return (
    <div className={`${styles.editor} ${className || ''}`} data-testid="markdown-editor">
      <EditorContent editor={editor} />
    </div>
  );
}
