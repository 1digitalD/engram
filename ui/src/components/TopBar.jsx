import { useEffect, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { Moon, Plus, Sparkles, Sun, Snowflake } from 'lucide-react';
import { legacyPath } from '../legacy/legacyPaths';
import styles from './TopBar.module.css';

const themeOptions = [
  ['light', 'Light', Sun],
  ['dark', 'Dark', Moon],
  ['glass', 'Glass', Sparkles],
  ['frost', 'Frost', Snowflake],
];

const lenses = [
  [legacyPath('/now'), 'Now'],
  [legacyPath('/threads'), 'Threads'],
  [legacyPath('/memory'), 'Memory'],
  [legacyPath('/recall'), 'Recall'],
];

function getInitialTheme() {
  try {
    const saved = localStorage.getItem('engram-theme');
    if (themeOptions.some(([value]) => value === saved)) return saved;
  } catch { /* localStorage unavailable */ }
  if (typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return 'dark';
  }
  return 'light';
}

function classNames(...parts) {
  return parts.filter(Boolean).join(' ');
}

function ThemeSwitcher({ theme, onChoose }) {
  return (
    <div className={styles.themeSwitcher} role="group" aria-label="Theme">
      {themeOptions.map(([value, label, Icon]) => (
        <button
          key={value}
          type="button"
          aria-pressed={theme === value}
          title={`${label} theme`}
          aria-label={`${label} theme`}
          className={classNames(
            styles.themeOption,
            theme === value && styles.themeOptionActive,
          )}
          onClick={() => onChoose(value)}
        >
          <Icon size={14} strokeWidth={2} aria-hidden="true" />
        </button>
      ))}
    </div>
  );
}

function TrustChip({ score }) {
  let sentiment = styles.trustHigh;
  if (score < 50) sentiment = styles.trustLow;
  else if (score < 80) sentiment = styles.trustMedium;

  return (
    <span className={styles.trustChip} title={`Trust score: ${score}%`}>
      <span className={styles.trustLabel}>Trust</span>
      <span className={classNames(styles.trustValue, sentiment)}>{score}%</span>
    </span>
  );
}

export default function TopBar({
  trustScore = null,
  onAsk,
  onRecall,
  onReview,
  nowCount,
  threadsCount,
  recallCount,
  suggestionsCount = 0,
}) {
  const location = useLocation();
  const [theme, setTheme] = useState(getInitialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  function chooseTheme(value) {
    setTheme(value);
    try {
      localStorage.setItem('engram-theme', value);
    } catch { /* localStorage unavailable */ }
  }

  const counts = {
    [legacyPath('/now')]: nowCount,
    [legacyPath('/threads')]: threadsCount,
    [legacyPath('/recall')]: recallCount,
  };

  const nowPath = legacyPath('/now');
  const recallPath = legacyPath('/recall');

  return (
    <header className={styles.bar} role="banner">
      <NavLink to={nowPath} className={styles.brand} aria-label="Engram home">
        <span className={styles.brandGlyph} aria-hidden="true">◈</span>
      </NavLink>

      <nav className={styles.lenses} aria-label="Lenses">
        {lenses.map(([to, label]) => {
          const isActive = location.pathname === to
            || (to !== nowPath && to !== recallPath && location.pathname.startsWith(to));
          const count = counts[to];
          const isRecall = to === recallPath && onRecall;
          const children = (
            <>
              <span className={styles.lensLabel}>{label}</span>
              {count !== undefined && count !== null ? (
                <span className={styles.lensCount}>{count}</span>
              ) : null}
            </>
          );
          if (isRecall) {
            return (
              <button
                key={to}
                type="button"
                className={classNames(styles.lens, styles.lensButton)}
                onClick={onRecall}
                aria-label="Open Recall"
              >
                {children}
              </button>
            );
          }
          return (
            <NavLink
              key={to}
              to={to}
              aria-current={isActive ? 'page' : undefined}
              className={classNames(styles.lens, isActive && styles.lensActive)}
            >
              {children}
            </NavLink>
          );
        })}
      </nav>

      <NavLink
        to={legacyPath('/lab')}
        className={({ isActive }) => (
          `${styles.labLink} ${isActive ? styles.labLinkActive : ''}`.trim()
        )}
      >
        Try the redesign (beta)
      </NavLink>

      <div className={styles.spacer} />

      <button
        type="button"
        className={styles.askButton}
        onClick={onAsk}
        aria-label="Ask Engram"
      >
        <Plus size={16} strokeWidth={2.4} aria-hidden="true" />
        <span className={styles.askLabel}>Ask</span>
        <span className={styles.askGlyph} aria-hidden="true">✦</span>
      </button>

      {suggestionsCount > 0 && onReview ? (
        <button
          type="button"
          className={styles.reviewButton}
          onClick={onReview}
          aria-label={`Review ${suggestionsCount} pending suggestion${suggestionsCount === 1 ? '' : 's'}`}
        >
          <span className={styles.reviewLabel}>Review</span>
          <span className={styles.reviewCount}>{suggestionsCount}</span>
        </button>
      ) : null}

      {trustScore != null && <TrustChip score={trustScore} />}

      <ThemeSwitcher theme={theme} onChoose={chooseTheme} />
    </header>
  );
}
