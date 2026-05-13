import React, { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, Plus, Pencil, Trash2, ChevronDown, AlertTriangle, Loader2 } from 'lucide-react';
import Modal from '../components/ui/Modal';
import useStore from '../stores/useStore';
import NoteCard from '../components/notes/NoteCard';
import NoteEditor from '../components/notes/NoteEditor';
import TaskCheckboxRow from '../components/tasks/TaskCheckboxRow';
import ConnectionsPanel from '../components/ConnectionsPanel/ConnectionsPanel';
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

export default function AreaFocus() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { areas, notes, projects, tasks, updateArea, deleteArea, getDeletePreview } = useStore();
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
  if (!area) return (
    <div className={styles.page}>
      <p>Area not found.</p>
      <button className="btn btn-ghost" onClick={() => navigate('/areas')}>
        <ArrowLeft size={14} /> Back to Areas
      </button>
    </div>
  );

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
      } catch {
        // Status change failed
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

      {tab === 'notes' && (
        <div className={styles.content}>
          <div className={styles.contentHeader}>
            <button type="button" className="btn btn-primary btn-sm" onClick={() => setShowNoteEditor(true)}>
              <Plus size={13} /> Add Note
            </button>
          </div>
          {areaNotes.length === 0 ? (
            <p className={styles.empty}>No notes in this area yet.</p>
          ) : (
            <div className={styles.noteGrid}>
              {areaNotes.map(n => <NoteCard key={n.id} note={n} />)}
            </div>
          )}
        </div>
      )}

      {tab === 'projects' && (
        <div className={styles.content}>
          {areaProjects.length === 0 ? (
            <p className={styles.empty}>No projects linked to this area yet.</p>
          ) : (
            <div className={styles.taskList}>
              {areaProjects.map(p => (
                <Link
                  key={p.id}
                  to={`/projects/${p.id}`}
                  className={styles.areaProjectRow}
                >
                  <span className={styles.projectDot} style={{ background: p.color || 'var(--accent)' }} />
                  <span>{p.title}</span>
                </Link>
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
        <div className={styles.content}>
          <ConnectionsPanel entityId={id} />
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
