import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, ChevronRight, Pencil, Trash2, Loader2, Sparkles } from 'lucide-react';
import Modal from '../components/ui/Modal';
import useStore from '../stores/useStore';
import EmptyState from '../components/ui/EmptyState';
import styles from './Areas.module.css';

export default function Areas() {
  const { areas, notes, createArea, updateArea, deleteArea } = useStore();
  const [showModal, setShowModal] = useState(false);
  const [editingArea, setEditingArea] = useState(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [color, setColor] = useState('');

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    await createArea({ title: name.trim(), description: description.trim() || undefined, color: color.trim() || undefined });
    setName(''); setDescription(''); setColor(''); setShowModal(false);
  };

  const openEdit = (area) => {
    setEditingArea(area);
    setName(area.title || '');
    setDescription(area.description || '');
    setColor(area.color || '');
  };

  const closeEdit = () => {
    setEditingArea(null);
    setName('');
    setDescription('');
    setColor('');
  };

  const handleUpdate = async (e) => {
    e.preventDefault();
    if (!editingArea || !name.trim()) return;
    await updateArea(editingArea.id, {
      title: name.trim(),
      description: description.trim() || null,
      color: color.trim() || null,
    });
    closeEdit();
  };

  const handleDelete = async (area) => {
    if (!window.confirm(`Delete area "${area.title}"? This cannot be undone.`)) return;
    await deleteArea(area.id);
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1>Areas</h1>
          <p className={styles.count}>{areas.length} areas</p>
          <p className={styles.hint}>Areas are ongoing responsibilities — not deliverables, but domains you maintain.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowModal(true)}>
          <Plus size={15} /> New Area
        </button>
      </div>

      {areas.length === 0 ? (
        <EmptyState
          type="projects"
          title="No areas yet"
          message="Areas represent ongoing responsibilities — e.g. Agent Security, Technical Writing, Team Health."
          action={<button className="btn btn-primary" onClick={() => setShowModal(true)}><Plus size={14} /> Create area</button>}
        />
      ) : (
        <div className={styles.grid}>
          {areas.map(a => {
            const areaNotes = notes.filter(n => n.area_id === a.id);
            return (
              <div key={a.id} className={styles.card}>
                <Link to={`/areas/${a.id}`} className={styles.cardLink}>
                  <div className={styles.cardHeader}>
                    <span className={styles.dot} style={{ background: a.color || 'var(--accent-blue)' }} />
                    <span className={styles.name}>{a.title}</span>
                    {a.ai_status === 'processing' && (
                      <span className={styles.aiProcessing}><Loader2 size={10} className="spin" /></span>
                    )}
                    {a.ai_status === 'done' && a._ai_meta?.bucket && (
                      <span className={styles.aiClassification}>
                        <Sparkles size={10} />
                        {a._ai_meta.bucket}
                      </span>
                    )}
                    <ChevronRight size={14} className={styles.arrow} />
                  </div>
                  {a.description && <p className={styles.desc}>{a.description}</p>}
                  <div className={styles.meta}>{areaNotes.length} notes</div>
                </Link>
                <div className={styles.cardActions}>
                  <button className={styles.iconBtn} onClick={() => openEdit(a)} title="Edit area">
                    <Pencil size={13} /> Edit
                  </button>
                  <button className={`${styles.iconBtn} ${styles.dangerBtn}`} onClick={() => handleDelete(a)} title="Delete area">
                    <Trash2 size={13} /> Delete
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {showModal && (
        <Modal isOpen onClose={() => setShowModal(false)} title="New Area" footer={
          <><button className="btn btn-ghost" onClick={() => setShowModal(false)}>Cancel</button>
          <button className="btn btn-primary" onClick={handleCreate} disabled={!name.trim()}>Create</button></>
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

      {editingArea && (
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
