import React, { useState } from 'react';
import { ArrowRight, Sparkles } from 'lucide-react';
import useStore from '../stores/useStore';
import NoteCard from '../components/notes/NoteCard';
import NoteEditor from '../components/notes/NoteEditor';
import EmptyState from '../components/ui/EmptyState';
import { BucketBadge } from '../components/ui/Badge';
import styles from './Inbox.module.css';

const ROUTABLE_BUCKETS = new Set(['PROJECTS', 'AREAS', 'RESOURCES', 'ARCHIVES']);

function AiSuggestionRow({ note, onApplyBucket }) {
  const meta = note.ai_meta;
  if (!meta) return null;

  const suggested = typeof meta.bucket === 'string' ? meta.bucket.toUpperCase() : '';
  const canApplyBucket = suggested && ROUTABLE_BUCKETS.has(suggested) && note.bucket === 'INBOX';
  const reasonStr = meta.reasoning != null ? String(meta.reasoning) : '';
  const reasoningSnip = reasonStr
    ? reasonStr.slice(0, 120) + (reasonStr.length > 120 ? '…' : '')
    : '';

  return (
    <div className={styles.aiSuggest}>
      <div className={styles.aiSuggestHeader}>
        <Sparkles size={14} className={styles.aiSuggestIcon} />
        <span className={styles.aiSuggestLabel}>AI suggestion</span>
        {suggested ? <BucketBadge bucket={suggested} /> : null}
        {meta.confidence != null && (
          <span className={styles.aiSuggestConf}>{Math.round(Number(meta.confidence) * 100)}%</span>
        )}
      </div>
      {(meta.suggested_project || meta.suggested_area) && (
        <p className={styles.aiSuggestHints}>
          {meta.suggested_project && <span>Project hint: {meta.suggested_project}</span>}
          {meta.suggested_area && <span>Area hint: {meta.suggested_area}</span>}
        </p>
      )}
      {reasoningSnip && <p className={styles.aiSuggestReason}>{reasoningSnip}</p>}
      {canApplyBucket && (
        <button type="button" className={styles.aiApplyBtn} onClick={() => onApplyBucket(note, suggested)}>
          Apply suggested bucket ({suggested})
        </button>
      )}
    </div>
  );
}

export default function Inbox() {
  const { notes, updateNote } = useStore();
  const [editingNote, setEditingNote] = useState(null);
  const [showEditor, setShowEditor] = useState(false);

  const inbox = notes.filter(n => n.bucket === 'INBOX');

  const handleRoute = async (note, bucket) => {
    await updateNote(note.id, { bucket });
  };

  const handleApplyAiBucket = async (note, bucket) => {
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
                <AiSuggestionRow note={note} onApplyBucket={handleApplyAiBucket} />
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
