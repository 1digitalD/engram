import { useEffect } from 'react';

import MarkdownEditor from '../components/MarkdownEditor';
import styles from './CaptureComposer.module.css';

export const CAPTURE_PLACEHOLDER =
  'Paste meeting notes, bullets, or a long write-up. Markdown works — use headings and lists if it helps.';

export const QUICK_CAPTURE_PLACEHOLDER = 'Set something down…';

export default function CaptureComposer({
  open,
  onOpenChange,
  quickValue,
  onQuickChange,
  onQuickSubmit,
  value,
  onChange,
  onSubmit,
  busy = false,
  error = '',
}) {
  useEffect(() => {
    if (!open) return undefined;

    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        event.preventDefault();
        onOpenChange(false);
      }
      if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
        event.preventDefault();
        onSubmit?.();
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, onOpenChange, onSubmit]);

  function handleExpand() {
    const quick = quickValue.trim();
    if (quick && !value.trim()) {
      onChange(quick);
      onQuickChange('');
    } else if (quick && value.trim()) {
      onChange(`${value.trim()}\n\n${quick}`);
      onQuickChange('');
    }
    onOpenChange(true);
  }

  function handleQuickSubmit(event) {
    event.preventDefault();
    onQuickSubmit?.();
  }

  return (
    <div className={styles.wrap}>
      <form className={styles.quickBar} onSubmit={handleQuickSubmit}>
        <button
          type="button"
          className={styles.expandButton}
          aria-label="Open expanded capture"
          aria-expanded={open}
          aria-haspopup="dialog"
          disabled={busy}
          onClick={handleExpand}
        >
          ＋
        </button>
        <input
          className={styles.quickInput}
          type="text"
          value={quickValue}
          onChange={(event) => onQuickChange(event.target.value)}
          placeholder={QUICK_CAPTURE_PLACEHOLDER}
          aria-label="Quick capture"
          disabled={busy}
        />
      </form>

      {open ? (
        <div
          className={styles.backdrop}
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) onOpenChange(false);
          }}
        >
          <div className={styles.panel} role="dialog" aria-label="Capture">
            <header className={styles.header}>
              <h2 className={styles.title}>Capture</h2>
            </header>

            <div className={styles.body}>
              <MarkdownEditor
                className={styles.editor}
                value={value}
                onChange={onChange}
                placeholder={CAPTURE_PLACEHOLDER}
                ariaLabel="Capture text"
                editable={!busy}
                minRows={12}
                autoFocus
              />
              <p className={styles.hint}>
                Name the Space or person in the text to improve linking. After capture, check Review for extracted
                tasks and decisions.
              </p>
            </div>

            {error ? (
              <p className={styles.panelError} role="alert">
                {error}
              </p>
            ) : null}

            <footer className={styles.footer}>
              <span className={styles.shortcutHint}>⌘↵ Capture · Esc close</span>
              <div className={styles.actions}>
                <button
                  type="button"
                  className={styles.button}
                  disabled={busy}
                  onClick={() => onOpenChange(false)}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className={styles.buttonPrimary}
                  disabled={busy || !value.trim()}
                  onClick={() => onSubmit?.()}
                >
                  {busy ? 'Capturing…' : 'Capture'}
                </button>
              </div>
            </footer>
          </div>
        </div>
      ) : null}
    </div>
  );
}
