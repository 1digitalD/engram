import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { v4API, friendlyApiError } from '../api/v4Client';
import RecallPanel from './RecallPanel';
import CaptureComposer from './CaptureComposer';
import NextLegacyProviders from './NextLegacyProviders';
import { fetchReviewQueueReports, reportQueueTitle, reportStatusLabel } from './reviewUtils';
import { recallEntityPath } from './recallUtils';
import useRecallSearch from './useRecallSearch';
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

const BROWSE_NAV_ITEMS = [
  { to: '/notes', label: SURFACE_LABELS.notes },
  { to: '/tasks', label: SURFACE_LABELS.tasks },
  { to: '/projects', label: SURFACE_LABELS.projects },
  { to: '/areas', label: SURFACE_LABELS.areas },
  { to: '/resources', label: SURFACE_LABELS.references },
];

function pulseActivityLabel(item) {
  if (item?.entity?.title) return item.entity.title;
  if (item?.reason) return item.reason;
  return 'Agent activity';
}

function formatPulseCategory(category) {
  if (category === 'auto_applied') return 'Auto-applied';
  if (category === 'suggested') return 'Suggested';
  if (category === 'failed') return 'Failed';
  if (category === 'review_action') return 'Review action';
  return category || 'Activity';
}

export default function NextShell({ onReviewCountChange }) {
  const navigate = useNavigate();
  const pulseRef = useRef(null);
  const recallRef = useRef(null);
  const [quickCapture, setQuickCapture] = useState('');
  const [captureValue, setCaptureValue] = useState('');
  const [captureOpen, setCaptureOpen] = useState(false);
  const [omniQuery, setOmniQuery] = useState('');
  const [recallOpen, setRecallOpen] = useState(false);
  const [selectedRecallIndex, setSelectedRecallIndex] = useState(0);
  const [captureBusy, setCaptureBusy] = useState(false);
  const [captureStatus, setCaptureStatus] = useState('');
  const [captureError, setCaptureError] = useState('');
  const [reviewCount, setReviewCount] = useState(0);
  const [reviewQueue, setReviewQueue] = useState([]);
  const [activityItems, setActivityItems] = useState([]);
  const [pulseOpen, setPulseOpen] = useState(false);
  const { results: recallResults, loading: recallLoading, error: recallError } = useRecallSearch(
    recallOpen ? omniQuery : '',
  );

  const refreshPulse = useCallback(async () => {
    const [reportsResult, activityResult] = await Promise.allSettled([
      fetchReviewQueueReports(v4API.reports),
      v4API.agentActivity({ limit: 8 }),
    ]);

    if (reportsResult.status === 'fulfilled') {
      const { rows, total } = reportsResult.value;
      setReviewCount(total);
      setReviewQueue(rows);
      onReviewCountChange?.(total);
    } else {
      setReviewCount(0);
      setReviewQueue([]);
      onReviewCountChange?.(0);
    }

    if (activityResult.status === 'fulfilled') {
      setActivityItems(activityResult.value?.data || []);
    } else {
      setActivityItems([]);
    }
  }, [onReviewCountChange]);

  useEffect(() => {
    refreshPulse();
  }, [refreshPulse]);

  useEffect(() => {
    if (!pulseOpen) return undefined;

    function handlePointerDown(event) {
      if (pulseRef.current && !pulseRef.current.contains(event.target)) {
        setPulseOpen(false);
      }
    }

    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        setPulseOpen(false);
      }
    }

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [pulseOpen]);

  async function runCapture(content) {
    setCaptureBusy(true);
    setCaptureError('');
    setCaptureStatus('Capturing…');
    try {
      const payload = await v4API.capture({ content, mode: 'auto' });
      setQuickCapture('');
      setCaptureValue('');
      setCaptureOpen(false);
      setCaptureStatus('Captured.');
      await refreshPulse();
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

  async function handleQuickCaptureSubmit() {
    const content = quickCapture.trim();
    if (!content || captureBusy) return;
    await runCapture(content);
  }

  async function handleCaptureSubmit() {
    const content = captureValue.trim();
    if (!content || captureBusy) return;
    await runCapture(content);
  }

  useEffect(() => {
    setSelectedRecallIndex(0);
  }, [omniQuery, recallResults.length]);

  useEffect(() => {
    if (!recallOpen) return undefined;

    function handlePointerDown(event) {
      if (recallRef.current && !recallRef.current.contains(event.target)) {
        setRecallOpen(false);
      }
    }

    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        setRecallOpen(false);
        setOmniQuery('');
      }
    }

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [recallOpen]);

  const openRecallResult = useCallback((entity) => {
    const path = recallEntityPath(entity);
    setRecallOpen(false);
    setOmniQuery('');
    if (path) navigate(path);
  }, [navigate]);

  function handleRecallKeyDown(event) {
    if (!recallOpen || recallResults.length === 0) return;
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setSelectedRecallIndex((index) => (index + 1) % recallResults.length);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setSelectedRecallIndex((index) => (index - 1 + recallResults.length) % recallResults.length);
    } else if (event.key === 'Enter') {
      event.preventDefault();
      const entity = recallResults[selectedRecallIndex];
      if (entity) openRecallResult(entity);
    }
  }

  async function handleOmniSubmit(event) {
    event.preventDefault();
    const query = omniQuery.trim();
    if (!query) return;
    if (recallResults[selectedRecallIndex]) {
      openRecallResult(recallResults[selectedRecallIndex]);
      return;
    }
    setRecallOpen(true);
  }

  const runningCount = 0;
  const reportLabel = reviewCount === 1 ? 'report' : 'reports';
  const pulseSummary = `✦ ${runningCount} running · ${reviewCount} ${reportLabel}`;
  const pulseAriaLabel = `Pulse: ${runningCount} running, ${reviewCount} capture ${reportLabel} to review`;

  return (
    <NextLegacyProviders onSummaryRefresh={refreshPulse}>
      <div className={styles.shell} data-next-shell="true">
      <div className={styles.stickyChrome}>
        <header className={styles.chrome}>
          <CaptureComposer
            open={captureOpen}
            onOpenChange={setCaptureOpen}
            quickValue={quickCapture}
            onQuickChange={setQuickCapture}
            onQuickSubmit={handleQuickCaptureSubmit}
            value={captureValue}
            onChange={setCaptureValue}
            onSubmit={handleCaptureSubmit}
            busy={captureBusy}
            error={captureError}
          />

          <div className={styles.omniWrap} ref={recallRef}>
            <form className={styles.omniBar} onSubmit={handleOmniSubmit}>
              <input
                className={styles.omniInput}
                type="search"
                value={omniQuery}
                onChange={(event) => {
                  setOmniQuery(event.target.value);
                  setRecallOpen(true);
                }}
                onFocus={() => setRecallOpen(true)}
                onKeyDown={handleRecallKeyDown}
                placeholder="⌕ Recall anything…"
                aria-label="Recall search"
                aria-expanded={recallOpen && Boolean(omniQuery.trim())}
                aria-controls="recall-results"
                autoComplete="off"
              />
            </form>
            {recallOpen && omniQuery.trim() ? (
              <RecallPanel
                query={omniQuery}
                results={recallResults}
                loading={recallLoading}
                error={recallError}
                selectedIndex={selectedRecallIndex}
                onSelect={openRecallResult}
                onHover={setSelectedRecallIndex}
              />
            ) : null}
          </div>

          <div className={styles.pulseWrap} ref={pulseRef}>
            <button
              type="button"
              className={`${styles.pulse} ${pulseOpen ? styles.pulseActive : ''}`}
              aria-label={pulseAriaLabel}
              aria-expanded={pulseOpen}
              aria-haspopup="dialog"
              onClick={() => setPulseOpen((open) => !open)}
            >
              <span>{pulseSummary}</span>
              {reviewCount > 0 ? (
                <span className={styles.pulseCount} aria-hidden="true">{reviewCount}</span>
              ) : null}
            </button>

            {pulseOpen ? (
              <div className={styles.pulsePeek} role="dialog" aria-label="Pulse activity peek">
                <p className={styles.pulsePeekTitle}>Capture reports</p>
                {reviewQueue.length > 0 ? (
                  <ul className={styles.pulsePeekList}>
                    {reviewQueue.slice(0, 5).map((row) => (
                      <li key={row.id} className={styles.pulsePeekItem}>
                        <Link
                          className={styles.pulsePeekLink}
                          to={`/review?report=${encodeURIComponent(row.id)}`}
                          onClick={() => setPulseOpen(false)}
                        >
                          {reportQueueTitle(row)}
                        </Link>
                        <span className={styles.pulsePeekMeta}>{reportStatusLabel(row)}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className={styles.pulsePeekEmpty}>No pending capture reports.</p>
                )}

                <p className={styles.pulsePeekTitle}>Recent agent activity</p>
                {activityItems.length > 0 ? (
                  <ul className={styles.pulsePeekList}>
                    {activityItems.slice(0, 5).map((item) => (
                      <li key={item.id || `${item.category}-${item.created_at}`} className={styles.pulsePeekItem}>
                        <span>{pulseActivityLabel(item)}</span>
                        <span className={styles.pulsePeekMeta}>{formatPulseCategory(item.category)}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className={styles.pulsePeekEmpty}>No recent agent activity.</p>
                )}
                <div className={styles.pulsePeekFooter}>
                  <Link className={styles.pulsePeekLink} to="/review" onClick={() => setPulseOpen(false)}>
                    Open Review
                  </Link>
                </div>
              </div>
            ) : null}
          </div>
        </header>

        {captureStatus || captureError ? (
          <div className={styles.chromeStatus}>
            {captureStatus ? <span className={styles.status}>{captureStatus}</span> : null}
            {captureError ? <span className={styles.error} role="alert">{captureError}</span> : null}
          </div>
        ) : null}

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

        <nav className={styles.browseNav} aria-label="Browse entities">
          <span className={styles.browseNavLabel}>Browse</span>
          {BROWSE_NAV_ITEMS.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `${styles.navLink} ${isActive ? styles.navLinkActive : ''}`}
            >
              {label}
            </NavLink>
          ))}
        </nav>
      </div>

      <main className={styles.main}>
        <Outlet context={{ refreshReviewCount: refreshPulse }} />
      </main>
      </div>
    </NextLegacyProviders>
  );
}
