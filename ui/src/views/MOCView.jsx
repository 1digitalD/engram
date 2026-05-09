import React, { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Map } from 'lucide-react';
import useStore from '../stores/useStore';
import EmptyState from '../components/ui/EmptyState';
import styles from './MOCView.module.css';

function noteTitleLine(note) {
  if (!note) return 'Untitled';
  const line = (note.raw_text || '').split('\n')[0].replace(/^#\s*/, '').trim();
  return line || 'Untitled';
}

function isMoc(note) {
  return String(note?.note_type || 'NOTE').toUpperCase() === 'MOC';
}

export default function MOCView() {
  const { notes } = useStore();

  const mocs = useMemo(() => {
    const rows = notes.filter(isMoc);
    rows.sort((a, b) => noteTitleLine(a).localeCompare(noteTitleLine(b), undefined, { sensitivity: 'base' }));
    return rows;
  }, [notes]);

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1>
          <Map size={22} style={{ verticalAlign: 'text-bottom', marginRight: 8 }} aria-hidden />
          Maps of content
        </h1>
        <p className={styles.subtitle}>
          MOC notes index linked knowledge. Counts include outgoing and incoming links.
        </p>
      </header>

      {mocs.length === 0 ? (
        <EmptyState
          type="notes"
          title="No MOC notes yet"
          message="Create a map of content from the API or mark a note as type MOC to see it here."
        />
      ) : (
        <ul className={styles.list} aria-label="Maps of content">
          {mocs.map((n) => {
            const count = typeof n.link_count === 'number' ? n.link_count : 0;
            return (
              <li key={n.id} className={styles.row}>
                <Link className={styles.rowLink} to={`/notes/${n.id}`}>
                  {noteTitleLine(n)}
                </Link>
                <span className={styles.count} title="Linked notes (total link endpoints)">
                  {count} links
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
