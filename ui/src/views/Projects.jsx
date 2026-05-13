import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Search } from 'lucide-react';
import Modal from '../components/ui/Modal';
import useStore from '../stores/useStore';
import EmptyState from '../components/ui/EmptyState';
import styles from './Projects.module.css';

export default function Projects() {
  const { projects, notes, createProject } = useStore();
  const [showModal, setShowModal] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [filter, setFilter] = useState('');

  const active = projects.filter(p => !p.is_archived);
  const archived = projects.filter(p => p.is_archived);

  const filteredActive = active.filter(p =>
    p.title.toLowerCase().includes(filter.toLowerCase()) ||
    (p.description || '').toLowerCase().includes(filter.toLowerCase())
  );

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    await createProject({ name: name.trim(), description, status: 'active' });
    setName('');
    setDescription('');
    setShowModal(false);
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1>Projects</h1>
          <p className={styles.count}>{active.length} active</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowModal(true)}>
          <Plus size={15} /> New Project
        </button>
      </div>

      {active.length === 0 ? (
        <EmptyState
          type="projects"
          title="No projects yet"
          message="Projects are your active work — things you're building, launching, or maintaining."
          action={<button className="btn btn-primary" onClick={() => setShowModal(true)}><Plus size={14} /> Create project</button>}
        />
      ) : (
        <>
          <div className={styles.filterRow}>
            <Search size={14} className={styles.filterIcon} />
            <input
              className={styles.filterInput}
              type="text"
              placeholder="Filter projects..."
              value={filter}
              onChange={e => setFilter(e.target.value)}
            />
          </div>

          <div className={styles.list}>
            {filteredActive.map(p => {
              const projectNotes = notes.filter(n => n.project_id === p.id);
              return (
                <Link key={p.id} to={`/projects/${p.id}`} className={styles.row}>
                  <span className={styles.dot} style={{ background: p.color || 'var(--accent)' }} />
                  <span className={styles.rowTitle}>{p.title}</span>
                  {p.description && <span className={styles.rowDesc}>{p.description}</span>}
                  <span className={styles.rowMeta}>{projectNotes.length} notes</span>
                  {p.priority && <span className={styles.priority}>{p.priority}</span>}
                </Link>
              );
            })}
          </div>
        </>
      )}

      {archived.length > 0 && (
        <>
          <h3 className={styles.archiveLabel}>Archived</h3>
          <div className={styles.list}>
            {archived.map(p => (
              <Link key={p.id} to={`/projects/${p.id}`} className={`${styles.row} ${styles.rowArchived}`}>
                <span className={styles.rowTitle}>{p.title}</span>
                <span className={styles.archivedBadge}>Archived</span>
              </Link>
            ))}
          </div>
        </>
      )}

      {showModal && (
        <Modal
          isOpen
          onClose={() => setShowModal(false)}
          title="New Project"
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setShowModal(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleCreate} disabled={!name.trim()}>Create</button>
            </>
          }
        >
          <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            <div>
              <label className={styles.label}>Name</label>
              <input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Agent Toolkit TypeScript" autoFocus />
            </div>
            <div>
              <label className={styles.label}>Description</label>
              <textarea value={description} onChange={e => setDescription(e.target.value)} placeholder="What is this project about?" rows={3} />
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}