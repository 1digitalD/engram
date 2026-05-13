import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, FolderOpen, ChevronRight, Loader2, Sparkles } from 'lucide-react';
import Modal from '../components/ui/Modal';
import useStore from '../stores/useStore';
import EmptyState from '../components/ui/EmptyState';
import styles from './Projects.module.css';

export default function Projects() {
  const { projects, notes, createProject } = useStore();
  const [showModal, setShowModal] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const active = projects.filter(p => !p.is_archived);
  const archived = projects.filter(p => p.is_archived);

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
        <div className={styles.grid}>
          {active.map(p => {
            const projectNotes = notes.filter(n => n.project_id === p.id);
            return (
              <Link key={p.id} to={`/projects/${p.id}`} className={styles.card}>
                <div className={styles.cardHeader}>
                  <span className={styles.dot} style={{ background: p.color || 'var(--accent)' }} />
                  <span className={styles.name}>{p.title}</span>
                  {p.ai_status === 'processing' && (
                    <span className={styles.aiProcessing}><Loader2 size={10} className="spin" /></span>
                  )}
                  {p.ai_status === 'done' && p._ai_meta?.bucket && (
                    <span className={styles.aiClassification}>
                      <Sparkles size={10} />
                      {p._ai_meta.bucket}
                    </span>
                  )}
                  <ChevronRight size={14} className={styles.arrow} />
                </div>
                {p.description && (
                  <p className={styles.desc}>{p.description}</p>
                )}
                <div className={styles.cardMeta}>
                  <span>{projectNotes.length} notes</span>
                  {p.priority && <span className={styles.priority}>{p.priority}</span>}
                </div>
              </Link>
            );
          })}
        </div>
      )}

      {archived.length > 0 && (
        <>
          <h3 className={styles.archiveLabel}>Archived</h3>
          <div className={styles.grid}>
            {archived.map(p => (
              <Link key={p.id} to={`/projects/${p.id}`} className={`${styles.card} ${styles.cardArchived}`}>
                <span className={styles.name}>{p.title}</span>
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
