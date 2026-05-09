import React from 'react';
import { X } from 'lucide-react';
import styles from './KeyboardShortcutsModal.module.css';

function CmdOrCtrl({ mac, win }) {
  if (typeof navigator === 'undefined') return win;
  return /Mac|iPhone|iPad|iPod/i.test(navigator.userAgent) ? mac : win;
}

function Kbd({ children }) {
  return <kbd className={styles.inlineKbd}>{children}</kbd>;
}

const ROWS_GENERAL = ({ paletteKbd, captureKbd }) => [
  {
    desc: 'Command palette — search & jump',
    keys: [<Kbd key="p">{paletteKbd}</Kbd>],
  },
  {
    desc: 'Quick capture floating note',
    keys: [<Kbd key="c">{captureKbd}</Kbd>],
  },
  {
    desc: 'Full note editor (all fields)',
    keys: [<Kbd key="f">{CmdOrCtrl({ mac: '⌘⇧N', win: 'Ctrl+Shift+N' })}</Kbd>],
  },
  {
    desc: 'This shortcuts list',
    keys: [<Kbd key="h">{CmdOrCtrl({ mac: '⌘/', win: 'Ctrl+/' })}</Kbd>],
  },
];

export default function KeyboardShortcutsModal({ onClose }) {
  const paletteKbd = CmdOrCtrl({ mac: '⌘K', win: 'Ctrl+K' });
  const captureKbd = CmdOrCtrl({ mac: '⌘N', win: 'Ctrl+N' });

  const rowsGeneral = ROWS_GENERAL({ paletteKbd, captureKbd });

  return (
    <div className={styles.backdrop} role="presentation" onClick={onClose}>
      <div
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-labelledby="kbd-help-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className={styles.head}>
          <h2 id="kbd-help-title" className={styles.title}>
            Keyboard shortcuts
          </h2>
          <button type="button" className={styles.closeBtn} aria-label="Close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Global</h3>
          <div className={styles.rows}>
            {rowsGeneral.map((r, i) => (
              <div key={i} className={styles.row}>
                <span className={styles.desc}>{r.desc}</span>
                <span className={styles.kbdWrap}>{r.keys}</span>
              </div>
            ))}
          </div>
        </section>

        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>While editing a note</h3>
          <div className={styles.rows}>
            <div className={styles.row}>
              <span className={styles.desc}>Save inline edits (note detail)</span>
              <span className={styles.kbdWrap}>
                <Kbd>{CmdOrCtrl({ mac: '⌘↵', win: 'Ctrl+Enter' })}</Kbd>
              </span>
            </div>
            <div className={styles.row}>
              <span className={styles.desc}>Cancel inline edits</span>
              <span className={styles.kbdWrap}>
                <Kbd>Esc</Kbd>
              </span>
            </div>
          </div>
        </section>

        <p className={styles.footer}>
          Shortcuts are disabled while typing in inputs and text areas so you can edit normally.
        </p>
      </div>
    </div>
  );
}
