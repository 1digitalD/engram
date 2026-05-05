import React, { useState } from 'react';
import { Plus, CheckCircle, Circle, Clock } from 'lucide-react';
import Modal from '../components/ui/Modal';
import useStore from '../stores/useStore';
import EmptyState from '../components/ui/EmptyState';
import styles from './Tasks.module.css';

const COLUMNS = [
  { key: 'inbox',     label: 'Inbox',    icon: Circle },
  { key: 'open',      label: 'Open',     icon: Circle },
  { key: 'in-progress', label: 'In Progress', icon: Clock },
  { key: 'done',      label: 'Done',     icon: CheckCircle },
];

export default function Tasks() {
  const { tasks, projects, createTask, updateTask, deleteTask } = useStore();
  const [showModal, setShowModal] = useState(false);
  const [content, setContent] = useState('');
  const [status, setStatus] = useState('open');
  const [projectId, setProjectId] = useState('');

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!content.trim()) return;
    await createTask({ content: content.trim(), status, ...(projectId && { project_id: projectId }) });
    setContent(''); setStatus('open'); setProjectId(''); setShowModal(false);
  };

  const handleStatusChange = async (task, newStatus) => {
    await updateTask(task.id, { ...task, status: newStatus });
  };

  const getColumnTasks = (status) => tasks.filter(t => t.status === status);

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1>Tasks</h1>
          <p className={styles.count}>{tasks.filter(t => t.status !== 'done').length} pending</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowModal(true)}>
          <Plus size={15} /> New Task
        </button>
      </div>

      {tasks.length === 0 ? (
        <EmptyState
          type="tasks"
          title="No tasks yet"
          message="Break your work into actionable tasks and track them here."
          action={<button className="btn btn-primary" onClick={() => setShowModal(true)}><Plus size={14} /> Add task</button>}
        />
      ) : (
        <div className={styles.board}>
          {COLUMNS.map(col => {
            const colTasks = getColumnTasks(col.key);
            const Icon = col.icon;
            return (
              <div key={col.key} className={styles.column}>
                <div className={styles.columnHeader}>
                  <Icon size={14} />
                  <span>{col.label}</span>
                  <span className={styles.colCount}>{colTasks.length}</span>
                </div>
                <div className={styles.columnBody}>
                  {colTasks.map(task => {
                    const project = task.project_id ? projects.find(p => p.id === task.project_id) : null;
                    return (
                      <div key={task.id} className={styles.taskCard}>
                        <span className={styles.taskContent}>{task.content}</span>
                        {project && (
                          <span className={styles.taskProject}>{project.name}</span>
                        )}
                        <div className={styles.taskActions}>
                          {/* Move left/right */}
                          {col.key !== 'inbox' && col.key !== 'open' && (
                            <button
                              className={styles.moveBtn}
                              onClick={() => {
                                const colIndex = COLUMNS.findIndex(c => c.key === col.key);
                                const newCol = COLUMNS[colIndex - 1];
                                handleStatusChange(task, newCol.key);
                              }}
                              title="Move back"
                            >←</button>
                          )}
                          <button
                            className={`${styles.moveBtn} ${styles.doneBtn}`}
                            onClick={() => handleStatusChange(task, 'done')}
                            title="Mark done"
                          >✓</button>
                          <button
                            className={styles.moveBtn}
                            onClick={() => deleteTask(task.id)}
                            title="Delete"
                          >×</button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {showModal && (
        <Modal isOpen onClose={() => setShowModal(false)} title="New Task" footer={
          <><button className="btn btn-ghost" onClick={() => setShowModal(false)}>Cancel</button>
          <button className="btn btn-primary" onClick={handleCreate} disabled={!content.trim()}>Add</button></>
        }>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            <div>
              <label className={styles.label}>Task</label>
              <textarea value={content} onChange={e => setContent(e.target.value)} placeholder="What needs to be done?" rows={3} autoFocus />
            </div>
            <div>
              <label className={styles.label}>Status</label>
              <select value={status} onChange={e => setStatus(e.target.value)} className={styles.select}>
                {COLUMNS.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}
              </select>
            </div>
            <div>
              <label className={styles.label}>Project (optional)</label>
              <select value={projectId} onChange={e => setProjectId(e.target.value)} className={styles.select}>
                <option value="">— None —</option>
                {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
