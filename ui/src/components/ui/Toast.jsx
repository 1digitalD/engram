import React from 'react';
import { CheckCircle, XCircle, AlertCircle, Info, X } from 'lucide-react';
import styles from './Toast.module.css';

const ICONS = {
  success: CheckCircle,
  error:   XCircle,
  warning: AlertCircle,
  info:    Info,
};

export default function Toast({ toast, onDismiss }) {
  const { type = 'info', message } = toast;
  const Icon = ICONS[type] || Info;

  return (
    <div className={`${styles.toast} ${styles[type]}`}>
      <Icon size={15} className={styles.icon} />
      <span className={styles.message}>{message}</span>
      <button className={styles.dismiss} onClick={onDismiss}>
        <X size={12} />
      </button>
    </div>
  );
}
