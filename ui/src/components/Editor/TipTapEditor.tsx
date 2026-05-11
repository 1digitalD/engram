import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';
import TaskList from '@tiptap/extension-task-list';
import TaskItem from '@tiptap/extension-task-item';
import Link from '@tiptap/extension-link';
import CharacterCount from '@tiptap/extension-character-count';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Sparkles, Link2, Tag, CheckSquare, Bold, Italic,
  List, ListOrdered, Quote, Code, Heading1, Heading2,
  Loader2, Eye, Edit3, X,
} from 'lucide-react';
import useStore from '../../stores/useStore';
import styles from './TipTapEditor.module.css';

// ─── Slash Command Items ────────────────────────────────────────────────

const SLASH_COMMANDS = [
  { id: 'task', label: 'Task', icon: CheckSquare, description: 'Insert a task checkbox', shortcut: '/task' },
  { id: 'link', label: 'Link', icon: Link2, description: 'Insert a link', shortcut: '/link' },
  { id: 'tag', label: 'Tag', icon: Tag, description: 'Insert a tag mention', shortcut: '/tag' },
];

function SlashCommandMenu({ items, onSelect, selectedIndex }) {
  if (!items.length) return null;
  return (
    <div className={styles.slashMenu} data-testid="slash-menu" role="listbox">
      {items.map((item, i) => {
        const Icon = item.icon;
        return (
          <button
            key={item.id}
            role="option"
            aria-selected={i === selectedIndex}
            className={`${styles.slashItem} ${i === selectedIndex ? styles.slashItemSelected : ''}`}
            onClick={() => onSelect(item)}
            data-testid={`slash-item-${item.id}`}
          >
            <Icon size={16} />
            <div className={styles.slashItemText}>
              <span className={styles.slashItemLabel}>{item.label}</span>
              <span className={styles.slashItemDesc}>{item.description}</span>
            </div>
          </button>
        );
      })}
    </div>
  );
}

// ─── AI Assistant Panel ─────────────────────────────────────────────────

function AIPanel({ editor, onClose }) {
  const [prompt, setPrompt] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState('');
  const { addToast } = useStore();

  const handleAIAction = async () => {
    if (!prompt.trim() || busy) return;
    setBusy(true);
    try {
      // Simulate AI action — in production this calls the backend AI endpoint
      const selection = editor?.state.selection;
      const selectedText = selection ? editor.state.doc.textBetween(selection.from, selection.to, ' ') : '';
      const aiResponse = `[AI: ${prompt}]${selectedText ? ` for "${selectedText}"` : ''}`;
      setResult(aiResponse);

      if (editor && selectedText) {
        editor.chain().focus().insertContent(` ${aiResponse} `).run();
      } else if (editor) {
        editor.chain().focus().insertContent(`\n${aiResponse}\n`).run();
      }

      addToast({ type: 'success', message: 'AI assistant applied' });
      setPrompt('');
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'AI action failed' });
    } finally {
      setBusy(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleAIAction();
    }
    if (e.key === 'Escape') {
      onClose();
    }
  };

  return (
    <div className={styles.aiPanel} data-testid="ai-panel">
      <div className={styles.aiPanelHeader}>
        <span className={styles.aiPanelTitle}><Sparkles size={14} /> AI Assistant</span>
        <button className={styles.aiPanelClose} onClick={onClose} aria-label="Close AI panel">
          <X size={14} />
        </button>
      </div>
      <textarea
        className={styles.aiPrompt}
        placeholder="Ask AI to improve, summarize, or rewrite..."
        value={prompt}
        onChange={e => setPrompt(e.target.value)}
        onKeyDown={handleKeyDown}
        rows={3}
        autoFocus
        data-testid="ai-prompt"
      />
      <div className={styles.aiActions}>
        <span className={styles.aiHint}>Cmd/Ctrl+Enter to apply</span>
        <button
          className="btn btn-primary btn-sm"
          onClick={handleAIAction}
          disabled={busy || !prompt.trim()}
          data-testid="ai-apply-btn"
        >
          {busy ? <Loader2 size={13} className="spin" /> : <Sparkles size={13} />}
          Apply
        </button>
      </div>
      {result && (
        <div className={styles.aiResult} data-testid="ai-result">
          <span className={styles.aiResultLabel}>Result:</span>
          <p>{result}</p>
        </div>
      )}
    </div>
  );
}

// ─── Main TipTapEditor Component ────────────────────────────────────────

