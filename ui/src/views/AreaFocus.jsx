import React, { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, Plus, Pencil, Trash2 } from 'lucide-react';
import Modal from '../components/ui/Modal';
import useStore from '../stores/useStore';
import NoteCard from '../components/notes/NoteCard';
import NoteEditor from '../components/notes/NoteEditor';
import TaskCheckboxRow from '../components/tasks/TaskCheckboxRow';
import styles from './ProjectFocus.module.css';

export default function AreaFocus() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { areas, notes, projects, tasks, updateArea, deleteArea } = useStore();
  const [tab, setTab] = useState('notes');
  const [showNoteEditor, setShowNoteEditor] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [color, setColor] = useState('');

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
    setName(area.name || '');
    setDescription(area.description || '');
    setColor(area.color || '');
    setShowEditModal(true);
  };

  const closeEdit = () => setShowEditModal(false);

  const handleUpdate = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    await updateArea(area.id, {
      name: name.trim(),
      description: description.trim() || null,
      color: color.trim() || null,
    });
    closeEdit();
  };

  const handleDelete = async () => {
    if (!window.confirm(`Delete area "${area.name}"? This cannot be undone.`)) return;
    await deleteArea(area.id);
    navigate('/areas');
  };

  return (
    <div className={styles.page}>
      <nav className={styles.breadcrumb} aria-label="Breadcrumb">
        <Link to="/areas">Areas</Link>
        <span className={styles.breadcrumbSep}>/</span>
        <span className={styles.breadcrumbCurrent}>{area.name}</span>
      </nav>

      <button type="button" className={styles.backBtn} onClick={() => navigate('/areas')}>
        <ArrowLeft size={14} /> All Areas
      </button>

      <div className={styles.projectHeader}>
        <span className={styles.dot} style={{ background: area.color || 'var(--accent-blue)' }} />
        <h1>{area.name}</h1>
        {area.description && <p className={styles.desc}>{area.description}</p>}
        <div className={styles.headerActions}>
          <button type="button" className="btn btn-ghost btn-sm" onClick={openEdit}>
            <Pencil size={13} /> Edit
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={handleDelete}>
            <Trash2 size={13} /> Delete
          </button>
        </div>
      </div>

      <div className={styles.tabs}>
        {[
          { key: 'notes', label: `Notes (${areaNotes.length})` },
          { key: 'projects', label: `Projects (${areaProjects.length})` },
          { key: 'tasks', label: `Tasks (${areaTasks.length})` },
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
                  <span>{p.name}</span>
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
    </div>
  );
}
