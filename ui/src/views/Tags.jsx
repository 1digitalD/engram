import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Tag, Plus, X, Loader2 } from 'lucide-react';
import Modal from '../components/ui/Modal';
import useStore from '../stores/useStore';
import { tagsAPI } from '../api/engram';
import EmptyState from '../components/ui/EmptyState';
import styles from './Tags.module.css';

const TAG_COLORS = [
  '#7c6aff', '#06b6d4', '#10b981', '#f59e0b', '#ef4444',
  '#ec4899', '#8b5cf6', '#14b8a6', '#84cc16', '#f97316',
  '#6366f1', '#0ea5e9', '#22c55e', '#eab308', '#fb923c',
];

export default function Tags() {
  const navigate = useNavigate();
  const { tags, addToast } = useStore();
  const [showModal, setShowModal] = useState(false);
  const [name, setName] = useState('');
  const [color, setColor] = useState(TAG_COLORS[0]);
  const [creating, setCreating] = useState(false);

  const resetForm = () => {
    setName('');
    setColor(TAG_COLORS[0]);
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!name.trim() || creating) return;
    setCreating(true);
    try {
      await tagsAPI.create({ name: name.trim(), color });
      await useStore.getState().loadAll();
      setShowModal(false);
      resetForm();
      addToast({ type: 'success', message: 'Tag created' });
    } catch (e) {
      addToast({ type: 'error', message: e.message });
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1>Tags</h1>
          <p className={styles.count}>{tags.length} tags</p>
        </div>
        <button className={styles.addBtn} onClick={() => setShowModal(true)}>
          <Plus size={12} /> New Tag
        </button>
      </div>

      {tags.length === 0 ? (
        <EmptyState
          type="notes"
          title="No tags yet"
          message="Tags help you organize your notes across projects and areas."
          action={<button className="btn btn-primary" onClick={() => setShowModal(true)}><Plus size={14} /> Create your first tag</button>}
        />
      ) : (
        <div className={styles.grid}>
          {tags.map((tag) => (
            <div
              key={tag.id}
              className={styles.card}
              role="button"
              tabIndex={0}
              onClick={() => navigate(`/notes?tag=${encodeURIComponent(tag.name)}`)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  navigate(`/notes?tag=${encodeURIComponent(tag.name)}`);
                }
              }}
            >
              <span className={styles.dot} style={{ background: tag.color || '#7c6aff' }} />
              <span className={styles.name}>{tag.name}</span>
              <Tag size={14} className={styles.tagIcon} />
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <Modal
          isOpen
          onClose={() => { setShowModal(false); resetForm(); }}
          title="New Tag"
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => { setShowModal(false); resetForm(); }}>Cancel</button>
              <button className="btn btn-primary" onClick={handleCreate} disabled={!name.trim() || creating}>
                {creating ? <><Loader2 size={14} className="spin" /> Creating...</> : 'Create'}
              </button>
            </>
          }
        >
          <div className={styles.formFields}>
            <div>
              <label className={styles.label}>Name</label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Tag name"
                autoFocus
              />
            </div>
            <div>
              <label className={styles.label}>Color</label>
              <div className={styles.colorPicker}>
                {TAG_COLORS.map((c) => (
                  <button
                    key={c}
                    type="button"
                    className={`${styles.colorSwatch} ${color === c ? styles.colorSwatchActive : ''}`}
                    style={{ background: c }}
                    onClick={() => setColor(c)}
                    aria-label={`Select color ${c}`}
                  />
                ))}
              </div>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
