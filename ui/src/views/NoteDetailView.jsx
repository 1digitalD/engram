import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ArrowLeft, Edit2, Loader2, Trash2, Tag, User, FolderOpen, Map } from 'lucide-react';
import useStore from '../stores/useStore';
import { BucketBadge, TagBadge } from '../components/ui/Badge';
import styles from './NoteDetailView.module.css';

export default function NoteDetailView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { notes, projects, areas, people, updateNote, deleteNote } = useStore();
  const [isEditing, setIsEditing] = useState(false);
  const [draftText, setDraftText] = useState('');
  const [saving, setSaving] = useState(false);

  const note = notes.find(n => n.id === id);

  useEffect(() => {
    if (!isEditing) setDraftText(note?.raw_text || '');
  }, [note?.id, note?.raw_text, isEditing]);

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

  const startEditing = () => {
    setDraftText(note.raw_text || '');
    setIsEditing(true);
  };

  const cancelEditing = () => {
    setDraftText(note.raw_text || '');
    setIsEditing(false);
  };

  const saveInlineEdit = async () => {
    if (!draftText.trim() || saving) return;
    setSaving(true);
    try {
      await updateNote(note.id, { raw_text: draftText });
      setIsEditing(false);
    } finally {
      setSaving(false);
    }
  };

  const handleEditKeyDown = (e) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      cancelEditing();
      return;
    }
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      saveInlineEdit();
    }
  };

  const handleBodyClick = (e) => {
    if (e.target instanceof Element && e.target.closest('a')) return;
    startEditing();
  };

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
            {!isEditing && (
              <button className="btn btn-ghost btn-sm" onClick={startEditing}>
                <Edit2 size={13} /> Edit
              </button>
            )}
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
        {isEditing ? (
          <div className={styles.inlineEditor}>
            <textarea
              className={styles.inlineTextarea}
              value={draftText}
              onChange={e => setDraftText(e.target.value)}
              onKeyDown={handleEditKeyDown}
              rows={14}
              autoFocus
            />
            <div className={styles.inlineActions}>
              <span className={styles.shortcutHint}>Cmd/Ctrl+Enter to save · Esc to cancel</span>
              <button type="button" className="btn btn-ghost btn-sm" onClick={cancelEditing} disabled={saving}>
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={saveInlineEdit}
                disabled={saving || !draftText.trim()}
              >
                {saving ? <Loader2 size={13} className="spin" /> : null}
                Save
              </button>
            </div>
          </div>
        ) : (
          <article
            className={styles.body}
            onClick={handleBodyClick}
            onKeyDown={e => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                startEditing();
              }
            }}
            role="button"
            tabIndex={0}
            aria-label="Edit note text"
          >
            <span className={styles.editHint}>Click to edit</span>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {note.raw_text}
            </ReactMarkdown>
          </article>
        )}

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
    </div>
  );
}
