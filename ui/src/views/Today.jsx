import React, { useState, useMemo, useEffect } from 'react';
import { CheckSquare, FileText, Folder, Circle, User, BookOpen, Plus, Loader2 } from 'lucide-react';
import useStore from '../stores/useStore';
import styles from './Today.module.css';

const ENTITY_ICONS = {
  task: CheckSquare,
  note: FileText,
  project: Folder,
  area: Circle,
  person: User,
  resource: BookOpen,
};

const SECTIONS = [
  { key: 'overdue', label: 'Overdue', dot: 'var(--red)', emptyMsg: 'Nothing overdue. Great job staying on top of things!' },
  { key: 'dueToday', label: 'Due Today', dot: 'var(--yellow)', emptyMsg: 'No tasks due today. Enjoy the breathing room.' },
  { key: 'followUp', label: 'Follow-up', dot: 'var(--accent)', emptyMsg: 'No follow-ups scheduled. Set one from any entity.' },
];

const NEW_SECTIONS = [
  {
    key: 'projectsWithoutNextAction',
    label: 'Projects with no next action',
    dot: 'var(--orange)',
    emptyMsg: 'All active projects have upcoming tasks.',
    icon: Folder,
  },
  {
    key: 'waitingOnPeople',
    label: 'Waiting on people',
    dot: 'var(--blue)',
    emptyMsg: 'No tasks are blocked waiting on someone.',
    icon: User,
  },
];

function localDateISO(d = new Date()) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function formatDueTime(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}

function isOverdue(task) {
  if (!task?.due_date || task.status === 'done' || task.status === 'cancelled') return false;
  const due = new Date(task.due_date);
  if (Number.isNaN(due.getTime())) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return due < today;
}

function isDueToday(task, dateStr) {
  if (!task?.due_date || task.status === 'done' || task.status === 'cancelled') return false;
  return task.due_date.slice(0, 10) === dateStr;
}

function hasFollowUpToday(entity, dateStr) {
  if (!entity?.follow_up_at) return false;
  return entity.follow_up_at.slice(0, 10) === dateStr;
}

function EntityCard({ entity, projectsById }) {
  const Icon = ENTITY_ICONS[entity._entityType] || FileText;
  const project = entity.project_id ? projectsById[entity.project_id] : null;
  const dueTime = formatDueTime(entity.due_date || entity.follow_up_at);

  return (
    <div className={styles.entityCard}>
      <Icon size={14} className={styles.entityIcon} />
      <span className={styles.entityTitle}>{entity.title}</span>
      {project && (
        <span className={styles.projectBadge}>{project.title}</span>
      )}
      {dueTime && <span className={styles.dueTime}>{dueTime}</span>}
    </div>
  );
}

function Section({ section, items, projectsById }) {
  const Icon = section.icon;
  return (
    <div className={styles.section}>
      <div className={styles.sectionHeader}>
        {Icon && <Icon size={12} style={{ opacity: 0.6 }} />}
        <span className={styles.sectionDot} style={{ background: section.dot }} />
        <span className={styles.sectionLabel}>{section.label}</span>
        <span className={styles.sectionCount}>{items.length}</span>
      </div>
      {items.length === 0 ? (
        <p className={styles.emptyState}>{section.emptyMsg}</p>
      ) : (
        <div className={styles.cardList}>
          {items.map(entity => (
            <EntityCard key={`${entity._entityType}-${entity.id}`} entity={entity} projectsById={projectsById} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function Today() {
  const { tasks, notes, projects, people, createTask, addToast, loading } = useStore();
  const [quickAddValue, setQuickAddValue] = useState('');
  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const dateStr = localDateISO();

  useEffect(() => {
    setSummaryLoading(true);
    fetch('/api/v4/today')
      .then(r => r.json())
      .then(d => setSummary(d.data || { projects_without_next_action: [], waiting_on_people: [] }))
      .catch(() => setSummary({ projects_without_next_action: [], waiting_on_people: [] }))
      .finally(() => setSummaryLoading(false));
  }, []);

  const projectsById = useMemo(
    () => Object.fromEntries(projects.map(p => [p.id, p])),
    [projects]
  );

  const overdue = useMemo(
    () => tasks.filter(isOverdue).map(t => ({ ...t, _entityType: 'task' })),
    [tasks]
  );

  const dueToday = useMemo(
    () => tasks.filter(t => isDueToday(t, dateStr)).map(t => ({ ...t, _entityType: 'task' })),
    [tasks, dateStr]
  );

  const followUp = useMemo(() => {
    const followUpTasks = tasks
      .filter(t => hasFollowUpToday(t, dateStr) && !isDueToday(t, dateStr) && !isOverdue(t))
      .map(t => ({ ...t, _entityType: 'task' }));
    const followUpNotes = notes
      .filter(n => hasFollowUpToday(n, dateStr))
      .map(n => ({ ...n, _entityType: 'note' }));
    return [...followUpTasks, ...followUpNotes];
  }, [tasks, notes, dateStr]);

  async function submitQuickAdd() {
    const title = quickAddValue.trim();
    if (!title) return;
    try {
      await createTask({ title, due_date: `${dateStr}T09:00:00Z` });
      setQuickAddValue('');
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Failed to create task' });
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && quickAddValue.trim()) {
      e.preventDefault();
      submitQuickAdd();
    }
    if (e.key === 'Escape') {
      setQuickAddValue('');
    }
  }

  const dateDisplay = new Date(`${dateStr}T12:00:00`).toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  });

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1>Today</h1>
        <p className={styles.date}>{dateDisplay}</p>
      </header>

      <div className={styles.quickAdd}>
        <Plus size={14} className={styles.quickAddIcon} />
        <input
          type="text"
          className={styles.quickAddInput}
          placeholder="Add a task for today..."
          value={quickAddValue}
          onChange={e => setQuickAddValue(e.target.value)}
          onKeyDown={handleKeyDown}
        />
      </div>

      {loading && tasks.length === 0 && notes.length === 0 ? (
        <Loader2 size={20} className="spin" style={{ display: 'block', margin: '40px auto', color: 'var(--text-muted)' }} />
      ) : (
        <div className={styles.sections}>
          {SECTIONS.map(section => {
            const items = section.key === 'overdue' ? overdue
              : section.key === 'dueToday' ? dueToday
              : followUp;
            return (
              <Section
                key={section.key}
                section={section}
                items={items}
                projectsById={projectsById}
              />
            );
          })}

          {summaryLoading ? (
            <div className={styles.section}>
              <div className={styles.sectionHeader}>
                <Loader2 size={14} className="spin" />
                <span className={styles.sectionLabel}>Loading attention items…</span>
              </div>
            </div>
          ) : (
            NEW_SECTIONS.map(section => {
              const items = section.key === 'projectsWithoutNextAction'
                ? (summary?.projects_without_next_action || []).map(p => ({ ...p, _entityType: 'project' }))
                : (summary?.waiting_on_people || []).map(p => ({ ...p, _entityType: 'person' }));
              return (
                <Section
                  key={section.key}
                  section={section}
                  items={items}
                  projectsById={projectsById}
                />
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
