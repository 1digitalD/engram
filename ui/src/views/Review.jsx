import React from 'react';
import { Link } from 'react-router-dom';
import { Calendar, Inbox, CheckCircle, Clock } from 'lucide-react';
import useStore from '../stores/useStore';
import NoteCard from '../components/notes/NoteCard';
import styles from './Review.module.css';

export default function Review() {
  const { notes, tasks } = useStore();

  const now = new Date();
  const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  const weekAhead = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);

  const inbox = notes.filter(n => n.bucket === 'INBOX');
  const recent = notes.filter(n => new Date(n.created_at) >= weekAgo && n.bucket !== 'INBOX');
  const stale = notes.filter(n => {
    const d = new Date(n.modified_at || n.created_at);
    return d < weekAgo && n.bucket === 'INBOX';
  });

  const upcomingTasks = tasks.filter(t => {
    if (!t.due_date) return false;
    const d = new Date(t.due_date);
    return d >= now && d <= weekAhead;
  });

  const pendingTasks = tasks.filter(t => !t.due_date && t.status !== 'DONE' && t.status !== 'CANCELLED');

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1>Weekly Review</h1>
        <p className={styles.subtitle}>
          Week of {weekAgo.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} — {weekAhead.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
        </p>
      </div>

      <div className={styles.grid}>
        {/* Inbox Queue */}
        <section className={styles.section}>
          <div className={styles.sectionHeader}>
            <Inbox size={15} />
            <h2>Inbox Queue</h2>
            <span className={styles.badge}>{inbox.length}</span>
          </div>
          <p className={styles.desc}>Notes captured but not yet routed.</p>
          {inbox.length === 0 ? (
            <p className={styles.empty}>Inbox is clear.</p>
          ) : (
            <div className={styles.noteList}>
              {inbox.slice(0, 5).map(n => <NoteCard key={n.id} note={n} />)}
              {inbox.length > 5 && <Link to="/inbox" className={styles.moreLink}>+{inbox.length - 5} more in inbox →</Link>}
            </div>
          )}
        </section>

        {/* This Week's Captures */}
        <section className={styles.section}>
          <div className={styles.sectionHeader}>
            <Calendar size={15} />
            <h2>This Week</h2>
            <span className={styles.badge}>{recent.length}</span>
          </div>
          <p className={styles.desc}>Notes captured in the past 7 days.</p>
          {recent.length === 0 ? (
            <p className={styles.empty}>Nothing captured this week.</p>
          ) : (
            <div className={styles.noteList}>
              {recent.slice(0, 5).map(n => <NoteCard key={n.id} note={n} />)}
            </div>
          )}
        </section>

        {/* Upcoming Tasks */}
        <section className={styles.section}>
          <div className={styles.sectionHeader}>
            <Clock size={15} />
            <h2>Upcoming (7 days)</h2>
            <span className={styles.badge}>{upcomingTasks.length}</span>
          </div>
          {upcomingTasks.length === 0 ? (
            <p className={styles.empty}>No tasks due this week.</p>
          ) : (
            <div className={styles.taskList}>
              {upcomingTasks.map(t => (
                <div key={t.id} className={styles.taskItem}>
                  <span>{t.title}</span>
                  <span className={styles.dueDate}>
                    {new Date(t.due_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Pending without dates */}
        <section className={styles.section}>
          <div className={styles.sectionHeader}>
            <CheckCircle size={15} />
            <h2>Open Tasks</h2>
            <span className={styles.badge}>{pendingTasks.length}</span>
          </div>
          {pendingTasks.length === 0 ? (
            <p className={styles.empty}>All tasks are done or dated.</p>
          ) : (
            <div className={styles.taskList}>
              {pendingTasks.slice(0, 8).map(t => (
                <div key={t.id} className={styles.taskItem}>
                  <span>{t.title}</span>
                  <span className={styles.taskStatus}>{t.status || 'PENDING'}</span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
