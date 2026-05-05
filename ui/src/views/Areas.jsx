import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, ChevronRight } from 'lucide-react';
import Modal from '../components/ui/Modal';
import useStore from '../stores/useStore';
import EmptyState from '../components/ui/EmptyState';
import styles from './Areas.module.css';

export default function Areas() {
  const { areas, notes, createArea } = useStore();
  const [showModal, setShowModal] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    await createArea({ name: name.trim(), description });
    setName(''); setDescription(''); setShowModal(false);
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
              <Link key={a.id} to={`/areas/${a.id}`} className={styles.card}>
                <div className={styles.cardHeader}>
                  <span className={styles.dot} style={{ background: a.color || 'var(--accent-blue)' }} />
                  <span className={styles.name}>{a.name}</span>
                  <ChevronRight size={14} className={styles.arrow} />
                </div>
                {a.description && <p className={styles.desc}>{a.description}</p>}
                <div className={styles.meta}>{areaNotes.length} notes</div>
              </Link>
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
          </div>
        </Modal>
      )}
    </div>
  );
}
