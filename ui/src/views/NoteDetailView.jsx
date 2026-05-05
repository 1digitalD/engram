import React, { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ArrowLeft, Edit2, Trash2, Archive, ExternalLink, Tag, User, FolderOpen, Map } from 'lucide-react';
import useStore from '../stores/useStore';
import NoteEditor from '../components/notes/NoteEditor';
import { BucketBadge, TagBadge } from '../components/ui/Badge';
import styles from './NoteDetailView.module.css';

export default function NoteDetailView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { notes, projects, areas, people, updateNote, deleteNote } = useStore();
  const [editing, setEditing] = useState(false);

  const note = notes.find(n => n.id === id);

  if (!note) {
    return (
      <div className={styles.page}>
        <p className={styles.notFound}>Note not found.</p>
        <button className="btn btn-ghost" onClick={() => navigate(-1)}>
          <ArrowLeft size={14} /> Go back
        </button>
      </div>
    );
  }

  const project = note.project_id ? projects.find(p => p.id === note.project_id) : null;
  const area    = note.area_id    ? areas.find(a => a.id === note.area_id)     : null;
  const person  = note.person_id  ? people.find(p => p.id === note.person_id)  : null;

  const handleDelete = async () => {
    if (!confirm('Delete this note?')) return;
    await deleteNote(note.id);
    navigate('/notes');
  };

  return (
    <div className={styles.page}>
      {/* Back */}
      <button className={styles.backBtn} onClick={() => navigate(-1)}>
        <ArrowLeft size={14} /> Back
      </button>

      <div className={styles.content}>
        {/* Meta bar */}
        <div className={styles.metaBar}>
          <BucketBadge bucket={note.bucket} />
          <span className={styles.date}>
            {new Date(note.created_at).toLocaleDateString('en-US', {
              weekday: 'short', month: 'short', day: 'numeric', year: 'numeric',
            })}
          </span>
          <div className={styles.metaActions}>
            <button className="btn btn-ghost btn-sm" onClick={() => setEditing(true)}>
              <Edit2 size={13} /> Edit
            </button>
            <button className="btn btn-ghost btn-sm" onClick={handleDelete}>
              <Trash2 size={13} />
            </button>
          </div>
        </div>

        {/* Linked entities */}
        {(project || area || person) && (
          <div className={styles.linkedEntities}>
            {project && (
              <Link to={`/projects/${project.id}`} className={styles.entityChip}>
                <FolderOpen size={12} /> {project.name}
              </Link>
            )}
            {area && (
              <span className={styles.entityChip}>
                <Map size={12} /> {area.name}
              </span>
            )}
            {person && (
              <span className={styles.entityChip}>
                <User size={12} /> {person.name}
              </span>
            )}
          </div>
        )}

        {/* Note body */}
        <article className={styles.body}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {note.raw_text}
          </ReactMarkdown>
        </article>

        {/* Tags */}
        {note.tag_names?.length > 0 && (
          <div className={styles.tags}>
            <Tag size={13} className={styles.tagIcon} />
            {note.tag_names.map(t => <TagBadge key={t} tag={t} />)}
          </div>
        )}

        {/* AI info */}
        {note.ai_meta && (
          <div className={styles.aiInfo}>
            <span className={styles.aiLabel}>AI classified as</span>
            <BucketBadge bucket={note.ai_meta.bucket?.toUpperCase()} />
            <span className={styles.aiConf}>
              {Math.round((note.ai_meta.confidence || 0) * 100)}% confidence
            </span>
            {note.ai_meta.reasoning && (
              <p className={styles.aiReason}>{note.ai_meta.reasoning}</p>
            )}
          </div>
        )}
      </div>

      {editing && (
        <NoteEditor
          initialData={note}
          onClose={() => setEditing(false)}
          onSaved={() => setEditing(false)}
        />
      )}
    </div>
  );
}
