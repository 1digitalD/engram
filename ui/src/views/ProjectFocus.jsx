import React, { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, Plus } from 'lucide-react';
import useStore from '../stores/useStore';
import NoteCard from '../components/notes/NoteCard';
import NoteEditor from '../components/notes/NoteEditor';
import styles from './ProjectFocus.module.css';

export default function ProjectFocus() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { projects, notes, tasks, people, createNote } = useStore();
  const [tab, setTab] = useState('notes');
  const [showNoteEditor, setShowNoteEditor] = useState(false);

  const project = projects.find(p => p.id === id);
  if (!project) return <div className={styles.page}><p>Project not found.</p><button onClick={() => navigate('/projects')}>Back</button></div>;

  const projectNotes = notes.filter(n => n.project_id === id);
  const projectTasks = tasks.filter(t => t.project_id === id);

  // Get unique people linked via notes
  const linkedPersonIds = [...new Set(projectNotes.map(n => n.person_id).filter(Boolean))];
  const linkedPeople = people.filter(p => linkedPersonIds.includes(p.id));

  return (
    <div className={styles.page}>
      <button className={styles.backBtn} onClick={() => navigate('/projects')}>
        <ArrowLeft size={14} /> All Projects
      </button>

      {/* Project header */}
      <div className={styles.projectHeader}>
        <span className={styles.dot} style={{ background: project.color || 'var(--accent)' }} />
        <h1>{project.name}</h1>
        {project.description && <p className={styles.desc}>{project.description}</p>}
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
                  <span>{t.content}</span>
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
          initialData={{ project_id: id, bucket: 'PROJECTS' }}
          onClose={() => setShowNoteEditor(false)}
          onSaved={() => setShowNoteEditor(false)}
        />
      )}
    </div>
  );
}
