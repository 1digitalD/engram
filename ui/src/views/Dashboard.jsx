import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Inbox, CheckSquare, FileText, FolderOpen, Calendar } from 'lucide-react';
import useStore from '../stores/useStore';
import NoteCard from '../components/notes/NoteCard';
import { StatusBadge } from '../components/ui/Badge';
import styles from './Dashboard.module.css';

export default function Dashboard() {
  const { notes, projects, tasks, people, loading } = useStore();

  const inbox = notes.filter(n => n.bucket === 'INBOX');
  const recent = [...notes].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, 6);
  const upcomingTasks = tasks.filter(t => t.status !== 'DONE' && t.status !== 'CANCELLED').slice(0, 5);
  const activeProjects = projects.filter(p => !p.is_archived).slice(0, 6);

  const stats = [
    { label: 'Inbox', value: inbox.length, icon: Inbox, to: '/inbox', color: 'var(--bucket-inbox)' },
    { label: 'Notes', value: notes.length, icon: FileText, to: '/notes', color: 'var(--text-secondary)' },
    { label: 'Projects', value: activeProjects.length, icon: FolderOpen, to: '/projects', color: 'var(--bucket-projects)' },
    { label: 'Tasks', value: upcomingTasks.length, icon: CheckSquare, to: '/tasks', color: 'var(--accent-amber)' },
  ];

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.header}>
        <div>
          <h1>Dashboard</h1>
          <p className={styles.subtitle}>
            {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
          </p>
        </div>
      </div>

      {/* Stats */}
      <div className={styles.stats}>
        {stats.map(s => {
          const Icon = s.icon;
          return (
            <Link key={s.label} to={s.to} className={styles.statCard}>
              <div className={styles.statIcon} style={{ color: s.color }}>
                <Icon size={18} />
              </div>
              <div className={styles.statContent}>
                <span className={styles.statValue}>{s.value}</span>
                <span className={styles.statLabel}>{s.label}</span>
              </div>
            </Link>
          );
        })}
      </div>

      <div className={styles.grid}>
        {/* Recent Notes */}
        <section className={styles.section}>
          <div className={styles.sectionHeader}>
            <h2>Recent</h2>
            <Link to="/notes" className={styles.seeAll}>
              All notes <ArrowRight size={13} />
            </Link>
          </div>
          {loading ? (
            <div className={styles.loading}><div className="spinner" /></div>
          ) : recent.length === 0 ? (
            <p className={styles.empty}>No notes yet. Capture something!</p>
          ) : (
            <div className={styles.noteList}>
              {recent.map(n => <NoteCard key={n.id} note={n} />)}
            </div>
          )}
        </section>

        {/* Right column */}
        <div className={styles.rightCol}>
          {/* Inbox */}
          {inbox.length > 0 && (
            <section className={styles.section}>
              <div className={styles.sectionHeader}>
                <h2>Inbox</h2>
                <Link to="/inbox" className={styles.seeAll}>
                  Review <ArrowRight size={13} />
                </Link>
              </div>
              <div className={styles.inboxItems}>
                {inbox.slice(0, 4).map(n => (
                  <Link key={n.id} to={`/notes/${n.id}`} className={styles.inboxItem}>
                    <span className={styles.inboxDot} />
                    <span className={styles.inboxText}>{n.raw_text.slice(0, 80)}…</span>
                  </Link>
                ))}
              </div>
            </section>
          )}

          {/* Upcoming Tasks */}
          <section className={styles.section}>
            <div className={styles.sectionHeader}>
              <h2>Upcoming Tasks</h2>
              <Link to="/tasks" className={styles.seeAll}>
                All tasks <ArrowRight size={13} />
              </Link>
            </div>
            {upcomingTasks.length === 0 ? (
              <p className={styles.empty}>No pending tasks.</p>
            ) : (
              <div className={styles.taskList}>
                {upcomingTasks.map(t => (
                  <div key={t.id} className={styles.taskItem}>
                    <CheckSquare size={13} className={styles.taskIcon} />
                    <span className={styles.taskText}>{t.title}</span>
                    {t.status && <StatusBadge status={t.status} />}
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Active Projects */}
          <section className={styles.section}>
            <div className={styles.sectionHeader}>
              <h2>Active Projects</h2>
              <Link to="/projects" className={styles.seeAll}>
                All <ArrowRight size={13} />
              </Link>
            </div>
            <div className={styles.projectGrid}>
              {activeProjects.map(p => (
                <Link key={p.id} to={`/projects/${p.id}`} className={styles.projectCard}>
                  <span
                    className={styles.projectDot}
                    style={{ background: p.color || 'var(--accent)' }}
                  />
                  <span className={styles.projectName}>{p.name}</span>
                </Link>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
