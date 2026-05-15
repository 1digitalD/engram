import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  FileText,
  FolderOpen,
  Plus,
  ChevronDown,
  X,
  Loader2,
  CheckCircle,
  User,
} from 'lucide-react';
import useStore from '../stores/useStore';
import NoteEditor from '../components/notes/NoteEditor';
import { linksAPI, relationshipsAPI } from '../api/engram';
import LinkedContextPanel from '../components/LinkedContextPanel/LinkedContextPanel';
import LinkToEntity from '../components/LinkToEntity/LinkToEntity';
import styles from './ProjectFocus.module.css';

const TABS = [
  { key: 'notes', label: 'Notes' },
  { key: 'tasks', label: 'Tasks' },
  { key: 'people', label: 'People' },
  { key: 'connections', label: 'Connections' },
];

const TASK_COLUMNS = [
  { key: 'done', label: 'Done' },
  { key: 'in_progress', label: 'In Progress' },
  { key: 'pending', label: 'Pending' },
];

const PROJECT_STATUSES = [
  { value: 'active', label: 'Active' },
  { value: 'on_hold', label: 'On Hold' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Archived' },
];

const surfaceCardStyle = {
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: '14px',
};

const STATUS_COLORS = {
  active: 'var(--green)',
  on_hold: 'var(--yellow)',
  completed: 'var(--accent)',
  cancelled: 'var(--text-muted)',
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
      <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: '20px', fontWeight: 700, lineHeight: 1 }}>
        {value}
      </span>
      <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
        {label}
      </span>
    </div>
  );
}

