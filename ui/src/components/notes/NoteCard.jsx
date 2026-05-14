import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Link, useNavigate } from 'react-router-dom';
import { MoreHorizontal, Trash2, Edit2, Loader2, Sparkles, Calendar } from 'lucide-react';
import useStore from '../../stores/useStore';
import DeleteConfirmModal from '../DeleteConfirmModal';
import styles from './NoteCard.module.css';

const PREVIEW_LIMIT = 400;

function isMetadataOnlyImport(text = '') {
  return text.startsWith('Imported from') && text.includes('Source Notion ID');
}

function truncateMarkdown(text = '') {
  return text.length > PREVIEW_LIMIT ? `${text.slice(0, PREVIEW_LIMIT).trimEnd()}…` : text;
}

function isFollowUpOverdue(followUpAt) {
  if (!followUpAt) return false;
  const date = new Date(followUpAt);
  if (Number.isNaN(date.getTime())) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return date < today;
}

function formatFollowUpDate(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  });
}

const markdownComponents = {
  h1: ({ children }) => <strong className={styles.markdownHeading}>{children}</strong>,
  h2: ({ children }) => <strong className={styles.markdownHeading}>{children}</strong>,
  h3: ({ children }) => <strong className={styles.markdownHeading}>{children}</strong>,
  h4: ({ children }) => <strong className={styles.markdownHeading}>{children}</strong>,
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>
      {children}
    </a>
  ),
};

function EntityChip({ to, children, emoji }) {
  return (
    <Link to={to} className={styles.entityChip} onClick={e => e.stopPropagation()}>
      <span>{emoji}</span>
      <span>{children}</span>
    </Link>
  );
}

export default function NoteCard({ note, onEdit }) {
  const { deleteNote, projects, areas, people, getDeletePreview } = useStore();
  const [menuOpen, setMenuOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deletePreview, setDeletePreview] = useState(null);
  const navigate = useNavigate();

  const project = note.project_id
    ? projects.find(p => p.id === note.project_id)
    : null;

  const area = note.area_id ? areas.find(a => a.id === note.area_id) : null;
  const person = note.person_id ? people.find(p => p.id === note.person_id) : null;

  const rawText = note.raw_text || '';
  const metadataOnlyImport = isMetadataOnlyImport(rawText);
  const content = expanded ? rawText : truncateMarkdown(rawText);
  const canExpand = !metadataOnlyImport && rawText.length > PREVIEW_LIMIT;

  const date = new Date(note.created_at).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });

  const followUpDate = formatFollowUpDate(note.follow_up_at);
  const followUpOverdue = isFollowUpOverdue(note.follow_up_at);

  return (
    <div className={`${styles.card} ${expanded ? styles.expanded : ''}`}>
      <div className={styles.header}>
        <div className={styles.entityChips}>
          {project && <EntityChip to={`/projects/${project.id}`} emoji="📁">{project.title}</EntityChip>}
          {area    && <EntityChip to={`/areas/${area.id}`}       emoji="🎯">{area.title}</EntityChip>}
          {person  && <EntityChip to={`/people/${person.id}`}    emoji="👤">{person.title}</EntityChip>}
          {!project && !area && !person && (
            <span className={styles.inboxBadge}>Inbox</span>
          )}
        </div>
        <span className={styles.date}>{date}</span>
        {followUpDate && (
          <span className={`${styles.followUpDate} ${followUpOverdue ? styles.followUpOverdue : ''}`}>
            <Calendar size={10} /> {followUpDate}
          </span>
        )}
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
                onClick={async () => {
                  setMenuOpen(false);
                  try {
                    const preview = await getDeletePreview(note.id);
                    setDeletePreview(preview);
                    setShowDeleteModal(true);
                  } catch (e) {
                    // ignore — delete will proceed without preview
                  }
                }}
              >
                <Trash2 size={13} /> Delete
              </button>
            </div>
          )}
        </div>
      </div>

      <div
        className={styles.body}
        role="link"
        tabIndex={0}
        onClick={() => navigate(`/notes/${note.id}`)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            navigate(`/notes/${note.id}`);
          }
        }}
      >
        {metadataOnlyImport ? (
          <p className={styles.placeholder}>Imported note — click to view</p>
        ) : (
          <div className={`${styles.markdown} ${expanded ? styles.markdownExpanded : ''}`}>
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
              {content}
            </ReactMarkdown>
          </div>
        )}
      </div>

      <div className={styles.footer}>
        {note.tag_names?.length > 0 && (
          <div className={styles.tags}>
            {note.tag_names.slice(0, 3).map(t => (
              <Link
                key={t}
                to={`/notes?tag=${encodeURIComponent(t)}`}
                className={styles.tag}
                onClick={(e) => e.stopPropagation()}
              >
                #{t}
              </Link>
            ))}
          </div>
        )}
        <div className={styles.meta}>
          {canExpand && (
            <button
              className={styles.expandBtn}
              onClick={(e) => { e.stopPropagation(); setExpanded(value => !value); }}
              aria-expanded={expanded}
            >
              {expanded ? 'Show less' : 'Show more'}
            </button>
          )}
          {note.ai_status === 'processing' && (
            <span className={styles.aiProcessing}>
              <Loader2 size={10} className="spin" />
              Classifying…
            </span>
          )}
          {note.ai_status === 'done' && note._ai_meta?.bucket && (
            <span className={styles.aiClassification}>
              <Sparkles size={10} />
              {note._ai_meta.bucket}
              {note._ai_meta?.confidence != null && (
                <span className={styles.aiConfidence}>
                  {Math.round(note._ai_meta.confidence * 100)}%
                </span>
              )}
            </span>
          )}
          {note.ai_status !== 'processing' && !note._ai_meta?.bucket && note._ai_meta?.confidence && (
            <span className={styles.aiBadge}>
              AI {Math.round(note._ai_meta.confidence * 100)}%
            </span>
          )}
        </div>
      </div>

      <DeleteConfirmModal
        isOpen={showDeleteModal}
        onClose={() => { setShowDeleteModal(false); setDeletePreview(null); }}
        onConfirm={async (cascadeIds) => {
          await deleteNote(note.id, cascadeIds);
          setShowDeleteModal(false);
          setDeletePreview(null);
        }}
        entityTitle={(note.raw_text || note.content || '').split('\n')[0].replace(/^#\s*/, '').trim() || 'Untitled'}
        entityType="note"
        preview={deletePreview}
      />
    </div>
  );
}
