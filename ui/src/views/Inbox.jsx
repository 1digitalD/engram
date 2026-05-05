import React, { useState } from 'react';
import { CheckCircle, ArrowRight } from 'lucide-react';
import useStore from '../stores/useStore';
import NoteCard from '../components/notes/NoteCard';
import NoteEditor from '../components/notes/NoteEditor';
import EmptyState from '../components/ui/EmptyState';
import styles from './Inbox.module.css';

export default function Inbox() {
  const { notes, updateNote } = useStore();
  const [editingNote, setEditingNote] = useState(null);
  const [showEditor, setShowEditor] = useState(false);

  const inbox = notes.filter(n => n.bucket === 'INBOX');

  const handleRoute = async (note, bucket) => {
    await updateNote(note.id, { bucket });
  };

  const sorted = [...inbox].sort(
    (a, b) => new Date(b.created_at) - new Date(a.created_at)
  );

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1>Inbox</h1>
          <p className={styles.count}>{sorted.length} items needing attention</p>
          <p className={styles.hint}>Review captured items and route them to the right bucket.</p>
        </div>
      </div>

      {sorted.length === 0 ? (
        <EmptyState
          type="notes"
          title="Inbox is clear"
          message="All captured notes have been triaged. Capture something new or review recent activity."
        />
      ) : (
        <div className={styles.list}>
          {sorted.map(note => (
            <div key={note.id} className={styles.inboxItem}>
              <div className={styles.noteArea}>
                <NoteCard note={note} onEdit={() => { setEditingNote(note); setShowEditor(true); }} />
              </div>
              <div className={styles.routing}>
                <p className={styles.routingLabel}>Route to:</p>
                {['PROJECTS', 'AREAS', 'RESOURCES', 'ARCHIVES'].map(b => (
                  <button
                    key={b}
                    className={styles.routeBtn}
                    onClick={() => handleRoute(note, b)}
                    title={`Move to ${b}`}
                  >
                    {b === 'PROJECTS' ? 'Project' : b === 'AREAS' ? 'Area' : b === 'RESOURCES' ? 'Resource' : 'Archive'}
                    <ArrowRight size={12} />
                  </button>
                ))}
              </div>
            </div>
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
