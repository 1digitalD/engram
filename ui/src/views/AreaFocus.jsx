import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Plus, Pencil, Trash2 } from 'lucide-react';
import Modal from '../components/ui/Modal';
import useStore from '../stores/useStore';
import NoteCard from '../components/notes/NoteCard';
import NoteEditor from '../components/notes/NoteEditor';
import styles from './ProjectFocus.module.css'; // reuse ProjectFocus styles

export default function AreaFocus() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { areas, notes, updateArea, deleteArea } = useStore();
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
      <button className={styles.backBtn} onClick={() => navigate('/areas')}>
        <ArrowLeft size={14} /> All Areas
      </button>

      <div className={styles.projectHeader}>
        <span className={styles.dot} style={{ background: area.color || 'var(--accent-blue)' }} />
        <h1>{area.name}</h1>
        {area.description && <p className={styles.desc}>{area.description}</p>}
        <div className={styles.headerActions}>
          <button className="btn btn-ghost btn-sm" onClick={openEdit}>
            <Pencil size={13} /> Edit
          </button>
          <button className="btn btn-ghost btn-sm" onClick={handleDelete}>
            <Trash2 size={13} /> Delete
          </button>
        </div>
      </div>

      <div className={styles.content}>
        <div className={styles.contentHeader}>
          <button className="btn btn-primary btn-sm" onClick={() => setShowNoteEditor(true)}>
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

      {showNoteEditor && (
        <NoteEditor
          initialData={{ area_id: id, bucket: 'AREAS' }}
          onClose={() => setShowNoteEditor(false)}
          onSaved={() => setShowNoteEditor(false)}
        />
      )}

      {showEditModal && (
        <Modal isOpen onClose={closeEdit} title="Edit Area" footer={
          <><button className="btn btn-ghost" onClick={closeEdit}>Cancel</button>
          <button className="btn btn-primary" onClick={handleUpdate} disabled={!name.trim()}>Save</button></>
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