export default function ProjectFocus() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { projects, notes, tasks, people, areas, updateProject, updateNote, createTask, updateTask, addToast, loading } = useStore();
  const [tab, setTab] = useState('notes');
  const [showNoteEditor, setShowNoteEditor] = useState(false);
  const [completionState, setCompletionState] = useState('idle');
  const [showStatusPicker, setShowStatusPicker] = useState(false);
  const statusPickerRef = useRef(null);

  // Add-note modal state
  const [showAddNoteModal, setShowAddNoteModal] = useState(false);
  const [noteSearchQuery, setNoteSearchQuery] = useState('');
  const [notePick, setNotePick] = useState('');
  const [noteLinkBusy, setNoteLinkBusy] = useState(false);

  // Add-person modal state
  const [showAddPersonModal, setShowAddPersonModal] = useState(false);
  const [personSearchQuery, setPersonSearchQuery] = useState('');
  const [personPick, setPersonPick] = useState('');
  const [personLinkBusy, setPersonLinkBusy] = useState(false);

  // Connections tab refresh
  const [connRefreshKey, setConnRefreshKey] = useState(0);

  // Inline task creation
  const [newTaskTitle, setNewTaskTitle] = useState('');

  // Linked context
  const [linksOut, setLinksOut] = useState([]);
  const [linksIn, setLinksIn] = useState([]);
  const [linksLoading, setLinksLoading] = useState(false);

  const loadLinks = useCallback(async () => {
    if (!id) return;
    setLinksLoading(true);
    try {
      const res = await relationshipsAPI.list(id);
      setLinksOut(res.outgoing || []);
      setLinksIn(res.incoming || []);
    } catch {
      setLinksOut([]);
      setLinksIn([]);
    } finally {
      setLinksLoading(false);
    }
  }, [id]);

  useEffect(() => { loadLinks(); }, [loadLinks]);

  useEffect(() => {
    function handleClickOutside(e) {
      if (statusPickerRef.current && !statusPickerRef.current.contains(e.target)) {
        setShowStatusPicker(false);
      }
    }
    if (showStatusPicker) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showStatusPicker]);

  const project = projects.find((entry) => entry.id === id);

  const parentArea = project?.area_id ? areas.find((area) => area.id === project.area_id) : null;
  const projectNotes = useMemo(() => notes.filter((note) => {
    const noteProjectIds = note.project_ids?.length ? note.project_ids : (note.project_id ? [note.project_id] : []);
    return noteProjectIds.includes(id);
  }), [id, notes]);
  const projectTasks = useMemo(() => tasks.filter((task) => task.project_id === id), [id, tasks]);

  const linkedPeople = useMemo(() => {
    const personIds = new Set(projectNotes.map((note) => note.person_id).filter(Boolean));
    return people.filter((person) => personIds.has(person.id));
  }, [people, projectNotes]);

  const taskCounts = useMemo(() => ({
    DONE: projectTasks.filter((task) => task.status === 'done').length,

    IN_PROGRESS: projectTasks.filter((task) => task.status === 'in_progress').length,

    PENDING: projectTasks.filter((task) => task.status === 'pending').length,
  }), [projectTasks]);

  const tasksByColumn = useMemo(() => (
    TASK_COLUMNS.reduce((acc, column) => {
      acc[column.key] = projectTasks.filter((task) => task.status === column.key);
      return acc;
    }, {})
  ), [projectTasks]);

  const nextAction = tasksByColumn['pending']?.[0] || tasksByColumn['in_progress']?.[0] || null;

  const completionPercent = projectTasks.length
    ? Math.round((taskCounts.DONE / projectTasks.length) * 100)
    : 0;

  // Note candidates: notes not already linked to this project
  const alreadyLinkedNoteIds = new Set(projectNotes.map(n => n.id));
  const noteCandidates = notes
    .filter(n => !alreadyLinkedNoteIds.has(n.id))
    .filter(n => firstLine(n.raw_text || n.title).toLowerCase().includes(noteSearchQuery.trim().toLowerCase()))
    .slice(0, 80);

  // Person candidates: people not already linked
  const alreadyLinkedPersonIds = new Set(linkedPeople.map(p => p.id));
  const personCandidates = people
    .filter(p => !alreadyLinkedPersonIds.has(p.id))
    .filter(p => (p.title || '').toLowerCase().includes(personSearchQuery.trim().toLowerCase()))
    .slice(0, 80);

  if (!project) {
    if (loading) {
      return (
        <div className={styles.page}>
          <Loader2 size={20} className="spin" style={{ display: 'block', margin: '40px auto', color: 'var(--text-muted)' }} />
        </div>
      );
    }
    return (
      <div className={styles.page}>
        <p>Project not found.</p>
        <button type="button" onClick={() => navigate('/projects')}>Back</button>
      </div>
    );
  }

  async function handleStatusChange(newStatus) {
    setShowStatusPicker(false);
    if (newStatus === 'completed') {
      setCompletionState('rolling-up');
      try {
        await updateProject(id, { status: 'completed' });
        setCompletionState('completed');
      } catch (e) {
        setCompletionState('idle');
        addToast({ type: 'error', message: e.message || 'Status change failed' });
      }
    } else {
      try {
        await updateProject(id, { status: newStatus });
      } catch (e) {
        addToast({ type: 'error', message: e.message || 'Status change failed' });
      }
    }
  }

  const currentStatus = completionState === 'completed' ? 'completed' : (project.status || 'active');
  const currentStatusConfig = PROJECT_STATUSES.find(s => s.value === currentStatus) || PROJECT_STATUSES[0];
  const statusColor = STATUS_COLORS[currentStatus] || 'var(--text)';

  const completeButtonLabel = completionState === 'rolling-up'
    ? 'Rolling up...'
    : completionState === 'completed'
      ? 'Completed'
      : 'Complete Project';

  // ── Add note to project ──
  async function handleAddNoteLink() {
    if (!notePick || noteLinkBusy) return;
    setNoteLinkBusy(true);
    try {
      const note = notes.find(n => n.id === notePick);
      if (!note) return;
      const existingIds = note.project_ids?.length ? note.project_ids : (note.project_id ? [note.project_id] : []);
      if (!existingIds.includes(id)) {
        await updateNote(note.id, { project_ids: [...existingIds, id] });
      }
      setNotePick('');
      setNoteSearchQuery('');
      setShowAddNoteModal(false);
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Could not link note' });
    } finally {
      setNoteLinkBusy(false);
    }
  }

  // ── Remove note from project ──
  async function handleRemoveNoteFromProject(noteId, e) {
    e.preventDefault();
    e.stopPropagation();
    try {
      const note = notes.find(n => n.id === noteId);
      if (!note) return;
      const existingIds = note.project_ids?.length ? note.project_ids : (note.project_id ? [note.project_id] : []);
      const newIds = existingIds.filter(pid => pid !== id);
      await updateNote(note.id, { project_ids: newIds.length ? newIds : null });
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Could not unlink note' });
    }
  }

  // ── Create task for this project ──
  async function handleCreateTask(e) {
    e.preventDefault();
    const title = newTaskTitle.trim();
    if (!title) return;
    try {
      await createTask({ title, project_id: id });
      setNewTaskTitle('');
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Could not create task' });
    }
  }

  // ── Remove task from project ──
  async function handleRemoveTaskFromProject(taskId) {
    try {
      await updateTask(taskId, { project_id: null });
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Could not unlink task' });
    }
  }

  // ── Add person to project notes ──
  async function handleAddPersonLink() {
    if (!personPick || personLinkBusy) return;
    setPersonLinkBusy(true);
    try {
      // Associate the person with all notes linked to this project that don't have a person yet
      const notesToUpdate = projectNotes.filter(n => !n.person_id);
      if (notesToUpdate.length === 0) {
        addToast({ type: 'info', message: 'All project notes already have a person assigned' });
      } else {
        for (const note of notesToUpdate) {
          await updateNote(note.id, { person_id: personPick });
        }
        addToast({ type: 'success', message: `Person added to ${notesToUpdate.length} note(s)` });
      }
      setPersonPick('');
      setPersonSearchQuery('');
      setShowAddPersonModal(false);
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Could not link person' });
    } finally {
      setPersonLinkBusy(false);
    }
  }

  // ── Remove person from project notes ──
  async function handleRemovePersonFromProject(personId, e) {
    e.preventDefault();
    e.stopPropagation();
    try {
      const notesToUpdate = projectNotes.filter(n => n.person_id === personId);
      for (const note of notesToUpdate) {
        await updateNote(note.id, { person_id: null });
      }
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Could not unlink person' });
    }
  }

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
                {parentArea.title}
              </Link>
            )}
            <h1 style={{ margin: 0, fontSize: '22px', lineHeight: 1.05 }}>{project.title}</h1>
            <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '12.5px', lineHeight: 1.5 }}>
              {project.description || 'No description yet.'}
            </p>
          </div>

          <div style={{ display: 'grid', gap: '8px', justifyItems: 'end', flex: '0 0 auto' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
              {/* Status picker dropdown */}
              <div ref={statusPickerRef} style={{ position: 'relative' }}>
                <button
                  type="button"
                  onClick={() => setShowStatusPicker(!showStatusPicker)}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '5px 10px',
                    borderRadius: '999px',
                    background: 'var(--surface2)',
                    border: `1px solid ${statusColor}`,
                    color: statusColor,
                    fontSize: '11px',
                    fontWeight: 600,
                    letterSpacing: '0.06em',
                    textTransform: 'uppercase',
                    cursor: 'pointer',
                  }}
                >
                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: statusColor }} />
                  {currentStatusConfig.label}
                  <ChevronDown size={12} />
                </button>
                {showStatusPicker && (
                  <div style={{
                    position: 'absolute',
                    top: '100%',
                    right: 0,
                    marginTop: '4px',
                    background: 'var(--surface)',
                    border: '1px solid var(--border)',
                    borderRadius: '8px',
                    padding: '4px',
                    minWidth: '140px',
                    zIndex: 100,
                    boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
                  }}>
                    {PROJECT_STATUSES.map((status) => {
                      const color = STATUS_COLORS[status.value];
                      return (
                        <button
                          key={status.value}
                          type="button"
                          onClick={() => handleStatusChange(status.value)}
                          disabled={status.value === currentStatus || completionState !== 'idle'}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            width: '100%',
                            padding: '8px 10px',
                            border: 'none',
                            borderRadius: '6px',
                            background: status.value === currentStatus ? 'var(--surface2)' : 'transparent',
                            color: 'var(--text)',
                            fontSize: '12px',
                            cursor: status.value === currentStatus || completionState !== 'idle' ? 'default' : 'pointer',
                            textAlign: 'left',
                          }}
                        >
                          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: color }} />
                          {status.label}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
              {project.due_date && (
                <span style={{ color: 'var(--text-secondary)', fontSize: '12px', fontFamily: 'var(--font-mono, monospace)' }}>
                  Due {formatDate(project.due_date)}
                </span>
              )}
            </div>
            {currentStatus !== 'completed' && (
              <button
                type="button"
                data-testid="complete-project-btn"
                onClick={() => handleStatusChange('completed')}
                disabled={completionState !== 'idle'}
                style={{
                  minWidth: '148px',
                  height: '34px',
                  padding: '0 14px',
                  borderRadius: '999px',
                  border: '1px solid transparent',
                  background: completionState === 'completed' ? 'var(--green)' : 'var(--accent)',
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
            )}
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
            <div style={{ height: '3px', borderRadius: '999px', background: 'var(--surface2)', overflow: 'hidden' }}>
              <div
                style={{
                  width: `${completionPercent}%`,
                  height: '100%',
                  background: 'var(--accent)',
                  transition: 'width 0.6s ease',
                }}
              />
            </div>
            {nextAction ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 12px', borderRadius: '8px', background: 'color-mix(in srgb, var(--accent) 10%, transparent)', border: '1px solid color-mix(in srgb, var(--accent) 25%, var(--border))' }}>
                <span style={{ fontSize: '10px', color: 'var(--accent)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Next Action</span>
                <span style={{ fontSize: '12px', color: 'var(--text)', fontWeight: 600, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {nextAction.title}
                </span>
                {nextAction.due_date && (
                  <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono, monospace)' }}>
                    Due {formatDate(nextAction.due_date)}
                  </span>
                )}
              </div>
            ) : projectTasks.length > 0 ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 12px', borderRadius: '8px', background: 'color-mix(in srgb, var(--yellow) 10%, transparent)', border: '1px solid color-mix(in srgb, var(--yellow) 25%, var(--border))' }}>
                <span style={{ fontSize: '11px', color: 'var(--yellow)', fontWeight: 600 }}>No next action set — add a pending task to define one</span>
              </div>
            ) : null}
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
                color: tab === entry.key ? 'var(--text)' : 'var(--text-secondary)',
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
              <div style={{ display: 'flex', gap: '8px' }}>
                <button className="btn btn-secondary btn-sm" type="button" onClick={() => setShowAddNoteModal(true)}>
                  <Plus size={13} /> Add Note
                </button>
                <button className="btn btn-primary btn-sm" type="button" onClick={() => setShowNoteEditor(true)}>
                  <Plus size={13} /> New Note
                </button>
              </div>
            </div>

            {/* Add Note Modal */}
            {showAddNoteModal && (
              <div style={{
                ...surfaceCardStyle,
                padding: '14px',
                display: 'grid',
                gap: '10px',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text)' }}>Link existing note</span>
                  <button
                    type="button"
                    onClick={() => { setShowAddNoteModal(false); setNotePick(''); setNoteSearchQuery(''); }}
                    style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '2px' }}
                  >
                    <X size={14} />
                  </button>
                </div>
                <input
                  type="search"
                  placeholder="Filter notes…"
                  value={noteSearchQuery}
                  onChange={e => setNoteSearchQuery(e.target.value)}
                  style={{
                    padding: '8px 10px',
                    fontSize: '12px',
                    background: 'var(--surface2)',
                    border: '1px solid var(--border-faint)',
                    borderRadius: '6px',
                    color: 'var(--text)',
                    outline: 'none',
                  }}
                />
                <select
                  value={notePick}
                  onChange={e => setNotePick(e.target.value)}
                  style={{
                    padding: '8px 10px',
                    fontSize: '12px',
                    background: 'var(--surface2)',
                    border: '1px solid var(--border-faint)',
                    borderRadius: '6px',
                    color: 'var(--text)',
                    cursor: 'pointer',
                  }}
                >
                  <option value="">Select a note…</option>
                  {noteCandidates.map(n => (
                    <option key={n.id} value={n.id}>{firstLine(n.raw_text || n.title)}</option>
                  ))}
                </select>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={handleAddNoteLink}
                  disabled={!notePick || noteLinkBusy}
                  style={{ alignSelf: 'end' }}
                >
                  {noteLinkBusy ? <Loader2 size={13} className="spin" /> : <CheckCircle size={13} />}
                  Add link
                </button>
              </div>
            )}

            {projectNotes.length === 0 ? (
              <div style={{ ...surfaceCardStyle, padding: '18px', color: 'var(--text-secondary)', fontSize: '12px' }}>
                No notes linked to this project yet.
              </div>
            ) : (
              projectNotes.map((note) => (
                <div
                  key={note.id}
                  style={{
                    ...surfaceCardStyle,
                    padding: '14px 16px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '12px',
                  }}
                >
                  <Link
                    to={`/notes/${note.id}`}
                    style={{
                      minWidth: 0,
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                      color: 'inherit',
                      textDecoration: 'none',
                      flex: 1,
                    }}
                  >
                    <div style={{
                      width: '30px',
                      height: '30px',
                      borderRadius: '10px',
                      background: 'var(--surface2)',
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
                      <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text)' }}>
                        {firstLine(note.raw_text || note.title)}
                      </div>
                      <div style={{ marginTop: '4px', color: 'var(--text-muted)', fontSize: '11px' }}>
                        {formatModifiedTime(note.updated_at || note.created_at)}
                      </div>
                    </div>
                  </Link>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'flex-end', alignItems: 'center' }}>
                    {(note.tag_names || []).map((tag) => (
                      <span
                        key={tag}
                        style={{
                          padding: '4px 8px',
                          borderRadius: '999px',
                          background: 'var(--surface2)',
                          border: '1px solid var(--border)',
                          color: 'var(--text-secondary)',
                          fontSize: '11px',
                        }}
                      >
                        {tag}
                      </span>
                    ))}
                    <button
                      type="button"
                      onClick={(e) => handleRemoveNoteFromProject(note.id, e)}
                      style={{
                        background: 'none',
                        border: '1px solid var(--border-faint)',
                        borderRadius: '6px',
                        color: 'var(--text-muted)',
                        cursor: 'pointer',
                        padding: '4px 6px',
                        display: 'flex',
                        alignItems: 'center',
                        fontSize: '10px',
                      }}
                      title="Remove note from project"
                    >
                      <X size={12} />
                    </button>
                  </div>
                </div>
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
                    <div key={task.id} style={{ padding: '12px', borderRadius: '12px', background: 'var(--surface2)', border: '1px solid var(--border)', display: 'grid', gap: '8px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
                        <div style={{ fontSize: '12.5px', fontWeight: 600, color: 'var(--text)', flex: 1 }}>
                          {task.title}
                        </div>
                        <button
                          type="button"
                          onClick={() => handleRemoveTaskFromProject(task.id)}
                          style={{
                            background: 'none',
                            border: 'none',
                            color: 'var(--text-muted)',
                            cursor: 'pointer',
                            padding: '2px',
                            display: 'flex',
                            alignItems: 'center',
                            flexShrink: 0,
                          }}
                          title="Remove task from project"
                        >
                          <X size={12} />
                        </button>
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
                {/* Quick-add task form for PENDING column */}
                {column.key === 'pending' && (
                  <form onSubmit={handleCreateTask} style={{ display: 'flex', gap: '6px', marginTop: '4px' }}>
                    <input
                      type="text"
                      placeholder="New task…"
                      value={newTaskTitle}
                      onChange={e => setNewTaskTitle(e.target.value)}
                      style={{
                        flex: 1,
                        padding: '7px 9px',
                        fontSize: '11.5px',
                        background: 'var(--surface2)',
                        border: '1px solid var(--border-faint)',
                        borderRadius: '6px',
                        color: 'var(--text)',
                        outline: 'none',
                      }}
                    />
                    <button
                      type="submit"
                      className="btn btn-primary btn-sm"
                      disabled={!newTaskTitle.trim()}
                      style={{ padding: '6px 10px', fontSize: '11px' }}
                    >
                      Add
                    </button>
                  </form>
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
              <div style={{ display: 'flex', gap: '8px' }}>
                <button className="btn btn-secondary btn-sm" type="button" onClick={() => setShowAddPersonModal(true)}>
                  <Plus size={13} /> Add person
                </button>
              </div>
            </div>

            {/* Add Person Modal */}
            {showAddPersonModal && (
              <div style={{
                ...surfaceCardStyle,
                padding: '14px',
                display: 'grid',
                gap: '10px',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text)' }}>Link person to project notes</span>
                  <button
                    type="button"
                    onClick={() => { setShowAddPersonModal(false); setPersonPick(''); setPersonSearchQuery(''); }}
                    style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '2px' }}
                  >
                    <X size={14} />
                  </button>
                </div>
                <input
                  type="search"
                  placeholder="Filter people…"
                  value={personSearchQuery}
                  onChange={e => setPersonSearchQuery(e.target.value)}
                  style={{
                    padding: '8px 10px',
                    fontSize: '12px',
                    background: 'var(--surface2)',
                    border: '1px solid var(--border-faint)',
                    borderRadius: '6px',
                    color: 'var(--text)',
                    outline: 'none',
                  }}
                />
                <select
                  value={personPick}
                  onChange={e => setPersonPick(e.target.value)}
                  style={{
                    padding: '8px 10px',
                    fontSize: '12px',
                    background: 'var(--surface2)',
                    border: '1px solid var(--border-faint)',
                    borderRadius: '6px',
                    color: 'var(--text)',
                    cursor: 'pointer',
                  }}
                >
                  <option value="">Select a person…</option>
                  {personCandidates.map(p => (
                    <option key={p.id} value={p.id}>{p.title}</option>
                  ))}
                </select>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={handleAddPersonLink}
                  disabled={!personPick || personLinkBusy}
                  style={{ alignSelf: 'end' }}
                >
                  {personLinkBusy ? <Loader2 size={13} className="spin" /> : <CheckCircle size={13} />}
                  Add link
                </button>
              </div>
            )}

            {linkedPeople.length === 0 ? (
              <div style={{ ...surfaceCardStyle, padding: '18px', color: 'var(--text-secondary)', fontSize: '12px' }}>
                No people linked to this project yet.
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '12px' }}>
                {linkedPeople.map((person) => (
                  <div
                    key={person.id}
                    style={{
                      ...surfaceCardStyle,
                      padding: '14px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                    }}
                  >
                    <Link
                      to={`/people/${person.id}`}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px',
                        textDecoration: 'none',
                        color: 'inherit',
                        flex: 1,
                        minWidth: 0,
                      }}
                    >
                      <div style={{
                        width: '32px',
                        height: '32px',
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
                        {getInitials(person.title)}
                      </div>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontSize: '12.5px', fontWeight: 600, color: 'var(--text)' }}>{person.title}</div>
                        <div style={{ marginTop: '3px', color: 'var(--text-secondary)', fontSize: '11px' }}>
                          {person.role || 'No role set'}
                        </div>
                      </div>
                    </Link>
                    <button
                      type="button"
                      onClick={(e) => handleRemovePersonFromProject(person.id, e)}
                      style={{
                        background: 'none',
                        border: '1px solid var(--border-faint)',
                        borderRadius: '6px',
                        color: 'var(--text-muted)',
                        cursor: 'pointer',
                        padding: '4px 6px',
                        display: 'flex',
                        alignItems: 'center',
                        flexShrink: 0,
                      }}
                      title="Remove person from project"
                    >
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {tab === 'connections' && (
          <section style={{ display: 'grid', gap: '10px' }}>
            <section style={{ ...surfaceCardStyle, padding: '14px' }}>
              <LinkToEntity entityId={id} entityType="project" onLinkCreated={() => setConnRefreshKey(k => k + 1)} />
            </section>
            <section style={{ ...surfaceCardStyle, padding: '14px' }}>
              <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Linked Context
              </div>
              <LinkedContextPanel
                entityId={id}
                linksOut={linksOut}
                linksIn={linksIn}
                loading={linksLoading}
              />
            </section>
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
