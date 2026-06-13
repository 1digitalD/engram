import { forwardRef, useEffect, useImperativeHandle, useState } from 'react';
import styles from './MentionList.module.css';

const TYPE_LABELS = {
  task: 'Tasks',
  project: 'Projects',
  area: 'Areas',
  person: 'People',
  note: 'Notes',
  resource: 'Resources',
};

const MentionList = forwardRef(function MentionList({ items = {}, command }, ref) {
  const groups = Object.entries(items).filter(([, list]) => (list || []).length > 0);
  const flat = groups.flatMap(([type, list]) => list.map((item) => ({ ...item, _type: type })));

  const [selected, setSelected] = useState(0);
  useEffect(() => setSelected(0), [items]);

  useImperativeHandle(ref, () => ({
    onKeyDown: ({ event }) => {
      if (flat.length === 0) return false;
      if (event.key === 'ArrowDown') {
        setSelected((s) => (s + 1) % flat.length);
        return true;
      }
      if (event.key === 'ArrowUp') {
        setSelected((s) => (s - 1 + flat.length) % flat.length);
        return true;
      }
      if (event.key === 'Enter' || event.key === 'Tab') {
        command(flat[selected]);
        return true;
      }
      return false;
    },
  }));

  if (flat.length === 0) {
    return (
      <div className={styles.menu}>
        <div className={styles.empty}>No matches</div>
      </div>
    );
  }

  let index = -1;
  return (
    <div className={styles.menu}>
      {groups.map(([type, list]) => (
        <div key={type} className={styles.group}>
          <div className={styles.groupLabel}>{TYPE_LABELS[type] || type}</div>
          {list.map((item) => {
            index += 1;
            const isActive = index === selected;
            return (
              <button
                key={item.id}
                type="button"
                className={`${styles.item} ${isActive ? styles.itemActive : ''}`}
                onMouseDown={(event) => {
                  event.preventDefault();
                  command({ ...item, _type: type });
                }}
              >
                {item.title}
              </button>
            );
          })}
        </div>
      ))}
    </div>
  );
});

export default MentionList;
