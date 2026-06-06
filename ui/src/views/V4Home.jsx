import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { v4API } from '../api/v4Client';
import MarkdownContent from '../components/MarkdownContent';
import { getTodayActionableEntities, getTodayAttentionCount, getTodayStuckEntities } from '../utils/today';
import styles from './V4Home.module.css';

function entityPath(entity) {
  if (!entity) return '#';
  const base = entity.type === 'person' ? 'people' : `${entity.type}s`;
  return `/${base}/${entity.id}`;
}

function HomeSection({ title, hint, count, action, children }) {
  return (
    <section className={styles.panel}>
      <header className={styles.panelHeader}>
        <div className={styles.panelTitleBlock}>
          <h2>{title}</h2>
          {hint ? <p>{hint}</p> : null}
        </div>
        <div className={styles.panelHeaderRight}>
          {typeof count === 'number' ? <span className={styles.countPill}>{count}</span> : null}
          {action || null}
        </div>
      </header>
      {children}
    </section>
  );
}

function EntityList({ items, fromState }) {
  if (!items.length) {
    return <p className={styles.empty}>Nothing here.</p>;
  }
  return (
    <ul className={styles.list}>
      {items.map((entity) => (
        <li key={entity.id} className={styles.row}>
          <Link to={entityPath(entity)} state={fromState} className={styles.rowLink}>
            <strong>{entity.title || 'Untitled'}</strong>
            {entity.content ? <MarkdownContent content={entity.content} compact /> : null}
            <span className={styles.metaRow}>
              <span className={styles.typePill}>{entity.type}</span>
              <span className={styles.statusPill}>{entity.status}</span>
              {entity.properties?.priority ? (
                <span className={styles.priorityPill}>!{entity.properties.priority}</span>
              ) : null}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

export default function V4Home() {
  const location = useLocation();
  const fromState = { from: location.pathname + location.search };
  const [state, setState] = useState({
    inbox: null,
    today: null,
    projects: [],
    error: '',
  });

  useEffect(() => {
    let active = true;
    Promise.all([
      v4API.inbox({ limit: 8 }),
      v4API.today(),
      v4API.entities.list({ type: 'project', status: 'active', lifecycle: 'active', limit: 8 }),
    ])
      .then(([inbox, today, projects]) => {
        if (!active) return;
        setState({
          inbox,
          today,
          projects: projects.data || [],
          error: '',
        });
      })
      .catch((err) => {
        if (!active) return;
        setState((current) => ({ ...current, error: err.message || 'Failed to load home' }));
      });
    return () => {
      active = false;
    };
  }, []);

  if (state.error) {
    return (
      <main className={styles.home}>
        <section className={styles.hero}>
          <h1>Home</h1>
          <p>{state.error}</p>
        </section>
      </main>
    );
  }

  if (!state.inbox || !state.today) {
    return (
      <main className={styles.home}>
        <section className={styles.hero}>
          <h1>Home</h1>
          <p>Loading current state…</p>
        </section>
      </main>
    );
  }

  const { inbox, today, projects } = state;
  const needsReview = inbox.needs_review || [];
  const recent = inbox.recent || [];
  const actionableToday = getTodayActionableEntities(today).slice(0, 6);
  const stuck = getTodayStuckEntities(today).slice(0, 6);
  const stalledProjects = today.projects_without_open_tasks || [];
  const summary = {
    review: needsReview.length,
    today: getTodayAttentionCount(today),
    suggestions: (today.pending_suggestions || []).length,
    stalledProjects: stalledProjects.length,
  };

  return (
    <main className={styles.home}>
      <section className={styles.hero}>
        <div>
          <p className={styles.eyebrow}>Engram v4 Home</p>
          <h1>Run the system, then capture into it.</h1>
          <p className={styles.heroText}>
            Start with review and pressure, then move into projects or fresh capture.
          </p>
        </div>
        <div className={styles.heroStats}>
          <Link to="/suggestions" className={styles.statCard}>
            <strong>{summary.review}</strong>
            <span>need review</span>
          </Link>
          <Link to="/today" className={styles.statCard}>
            <strong>{summary.today}</strong>
            <span>need attention</span>
          </Link>
          <Link to="/projects" className={styles.statCard}>
            <strong>{projects.length}</strong>
            <span>active projects</span>
          </Link>
          <Link to="/inbox" className={styles.statCard}>
            <strong>{recent.length}</strong>
            <span>recent captures</span>
          </Link>
        </div>
      </section>

      <div className={styles.grid}>
        <HomeSection
          title="Needs review"
          hint="Notes with pending suggestions or incomplete AI processing."
          count={needsReview.length}
          action={<Link to="/inbox" className={styles.inlineLink}>Open inbox</Link>}
        >
          <EntityList items={needsReview.slice(0, 5)} fromState={fromState} />
        </HomeSection>

        <HomeSection
          title="Today"
          hint="Overdue, due, and follow-up work."
          count={actionableToday.length}
          action={<Link to="/today" className={styles.inlineLink}>Open today</Link>}
        >
          <EntityList items={actionableToday} fromState={fromState} />
        </HomeSection>

        <HomeSection
          title="Stuck"
          hint="Blocked or waiting work that needs movement."
          count={stuck.length + stalledProjects.length}
          action={<Link to="/today" className={styles.inlineLink}>Review blockers</Link>}
        >
          {stuck.length > 0 ? (
            <EntityList items={stuck} fromState={fromState} />
          ) : (
            <p className={styles.empty}>No blocked or waiting tasks.</p>
          )}
          {stalledProjects.length > 0 ? (
            <div className={styles.stalledBlock}>
              <p className={styles.subhead}>Projects missing a next task</p>
              <EntityList items={stalledProjects.slice(0, 4)} fromState={fromState} />
            </div>
          ) : null}
        </HomeSection>

        <HomeSection
          title="Active projects"
          hint="Current project surfaces worth revisiting."
          count={projects.length}
          action={<Link to="/projects" className={styles.inlineLink}>All projects</Link>}
        >
          <EntityList items={projects.slice(0, 6)} fromState={fromState} />
        </HomeSection>

        <HomeSection
          title="Recent captures"
          hint="Latest source notes saved into the system."
          count={recent.length}
          action={<Link to="/inbox" className={styles.inlineLink}>Capture more</Link>}
        >
          <EntityList items={recent.slice(0, 6)} fromState={fromState} />
        </HomeSection>
      </div>
    </main>
  );
}
