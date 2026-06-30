import { useEffect, useRef, useState } from 'react';
import styles from './Sheet.module.css';

export default function Sheet({
  open,
  onClose,
  ariaLabel,
  children,
  mobileBottomSheet = true,
}) {
  const panelRef = useRef(null);
  const dragRef = useRef({ startY: 0, currentY: 0, dragging: false });
  const [dragY, setDragY] = useState(0);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    if (!open) return undefined;
    function onKeyDown(event) {
      if (event.key === 'Escape') onClose?.();
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) {
      setDragY(0);
      setDragging(false);
    }
  }, [open]);

  if (!open) return null;

  function isMobileSheet() {
    return mobileBottomSheet && window.matchMedia('(max-width: 900px)').matches;
  }

  function onPointerDown(event) {
    if (!isMobileSheet()) return;
    dragRef.current = {
      startY: event.clientY,
      currentY: event.clientY,
      dragging: true,
    };
    setDragging(true);
    event.currentTarget.setPointerCapture?.(event.pointerId);
  }

  function onPointerMove(event) {
    if (!dragRef.current.dragging) return;
    const delta = Math.max(0, event.clientY - dragRef.current.startY);
    dragRef.current.currentY = event.clientY;
    setDragY(delta);
  }

  function finishDrag() {
    if (!dragRef.current.dragging) return;
    const delta = dragRef.current.currentY - dragRef.current.startY;
    dragRef.current.dragging = false;
    setDragging(false);
    setDragY(0);
    if (delta > 120) onClose?.();
  }

  return (
    <div
      className={styles.backdrop}
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose?.();
      }}
    >
      <div
        ref={panelRef}
        className={`${styles.panel} ${dragging ? styles.panelDragging : ''}`}
        style={dragY ? { '--sheet-drag-y': `${dragY}px` } : undefined}
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel}
        onClick={(event) => event.stopPropagation()}
      >
        <div
          className={styles.handleWrap}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={finishDrag}
          onPointerCancel={finishDrag}
        >
          <div className={styles.handle} aria-hidden="true" />
        </div>
        <div className={styles.body}>{children}</div>
      </div>
    </div>
  );
}
