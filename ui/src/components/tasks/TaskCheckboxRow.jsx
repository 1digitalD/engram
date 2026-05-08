import React from 'react';
import { CheckCircle, Circle } from 'lucide-react';
import useStore from '../../stores/useStore';
import styles from './TaskCheckboxRow.module.css';

export default function TaskCheckboxRow({ task, className = '', children }) {
  const { updateTask } = useStore();

  const toggle = async () => {
    const next = task.status === 'DONE' ? 'PENDING' : 'DONE';
    await updateTask(task.id, { status: next });
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
        aria-label={task.status === 'DONE' ? 'Mark task pending' : 'Mark task done'}
      >
        {task.status === 'DONE' ? <CheckCircle size={16} /> : <Circle size={16} />}
      </button>
      <span className={`${styles.title} ${task.status === 'DONE' ? styles.done : ''}`}>
        {task.title}
      </span>
      {children}
    </div>
  );
}
