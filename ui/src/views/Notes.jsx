import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Plus } from 'lucide-react';
import useStore from '../stores/useStore';
import NoteCard from '../components/notes/NoteCard';
import NoteEditor from '../components/notes/NoteEditor';
import EmptyState from '../components/ui/EmptyState';
import styles from './Notes.module.css';

const FILTER_TABS = [
  { key: 'all',      label: 'All Notes' },
  { key: 'project', label: '📁 Projects' },
  { key: 'area',    label: '🎯 Areas' },
  { key: 'person',  label: '👤 People' },
  { key: 'inbox',   label: 'Inbox' },
  { key: 'resource',label: '📚 Resources' },
  { key: 'archive', label: '🗄️ Archive' },
];

export default function Notes() {
  const { notes, projects, areas, people } = useStore();
  const [searchParams, setSearchParams] = useSearchParams();
  const [filter, setFilter] = useState('all');
  const [editingNote, setEditingNote] = useState(null);
  const [showEditor, setShowEditor] = useState(false);
  const tagFilter = searchParams.get('tag');

  // Entity name sub-filter when in project/area/person mode
  const [entityFilter, setEntityFilter] = useState('');

  const filtered = notes.filter(n => {
    const tagMatches = !tagFilter || n.tag_names?.includes(tagFilter);

    if (filter === 'all') return tagMatches;
    if (filter === 'inbox')  return tagMatches && n.bucket === 'INBOX';
    if (filter === 'resource') return tagMatches && n.bucket === 'RESOURCES';
    if (filter === 'archive')  return tagMatches && n.bucket === 'ARCHIVES';
    if (filter === 'project') {
      const match = tagMatches && (n.project_id || (n.project_ids?.length > 0));
      if (!entityFilter) return match;
      const target = projects.find(p => p.id === entityFilter);
      if (!target) return match;
      return match && (n.project_id === entityFilter || n.project_ids?.includes(entityFilter));
    }
    if (filter === 'area') {
      const match = tagMatches && !!n.area_id;
      if (!entityFilter) return match;
      return match && n.area_id === entityFilter;
    }
    if (filter === 'person') {
      const match = tagMatches && !!n.person_id;
      if (!entityFilter) return match;
      return match && n.person_id === entityFilter;
    }
    return tagMatches;
  });

  const sorted = [...filtered].sort(
    (a, b) => new Date(b.created_at) - new Date(a.created_at)
  );

  // Sub-filter options for project/area/person tabs
  const entityOptions = filter === 'project'
    ? projects.filter(p => !p.is_archived)
    : filter === 'area'
    ? areas.filter(a => !a.is_archived)
    : filter === 'person'
    ? people
    : [];

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

      {/* Top-level filter tabs */}
      <div className={styles.filters}>
        {FILTER_TABS.map(f => (
          <button
            key={f.key}
            className={`${styles.filterBtn} ${filter === f.key ? styles.filterActive : ''}`}
            onClick={() => {
              setFilter(f.key);
              setEntityFilter('');
            }}
          >
            {f.label}
          </button>
        ))}
        {tagFilter && (
          <button
            className={`${styles.filterBtn} ${styles.filterActive}`}
            onClick={() => setSearchParams({})}
          >
            #{tagFilter} ×
          </button>
        )}
      </div>

      {/* Entity sub-filter (when project/area/person tab selected) */}
      {['project', 'area', 'person'].includes(filter) && entityOptions.length > 0 && (
        <div className={styles.filters} style={{ marginTop: 'var(--space-2)', paddingLeft: 'var(--space-1)' }}>
          <button
            className={`${styles.filterBtn} ${!entityFilter ? styles.filterActive : ''}`}
            onClick={() => setEntityFilter('')}
          >
            All
          </button>
          {entityOptions.map(e => (
            <button
              key={e.id}
              className={`${styles.filterBtn} ${entityFilter === e.id ? styles.filterActive : ''}`}
              onClick={() => setEntityFilter(e.id)}
            >
              {e.title}
            </button>
          ))}
        </div>
      )}

      {/* Note list */}
      {sorted.length === 0 ? (
        <EmptyState
          type="notes"
          title={filter === 'all' ? 'No notes yet' : `No notes`}
          message={tagFilter ? `No notes tagged #${tagFilter}.` : 'Capture your first thought with the button above.'}
          action={
            filter === 'all'
              ? <button className="btn btn-primary" onClick={() => setShowEditor(true)}><Plus size={14} /> Capture</button>
              : undefined
          }
        />
      ) : (
        <div className={styles.grid}>
          {sorted.map(n => (
            <NoteCard
              key={n.id}
              note={n}
              onEdit={(note) => { setEditingNote(note); setShowEditor(true); }}
            />
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
