import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { MoreHorizontal, Trash2, Edit2, Archive, ExternalLink } from 'lucide-react';
import { BucketBadge } from '../ui/Badge';
import useStore from '../../stores/useStore';
import styles from './NoteCard.module.css';

export default function NoteCard({ note, onEdit }) {
  const { deleteNote, projects } = useStore();
  const [menuOpen, setMenuOpen] = useState(false);

  const project = note.project_id
    ? projects.find(p => p.id === note.project_id)
    : null;

  const preview = note.raw_text?.length > 160
    ? note.raw_text.slice(0, 160) + '…'
    : note.raw_text;

  const date = new Date(note.created_at).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <BucketBadge bucket={note.bucket} />
        {project && (
          <Link to={`/projects/${project.id}`} className={styles.projectChip}>
            {project.name}
          </Link>
        )}
        <span className={styles.date}>{date}</span>
        <div className={styles.actions}>
          <button
            className={styles.menuBtn}
            onClick={(e) => { e.stopPropagation(); setMenuOpen(m => !m); }}
          >
            <MoreHorizontal size={14} />
          </button>
          {menuOpen && (
            <div className={styles.menu} onMouseLeave={() => setMenuOpen(false)}>
              <button onClick={() => { onEdit && onEdit(note); setMenuOpen(false); }}>
                <Edit2 size={13} /> Edit
              </button>
              <button
                className={styles.danger}
                onClick={() => { deleteNote(note.id); setMenuOpen(false); }}
              >
                <Trash2 size={13} /> Delete
              </button>
            </div>
          )}
        </div>
      </div>

      <Link to={`/notes/${note.id}`} className={styles.body}>
        <p className={styles.text}>{preview}</p>
      </Link>

      <div className={styles.footer}>
        {note.tag_names?.length > 0 && (
          <div className={styles.tags}>
            {note.tag_names.slice(0, 3).map(t => (
              <span key={t} className={styles.tag}>#{t}</span>
            ))}
          </div>
        )}
        <div className={styles.meta}>
          {note.ai_meta?.confidence && (
            <span className={styles.aiBadge}>
              AI {Math.round(note.ai_meta.confidence * 100)}%
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
