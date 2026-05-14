import React, { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, Edit2, Trash2, Loader2, CheckCircle, Circle, Calendar, FolderOpen, FileText } from 'lucide-react';
import useStore from '../stores/useStore';
import ConnectionsPanel from '../components/ConnectionsPanel/ConnectionsPanel';
import DeleteConfirmModal from '../components/DeleteConfirmModal';
import styles from './TaskDetail.module.css';

function formatDate(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatDateTime(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

const PRIORITY_COLORS = {
  URGENT: 'var(--danger)',
  HIGH: 'var(--danger)',
  MEDIUM: 'var(--warning)',
  LOW: 'var(--text-muted)',
};

const STATUS_BADGE = {
  pending: { label: 'Pending', color: 'var(--text-muted)' },
  in_progress: { label: 'In Progress', color: 'var(--yellow)' },
  done: { label: 'Done', color: 'var(--green)' },
};

export default function TaskDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const {
    tasks, projects, notes, loading,
    updateTask, deleteTask, getDeletePreview, addToast,
  } = useStore();

  const [isEditing, setIsEditing] = useState(false);
  const [draftTitle, setDraftTitle] = useState('');
  const [saving, setSaving] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deletePreview, setDeletePreview] = useState(null);

  const task = tasks.find(t => t.id === id);
  const project = task?.project_id ? projects.find(p => p.id === task.project_id) : null;
  const note = task?.note_id ? notes.find(n => n.id === task.note_id) : null;

  if (!task) {
    if (loading) {
      return (
        <div className={styles.page}>
          <Loader2 size={20} className="spin" style={{ display: 'block', margin: '40px auto', color: 'var(--text-muted)' }} />
        </div>
      );
    }
    return (
      <div className={styles.page}>
        <p className={styles.notFound}>Task not found.</p>
        <button className="btn btn-ghost" onClick={() => navigate(-1)}>
          <ArrowLeft size={14} /> Go back
        </button>
      </div>
    );
  }

  const statusConfig = STATUS_BADGE[task.status] || STATUS_BADGE.pending;
  const priorityColor = PRIORITY_COLORS[task.priority] || 'var(--text-muted)';

  const startEditing = () => {
    setDraftTitle(task.title || '');
    setIsEditing(true);
  };

  const cancelEditing = () => {
    setIsEditing(false);
  };

  const handleSaveTitle = async () => {
    const title = draftTitle.trim();
    if (!title || saving) return;
    setSaving(true);
    try {
      await updateTask(task.id, { title });
      setIsEditing(false);
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Failed to update title' });
    } finally {
      setSaving(false);
    }
  };

  const handleToggleDone = async () => {
    try {
      const next = task.status === 'done' ? 'pending' : 'done';
      await updateTask(task.id, { status: next });
      addToast({ type: 'success', message: next === 'done' ? 'Task completed' : 'Task reopened' });
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Failed to update task' });
    }
  };

  const handleDeleteClick = async () => {
    try {
      const preview = await getDeletePreview(task.id);
      setDeletePreview(preview);
      setShowDeleteModal(true);
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Failed to load delete preview' });
    }
  };

  const handleDeleteConfirm = async (cascadeIds) => {
    await deleteTask(task.id, cascadeIds);
    setShowDeleteModal(false);
    setDeletePreview(null);
    navigate('/tasks');
  };

  return (
    <div className={styles.page}>
      <nav className={styles.breadcrumb} aria-label="Breadcrumb">
        <Link to="/tasks">Tasks</Link>
        <span className={styles.breadcrumbSep}>/</span>
        <span className={styles.breadcrumbCurrent}>{task.title}</span>
      </nav>

      <button type="button" className={styles.backBtn} onClick={() => navigate(-1)}>
        <ArrowLeft size={14} /> Back
      </button>

      <div className={styles.shell}>
        <div className={styles.mainContent}>
          <header className={styles.header}>
            <div className={styles.headerTop}>
              <div className={styles.headerIcon}>
                <CheckCircle size={22} strokeWidth={1.5} />
              </div>
              {isEditing ? (
                <div className={styles.titleEditGroup}>
                  <input
                    className={styles.titleInput}
                    value={draftTitle}
                    onChange={e => setDraftTitle(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter') handleSaveTitle();
                      if (e.key === 'Escape') cancelEditing();
                    }}
                    autoFocus
                  />
                  <div className={styles.titleEditActions}>
                    <button className="btn btn-primary btn-sm" onClick={handleSaveTitle} disabled={saving || !draftTitle.trim()}>
                      {saving ? <Loader2 size={13} className="spin" /> : 'Save'}
                    </button>
                    <button className="btn btn-ghost btn-sm" onClick={cancelEditing} disabled={saving}>
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <h1 className={styles.title}>{task.title}</h1>
              )}
            </div>
            <div className={styles.metaRow}>
              <span className={styles.entityTypeLabel}>Task</span>
              <span
                className={styles.statusBadge}
                style={{
                  '--status-color': statusConfig.color,
                  background: `color-mix(in srgb, ${statusConfig.color} 15%, transparent)`,
                  color: statusConfig.color,
                  border: `1px solid color-mix(in srgb, ${statusConfig.color} 30%, transparent)`,
                }}
              >
                <span className={styles.statusDot} style={{ background: statusConfig.color }} />
                {statusConfig.label}
              </span>
              <div className={styles.metaActions}>
                {!isEditing && (
                  <button className="btn btn-ghost btn-sm" onClick={startEditing}>
                    <Edit2 size={13} /> Edit
                  </button>
                )}
                <button className="btn btn-ghost btn-sm" onClick={handleToggleDone}>
                  {task.status === 'done' ? <Circle size={13} /> : <CheckCircle size={13} />}
                  {task.status === 'done' ? 'Undo' : 'Done'}
                </button>
                <button className="btn btn-ghost btn-sm" onClick={handleDeleteClick}>
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          </header>

          {task.description && (
            <div className={styles.description}>{task.description}</div>
          )}

          <section className={styles.metadataSection}>
            <h2 className={styles.sectionTitle}>
              <FileText size={14} /> Details
            </h2>
            <div className={styles.metadataGrid}>
              <div className={styles.metaRow}>
                <span className={styles.metaLabel}>Status</span>
                <span className={styles.metaItem}>
                  <span className={styles.statusDot} style={{ background: statusConfig.color }} />
                  {statusConfig.label}
                </span>
              </div>
              <div className={styles.metaRow}>
                <span className={styles.metaLabel}>Priority</span>
                <span className={styles.metaItem}>
                  <span className={styles.priorityDot} style={{ background: priorityColor }} />
                  {task.priority || 'NONE'}
                </span>
              </div>
              {task.due_date && (
                <div className={styles.metaRow}>
                  <span className={styles.metaLabel}>Due date</span>
                  <span className={styles.metaItem}>
                    <Calendar size={12} /> {formatDate(task.due_date)}
                  </span>
                </div>
              )}
              {project && (
                <div className={styles.metaRow}>
                  <span className={styles.metaLabel}>Project</span>
                  <span className={styles.metaItem}>
                    <Link to={`/projects/${project.id}`} className={styles.metaLink}>
                      <FolderOpen size={12} />
                      {project.title}
                    </Link>
                  </span>
                </div>
              )}
              {note && (
                <div className={styles.metaRow}>
                  <span className={styles.metaLabel}>Note</span>
                  <span className={styles.metaItem}>
                    <Link to={`/notes/${note.id}`} className={styles.metaLink}>
                      <FileText size={12} />
                      {note.title || 'Untitled'}
                    </Link>
                  </span>
                </div>
              )}
              <div className={styles.metaRow}>
                <span className={styles.metaLabel}>Created</span>
                <span className={styles.metaItem}>{formatDateTime(task.created_at)}</span>
              </div>
              <div className={styles.metaRow}>
                <span className={styles.metaLabel}>Modified</span>
                <span className={styles.metaItem}>{formatDateTime(task.updated_at || task.created_at)}</span>
              </div>
            </div>
          </section>

          <section className={styles.connectionsSection}>
            <ConnectionsPanel entityId={id} />
          </section>
        </div>
      </div>

      <DeleteConfirmModal
        isOpen={showDeleteModal}
        onClose={() => { setShowDeleteModal(false); setDeletePreview(null); }}
        onConfirm={handleDeleteConfirm}
        entityTitle={task.title}
        entityType="task"
        preview={deletePreview}
      />
    </div>
  );
}
