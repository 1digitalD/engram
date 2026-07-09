import { useCallback, useEffect, useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { v4API, friendlyApiError } from '../api/v4Client';
import { SURFACE_LABELS } from './vocab';
import styles from './NextShell.module.css';

const NAV_ITEMS = [
  { to: '/today', label: SURFACE_LABELS.today, disabled: false },
  { to: '/workboard', label: SURFACE_LABELS.workboard, disabled: false },
  { to: '/stream', label: SURFACE_LABELS.stream, disabled: false },
  { to: '/review', label: SURFACE_LABELS.review, disabled: false },
  { to: '/spaces', label: SURFACE_LABELS.spaces, disabled: false },
  { to: '/people', label: SURFACE_LABELS.people, disabled: false },
];

export default function NextShell({ onReviewCountChange }) {
  const navigate = useNavigate();
  const [captureValue, setCaptureValue] = useState('');
  const [omniQuery, setOmniQuery] = useState('');
  const [captureBusy, setCaptureBusy] = useState(false);
  const [captureStatus, setCaptureStatus] = useState('');
  const [captureError, setCaptureError] = useState('');
  const [reviewCount, setReviewCount] = useState(0);

  const refreshReviewCount = useCallback(async () => {
    try {
      const payload = await v4API.reports.list({ status: 'pending' });
      const count = payload?.meta?.total ?? (payload?.data?.length || 0);
      setReviewCount(count);
      onReviewCountChange?.(count);
    } catch {
      setReviewCount(0);
      onReviewCountChange?.(0);
    }
  }, [onReviewCountChange]);

  useEffect(() => {
    refreshReviewCount();
  }, [refreshReviewCount]);

  async function handleCaptureSubmit(event) {
    event.preventDefault();
    const content = captureValue.trim();
    if (!content || captureBusy) return;

    setCaptureBusy(true);
    setCaptureError('');
    setCaptureStatus('Capturing…');
    try {
      const payload = await v4API.capture({ content, mode: 'auto' });
      setCaptureValue('');
      setCaptureStatus('Captured.');
      await refreshReviewCount();
      if (payload?.report_id) {
        navigate(`/review?report=${encodeURIComponent(payload.report_id)}`);
      }
    } catch (err) {
      setCaptureError(friendlyApiError(err, 'Capture failed.'));
      setCaptureStatus('');
    } finally {
      setCaptureBusy(false);
    }
  }

  async function handleOmniSubmit(event) {
    event.preventDefault();
    const query = omniQuery.trim();
    if (!query) return;
    try {
      await v4API.search({ q: query, limit: 8 });
      setCaptureStatus(`Recall searched for “${query}”.`);
    } catch (err) {
      setCaptureError(friendlyApiError(err, 'Search failed.'));
    }
  }

  return (
    <div className={styles.shell} data-next-shell="true">
      <header className={styles.chrome}>
        <form className={styles.captureField} onSubmit={handleCaptureSubmit}>
          <input
            className={styles.captureInput}
            type="text"
            value={captureValue}
            onChange={(event) => setCaptureValue(event.target.value)}
            placeholder="＋ Set something down…"
            aria-label="Capture"
            disabled={captureBusy}
          />
        </form>

        <form className={styles.omniBar} onSubmit={handleOmniSubmit}>
          <input
            className={styles.omniInput}
            type="search"
            value={omniQuery}
            onChange={(event) => setOmniQuery(event.target.value)}
            placeholder="⌕ Recall anything…"
            aria-label="Recall search"
          />
        </form>

        <NavLink
          to="/review"
          className={({ isActive }) => `${styles.pulse} ${isActive ? styles.pulseActive : ''}`}
          aria-label={`${SURFACE_LABELS.review}${reviewCount ? `, ${reviewCount} pending reports` : ''}`}
        >
          <span>{SURFACE_LABELS.review}</span>
          {reviewCount > 0 ? (
            <span className={styles.pulseCount} aria-hidden="true">{reviewCount}</span>
          ) : null}
        </NavLink>

        {captureStatus ? <span className={styles.status}>{captureStatus}</span> : null}
        {captureError ? <span className={styles.error} role="alert">{captureError}</span> : null}
      </header>

      <nav className={styles.nav} aria-label="Primary">
        {NAV_ITEMS.map(({ to, label, disabled }) => (
          disabled ? (
            <span key={to} className={styles.navLinkDisabled} aria-disabled="true">{label}</span>
          ) : (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `${styles.navLink} ${isActive ? styles.navLinkActive : ''}`}
            >
              {label}
            </NavLink>
          )
        ))}
      </nav>

      <main className={styles.main}>
        <Outlet context={{ refreshReviewCount }} />
      </main>
    </div>
  );
}
