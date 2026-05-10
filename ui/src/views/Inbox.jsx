import React, { useState } from 'react';
import { Sparkles, Check } from 'lucide-react';
import useStore from '../stores/useStore';
import NoteCard from '../components/notes/NoteCard';
import NoteEditor from '../components/notes/NoteEditor';
import EmptyState from '../components/ui/EmptyState';
import styles from './Inbox.module.css';

function AiSuggestionRow({ note, onAcceptProject, onAcceptArea }) {
  const meta = note.ai_meta;
  if (!meta) return null;

  const suggestedProject = meta.suggested_project;
  const suggestedArea = meta.suggested_area;
  const reasonStr = meta.reasoning != null ? String(meta.reasoning) : '';
  const reasoningSnip = reasonStr ? reasonStr.slice(0, 120) + (reasonStr.length > 120 ? '…' : '') : '';

  if (!suggestedProject && !suggestedArea && !reasoningSnip) return null;

  return (
    <div className={styles.aiSuggest}>
      <div className={styles.aiSuggestHeader}>
        <Sparkles size={13} className={styles.aiSuggestIcon} />
        <span className={styles.aiSuggestLabel}>AI suggests</span>
        {meta.confidence != null && (
          <span className={styles.aiSuggestConf}>{Math.round(Number(meta.confidence) * 100)}%</span>
        )}
      </div>
      {suggestedProject && (
        <button type="button" className={styles.entitySuggestChip} onClick={() => onAcceptProject(note, suggestedProject)}>
          <span>📁</span>
          <span>{suggestedProject}</span>
          <Check size={11} />
        </button>
      )}
      {suggestedArea && (
        <button type="button" className={styles.entitySuggestChip} onClick={() => onAcceptArea(note, suggestedArea)}>
          <span>🎯</span>
          <span>{suggestedArea}</span>
          <Check size={11} />
        </button>
      )}
      {reasoningSnip && <p className={styles.aiSuggestReason}>{reasoningSnip}</p>}
    </div>
  );
}

export default function Inbox() {
  const { notes, projects, areas, people, updateNote } = useStore();
  const [editingNote, setEditingNote] = useState(null);
  const [showEditor, setShowEditor] = useState(false);

  // Filter to truly inbox-y notes: bucket=INBOX OR no entity links
  // (notes with project/area/person links but still bucket=INBOX are still "unrouted")
  const inbox = notes.filter(n => n.bucket === 'INBOX');

  const sorted = [...inbox].sort(
    (a, b) => new Date(b.created_at) - new Date(a.created_at)
  );

  const resolveEntity = (list, name) => {
    const lower = name.toLowerCase();
    return list.find(e => e.name?.toLowerCase() === lower)
        || (() => {
          const matches = list.filter(e => e.name?.toLowerCase().includes(lower));
          return matches.length === 1 ? matches[0] : null;
        })();
  };

  const acceptProject = async (note, projectName) => {
    const match = resolveEntity(projects.filter(p => !p.is_archived), projectName);
    if (!match) return;
    await updateNote(note.id, {
      project_ids: note.project_ids ? [...note.project_ids, match.id] : [match.id],
    });
  };

  const acceptArea = async (note, areaName) => {
    const match = resolveEntity(areas.filter(a => !a.is_archived), areaName);
    if (!match) return;
    await updateNote(note.id, { area_id: match.id });
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1>Inbox</h1>
          <p className={styles.count}>{sorted.length} items needing attention</p>
          <p className={styles.hint}>
            Notes without project or area links. Click AI suggestions to route, or open to edit links.
          </p>
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
              <AiSuggestionRow
                note={note}
                onAcceptProject={acceptProject}
                onAcceptArea={acceptArea}
              />
              <NoteCard
                note={note}
                onEdit={() => { setEditingNote(note); setShowEditor(true); }}
              />
            </div>
          ))}
        </div>
      )}

      {showEditor && (
        <NoteEditor
          initialData={editingNote}
          onClose={() => { setShowEditor(false); setEditingNote(null); }}
          onSaved={() => { setShowEditor(false); setEditingNote(null); }}
        />
      )}
    </div>
  );
}