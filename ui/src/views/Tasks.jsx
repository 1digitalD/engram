import React, { useMemo, useState } from 'react';
import { Plus, X } from 'lucide-react';
import useStore from '../stores/useStore';
import EmptyState from '../components/ui/EmptyState';
import styles from './Tasks.module.css';

const COLUMNS = [
  { key: 'PENDING', label: 'Pending', dot: 'var(--text-muted)' },
  { key: 'IN_PROGRESS', label: 'In Progress', dot: 'var(--yellow)' },
  { key: 'DONE', label: 'Done', dot: 'var(--green)' },
];

const PRIORITY_COLORS = {
  URGENT: 'var(--danger)',
  HIGH: 'var(--danger)',
  MEDIUM: 'var(--warning)',
  LOW: 'var(--text-muted)',
};

const FILTERS = {
  ALL: 'ALL',
  BY_PROJECT: 'BY_PROJECT',
  OVERDUE: 'OVERDUE',
};

function formatDueDate(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  });
}

function isOverdue(task) {
  if (!task?.due_date || task.status === 'DONE') return false;
  const due = new Date(task.due_date);
  if (Number.isNaN(due.getTime())) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return due < today;
}

function buildProjectPalette(projects) {
  return projects.reduce((palette, project, index) => {
    const colors = [
      { border: 'rgba(59, 130, 246, 0.4)', text: 'var(--entity-project)' },
      { border: 'rgba(34, 197, 94, 0.4)', text: 'var(--entity-task)' },
      { border: 'rgba(245, 158, 11, 0.4)', text: 'var(--entity-area)' },
      { border: 'rgba(236, 72, 153, 0.4)', text: 'var(--entity-person)' },
    ];
    palette[project.id] = colors[index % colors.length];
    return palette;
  }, {});
}

function TaskCard({
  task,
  project,
  projectColor,
  isDragging,
  onDelete,
  onDragStart,
  onDragEnd,
}) {
  const dueDate = formatDueDate(task.due_date);
  const priorityColor = PRIORITY_COLORS[task.priority] || 'var(--text-muted)';

  return (
    <div
      draggable
      onDragStart={(event) => onDragStart(event, task)}
      onDragEnd={onDragEnd}
      className={`${styles.taskCard} ${isDragging ? styles.taskCardDragging : ''}`}
      data-testid={`task-card-${task.id}`}
      aria-label={task.title}
    >
      <div className={styles.cardHeader}>
        <div
          className={styles.priorityDot}
          aria-hidden="true"
          style={{ background: priorityColor }}
        />
        <button type="button" className={styles.deleteBtn} onClick={() => onDelete(task.id)} aria-label={`Delete ${task.title}`}>
          <X size={12} />
        </button>
      </div>

      <div className={styles.cardTitle}>{task.title}</div>

      <div className={styles.cardMeta}>
        {project && (
          <span
            className={styles.projectBadge}
            style={{
              borderColor: projectColor.border,
              color: projectColor.text,
            }}
          >
            {project.title}
          </span>
        )}
        {dueDate && <span className={styles.dueDate}>{dueDate}</span>}
      </div>
    </div>
  );
}

function TaskColumn({
  column,
  tasks,
  projectsById,
  projectPalette,
  quickAddValue,
  quickAddOpen,
  dragTarget,
  draggedTaskId,
  onQuickAddToggle,
  onQuickAddChange,
  onQuickAddKeyDown,
  onDrop,
  onDragOver,
  onDragLeave,
  onDragStart,
  onDragEnd,
  onDelete,
}) {
  return (
    <section className={styles.column} aria-label={column.label}>
      <div className={styles.columnHeader}>
        <div className={styles.columnHeading}>
          <span className={styles.statusDot} aria-hidden="true" style={{ background: column.dot }} />
          <span>{column.label}</span>
          <span className={styles.colCount}>{tasks.length}</span>
        </div>
        <button
          type="button"
          className={styles.addBtn}
          aria-label={`Add task to ${column.label}`}
          onClick={() => onQuickAddToggle(column.key)}
        >
          <Plus size={12} />
        </button>
      </div>

      {quickAddOpen && (
        <input
          className={styles.quickAddInput}
          placeholder="Add a task"
          value={quickAddValue}
          onChange={(event) => onQuickAddChange(event.target.value)}
          onKeyDown={(event) => onQuickAddKeyDown(event, column.key)}
          autoFocus
        />
      )}

      <div
        className={`${styles.columnBody} ${dragTarget === column.key ? styles.columnBodyActive : ''}`}
        data-testid={`task-column-${column.key}`}
        onDragOver={(event) => onDragOver(event, column.key)}
        onDragLeave={() => onDragLeave(column.key)}
        onDrop={(event) => onDrop(event, column.key)}
      >
        {tasks.length === 0 && (
          <p className={styles.emptyCol}>Drop tasks here</p>
        )}

        {tasks.map((task) => (
          <TaskCard
            key={task.id}
            task={task}
            project={task.project_id ? projectsById[task.project_id] : null}
            projectColor={projectPalette[task.project_id] || { border: 'var(--border)', text: 'var(--text-secondary)' }}
            isDragging={draggedTaskId === task.id}
            onDelete={onDelete}
            onDragStart={onDragStart}
            onDragEnd={onDragEnd}
          />
        ))}
      </div>
    </section>
  );
}

