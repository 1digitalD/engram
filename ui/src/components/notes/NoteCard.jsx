import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Link, useNavigate } from 'react-router-dom';
import { MoreHorizontal, Trash2, Edit2 } from 'lucide-react';
import { BucketBadge } from '../ui/Badge';
import useStore from '../../stores/useStore';
import styles from './NoteCard.module.css';

const PREVIEW_LIMIT = 400;

function isMetadataOnlyImport(text = '') {
  return text.startsWith('Imported from') && text.includes('Source Notion ID');
}

function truncateMarkdown(text = '') {
  return text.length > PREVIEW_LIMIT ? `${text.slice(0, PREVIEW_LIMIT).trimEnd()}…` : text;
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

export default function NoteCard({ note, onEdit }) {
  const { deleteNote, projects } = useStore();
  const [menuOpen, setMenuOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const navigate = useNavigate();

  const project = note.project_id
    ? projects.find(p => p.id === note.project_id)
    : null;

  const rawText = note.raw_text || '';
  const metadataOnlyImport = isMetadataOnlyImport(rawText);
  const content = expanded ? rawText : truncateMarkdown(rawText);
  const canExpand = !metadataOnlyImport && rawText.length > PREVIEW_LIMIT;

  const date = new Date(note.created_at).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });

  return (
    <div className={`${styles.card} ${expanded ? styles.expanded : ''}`}>
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
