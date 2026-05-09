import React, { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, Plus } from 'lucide-react';
import useStore from '../stores/useStore';
import NoteCard from '../components/notes/NoteCard';
import NoteEditor from '../components/notes/NoteEditor';
import TaskCheckboxRow from '../components/tasks/TaskCheckboxRow';
import styles from './ProjectFocus.module.css';

export default function ProjectFocus() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { projects, notes, tasks, people, areas, updateProject, loadAll } = useStore();
  const [tab, setTab] = useState('notes');
  const [showNoteEditor, setShowNoteEditor] = useState(false);
  const [completeFlow, setCompleteFlow] = useState(null);
  const [completing, setCompleting] = useState(false);

  const project = projects.find(p => p.id === id);
  if (!project) return <div className={styles.page}><p>Project not found.</p><button type="button" onClick={() => navigate('/projects')}>Back</button></div>;

  const parentArea = project.area_id ? areas.find(a => a.id === project.area_id) : null;

  const runComplete = async (rollupConfirmed) => {
    setCompleting(true);
    try {
      const payload = rollupConfirmed
        ? { is_archived: true, rollup_confirmed: true }
        : { is_archived: true };
      await updateProject(id, payload);
      await loadAll();
      setCompleteFlow(null);
      if (parentArea && rollupConfirmed) {
        navigate(`/areas/${parentArea.id}`);
      } else {
        navigate('/projects');
      }
    } finally {
      setCompleting(false);
    }
  };

  const onCompleteProjectClick = () => {
    if (parentArea) {
      setCompleteFlow('rollup');
    } else {
      setCompleteFlow('simple');
    }
  };

  const projectNotes = notes.filter(n => n.project_id === id);
  const projectTasks = tasks.filter(t => t.project_id === id);

  // Get unique people linked via notes
  const linkedPersonIds = [...new Set(projectNotes.map(n => n.person_id).filter(Boolean))];
  const linkedPeople = people.filter(p => linkedPersonIds.includes(p.id));

  return (
    <div className={styles.page}>
      {parentArea && (
        <nav className={styles.breadcrumb} aria-label="Breadcrumb">
          <Link to="/areas">Areas</Link>
          <span className={styles.breadcrumbSep}>/</span>
          <Link to={`/areas/${parentArea.id}`}>{parentArea.name}</Link>
          <span className={styles.breadcrumbSep}>/</span>
          <span className={styles.breadcrumbCurrent}>{project.name}</span>
        </nav>
      )}

      <button type="button" className={styles.backBtn} onClick={() => navigate('/projects')}>
        <ArrowLeft size={14} /> All Projects
      </button>

      {/* Project header */}
      <div className={styles.projectHeader}>
        <span className={styles.dot} style={{ background: project.color || 'var(--accent)' }} />
        <h1>{project.name}</h1>
        {project.description && <p className={styles.desc}>{project.description}</p>}
        <div className={styles.headerActions}>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            data-testid="complete-project-btn"
            onClick={onCompleteProjectClick}
          >
            Complete Project
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className={styles.tabs}>
        {[
          { key: 'notes', label: `Notes (${projectNotes.length})` },
          { key: 'tasks', label: `Tasks (${projectTasks.length})` },
          { key: 'people', label: `People (${linkedPeople.length})` },
        ].map(t => (
          <button
            key={t.key}
            className={`${styles.tab} ${tab === t.key ? styles.tabActive : ''}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'notes' && (
        <div className={styles.content}>
          <div className={styles.contentHeader}>
            <button className="btn btn-primary btn-sm" onClick={() => setShowNoteEditor(true)}>
              <Plus size={13} /> Add Note
            </button>
          </div>
          {projectNotes.length === 0 ? (
            <p className={styles.empty}>No notes in this project yet.</p>
          ) : (
            <div className={styles.noteGrid}>
              {projectNotes.map(n => <NoteCard key={n.id} note={n} />)}
            </div>
          )}
        </div>
      )}

      {tab === 'tasks' && (
        <div className={styles.content}>
          {projectTasks.length === 0 ? (
            <p className={styles.empty}>No tasks in this project yet.</p>
          ) : (
            <div className={styles.taskList}>
              {projectTasks.map(t => (
                <div key={t.id} className={styles.taskRow}>
                  <TaskCheckboxRow task={t} className={styles.taskRowCheckbox} />
                  {t.status && <span className={styles.taskStatus}>{t.status}</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === 'people' && (
        <div className={styles.content}>
          {linkedPeople.length === 0 ? (
            <p className={styles.empty}>No people linked to notes in this project.</p>
          ) : (
            <div className={styles.peopleList}>
              {linkedPeople.map(p => (
                <div key={p.id} className={styles.personCard}>
                  <div className={styles.personAvatar}>{p.name.charAt(0)}</div>
                  <span className={styles.personName}>{p.name}</span>
                  {p.role && <span className={styles.personRole}>{p.role}</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {showNoteEditor && (
        <NoteEditor
          initialData={{ project_ids: [id], bucket: 'PROJECTS' }}
          onClose={() => setShowNoteEditor(false)}
          onSaved={() => setShowNoteEditor(false)}
        />
      )}

      {completeFlow && (
        <div
          className={styles.completeOverlay}
          role="presentation"
          onClick={() => !completing && setCompleteFlow(null)}
        >
          <div
            className={styles.completeDialog}
            role="dialog"
            aria-modal="true"
            aria-labelledby="complete-project-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="complete-project-title" className={styles.completeTitle}>
              {completeFlow === 'rollup' ? 'Complete project with rollup' : 'Complete project'}
            </h2>
            {completeFlow === 'rollup' ? (
              <>
                <p className={styles.completeBody} data-testid="rollup-confirm-copy">
                  This project lives under <strong>{parentArea?.name}</strong>. Archiving will generate a
                  retrospective summary note in that area (tagged retrospective and project-complete),
                  then archive <strong>{project.name}</strong>.
                </p>
                <div className={styles.completeActions}>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    disabled={completing}
                    onClick={() => setCompleteFlow(null)}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    data-testid="rollup-confirm-submit"
                    disabled={completing}
                    onClick={() => runComplete(true)}
                  >
                    {completing ? 'Working…' : 'Create retrospective & archive'}
                  </button>
                </div>
              </>
            ) : (
              <>
                <p className={styles.completeBody}>
                  Archive <strong>{project.name}</strong>? You can still find it under archived projects.
                </p>
                <div className={styles.completeActions}>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    disabled={completing}
                    onClick={() => setCompleteFlow(null)}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    data-testid="archive-only-submit"
                    disabled={completing}
                    onClick={() => runComplete(false)}
                  >
                    {completing ? 'Working…' : 'Archive project'}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
