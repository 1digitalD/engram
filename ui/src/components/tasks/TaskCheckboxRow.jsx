import React from 'react';
import { CheckCircle, Circle } from 'lucide-react';
import useStore from '../../stores/useStore';
import styles from './TaskCheckboxRow.module.css';

export default function TaskCheckboxRow({ task, className = '', children }) {
  const { updateTask, addToast } = useStore();

  const toggle = async () => {
    try {
      const next = task.status === 'done' ? 'pending' : 'done';
      await updateTask(task.id, { status: next });
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Failed to update task' });
    }
  };

  return (
    <div className={`${styles.row} ${className}`}>
      <button
        type="button"
        className={styles.check}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          toggle();
        }}
        aria-label={task.status === 'done' ? 'Mark task pending' : 'Mark task done'}
      >
        {task.status === 'done' ? <CheckCircle size={16} /> : <Circle size={16} />}
      </button>
      <span className={`${styles.title} ${task.status === 'done' ? styles.done : ''}`}>
        {task.title}
      </span>
      {children}
    </div>
  );
}
