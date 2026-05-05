import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Plus } from 'lucide-react';
import useStore from '../stores/useStore';
import NoteCard from '../components/notes/NoteCard';
import NoteEditor from '../components/notes/NoteEditor';
import styles from './ProjectFocus.module.css'; // reuse ProjectFocus styles

export default function AreaFocus() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { areas, notes } = useStore();
  const [showNoteEditor, setShowNoteEditor] = useState(false);

  const area = areas.find(a => a.id === id);
  if (!area) return (
    <div className={styles.page}>
      <p>Area not found.</p>
      <button className="btn btn-ghost" onClick={() => navigate('/areas')}>
        <ArrowLeft size={14} /> Back to Areas
      </button>
    </div>
  );

  const areaNotes = notes.filter(n => n.area_id === id);

  return (
    <div className={styles.page}>
      <button className={styles.backBtn} onClick={() => navigate('/areas')}>
        <ArrowLeft size={14} /> All Areas
      </button>

      <div className={styles.projectHeader}>
        <span className={styles.dot} style={{ background: area.color || 'var(--accent-blue)' }} />
        <h1>{area.name}</h1>
        {area.description && <p className={styles.desc}>{area.description}</p>}
      </div>

      <div className={styles.content}>
        <div className={styles.contentHeader}>
          <button className="btn btn-primary btn-sm" onClick={() => setShowNoteEditor(true)}>
            <Plus size={13} /> Add Note
          </button>
        </div>
        {areaNotes.length === 0 ? (
          <p className={styles.empty}>No notes in this area yet.</p>
        ) : (
          <div className={styles.noteGrid}>
            {areaNotes.map(n => <NoteCard key={n.id} note={n} />)}
          </div>
        )}
      </div>

      {showNoteEditor && (
        <NoteEditor
          initialData={{ area_id: id, bucket: 'AREAS' }}
          onClose={() => setShowNoteEditor(false)}
          onSaved={() => setShowNoteEditor(false)}
        />
      )}
    </div>
  );
}
