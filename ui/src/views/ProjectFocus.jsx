import React, { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  FileText,
  FolderOpen,
  Plus,
} from 'lucide-react';
import useStore from '../stores/useStore';
import NoteEditor from '../components/notes/NoteEditor';
import ConnectionsPanel from '../components/ConnectionsPanel/ConnectionsPanel';
import styles from './ProjectFocus.module.css';

const TABS = [
  { key: 'notes', label: 'Notes' },
  { key: 'tasks', label: 'Tasks' },
  { key: 'people', label: 'People' },
  { key: 'connections', label: 'Connections' },
];

const TASK_COLUMNS = [
  { key: 'DONE', label: 'Done' },
  { key: 'IN_PROGRESS', label: 'In Progress' },
  { key: 'PENDING', label: 'Pending' },
];

const surfaceCardStyle = {
  background: 'var(--bg-surface)',
  border: '1px solid var(--border)',
  borderRadius: '14px',
};

function firstLine(text) {
  return (text || '')
    .split('\n')
    .map((line) => line.replace(/^#+\s*/, '').trim())
    .find(Boolean) || 'Untitled';
}

function formatDate(value, options = {}) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    ...options,
  });
}

function formatModifiedTime(value) {
  if (!value) return 'Recently updated';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Recently updated';
  return `Modified ${date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  })}`;
}

function getStatusLabel(value) {
  const normalized = String(value || 'ACTIVE').replace(/_/g, ' ').toLowerCase();
  return normalized.replace(/\b\w/g, (char) => char.toUpperCase());
}

function getInitials(name) {
  const parts = (name || '').trim().split(/\s+/).filter(Boolean).slice(0, 2);
  if (parts.length === 0) return '?';
  return parts.map((part) => part[0].toUpperCase()).join('');
}

function ProgressMetric({ label, value }) {
  return (
    <div style={{ display: 'grid', gap: '6px' }}>
      <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
        {label}
      </span>
      <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: '20px', fontWeight: 700, lineHeight: 1 }}>
        {value}
      </span>
    </div>
  );
}