export default function TipTapEditor({
  initialContent = '',
  onSave,
  placeholder = 'Start writing...',
  noteId,
  className = '',
}) {
  const { createTask, addToast, tags } = useStore();
  const [showSlashMenu, setShowSlashMenu] = useState(false);
  const [slashQuery, setSlashQuery] = useState('');
  const [slashIndex, setSlashIndex] = useState(0);
  const [showAIPanel, setShowAIPanel] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const slashMenuRef = useRef(null);
  const slashPosRef = useRef(null);

  const filteredCommands = slashQuery
    ? SLASH_COMMANDS.filter(c =>
        c.id.toLowerCase().includes(slashQuery.toLowerCase()) ||
        c.label.toLowerCase().includes(slashQuery.toLowerCase())
      )
    : SLASH_COMMANDS;

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
        link: false,
      }),
      Placeholder.configure({ placeholder }),
      TaskList,
      TaskItem.configure({ nested: true }),
      Link.configure({ openOnClick: true }),
      CharacterCount.configure({ limit: 50000 }),
    ],
    content: initialContent,
    editorProps: {
      attributes: {
        class: styles.editorContent,
      },
    },
    onUpdate: ({ editor: ed }) => {
      const text = ed.getText();
      const slashMatch = text.slice(0, ed.state.selection.from).match(/\/(\w*)$/);
      if (slashMatch) {
        setSlashQuery(slashMatch[1]);
        setShowSlashMenu(true);
        setSlashIndex(0);
      } else {
        setShowSlashMenu(false);
        setSlashQuery('');
      }
    },
  });

  // Close slash menu on outside click
  useEffect(() => {
    const handler = (e) => {
      if (slashMenuRef.current && !slashMenuRef.current.contains(e.target)) {
        setShowSlashMenu(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Keyboard navigation for slash menu
  useEffect(() => {
    if (!showSlashMenu) return;
    const handler = (e) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSlashIndex(i => Math.min(i + 1, filteredCommands.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSlashIndex(i => Math.max(i - 1, 0));
      } else if (e.key === 'Enter' && filteredCommands.length > 0) {
        e.preventDefault();
        handleSlashSelect(filteredCommands[slashIndex]);
      } else if (e.key === 'Escape') {
        setShowSlashMenu(false);
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [showSlashMenu, slashIndex, filteredCommands]);

  const handleSlashSelect = useCallback((command) => {
    if (!editor) return;
    setShowSlashMenu(false);
    setSlashQuery('');

    // Remove the slash command text
    const { from } = editor.state.selection;
    const text = editor.state.doc.textBetween(0, from, ' ');
    const slashMatch = text.match(/\/\w*$/);
    if (slashMatch) {
      const deleteFrom = from - slashMatch[0].length;
      editor.chain().focus().deleteRange({ from: deleteFrom, to: from }).run();
    }

    switch (command.id) {
      case 'task':
        editor.chain().focus().toggleTaskList().run();
        addToast({ type: 'info', message: 'Task list inserted' });
        break;
      case 'link': {
        const url = prompt('Enter URL:');
        if (url) {
          editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
          addToast({ type: 'success', message: 'Link inserted' });
        }
        break;
      }
      case 'tag': {
        const tagName = prompt('Enter tag name:');
        if (tagName) {
          editor.chain().focus().insertContent(` #${tagName.trim()} `).run();
          addToast({ type: 'success', message: `Tag #${tagName.trim()} inserted` });
        }
        break;
      }
      default:
        break;
    }
  }, [editor, addToast]);

  const handleSave = useCallback(() => {
    if (!editor) return;
    const html = editor.getHTML();
    const text = editor.getText();
    onSave?.({ html, text, noteId });
  }, [editor, onSave, noteId]);

  const getMarkdownContent = useCallback(() => {
    if (!editor) return '';
    // Convert editor content to a simple markdown-like representation
    const text = editor.getText();
    return text;
  }, [editor]);

  if (!editor) {
    return <div className={styles.editorLoading} data-testid="editor-loading">Loading editor...</div>;
  }

  return (
    <div className={`${styles.editorContainer} ${className}`} data-testid="tiptap-editor">
      {/* Toolbar */}
      <div className={styles.toolbar} data-testid="editor-toolbar">
        <div className={styles.toolbarGroup}>
          <button
            type="button"
            className={`${styles.toolbarBtn} ${editor.isActive('bold') ? styles.toolbarBtnActive : ''}`}
            onClick={() => editor.chain().focus().toggleBold().run()}
            title="Bold"
            data-testid="btn-bold"
          >
            <Bold size={16} />
          </button>
          <button
            type="button"
            className={`${styles.toolbarBtn} ${editor.isActive('italic') ? styles.toolbarBtnActive : ''}`}
            onClick={() => editor.chain().focus().toggleItalic().run()}
            title="Italic"
            data-testid="btn-italic"
          >
            <Italic size={16} />
          </button>
          <button
            type="button"
            className={`${styles.toolbarBtn} ${editor.isActive('heading', { level: 1 }) ? styles.toolbarBtnActive : ''}`}
            onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
            title="Heading 1"
            data-testid="btn-h1"
          >
            <Heading1 size={16} />
          </button>
          <button
            type="button"
            className={`${styles.toolbarBtn} ${editor.isActive('heading', { level: 2 }) ? styles.toolbarBtnActive : ''}`}
            onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
            title="Heading 2"
            data-testid="btn-h2"
          >
            <Heading2 size={16} />
          </button>
        </div>

        <div className={styles.toolbarGroup}>
          <button
            type="button"
            className={`${styles.toolbarBtn} ${editor.isActive('bulletList') ? styles.toolbarBtnActive : ''}`}
            onClick={() => editor.chain().focus().toggleBulletList().run()}
            title="Bullet list"
            data-testid="btn-bullet-list"
          >
            <List size={16} />
          </button>
          <button
            type="button"
            className={`${styles.toolbarBtn} ${editor.isActive('orderedList') ? styles.toolbarBtnActive : ''}`}
            onClick={() => editor.chain().focus().toggleOrderedList().run()}
            title="Ordered list"
            data-testid="btn-ordered-list"
          >
            <ListOrdered size={16} />
          </button>
          <button
            type="button"
            className={`${styles.toolbarBtn} ${editor.isActive('taskList') ? styles.toolbarBtnActive : ''}`}
            onClick={() => editor.chain().focus().toggleTaskList().run()}
            title="Task list"
            data-testid="btn-task-list"
          >
            <CheckSquare size={16} />
          </button>
          <button
            type="button"
            className={`${styles.toolbarBtn} ${editor.isActive('blockquote') ? styles.toolbarBtnActive : ''}`}
            onClick={() => editor.chain().focus().toggleBlockquote().run()}
            title="Quote"
            data-testid="btn-quote"
          >
            <Quote size={16} />
          </button>
          <button
            type="button"
            className={`${styles.toolbarBtn} ${editor.isActive('codeBlock') ? styles.toolbarBtnActive : ''}`}
            onClick={() => editor.chain().focus().toggleCodeBlock().run()}
            title="Code block"
            data-testid="btn-code"
          >
            <Code size={16} />
          </button>
        </div>

        <div className={styles.toolbarSpacer} />

        <div className={styles.toolbarGroup}>
          <button
            type="button"
            className={`${styles.toolbarBtn} ${showPreview ? styles.toolbarBtnActive : ''}`}
            onClick={() => setShowPreview(p => !p)}
            title="Toggle preview"
            data-testid="btn-preview"
          >
            {showPreview ? <Edit3 size={16} /> : <Eye size={16} />}
          </button>
          <button
            type="button"
            className={`${styles.toolbarBtn} ${showAIPanel ? styles.toolbarBtnActive : ''}`}
            onClick={() => setShowAIPanel(p => !p)}
            title="AI Assistant"
            data-testid="btn-ai-assistant"
          >
            <Sparkles size={16} />
          </button>
        </div>
      </div>

      {/* Editor / Preview */}
      <div className={styles.editorBody}>
        {showPreview ? (
          <div className={styles.previewPane} data-testid="editor-preview">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {getMarkdownContent()}
            </ReactMarkdown>
          </div>
        ) : (
          <div className={styles.editorWrapper} data-testid="editor-wrapper">
            <EditorContent editor={editor} />
            {showSlashMenu && filteredCommands.length > 0 && (
              <div ref={slashMenuRef}>
                <SlashCommandMenu
                  items={filteredCommands}
                  onSelect={handleSlashSelect}
                  selectedIndex={slashIndex}
                />
              </div>
            )}
          </div>
        )}

        {/* AI Panel */}
        {showAIPanel && (
          <AIPanel editor={editor} onClose={() => setShowAIPanel(false)} />
        )}
      </div>

      {/* Footer */}
      <div className={styles.editorFooter}>
        <span className={styles.charCount}>
          {editor.storage.characterCount.characters()} characters
        </span>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={handleSave}
          data-testid="btn-save"
        >
          Save
        </button>
      </div>
    </div>
  );
}

// ─── Helper: Create a task from editor selection ────────────────────────

export function createTaskFromSelection(editor, createTaskFn, noteId) {
  if (!editor) return;
  const { from, to } = editor.state.selection;
  const selectedText = editor.state.doc.textBetween(from, to, ' ').trim();
  if (!selectedText) return;
  createTaskFn({ title: selectedText, note_id: noteId });
}
