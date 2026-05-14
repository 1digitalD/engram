import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Inbox, CheckSquare, FileText, FolderOpen, HeartPulse } from 'lucide-react';
import useStore from '../stores/useStore';
import NoteCard from '../components/notes/NoteCard';
import TaskCheckboxRow from '../components/tasks/TaskCheckboxRow';
import { StatusBadge } from '../components/ui/Badge';
import { metricsAPI } from '../api/engram';
import styles from './Dashboard.module.css';

function orphanRateTier(rate) {
  if (rate <= 0.15) return 'good';
  if (rate <= 0.35) return 'warn';
  return 'bad';
}

function inboxTier(count) {
  if (count > 50) return 'bad';
  if (count > 20) return 'warn';
  return 'good';
}

export default function Dashboard() {
  const { notes, projects, tasks, loading } = useStore();
  const [health, setHealth] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await metricsAPI.health();
        if (!cancelled) setHealth(data);
      } catch {
        if (!cancelled) setHealth(null);
      }
    })();
    return () => { cancelled = true; };
  }, []);

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

  const captureBars = useMemo(() => {
    const raw = health?.weekly_capture_counts;
    if (!Array.isArray(raw) || raw.length === 0) return [0, 0, 0, 0];
    return raw.slice(-4);
  }, [health]);

  const maxCapture = useMemo(
    () => Math.max(1, ...captureBars),
    [captureBars],
  );

  const orphanTier = health != null ? orphanRateTier(health.orphan_rate ?? 0) : 'good';
  const inboxCount = health?.inbox_count ?? inbox.length;
  const inboxUrgency = inboxTier(inboxCount);

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

      {/* Knowledge Health */}
      <section
        className={styles.healthCard}
        data-testid="dashboard-health-card"
        aria-label="Knowledge health metrics"
      >
        <div className={styles.healthHeader}>
          <div className={styles.healthTitleRow}>
            <HeartPulse size={18} className={styles.healthIcon} aria-hidden />
            <h2 className={styles.healthTitle}>Knowledge Health</h2>
          </div>
        </div>
        {health ? (
          <>
            <div className={styles.healthMetrics}>
              <div className={styles.healthMetric}>
                <span className={styles.healthMetricLabel}>Orphan rate</span>
                <span
                  className={`${styles.healthMetricValue} ${styles[`orphan${orphanTier.charAt(0).toUpperCase() + orphanTier.slice(1)}`]}`}
                  data-testid="health-orphan-rate"
                  data-tier={orphanTier}
                >
                  {(health.orphan_rate * 100).toFixed(0)}%
                </span>
              </div>
              <div className={styles.healthMetric}>
                <span className={styles.healthMetricLabel}>Avg links / note</span>
                <span className={styles.healthMetricValue} data-testid="health-avg-links">
                  {(health.avg_links_per_note ?? 0).toFixed(2)}
                </span>
              </div>
              <div className={styles.healthMetric}>
                <span className={styles.healthMetricLabel}>Captures (7d)</span>
                <span className={styles.healthMetricValue} data-testid="health-capture-rate">
                  {health.weekly_capture_rate ?? 0}
                </span>
              </div>
              <div className={styles.healthMetric}>
                <span className={styles.healthMetricLabel}>Inbox</span>
                <Link
                  to="/inbox"
                  className={`${styles.healthMetricValue} ${styles.inboxLink} ${styles[`inbox${inboxUrgency.charAt(0).toUpperCase() + inboxUrgency.slice(1)}`]}`}
                  data-testid="health-inbox-count"
                  data-tier={inboxUrgency}
                >
                  {inboxCount}
                </Link>
              </div>
            </div>
            <div className={styles.captureChartWrap}>
              <span className={styles.captureChartLabel}>Capture rate (4 weeks)</span>
              <div
                className={styles.captureChart}
                data-testid="health-capture-chart"
                role="img"
                aria-label={`Notes captured per week over four weeks: ${captureBars.join(', ')}`}
              >
                {captureBars.map((c, i) => (
                  <div key={i} className={styles.captureBarTrack}>
                    <div
                      className={styles.captureBar}
                      style={{ height: `${(c / maxCapture) * 100}%` }}
                      data-count={c}
                    />
                  </div>
                ))}
              </div>
            </div>
          </>
        ) : (
          <p className={styles.healthLoading}>Loading health metrics…</p>
        )}
      </section>

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
                    <span className={styles.inboxText}>{(n.raw_text || '').slice(0, 80)}…</span>
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
                    <TaskCheckboxRow task={t} className={styles.taskItemInner}>
                      {t.status && <StatusBadge status={t.status} />}
                    </TaskCheckboxRow>
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
                  <span className={styles.projectName}>{p.title}</span>
                </Link>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
