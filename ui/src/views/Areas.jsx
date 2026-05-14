import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Pencil, Trash2, Search, Loader2 } from 'lucide-react';
import Modal from '../components/ui/Modal';
import useStore from '../stores/useStore';
import EmptyState from '../components/ui/EmptyState';
import DeleteConfirmModal from '../components/DeleteConfirmModal';
import styles from './Areas.module.css';

export default function Areas() {
  const { areas, notes, createArea, updateArea, deleteArea, getDeletePreview, loading } = useStore();
  const [showModal, setShowModal] = useState(false);
  const [editingArea, setEditingArea] = useState(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [color, setColor] = useState('');
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deletePreview, setDeletePreview] = useState(null);
  const [pendingDeleteArea, setPendingDeleteArea] = useState(null);
  const [filter, setFilter] = useState('');

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

  const handleDeleteClick = async (area) => {
    try {
      const preview = await getDeletePreview(area.id);
      setDeletePreview(preview);
      setPendingDeleteArea(area);
      setShowDeleteModal(true);
    } catch (e) {
      useStore.getState().addToast({ type: 'error', message: e.message || 'Failed to load delete preview' });
    }
  };

  const handleDeleteConfirm = async (cascadeIds) => {
    if (!pendingDeleteArea) return;
    await deleteArea(pendingDeleteArea.id, cascadeIds);
    setShowDeleteModal(false);
    setDeletePreview(null);
    setPendingDeleteArea(null);
  };

  const filtered = areas.filter(a =>
    a.title.toLowerCase().includes(filter.toLowerCase()) ||
    (a.description || '').toLowerCase().includes(filter.toLowerCase())
  );

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

      {loading && areas.length === 0 ? (
        <Loader2 size={20} className="spin" style={{ display: 'block', margin: '40px auto', color: 'var(--text-muted)' }} />
      ) : areas.length === 0 ? (
        <EmptyState
          type="projects"
          title="No areas yet"
          message="Areas represent ongoing responsibilities — e.g. Agent Security, Technical Writing, Team Health."
          action={<button className="btn btn-primary" onClick={() => setShowModal(true)}><Plus size={14} /> Create area</button>}
        />
      ) : (
        <>
          <div className={styles.filterRow}>
            <Search size={14} className={styles.filterIcon} />
            <input
              className={styles.filterInput}
              type="text"
              placeholder="Filter areas..."
              value={filter}
              onChange={e => setFilter(e.target.value)}
            />
          </div>

          <div className={styles.list}>
            {filtered.map(a => {
              const areaNotes = notes.filter(n => n.area_id === a.id);
              return (
                <div key={a.id} className={styles.row}>
                  <Link to={`/areas/${a.id}`} className={styles.rowLink}>
                    <span className={styles.dot} style={{ background: a.color || 'var(--accent-blue)' }} />
                    <span className={styles.rowTitle}>{a.title}</span>
                    {a.description && <span className={styles.rowDesc}>{a.description}</span>}
                    <span className={styles.rowMeta}>{areaNotes.length} notes</span>
                  </Link>
                  <div className={styles.rowActions}>
                    <button className={styles.iconBtn} onClick={() => openEdit(a)} title="Edit area">
                      <Pencil size={13} />
                    </button>
                    <button className={`${styles.iconBtn} ${styles.dangerBtn}`} onClick={() => handleDeleteClick(a)} title="Delete area">
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </>
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

      <DeleteConfirmModal
        isOpen={showDeleteModal}
        onClose={() => { setShowDeleteModal(false); setDeletePreview(null); setPendingDeleteArea(null); }}
        onConfirm={handleDeleteConfirm}
        entityTitle={pendingDeleteArea?.title || 'Area'}
        entityType="area"
        preview={deletePreview}
      />
    </div>
  );
}