import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, Plus, Pencil, Trash2, ChevronDown, AlertTriangle, Loader2, X, CheckCircle, FileText, FolderOpen } from 'lucide-react';
import Modal from '../components/ui/Modal';
import useStore from '../stores/useStore';
import NoteCard from '../components/notes/NoteCard';
import NoteEditor from '../components/notes/NoteEditor';
import TaskCheckboxRow from '../components/tasks/TaskCheckboxRow';
import { relationshipsAPI } from '../api/engram';
import LinkedContextPanel from '../components/LinkedContextPanel/LinkedContextPanel';
import DeleteConfirmModal from '../components/DeleteConfirmModal';
import styles from './ProjectFocus.module.css';

const AREA_STATUSES = [
  { value: 'active', label: 'Active' },
  { value: 'archived', label: 'Archived' },
];

const STATUS_COLORS = {
  active: 'var(--green)',
  archived: 'var(--text-muted)',
};

const signalStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  padding: '10px 14px',
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: '8px',
  fontSize: '12px',
  color: 'var(--text-secondary)',
};

const signalDot = (color) => ({
  width: '8px',
  height: '8px',
  borderRadius: '50%',
  background: color,
  flexShrink: 0,
});

export default function AreaFocus() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { areas, notes, projects, tasks, updateArea, deleteArea, getDeletePreview, createProject, updateProject, updateNote, addToast, loading } = useStore();
  const [tab, setTab] = useState('notes');
  const [showNoteEditor, setShowNoteEditor] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deletePreview, setDeletePreview] = useState(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [color, setColor] = useState('');

  // Status picker state
  const [showStatusPicker, setShowStatusPicker] = useState(false);
  const statusPickerRef = useRef(null);

  // Archive confirmation modal
  const [showArchiveModal, setShowArchiveModal] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [detachedCount, setDetachedCount] = useState(0);

  // Add-project modal state
  const [showAddProjectModal, setShowAddProjectModal] = useState(false);
  const [projectSearchQuery, setProjectSearchQuery] = useState('');
  const [projectPick, setProjectPick] = useState('');
  const [projectLinkBusy, setProjectLinkBusy] = useState(false);

  // Inline project creation
  const [newProjectTitle, setNewProjectTitle] = useState('');

  // Connections tab refresh
  const [connRefreshKey, setConnRefreshKey] = useState(0);

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

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const areaSignals = useMemo(() => {
    const signals = [];
    if (areaProjects.length === 0) {
      signals.push({ label: 'No active projects', color: 'var(--yellow)', icon: '!' });
    }
    const overdueFollowups = areaNotes.filter(n => n.follow_up_at && new Date(n.follow_up_at) < today);
    if (overdueFollowups.length > 0) {
      signals.push({ label: `${overdueFollowups.length} overdue follow-up${overdueFollowups.length > 1 ? 's' : ''}`, color: 'var(--red)', icon: '!' });
    }
    if (areaNotes.length === 0) {
      signals.push({ label: 'No notes captured yet', color: 'var(--text-muted)', icon: '?' });
    }
    return signals;
  }, [areaProjects, areaNotes, today]);

  // Add-note modal state (existing notes)
  const [showAddNoteModal, setShowAddNoteModal] = useState(false);
  const [noteSearchQuery, setNoteSearchQuery] = useState('');
  const [notePick, setNotePick] = useState('');
  const [noteLinkBusy, setNoteLinkBusy] = useState(false);

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

  const area = areas.find(a => a.id === id);
  if (!area) {
    if (loading) {
      return (
        <div className={styles.page}>
          <Loader2 size={20} className="spin" style={{ display: 'block', margin: '40px auto', color: 'var(--text-muted)' }} />
        </div>
      );
    }
    return (
      <div className={styles.page}>
        <p>Area not found.</p>
        <button className="btn btn-ghost" onClick={() => navigate('/areas')}>
          <ArrowLeft size={14} /> Back to Areas
        </button>
      </div>
    );
  }

  const areaNotes = notes.filter(n => n.area_id === id);
  const areaProjects = projects.filter(p => p.area_id === id && !p.is_archived);
  const areaTasks = tasks.filter(t => t.area_id === id);

  const openEdit = () => {
    setName(area.title || '');
    setDescription(area.description || '');
    setColor(area.color || '');
    setShowEditModal(true);
  };

  const closeEdit = () => setShowEditModal(false);

  const handleUpdate = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    await updateArea(area.id, {
      title: name.trim(),
      description: description.trim() || null,
      color: color.trim() || null,
    });
    closeEdit();
  };

  const handleDeleteClick = async () => {
    try {
      const preview = await getDeletePreview(area.id);
      setDeletePreview(preview);
      setShowDeleteModal(true);
    } catch (e) {
      useStore.getState().addToast({ type: 'error', message: e.message || 'Failed to load delete preview' });
    }
  };

  const handleDeleteConfirm = async (cascadeIds) => {
    await deleteArea(area.id, cascadeIds);
    setShowDeleteModal(false);
    setDeletePreview(null);
    navigate('/areas');
  };

  const handleStatusChange = async (newStatus) => {
    setShowStatusPicker(false);
    if (newStatus === 'archived') {
      setShowArchiveModal(true);
    } else {
      try {
        await updateArea(area.id, { status: newStatus });
      } catch (e) {
        useStore.getState().addToast({ type: 'error', message: e.message || 'Status change failed' });
      }
    }
  };

  const handleArchiveConfirm = async () => {
    setArchiving(true);
    try {
      const res = await updateArea(area.id, { is_archived: true });
      setDetachedCount(res.detached_projects || 0);
      setShowArchiveModal(false);
      useStore.getState().addToast({
        type: 'success',
        message: `Area archived${res.detached_projects ? `, ${res.detached_projects} project(s) detached` : ''}`,
      });
    } catch (e) {
      useStore.getState().addToast({ type: 'error', message: e.message || 'Failed to archive area' });
    } finally {
      setArchiving(false);
    }
  };

  const currentStatus = area.status || 'active';
  const currentStatusConfig = AREA_STATUSES.find(s => s.value === currentStatus) || AREA_STATUSES[0];
  const statusColor = STATUS_COLORS[currentStatus] || 'var(--text)';

  // ── Project candidates: projects not already linked to this area ──
  const alreadyLinkedProjectIds = new Set(areaProjects.map(p => p.id));
  const projectCandidates = projects
    .filter(p => !alreadyLinkedProjectIds.has(p.id) && !p.is_archived)
    .filter(p => (p.title || '').toLowerCase().includes(projectSearchQuery.trim().toLowerCase()))
    .slice(0, 80);

  // ── Note candidates: notes not already linked to this area ──
  const alreadyLinkedNoteIds = new Set(areaNotes.map(n => n.id));
  const noteCandidates = notes
    .filter(n => !alreadyLinkedNoteIds.has(n.id))
    .filter(n => (n.title || n.raw_text || '').toLowerCase().includes(noteSearchQuery.trim().toLowerCase()))
    .slice(0, 80);

  // ── Add existing project to area ──
  async function handleAddProjectLink() {
    if (!projectPick || projectLinkBusy) return;
    setProjectLinkBusy(true);
    try {
      await updateProject(projectPick, { area_id: id });
      setProjectPick('');
      setProjectSearchQuery('');
      setShowAddProjectModal(false);
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Could not link project' });
    } finally {
      setProjectLinkBusy(false);
    }
  }

  // ── Remove project from area ──
  async function handleRemoveProjectFromArea(projectId) {
    try {
      await updateProject(projectId, { area_id: null });
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Could not unlink project' });
    }
  }

  // ── Create new project for this area ──
  async function handleCreateProject(e) {
    e.preventDefault();
    const title = newProjectTitle.trim();
    if (!title) return;
    try {
      await createProject({ title, area_id: id });
      setNewProjectTitle('');
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Could not create project' });
    }
  }

  // ── Add existing note to area ──
  async function handleAddNoteLink() {
    if (!notePick || noteLinkBusy) return;
    setNoteLinkBusy(true);
    try {
      await updateNote(notePick, { area_id: id });
      setNotePick('');
      setNoteSearchQuery('');
      setShowAddNoteModal(false);
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Could not link note' });
    } finally {
      setNoteLinkBusy(false);
    }
  }

  // ── Remove note from area ──
  async function handleRemoveNoteFromArea(noteId) {
    try {
      await updateNote(noteId, { area_id: null });
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Could not unlink note' });
    }
  }

  return (
    <div className={styles.page}>
      <nav className={styles.breadcrumb} aria-label="Breadcrumb">
        <Link to="/areas">Areas</Link>
        <span className={styles.breadcrumbSep}>/</span>
        <span className={styles.breadcrumbCurrent}>{area.title}</span>
      </nav>

      <button type="button" className={styles.backBtn} onClick={() => navigate('/areas')}>
        <ArrowLeft size={14} /> All Areas
      </button>

      <div className={styles.projectHeader}>
        <span className={styles.dot} style={{ background: area.color || 'var(--accent-blue)' }} />
        <h1>{area.title}</h1>
        {area.description && <p className={styles.desc}>{area.description}</p>}
        <div className={styles.headerActions}>
          {/* Status picker */}
          <div ref={statusPickerRef} style={{ position: 'relative' }}>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => setShowStatusPicker(!showStatusPicker)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                border: `1px solid ${statusColor}`,
                color: statusColor,
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
                minWidth: '130px',
                zIndex: 100,
                boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
              }}>
                {AREA_STATUSES.map((status) => {
                  const color = STATUS_COLORS[status.value];
                  return (
                    <button
                      key={status.value}
                      type="button"
                      onClick={() => handleStatusChange(status.value)}
                      disabled={status.value === currentStatus}
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
                        cursor: status.value === currentStatus ? 'default' : 'pointer',
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
          <button type="button" className="btn btn-ghost btn-sm" onClick={openEdit}>
            <Pencil size={13} /> Edit
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={handleDeleteClick}>
            <Trash2 size={13} /> Delete
          </button>
        </div>
      </div>

      <div className={styles.tabs}>
        {[
          { key: 'overview', label: 'Overview' },
          { key: 'notes', label: `Notes (${areaNotes.length})` },
          { key: 'projects', label: `Projects (${areaProjects.length})` },
          { key: 'tasks', label: `Tasks (${areaTasks.length})` },
          { key: 'connections', label: 'Connections' },
        ].map(({ key, label }) => (
          <button
            key={key}
            type="button"
            className={`${styles.tab} ${tab === key ? styles.tabActive : ''}`}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <div className={styles.content}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {area.description && (
              <div style={{
                padding: '14px 16px',
                background: 'var(--surface)',
                border: '1px solid var(--border)',
                borderRadius: '8px',
                fontSize: '12.5px',
                color: 'var(--text-secondary)',
                lineHeight: 1.6,
              }}>
                {area.description}
              </div>
            )}

            {areaSignals.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <span style={{ fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: '2px' }}>
                  Needs attention
                </span>
                {areaSignals.map((signal, i) => (
                  <div key={i} style={signalStyle}>
                    <span style={signalDot(signal.color)}>{signal.icon}</span>
                    <span>{signal.label}</span>
                  </div>
                ))}
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
              <div style={{ padding: '12px 14px', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '8px', textAlign: 'center' }}>
                <div style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text)' }}>{areaProjects.length}</div>
                <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginTop: '2px' }}>Projects</div>
              </div>
              <div style={{ padding: '12px 14px', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '8px', textAlign: 'center' }}>
                <div style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text)' }}>{areaNotes.length}</div>
                <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginTop: '2px' }}>Notes</div>
              </div>
              <div style={{ padding: '12px 14px', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '8px', textAlign: 'center' }}>
                <div style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text)' }}>{areaTasks.length}</div>
                <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginTop: '2px' }}>Tasks</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === 'notes' && (
        <div className={styles.content}>
          <div className={styles.contentHeader}>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => setShowAddNoteModal(true)}>
                <Plus size={13} /> Add Note
              </button>
              <button type="button" className="btn btn-primary btn-sm" onClick={() => setShowNoteEditor(true)}>
                <Plus size={13} /> New Note
              </button>
            </div>
          </div>

          {/* Add existing note modal */}
          {showAddNoteModal && (
            <div style={{
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: '14px',
              padding: '14px',
              display: 'grid',
              gap: '10px',
              marginBottom: '12px',
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
                  <option key={n.id} value={n.id}>{n.title || (n.raw_text || '').slice(0, 60)}</option>
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

          {areaNotes.length === 0 ? (
            <p className={styles.empty}>No notes in this area yet.</p>
          ) : (
            <div className={styles.noteGrid}>
              {areaNotes.map(n => (
                <div key={n.id} style={{ position: 'relative' }}>
                  <NoteCard note={n} />
                  <button
                    type="button"
                    onClick={() => handleRemoveNoteFromArea(n.id)}
                    style={{
                      position: 'absolute',
                      top: '8px',
                      right: '8px',
                      background: 'var(--surface)',
                      border: '1px solid var(--border-faint)',
                      borderRadius: '6px',
                      color: 'var(--text-muted)',
                      cursor: 'pointer',
                      padding: '4px 6px',
                      display: 'flex',
                      alignItems: 'center',
                      fontSize: '10px',
                      zIndex: 1,
                    }}
                    title="Remove note from area"
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === 'projects' && (
        <div className={styles.content}>
          <div className={styles.contentHeader}>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => setShowAddProjectModal(true)}>
                <Plus size={13} /> Add Project
              </button>
            </div>
          </div>

          {/* Add existing project modal */}
          {showAddProjectModal && (
            <div style={{
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: '14px',
              padding: '14px',
              display: 'grid',
              gap: '10px',
              marginBottom: '12px',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text)' }}>Link existing project</span>
                <button
                  type="button"
                  onClick={() => { setShowAddProjectModal(false); setProjectPick(''); setProjectSearchQuery(''); }}
                  style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '2px' }}
                >
                  <X size={14} />
                </button>
              </div>
              <input
                type="search"
                placeholder="Filter projects…"
                value={projectSearchQuery}
                onChange={e => setProjectSearchQuery(e.target.value)}
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
                value={projectPick}
                onChange={e => setProjectPick(e.target.value)}
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
                <option value="">Select a project…</option>
                {projectCandidates.map(p => (
                  <option key={p.id} value={p.id}>{p.title}</option>
                ))}
              </select>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={handleAddProjectLink}
                disabled={!projectPick || projectLinkBusy}
                style={{ alignSelf: 'end' }}
              >
                {projectLinkBusy ? <Loader2 size={13} className="spin" /> : <CheckCircle size={13} />}
                Add link
              </button>
            </div>
          )}

          {/* Quick-add new project */}
          <form onSubmit={handleCreateProject} style={{ display: 'flex', gap: '6px', marginBottom: '12px' }}>
            <input
              type="text"
              placeholder="New project…"
              value={newProjectTitle}
              onChange={e => setNewProjectTitle(e.target.value)}
              style={{
                flex: 1,
                padding: '7px 9px',
                fontSize: '12px',
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
              disabled={!newProjectTitle.trim()}
              style={{ padding: '6px 10px', fontSize: '11px' }}
            >
              Create
            </button>
          </form>

          {areaProjects.length === 0 ? (
            <p className={styles.empty}>No projects linked to this area yet.</p>
          ) : (
            <div className={styles.taskList}>
              {areaProjects.map(p => (
                <div
                  key={p.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '12px',
                    padding: '10px 14px',
                    background: 'var(--surface)',
                    border: '1px solid var(--border-faint)',
                    borderRadius: '8px',
                  }}
                >
                  <Link
                    to={`/projects/${p.id}`}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      textDecoration: 'none',
                      color: 'inherit',
                      flex: 1,
                      minWidth: 0,
                    }}
                  >
                    <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: p.color || 'var(--accent)', flexShrink: 0 }} />
                    <span style={{ fontSize: '13px', fontWeight: 500 }}>{p.title}</span>
                  </Link>
                  <button
                    type="button"
                    onClick={() => handleRemoveProjectFromArea(p.id)}
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
                      flexShrink: 0,
                    }}
                    title="Remove project from area"
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === 'tasks' && (
        <div className={styles.content}>
          {areaTasks.length === 0 ? (
            <p className={styles.empty}>No tasks linked to this area yet.</p>
          ) : (
            <div className={styles.taskList}>
              {areaTasks.map(t => (
                <div key={t.id} className={styles.taskRow}>
                  <TaskCheckboxRow task={t} className={styles.taskRowCheckbox} />
                  {t.status && <span className={styles.taskStatus}>{t.status}</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === 'connections' && (
        <div style={{ display: 'grid', gap: '10px' }}>
          <LinkToEntity entityId={id} entityType="area" onLinkCreated={() => setConnRefreshKey(k => k + 1)} />
          <div style={{ ...surfaceCardStyle, padding: '14px' }}>
            <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Linked Context
            </div>
            <LinkedContextPanel
              entityId={id}
              linksOut={linksOut}
              linksIn={linksIn}
              loading={linksLoading}
            />
          </div>
        </div>
      )}

      {showNoteEditor && (
        <NoteEditor
          initialData={{ area_id: id, bucket: 'AREAS' }}
          onClose={() => setShowNoteEditor(false)}
          onSaved={() => setShowNoteEditor(false)}
        />
      )}

      {showEditModal && (
        <Modal isOpen onClose={closeEdit} title="Edit Area" footer={
          <><button type="button" className="btn btn-ghost" onClick={closeEdit}>Cancel</button>
          <button type="button" className="btn btn-primary" onClick={handleUpdate} disabled={!name.trim()}>Save</button></>
        }>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            <div>
              <label className={styles.label}>Name</label>
              <input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Agent Security" autoFocus />
            </div>
            <div>
              <label className={styles.label}>Description</label>
              <textarea value={description} onChange={e => setDescription(e.target.value)} rows={3} placeholder="What does this area cover?" />
            </div>
            <div>
              <label className={styles.label}>Color</label>
              <input value={color} onChange={e => setColor(e.target.value)} placeholder="e.g. #7c6aff" />
            </div>
          </div>
        </Modal>
      )}

      {/* Archive confirmation modal */}
      <Modal isOpen={showArchiveModal} onClose={() => !archiving && setShowArchiveModal(false)} title="Archive Area" footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={() => setShowArchiveModal(false)} disabled={archiving}>Cancel</button>
          <button type="button" className="btn btn-primary" onClick={handleArchiveConfirm} disabled={archiving} style={{ background: 'var(--yellow)', color: 'var(--text)' }}>
            {archiving ? <><Loader2 size={13} className="spin" /> Archiving...</> : 'Confirm Archive'}
          </button>
        </>
      }>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--yellow)' }}>
            <AlertTriangle size={16} />
            <span style={{ fontSize: '13px', fontWeight: 600 }}>This will archive the area</span>
          </div>
          {areaProjects.length > 0 && (
            <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary)' }}>
              {areaProjects.length} project(s) will be detached from this area. They will remain active but no longer linked.
            </p>
          )}
          <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-muted)' }}>
            You can restore the area later by changing its status back to Active.
          </p>
        </div>
      </Modal>

      <DeleteConfirmModal
        isOpen={showDeleteModal}
        onClose={() => { setShowDeleteModal(false); setDeletePreview(null); }}
        onConfirm={handleDeleteConfirm}
        entityTitle={area.title}
        entityType="area"
        preview={deletePreview}
      />
    </div>
  );
}
