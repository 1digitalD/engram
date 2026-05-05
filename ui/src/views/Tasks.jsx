import React, { useState } from 'react';
import { Plus, CheckCircle, Circle, Clock } from 'lucide-react';
import Modal from '../components/ui/Modal';
import useStore from '../stores/useStore';
import EmptyState from '../components/ui/EmptyState';
import styles from './Tasks.module.css';

const COLUMNS = [
  { key: 'PENDING',     label: 'Pending',     icon: Circle },
  { key: 'IN_PROGRESS', label: 'In Progress', icon: Clock },
  { key: 'DONE',        label: 'Done',        icon: CheckCircle },
];

export default function Tasks() {
  const { tasks, projects, createTask, updateTask, deleteTask } = useStore();
  const [showModal, setShowModal] = useState(false);
  const [title, setTitle] = useState('');
  const [status, setStatus] = useState('PENDING');
  const [projectId, setProjectId] = useState('');
  const [priority, setPriority] = useState('MEDIUM');

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!title.trim()) return;
    await createTask({
      title: title.trim(),
      status,
      priority,
      ...(projectId && { project_id: projectId }),
    });
    setTitle(''); setStatus('PENDING'); setProjectId(''); setPriority('MEDIUM'); setShowModal(false);
  };

  const handleStatusChange = async (task, newStatus) => {
    await updateTask(task.id, { status: newStatus });
  };

  const getColumnTasks = (s) => tasks.filter(t => t.status === s);
  const pendingCount = tasks.filter(t => t.status !== 'DONE' && t.status !== 'CANCELLED').length;

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1>Tasks</h1>
          <p className={styles.count}>{pendingCount} pending</p>
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
                  {colTasks.length === 0 && (
                    <p className={styles.emptyCol}>
                      {col.key === 'PENDING' ? 'No pending tasks' :
                       col.key === 'IN_PROGRESS' ? 'Nothing in progress' :
                       'No completed tasks'}
                    </p>
                  )}
                  {colTasks.map(task => {
                    const project = task.project_id ? projects.find(p => p.id === task.project_id) : null;
                    const due = task.due_date ? new Date(task.due_date).toLocaleDateString() : null;
                    return (
                      <div key={task.id} className={styles.taskCard}>
                        <span className={styles.taskContent}>{task.title}</span>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
                          {project && (
                            <span className={styles.taskProject}>{project.name}</span>
                          )}
                          {due && (
                            <span className={styles.taskProject}>📅 {due}</span>
                          )}
                          {task.priority && task.priority !== 'MEDIUM' && (
                            <span className={styles.taskProject}>{task.priority}</span>
                          )}
                        </div>
                        <div className={styles.taskActions}>
                          {col.key !== 'PENDING' && (
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
                          {col.key !== 'DONE' && (
                            <button
                              className={`${styles.moveBtn} ${styles.doneBtn}`}
                              onClick={() => handleStatusChange(task, 'DONE')}
                              title="Mark done"
                            >✓</button>
                          )}
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
          <button className="btn btn-primary" onClick={handleCreate} disabled={!title.trim()}>Add</button></>
        }>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            <div>
              <label className={styles.label}>Task</label>
              <textarea value={title} onChange={e => setTitle(e.target.value)} placeholder="What needs to be done?" rows={3} autoFocus />
            </div>
            <div>
              <label className={styles.label}>Status</label>
              <select value={status} onChange={e => setStatus(e.target.value)} className={styles.select}>
                {COLUMNS.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}
              </select>
            </div>
            <div>
              <label className={styles.label}>Priority</label>
              <select value={priority} onChange={e => setPriority(e.target.value)} className={styles.select}>
                <option value="LOW">Low</option>
                <option value="MEDIUM">Medium</option>
                <option value="HIGH">High</option>
                <option value="URGENT">Urgent</option>
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
