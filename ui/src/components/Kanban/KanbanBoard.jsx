import React, { useState, useMemo } from 'react';
import {
  DndContext,
  closestCorners,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragOverlay,
  useDroppable,
  useDraggable,
} from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Filter, X, Circle, Clock, CheckCircle } from 'lucide-react';
import useStore from '../../stores/useStore';
import styles from './KanbanBoard.module.css';

const COLUMNS = [
  { key: 'PENDING', label: 'Pending', icon: Circle },
  { key: 'IN_PROGRESS', label: 'In Progress', icon: Clock },
  { key: 'DONE', label: 'Done', icon: CheckCircle },
];

function KanbanCard({ task, projects, areas, tags, isOverlay }) {
  const project = task.project_id ? projects.find(p => p.id === task.project_id) : null;
  const area = task.area_id ? areas.find(a => a.id === task.area_id) : null;
  const taskTags = (task.tag_ids || []).map(tid => tags.find(t => t.id === tid)).filter(Boolean);
  const due = task.due_date ? new Date(task.due_date).toLocaleDateString() : null;

  return (
    <div
      className={styles.card}
      data-testid={`kanban-card-${task.id}`}
      style={isOverlay ? { boxShadow: '0 8px 24px rgba(0,0,0,0.2)', transform: 'rotate(2deg)', cursor: 'grabbing' } : {}}
    >
      <div className={styles.cardTitle}>{task.title}</div>
      <div className={styles.cardMeta}>
        {project && <span className={styles.cardBadge} data-testid={`card-project-${task.id}`}>{project.name}</span>}
        {area && <span className={styles.cardBadge} data-testid={`card-area-${task.id}`}>{area.name}</span>}
        {due && <span className={styles.cardDue}>{due}</span>}
      </div>
      {taskTags.length > 0 && (
        <div className={styles.cardTags}>
          {taskTags.map(tag => (
            <span key={tag.id} className={styles.tagBadge}>{tag.name}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function DroppableColumn({ column, tasks, projects, areas, tags, activeId }) {
  const { setNodeRef } = useDroppable({ id: column.key });
  const Icon = column.icon;

  return (
    <div className={styles.column} ref={setNodeRef} data-testid={`kanban-column-${column.key}`}>
      <div className={styles.columnHeader}>
        <Icon size={16} />
        <span>{column.label}</span>
        <span className={styles.colCount} data-testid={`column-count-${column.key}`}>{tasks.length}</span>
      </div>
      <div className={styles.columnBody} data-testid={`column-body-${column.key}`}>
        {tasks.length === 0 && (
          <div className={styles.emptyColumn}>Drop tasks here</div>
        )}
        <SortableContext items={tasks.map(t => t.id)} strategy={verticalListSortingStrategy}>
          {tasks.map(task => {
            if (task.id === activeId) return null;
            return <SortableTaskCard key={task.id} task={task} projects={projects} areas={areas} tags={tags} />;
          })}
        </SortableContext>
      </div>
    </div>
  );
}

function SortableTaskCard({ task, projects, areas, tags }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: task.id });

  const style = {
    transform: CSS.Translate.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners} className={styles.draggableCard}>
      <KanbanCard task={task} projects={projects} areas={areas} tags={tags} />
    </div>
  );
}

export default function KanbanBoard() {
  const { tasks, projects, areas, tags, updateTask } = useStore();
  const [activeId, setActiveId] = useState(null);
  const [filters, setFilters] = useState({ projectId: '', areaId: '', tagId: '' });
  const [showFilters, setShowFilters] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const filteredTasks = useMemo(() => {
    return tasks.filter(task => {
      if (filters.projectId && task.project_id !== filters.projectId) return false;
      if (filters.areaId && task.area_id !== filters.areaId) return false;
      if (filters.tagId && !(task.tag_ids || []).includes(filters.tagId)) return false;
      return true;
    });
  }, [tasks, filters]);

  const tasksByColumn = useMemo(() => {
    const grouped = {};
    COLUMNS.forEach(col => {
      grouped[col.key] = filteredTasks.filter(t => t.status === col.key);
    });
    return grouped;
  }, [filteredTasks]);

  const handleDragStart = ({ active }) => {
    setActiveId(active.id);
  };

  const handleDragEnd = async ({ active, over }) => {
    setActiveId(null);
    if (!over) return;

    const taskId = active.id;
    const targetColumn = over.id;

    const task = tasks.find(t => String(t.id) === String(taskId));
    if (!task || task.status === targetColumn) return;

    await updateTask(taskId, { status: targetColumn });
  };

  const activeTask = activeId ? tasks.find(t => String(t.id) === String(activeId)) : null;

  const clearFilters = () => setFilters({ projectId: '', areaId: '', tagId: '' });
  const hasActiveFilters = filters.projectId || filters.areaId || filters.tagId;

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1>Kanban Board</h1>
          <p className={styles.subtitle}>{filteredTasks.length} task{filteredTasks.length !== 1 ? 's' : ''}</p>
        </div>
        <div className={styles.headerActions}>
          <button
            className={`${styles.filterBtn} ${showFilters ? styles.filterBtnActive : ''}`}
            onClick={() => setShowFilters(!showFilters)}
            data-testid="toggle-filters"
          >
            <Filter size={16} />
            Filter
            {hasActiveFilters && <span className={styles.filterDot} />}
          </button>
        </div>
      </div>

      {showFilters && (
        <div className={styles.filterBar} data-testid="filter-bar">
          <div className={styles.filterGroup}>
            <label>Project</label>
            <select
              value={filters.projectId}
              onChange={e => setFilters(f => ({ ...f, projectId: e.target.value }))}
              data-testid="filter-project"
            >
              <option value="">All projects</option>
              {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div className={styles.filterGroup}>
            <label>Area</label>
            <select
              value={filters.areaId}
              onChange={e => setFilters(f => ({ ...f, areaId: e.target.value }))}
              data-testid="filter-area"
            >
              <option value="">All areas</option>
              {areas.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          </div>
          <div className={styles.filterGroup}>
            <label>Tag</label>
            <select
              value={filters.tagId}
              onChange={e => setFilters(f => ({ ...f, tagId: e.target.value }))}
              data-testid="filter-tag"
            >
              <option value="">All tags</option>
              {tags.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>
          {hasActiveFilters && (
            <button className={styles.clearFilters} onClick={clearFilters} data-testid="clear-filters">
              <X size={14} /> Clear
            </button>
          )}
        </div>
      )}

      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <div className={styles.board}>
          {COLUMNS.map(col => (
            <DroppableColumn
              key={col.key}
              column={col}
              tasks={tasksByColumn[col.key]}
              projects={projects}
              areas={areas}
              tags={tags}
              activeId={activeId}
            />
          ))}
        </div>
        <DragOverlay>
          {activeTask ? (
            <KanbanCard task={activeTask} projects={projects} areas={areas} tags={tags} isOverlay />
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  );
}