export default function ProjectFocus() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { projects, notes, tasks, people, areas, updateProject } = useStore();
  const [tab, setTab] = useState('notes');
  const [showNoteEditor, setShowNoteEditor] = useState(false);
  const [completionState, setCompletionState] = useState('idle');

  const project = projects.find((entry) => entry.id === id);

  const parentArea = project?.area_id ? areas.find((area) => area.id === project.area_id) : null;
  const projectNotes = useMemo(() => notes.filter((note) => note.project_id === id), [id, notes]);
  const projectTasks = useMemo(() => tasks.filter((task) => task.project_id === id), [id, tasks]);

  const linkedPeople = useMemo(() => {
    const personIds = new Set(projectNotes.map((note) => note.person_id).filter(Boolean));
    return people.filter((person) => personIds.has(person.id));
  }, [people, projectNotes]);

  const taskCounts = useMemo(() => ({
    DONE: projectTasks.filter((task) => task.status === 'DONE').length,
    IN_PROGRESS: projectTasks.filter((task) => task.status === 'IN_PROGRESS').length,
    PENDING: projectTasks.filter((task) => task.status === 'PENDING').length,
  }), [projectTasks]);

  const completionPercent = projectTasks.length
    ? Math.round((taskCounts.DONE / projectTasks.length) * 100)
    : 0;

  const tasksByColumn = useMemo(() => (
    TASK_COLUMNS.reduce((acc, column) => {
      acc[column.key] = projectTasks.filter((task) => task.status === column.key);
      return acc;
    }, {})
  ), [projectTasks]);

  if (!project) {
    return (
      <div className={styles.page}>
        <p>Project not found.</p>
        <button type="button" onClick={() => navigate('/projects')}>Back</button>
      </div>
    );
  }

  async function handleCompleteProject() {
    if (completionState !== 'idle') return;
    setCompletionState('rolling-up');
    try {
      await updateProject(id, { status: 'DONE' });
      setCompletionState('completed');
    } catch {
      setCompletionState('idle');
    }
  }

  const completeButtonLabel = completionState === 'rolling-up'
    ? 'Rolling up...'
    : completionState === 'completed'
      ? 'Completed'
      : 'Complete Project';

  return (
    <div className={styles.page} style={{ paddingBottom: '28px' }}>
      <div style={{ padding: '18px 28px 0', borderBottom: '1px solid var(--border)' }}>
        <button
          type="button"
          className={styles.backBtn}
          onClick={() => navigate('/projects')}
          style={{ marginBottom: '14px' }}
        >
          <ArrowLeft size={14} /> All Projects
        </button>

        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '24px', alignItems: 'flex-start', paddingBottom: '18px', flexWrap: 'wrap' }}>
          <div style={{ minWidth: 0, flex: '1 1 420px', display: 'grid', gap: '8px' }}>
            {parentArea && (
              <Link
                to={`/areas/${parentArea.id}`}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  width: 'fit-content',
                  padding: '5px 10px',
                  borderRadius: '999px',
                  border: '1px solid color-mix(in srgb, var(--accent) 28%, var(--border))',
                  background: 'color-mix(in srgb, var(--accent) 12%, transparent)',
                  color: 'var(--accent)',
                  textDecoration: 'none',
                  fontSize: '11px',
                  fontWeight: 600,
                  letterSpacing: '0.06em',
                  textTransform: 'uppercase',
                }}
              >
                <FolderOpen size={12} />
                {parentArea.name}
              </Link>
            )}
            <h1 style={{ margin: 0, fontSize: '22px', lineHeight: 1.05 }}>{project.name}</h1>
            <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '12.5px', lineHeight: 1.5 }}>
              {project.description || 'No description yet.'}
            </p>
          </div>

          <div style={{ display: 'grid', gap: '8px', justifyItems: 'end', flex: '0 0 auto' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                padding: '5px 10px',
                borderRadius: '999px',
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border)',
                color: 'var(--text-primary)',
                fontSize: '11px',
                fontWeight: 600,
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
              }}>
                {getStatusLabel(completionState === 'completed' ? 'DONE' : project.status)}
              </span>
              {project.due_date && (
                <span style={{ color: 'var(--text-secondary)', fontSize: '12px', fontFamily: 'var(--font-mono, monospace)' }}>
                  Due {formatDate(project.due_date)}
                </span>
              )}
            </div>
            <button
              type="button"
              data-testid="complete-project-btn"
              onClick={handleCompleteProject}
              disabled={completionState !== 'idle'}
              style={{
                minWidth: '148px',
                height: '34px',
                padding: '0 14px',
                borderRadius: '999px',
                border: '1px solid transparent',
                background: completionState === 'completed' ? 'var(--success)' : 'var(--accent)',
                color: completionState === 'completed' ? 'var(--text)' : 'var(--text)',
                fontSize: '12px',
                fontWeight: 700,
                cursor: completionState === 'idle' ? 'pointer' : 'default',
                opacity: completionState === 'rolling-up' ? 0.85 : 1,
                transition: 'background 180ms ease, opacity 180ms ease, transform 180ms ease',
              }}
            >
              {completeButtonLabel}
            </button>
            <span aria-live="polite" style={{ minHeight: '16px', color: 'var(--text-muted)', fontSize: '11px' }}>
              {completionState === 'rolling-up' ? 'Rolling up...' : completionState === 'completed' ? 'Completed' : ''}
            </span>
          </div>
        </div>
      </div>

      <div style={{ padding: '20px 28px 0', display: 'grid', gap: '18px' }}>
        <section style={{ ...surfaceCardStyle, padding: '18px' }}>
          <div style={{ display: 'grid', gap: '14px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '18px', alignItems: 'start', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', gap: '28px', flexWrap: 'wrap' }}>
                <ProgressMetric label="Done" value={taskCounts.DONE} />
                <ProgressMetric label="In Progress" value={taskCounts.IN_PROGRESS} />
                <ProgressMetric label="Pending" value={taskCounts.PENDING} />
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: '20px', fontWeight: 700, lineHeight: 1 }}>
                  {completionPercent}%
                </div>
                <div style={{ marginTop: '6px', color: 'var(--text-muted)', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                  Complete
                </div>
              </div>
            </div>
            <div style={{ height: '3px', borderRadius: '999px', background: 'var(--bg-elevated)', overflow: 'hidden' }}>
              <div
                style={{
                  width: `${completionPercent}%`,
                  height: '100%',
                  background: 'var(--accent)',
                  transition: 'width 220ms ease',
                }}
              />
            </div>
          </div>
        </section>

        <div style={{ display: 'flex', gap: '18px', borderBottom: '1px solid var(--border)' }}>
          {TABS.map((entry) => (
            <button
              key={entry.key}
              type="button"
              onClick={() => setTab(entry.key)}
              style={{
                padding: '0 0 10px',
                marginBottom: '-1px',
                border: 'none',
                borderBottom: tab === entry.key ? '2px solid var(--accent)' : '2px solid transparent',
                background: 'transparent',
                color: tab === entry.key ? 'var(--text-primary)' : 'var(--text-secondary)',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              {entry.label}
            </button>
          ))}
        </div>

        {tab === 'notes' && (
          <section style={{ display: 'grid', gap: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'center' }}>
              <span style={{ color: 'var(--text-muted)', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                {projectNotes.length} linked notes
              </span>
              <button className="btn btn-primary btn-sm" type="button" onClick={() => setShowNoteEditor(true)}>
                <Plus size={13} /> Add Note
              </button>
            </div>

            {projectNotes.length === 0 ? (
              <div style={{ ...surfaceCardStyle, padding: '18px', color: 'var(--text-secondary)', fontSize: '12px' }}>
                No notes linked to this project yet.
              </div>
            ) : (
              projectNotes.map((note) => (
                <Link
                  key={note.id}
                  to={`/notes/${note.id}`}
                  style={{
                    ...surfaceCardStyle,
                    padding: '14px 16px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '12px',
                    color: 'inherit',
                    textDecoration: 'none',
                  }}
                >
                  <div style={{ minWidth: 0, display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{
                      width: '30px',
                      height: '30px',
                      borderRadius: '10px',
                      background: 'var(--bg-elevated)',
                      border: '1px solid var(--border)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'var(--text-secondary)',
                      flexShrink: 0,
                    }}>
                      <FileText size={14} />
                    </div>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                        {firstLine(note.raw_text || note.title)}
                      </div>
                      <div style={{ marginTop: '4px', color: 'var(--text-muted)', fontSize: '11px' }}>
                        {formatModifiedTime(note.updated_at || note.created_at)}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                    {(note.tag_names || []).map((tag) => (
                      <span
                        key={tag}
                        style={{
                          padding: '4px 8px',
                          borderRadius: '999px',
                          background: 'var(--bg-elevated)',
                          border: '1px solid var(--border)',
                          color: 'var(--text-secondary)',
                          fontSize: '11px',
                        }}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </Link>
              ))
            )}
          </section>
        )}

        {tab === 'tasks' && (
          <section style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '12px' }}>
            {TASK_COLUMNS.map((column) => (
              <div key={column.key} style={{ ...surfaceCardStyle, padding: '14px', display: 'grid', gap: '10px', alignContent: 'start' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px' }}>
                  <span style={{ fontSize: '12px', fontWeight: 600 }}>{column.label}</span>
                  <span style={{ color: 'var(--text-muted)', fontSize: '11px', fontFamily: 'var(--font-mono, monospace)' }}>
                    {tasksByColumn[column.key].length}
                  </span>
                </div>
                {tasksByColumn[column.key].length === 0 ? (
                  <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>No tasks</div>
                ) : (
                  tasksByColumn[column.key].map((task) => (
                    <div key={task.id} style={{ padding: '12px', borderRadius: '12px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', display: 'grid', gap: '8px' }}>
                      <div style={{ fontSize: '12.5px', fontWeight: 600, color: 'var(--text-primary)' }}>
                        {task.title}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px' }}>
                        <span style={{ color: 'var(--text-secondary)', fontSize: '10px', fontFamily: 'var(--font-mono, monospace)' }}>
                          {formatDate(task.due_date) || 'No due date'}
                        </span>
                        <span style={{ color: 'var(--text-muted)', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                          {getStatusLabel(task.status)}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            ))}
          </section>
        )}

        {tab === 'people' && (
          <section style={{ display: 'grid', gap: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'center' }}>
              <span style={{ color: 'var(--text-muted)', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                {linkedPeople.length} people linked
              </span>
              <button className="btn btn-secondary btn-sm" type="button" onClick={() => navigate('/people')}>
                <Plus size={13} /> Add person
              </button>
            </div>
            {linkedPeople.length === 0 ? (
              <div style={{ ...surfaceCardStyle, padding: '18px', color: 'var(--text-secondary)', fontSize: '12px' }}>
                No people linked to this project yet.
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '12px' }}>
                {linkedPeople.map((person) => (
                  <Link
                    key={person.id}
                    to={`/people/${person.id}`}
                    style={{
                      ...surfaceCardStyle,
                      padding: '14px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                      textDecoration: 'none',
                      color: 'inherit',
                    }}
                  >
                    <div style={{
                      width: '34px',
                      height: '34px',
                      borderRadius: '999px',
                      background: 'var(--accent-dim)',
                      color: 'var(--accent)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '12px',
                      fontWeight: 700,
                      flexShrink: 0,
                    }}>
                      {getInitials(person.name)}
                    </div>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: '12.5px', fontWeight: 600, color: 'var(--text-primary)' }}>{person.name}</div>
                      <div style={{ marginTop: '3px', color: 'var(--text-secondary)', fontSize: '11px' }}>
                        {person.role || 'No role set'}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </section>
        )}

        {tab === 'connections' && (
          <section style={{ ...surfaceCardStyle, padding: '14px' }}>
            <ConnectionsPanel entityId={id} />
          </section>
        )}
      </div>

      {showNoteEditor && (
        <NoteEditor
          initialData={{ project_ids: [id], bucket: 'PROJECTS' }}
          onClose={() => setShowNoteEditor(false)}
          onSaved={() => setShowNoteEditor(false)}
        />
      )}
    </div>
  );
}
