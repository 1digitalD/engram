import React, { useState } from 'react';
import { Plus, Filter } from 'lucide-react';
import useStore from '../stores/useStore';
import NoteCard from '../components/notes/NoteCard';
import NoteEditor from '../components/notes/NoteEditor';
import EmptyState from '../components/ui/EmptyState';
import styles from './Notes.module.css';

const BUCKETS = ['all', 'INBOX', 'PROJECTS', 'AREAS', 'RESOURCES', 'ARCHIVES'];

export default function Notes() {
  const { notes } = useStore();
  const [filter, setFilter] = useState('all');
  const [editingNote, setEditingNote] = useState(null);
  const [showEditor, setShowEditor] = useState(false);

  const filtered = filter === 'all'
    ? notes
    : notes.filter(n => n.bucket === filter);

  const sorted = [...filtered].sort(
    (a, b) => new Date(b.created_at) - new Date(a.created_at)
  );

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1>Notes</h1>
          <p className={styles.count}>{sorted.length} notes</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowEditor(true)}>
          <Plus size={15} /> New Note
        </button>
      </div>

      {/* Filters */}
      <div className={styles.filters}>
        {BUCKETS.map(b => (
          <button
            key={b}
            className={`${styles.filterBtn} ${filter === b ? styles.filterActive : ''}`}
            onClick={() => setFilter(b)}
          >
            {b === 'all' ? 'All' : b.charAt(0) + b.slice(1).toLowerCase()}
          </button>
        ))}
      </div>

      {/* Note list */}
      {sorted.length === 0 ? (
        <EmptyState
          type="notes"
          title={filter === 'all' ? 'No notes yet' : `No ${filter.toLowerCase()} notes`}
          message={filter === 'all' ? 'Capture your first thought with the button above.' : undefined}
          action={
            filter === 'all'
              ? <button className="btn btn-primary" onClick={() => setShowEditor(true)}><Plus size={14} /> Capture</button>
              : undefined
          }
        />
      ) : (
        <div className={styles.grid}>
          {sorted.map(n => (
            <NoteCard key={n.id} note={n} onEdit={(note) => { setEditingNote(note); setShowEditor(true); }} />
          ))}
        </div>
      )}

      {(showEditor) && (
        <NoteEditor
          initialData={editingNote}
          onClose={() => { setShowEditor(false); setEditingNote(null); }}
          onSaved={() => { setShowEditor(false); setEditingNote(null); }}
        />
      )}
    </div>
  );
}