export default function Tasks() {
  const { tasks, projects, createTask, updateTask, deleteTask } = useStore();
  const [activeFilter, setActiveFilter] = useState(FILTERS.ALL);
  const [selectedProjectId, setSelectedProjectId] = useState(projects[0]?.id || '');
  const [quickAddStatus, setQuickAddStatus] = useState(null);
  const [quickAddValue, setQuickAddValue] = useState('');
  const [draggedTaskId, setDraggedTaskId] = useState(null);
  const [dragTarget, setDragTarget] = useState(null);

  const projectsById = useMemo(
    () => Object.fromEntries(projects.map((project) => [project.id, project])),
    [projects]
  );
  const projectPalette = useMemo(() => buildProjectPalette(projects), [projects]);

  const filteredTasks = useMemo(() => {
    if (activeFilter === FILTERS.OVERDUE) {
      return tasks.filter(isOverdue);
    }
    if (activeFilter === FILTERS.BY_PROJECT) {
      return tasks.filter((task) => task.project_id === selectedProjectId);
    }
    return tasks;
  }, [activeFilter, selectedProjectId, tasks]);

  const tasksByColumn = useMemo(
    () =>
      COLUMNS.reduce((acc, column) => {
        acc[column.key] = filteredTasks.filter((task) => task.status === column.key);
        return acc;
      }, {}),
    [filteredTasks]
  );

  const pendingCount = tasks.filter((task) => task.status !== 'DONE' && task.status !== 'CANCELLED').length;

  async function submitQuickAdd(status) {
    const nextTitle = quickAddValue.trim();
    if (!nextTitle) return;
    await createTask({ title: nextTitle, status });
    setQuickAddValue('');
    setQuickAddStatus(null);
  }

  function handleQuickAddToggle(status) {
    setQuickAddStatus((current) => (current === status ? null : status));
    setQuickAddValue('');
  }

  function handleQuickAddKeyDown(event, status) {
    if (event.key === 'Enter') {
      event.preventDefault();
      submitQuickAdd(status);
    }
    if (event.key === 'Escape') {
      event.preventDefault();
      setQuickAddStatus(null);
      setQuickAddValue('');
    }
  }

  function handleDragStart(event, task) {
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', task.id);
    setDraggedTaskId(task.id);
  }

  function handleDragEnd() {
    setDraggedTaskId(null);
    setDragTarget(null);
  }

  function handleDragOver(event, status) {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    if (dragTarget !== status) setDragTarget(status);
  }

  function handleDragLeave(status) {
    if (dragTarget === status) {
      setDragTarget(null);
    }
  }

  async function handleDrop(event, newStatus) {
    event.preventDefault();
    const taskId = event.dataTransfer.getData('text/plain') || draggedTaskId;
    setDragTarget(null);
    setDraggedTaskId(null);

    const task = tasks.find((item) => String(item.id) === String(taskId));
    if (!task || task.status === newStatus) return;

    await updateTask(task.id, { status: newStatus });
  }

  function activateFilter(filter) {
    if (filter === FILTERS.BY_PROJECT) {
      const nextProjectId = selectedProjectId || projects[0]?.id || '';
      setSelectedProjectId(nextProjectId);
      setActiveFilter(FILTERS.BY_PROJECT);
      return;
    }
    setActiveFilter(filter);
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1>Tasks</h1>
          <p className={styles.count}>{pendingCount} pending</p>
        </div>
      </div>

      <div className={styles.filterBar}>
        <button
          type="button"
          className={`${styles.filterChip} ${activeFilter === FILTERS.ALL ? styles.filterChipActive : ''}`}
          onClick={() => activateFilter(FILTERS.ALL)}
        >
          All
        </button>
        <button
          type="button"
          className={`${styles.filterChip} ${activeFilter === FILTERS.BY_PROJECT ? styles.filterChipActive : ''}`}
          onClick={() => activateFilter(FILTERS.BY_PROJECT)}
        >
          By Project
        </button>
        <button
          type="button"
          className={`${styles.filterChip} ${activeFilter === FILTERS.OVERDUE ? styles.filterChipActive : ''}`}
          onClick={() => activateFilter(FILTERS.OVERDUE)}
        >
          Overdue
        </button>
      </div>

      {activeFilter === FILTERS.BY_PROJECT && projects.length > 0 && (
        <div className={styles.projectFilters}>
          {projects.map((project) => (
            <button
              key={project.id}
              type="button"
              className={`${styles.projectChip} ${selectedProjectId === project.id ? styles.projectChipActive : ''}`}
              onClick={() => setSelectedProjectId(project.id)}
            >
              {project.title}
            </button>
          ))}
        </div>
      )}

      {tasks.length === 0 ? (
        <EmptyState
          type="tasks"
          title="No tasks yet"
          message="Break your work into actionable tasks and track them here."
        />
      ) : (
        <div className={styles.board}>
          {COLUMNS.map((column) => (
            <TaskColumn
              key={column.key}
              column={column}
              tasks={tasksByColumn[column.key]}
              projectsById={projectsById}
              projectPalette={projectPalette}
              quickAddValue={quickAddValue}
              quickAddOpen={quickAddStatus === column.key}
              dragTarget={dragTarget}
              draggedTaskId={draggedTaskId}
              onQuickAddToggle={handleQuickAddToggle}
              onQuickAddChange={setQuickAddValue}
              onQuickAddKeyDown={handleQuickAddKeyDown}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDragStart={handleDragStart}
              onDragEnd={handleDragEnd}
              onDelete={deleteTask}
            />
          ))}
        </div>
      )}
    </div>
  );
}
