import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { v4API } from '../api/v4Client';
import styles from './V4Home.module.css';

function ShortcutCard({ to, label, detail }) {
  return (
    <Link to={to} className={styles.shortcutCard}>
      <strong>{label}</strong>
      <span>{detail}</span>
    </Link>
  );
}

export default function V4Home() {
  const [state, setState] = useState({ summary: null, error: '' });

  useEffect(() => {
    let active = true;
    v4API.summary()
      .then((summary) => {
        if (!active) return;
        setState({ summary, error: '' });
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

  if (!state.summary) {
    return (
      <main className={styles.home}>
        <section className={styles.hero}>
          <h1>Home</h1>
          <p>Loading current state…</p>
        </section>
      </main>
    );
  }

  const { inbox_count: review, today_count: today, reviewed_today: reviewedToday } = state.summary;

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
            <strong>{review}</strong>
            <span>in review</span>
          </Link>
          <Link to="/today" className={styles.statCard}>
            <strong>{today}</strong>
            <span>need attention</span>
          </Link>
          <Link to="/today" className={styles.statCard}>
            <strong>{reviewedToday ? 'Yes' : 'No'}</strong>
            <span>day reviewed</span>
          </Link>
        </div>
      </section>

      <div className={styles.shortcutGrid}>
        <ShortcutCard
          to="/inbox"
          label="Capture"
          detail="Capture a note or jump into the inbox queue."
        />
        <ShortcutCard
          to="/suggestions"
          label="Clear review"
          detail={`${review} note${review === 1 ? '' : 's'} in review`}
        />
        <ShortcutCard
          to="/today"
          label="Run today"
          detail={`${today} item${today === 1 ? '' : 's'} need attention`}
        />
      </div>
    </main>
  );
}
