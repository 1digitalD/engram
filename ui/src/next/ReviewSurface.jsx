import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useOutletContext, useSearchParams } from 'react-router-dom';
import { v4API, friendlyApiError } from '../api/v4Client';
import CitationsList from '../components/CitationsList';
import ReviewItem from './ReviewItem';
import { ACTION_LABELS, SURFACE_LABELS, sectionLabel } from './vocab';
import {
  citationEntityPath,
  countPendingInReport,
  fetchReviewQueueReports,
  isResolvableItem,
  reportQueueTitle,
  reportStatusLabel,
} from './reviewUtils';
import { buildWeeklyDigest } from './weeklyDigest';
import styles from './ReviewSurface.module.css';

const REVIEW_TABS = [
  { id: 'captures', label: 'Captures' },
  { id: 'digest', label: 'Weekly digest' },
];

function tabFromParams(searchParams) {
  const tab = searchParams.get('tab');
  return tab === 'digest' ? 'digest' : 'captures';
}

export default function ReviewSurface() {
  const navigate = useNavigate();
  const { refreshReviewCount } = useOutletContext() || {};
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = tabFromParams(searchParams);

  const [reports, setReports] = useState([]);
  const [activeReportId, setActiveReportId] = useState(null);
  const [reportDetail, setReportDetail] = useState(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [loadingDigest, setLoadingDigest] = useState(true);
  const [error, setError] = useState('');
  const [digestError, setDigestError] = useState('');
  const [busyItemId, setBusyItemId] = useState(null);
  const [acceptRestBusy, setAcceptRestBusy] = useState(false);
  const [markDoneBusy, setMarkDoneBusy] = useState(false);
  const [undoBusy, setUndoBusy] = useState(false);
  const [createSpaceBusy, setCreateSpaceBusy] = useState(false);
  const [createSpaceTitle, setCreateSpaceTitle] = useState('');
  const [reviewStartedAt, setReviewStartedAt] = useState(null);
  const [summaryPayload, setSummaryPayload] = useState(null);
  const [briefPayload, setBriefPayload] = useState(null);
  const [digestDraft, setDigestDraft] = useState('');
  const [digestDirty, setDigestDirty] = useState(false);
  const [copyNote, setCopyNote] = useState('');

  const loadReports = useCallback(async () => {
    setLoadingList(true);
    setError('');
    try {
      const { rows } = await fetchReviewQueueReports(v4API.reports);
      setReports(rows);
      return rows;
    } catch (err) {
      setError(friendlyApiError(err, 'Could not load reports.'));
      setReports([]);
      return [];
    } finally {
      setLoadingList(false);
    }
  }, []);

  const loadReportDetail = useCallback(async (reportId) => {
    if (!reportId) {
      setReportDetail(null);
      return;
    }
    setLoadingDetail(true);
    setError('');
    try {
      const payload = await v4API.reports.get(reportId);
      setReportDetail(payload);
      setCreateSpaceTitle(payload?.source_note?.title || '');
    } catch (err) {
      setError(friendlyApiError(err, 'Could not load report.'));
      setReportDetail(null);
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  const loadDigest = useCallback(async () => {
    setLoadingDigest(true);
    setDigestError('');
    try {
      const [summaryResponse, briefResponse] = await Promise.all([v4API.summary(), v4API.brief()]);
      setSummaryPayload(summaryResponse || null);
      setBriefPayload(briefResponse || null);
    } catch (err) {
      setDigestError(friendlyApiError(err, 'Could not load weekly digest.'));
      setSummaryPayload(null);
      setBriefPayload(null);
    } finally {
      setLoadingDigest(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      const rows = await loadReports();
      if (!active) return;
      const fromQuery = searchParams.get('report');
      const nextId =
        fromQuery && rows.some((row) => row.id === fromQuery) ? fromQuery : rows[0]?.id || null;
      setActiveReportId(nextId);
    })();
    return () => {
      active = false;
    };
  }, [loadReports, searchParams]);

  useEffect(() => {
    if (activeTab === 'captures') {
      loadReportDetail(activeReportId);
    }
  }, [activeReportId, activeTab, loadReportDetail]);

  useEffect(() => {
    if (activeTab === 'digest') {
      loadDigest();
    }
  }, [activeTab, loadDigest]);

  useEffect(() => {
    setReviewStartedAt(null);
  }, [activeReportId]);

  useEffect(() => {
    if (!activeReportId) {
      setReviewStartedAt(null);
      return;
    }
    if (reportDetail?.data?.id === activeReportId) {
      setReviewStartedAt((current) => current ?? Date.now());
    }
  }, [activeReportId, reportDetail]);

  const suggestions = reportDetail?.suggestions || [];
  const narrative = reportDetail?.data?.narrative || {};
  const sections = narrative.sections || [];
  const pendingCount = useMemo(() => countPendingInReport(suggestions), [suggestions]);
  const canUndoReviewBatch = Boolean(reportDetail?.data?.reviewed_at);
  const digest = useMemo(
    () => buildWeeklyDigest(summaryPayload, briefPayload),
    [summaryPayload, briefPayload],
  );

  useEffect(() => {
    if (!digestDirty) {
      setDigestDraft(digest.text);
    }
  }, [digest.text, digestDirty]);

  function updateSearchParams(patch) {
    const next = new URLSearchParams(searchParams);
    Object.entries(patch).forEach(([key, value]) => {
      if (value === null || value === undefined || value === '') {
        next.delete(key);
      } else {
        next.set(key, value);
      }
    });
    setSearchParams(next);
  }

  function selectTab(tabId) {
    updateSearchParams({ tab: tabId === 'captures' ? null : tabId });
    if (tabId === 'digest') {
      loadDigest();
    }
  }

  async function afterResolve(reportId, metricsPayload = null) {
    await refreshReviewCount?.();
    const rows = await loadReports();
    const stillInQueue = rows.some((row) => row.id === reportId);
    if (stillInQueue) {
      await loadReportDetail(reportId);
      setActiveReportId(reportId);
      updateSearchParams({ report: reportId });
      return;
    }

    if (metricsPayload?.durationMs != null) {
      try {
        await v4API.metrics.recordReview({
          report_id: reportId,
          duration_ms: metricsPayload.durationMs,
          suggestion_count: metricsPayload.suggestionCount,
        });
      } catch (err) {
        void err;
      }
    }

    const nextId = rows[0]?.id || null;
    setActiveReportId(nextId);
    if (nextId) {
      updateSearchParams({ report: nextId });
    } else {
      updateSearchParams({ report: null });
      setReportDetail(null);
    }
    setReviewStartedAt(null);
  }

  async function resolveDecision(reportId, decision) {
    setBusyItemId(decision.suggestion_id);
    setError('');
    const metricsPayload =
      reviewStartedAt == null
        ? null
        : {
            durationMs: Math.max(0, Date.now() - reviewStartedAt),
            suggestionCount: pendingCount,
          };
    try {
      await v4API.reports.resolve(reportId, { decisions: [decision] });
      await afterResolve(reportId, metricsPayload);
    } catch (err) {
      setError(friendlyApiError(err, 'Could not apply action.'));
    } finally {
      setBusyItemId(null);
    }
  }

  function handleSelectReport(reportId) {
    setActiveReportId(reportId);
    updateSearchParams({ report: reportId });
    setReviewStartedAt(null);
  }

  function handleVerify(suggestionId) {
    if (!activeReportId) return;
    resolveDecision(activeReportId, { suggestion_id: suggestionId, action: 'accept' });
  }

  function handleEdit(suggestionId, edits) {
    if (!activeReportId) return;
    resolveDecision(activeReportId, { suggestion_id: suggestionId, action: 'edit', edits });
  }

  function handleDismiss(suggestionId, dismissalReason) {
    if (!activeReportId) return;
    const decision = { suggestion_id: suggestionId, action: 'dismiss' };
    if (dismissalReason) decision.dismissal_reason = dismissalReason;
    resolveDecision(activeReportId, decision);
  }

  function handleLater(suggestionId) {
    if (!activeReportId) return;
    resolveDecision(activeReportId, { suggestion_id: suggestionId, action: 'later' });
  }

  async function handleAcceptRest() {
    if (!activeReportId || acceptRestBusy) return;
    setAcceptRestBusy(true);
    setError('');
    const metricsPayload =
      reviewStartedAt == null
        ? null
        : {
            durationMs: Math.max(0, Date.now() - reviewStartedAt),
            suggestionCount: pendingCount,
          };
    try {
      await v4API.reports.resolve(activeReportId, { decisions: [], accept_rest: true });
      await afterResolve(activeReportId, metricsPayload);
    } catch (err) {
      setError(friendlyApiError(err, 'Could not accept remainder.'));
    } finally {
      setAcceptRestBusy(false);
    }
  }

  async function handleMarkDone() {
    if (!activeReportId || markDoneBusy) return;
    setMarkDoneBusy(true);
    setError('');
    const metricsPayload =
      reviewStartedAt == null
        ? null
        : {
            durationMs: Math.max(0, Date.now() - reviewStartedAt),
            suggestionCount: pendingCount,
          };
    try {
      await v4API.reports.markDone(activeReportId);
      await afterResolve(activeReportId, metricsPayload);
    } catch (err) {
      setError(friendlyApiError(err, 'Could not mark capture done.'));
    } finally {
      setMarkDoneBusy(false);
    }
  }

  async function handleUndoReviewBatch() {
    if (!activeReportId || undoBusy) return;
    setUndoBusy(true);
    setError('');
    try {
      await v4API.reports.undo(activeReportId);
      await refreshReviewCount?.();
      await loadReports();
      await loadReportDetail(activeReportId);
      setActiveReportId(activeReportId);
    } catch (err) {
      setError(friendlyApiError(err, 'Could not undo review batch.'));
    } finally {
      setUndoBusy(false);
    }
  }

  async function handleUndoApplied(eventId) {
    if (!eventId || busyItemId) return;
    setBusyItemId(eventId);
    setError('');
    try {
      await v4API.events.revert(eventId);
      if (activeReportId) {
        await loadReportDetail(activeReportId);
      }
    } catch (err) {
      setError(friendlyApiError(err, 'Could not undo applied change.'));
    } finally {
      setBusyItemId(null);
    }
  }

  async function handleCreateSpace() {
    const note = reportDetail?.source_note;
    if (!note?.id || createSpaceBusy) return;
    const title = createSpaceTitle.trim() || note.title || 'New Space';
    setCreateSpaceBusy(true);
    setError('');
    try {
      const created = await v4API.entities.create({
        type: 'project',
        title,
        lifecycle: 'active',
        source: 'user',
      });
      const space = created?.data || created;
      await v4API.entities.createLink(note.id, {
        target_id: space.id,
        relationship_type: 'related',
      });
      navigate(`/spaces/${space.id}`);
    } catch (err) {
      setError(friendlyApiError(err, 'Could not create Space.'));
    } finally {
      setCreateSpaceBusy(false);
    }
  }

  async function handleDigestCopy() {
    if (!digestDraft.trim()) return;
    try {
      await navigator.clipboard.writeText(digestDraft);
      setCopyNote('Digest copied.');
    } catch {
      setCopyNote('Copy failed. Select the draft and copy manually.');
    }
  }

  function handleCitationOpen(citation) {
    const path = citationEntityPath(citation);
    if (path) navigate(path);
  }

  const sourceNote = reportDetail?.source_note;
  const sourceTitle = sourceNote?.title || 'Stream entry';

  return (
    <div className={styles.surface}>
      <header className={styles.header}>
        <h1 className={styles.title}>{SURFACE_LABELS.review}</h1>
        <p className={styles.subtitle}>
          Verify proposals, undo auto-applied changes, or finish captures when nothing is left.
        </p>
      </header>

      <div className={styles.tabs} role="tablist" aria-label="Review sections">
        {REVIEW_TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            className={`${styles.tab} ${activeTab === tab.id ? styles.tabActive : ''}`}
            onClick={() => selectTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {error ? (
        <div className={styles.error} role="alert">
          {error}
        </div>
      ) : null}

      {activeTab === 'captures' ? (
        <>
          {loadingList ? (
            <p className={styles.empty}>Loading reports…</p>
          ) : reports.length === 0 ? (
            <p className={styles.empty}>No pending capture reports.</p>
          ) : (
            <>
              <div className={styles.queue} aria-label="Pending reports">
                {reports.map((row) => (
                  <button
                    key={row.id}
                    type="button"
                    className={`${styles.queueItem} ${row.id === activeReportId ? styles.queueItemActive : ''}`}
                    onClick={() => handleSelectReport(row.id)}
                  >
                    <span className={styles.queueTitle}>{reportQueueTitle(row)}</span>
                    <span className={styles.queueMeta}>{reportStatusLabel(row)}</span>
                  </button>
                ))}
              </div>

              {loadingDetail ? <p className={styles.empty}>Loading report…</p> : null}

              {!loadingDetail && reportDetail ? (
                <article className={styles.report} aria-label="Distillation report">
                  <div className={styles.reportHeader}>
                    <p className={styles.subtitle}>
                      From:{' '}
                      {sourceNote?.id ? (
                        <Link className={styles.sourceLink} to={`/stream?note=${encodeURIComponent(sourceNote.id)}`}>
                          {sourceTitle}
                        </Link>
                      ) : (
                        sourceTitle
                      )}
                    </p>
                  </div>

                  {sections.map((section) => {
                    const items = (section.items || []).filter(
                      (item) => item.kind !== 'routing_summary' || section.name === 'routing_summary',
                    );
                    if (!items.length) return null;
                    return (
                      <section key={section.name} className={styles.section}>
                        <h2 className={styles.sectionTitle}>{sectionLabel(section.name)}</h2>
                        <ul className={styles.itemList}>
                          {items.map((item) => (
                            <ReviewItem
                              key={`${section.name}-${item.id || item.event_id || item.title}`}
                              item={item}
                              suggestions={suggestions}
                              busy={busyItemId === item.id || busyItemId === item.event_id || acceptRestBusy}
                              onVerify={handleVerify}
                              onEdit={handleEdit}
                              onDismiss={handleDismiss}
                              onLater={handleLater}
                              onUndoApplied={handleUndoApplied}
                            />
                          ))}
                        </ul>
                      </section>
                    );
                  })}

                  <section className={styles.createSpacePanel} aria-label="Create Space from capture">
                    <h2 className={styles.sectionTitle}>Missing a Space?</h2>
                    <p className={styles.appliedNote}>
                      If this capture should have created a Space, add one here and link it to the source note.
                    </p>
                    <label htmlFor="create-space-title">Space title</label>
                    <input
                      id="create-space-title"
                      className={styles.editInput}
                      value={createSpaceTitle}
                      onChange={(event) => setCreateSpaceTitle(event.target.value)}
                      disabled={createSpaceBusy}
                    />
                    <div className={styles.actions}>
                      <button
                        type="button"
                        className={styles.buttonPrimary}
                        disabled={createSpaceBusy || !createSpaceTitle.trim()}
                        onClick={handleCreateSpace}
                      >
                        {ACTION_LABELS.createSpace}
                      </button>
                    </div>
                  </section>

                  <div className={styles.batchBar}>
                    {pendingCount > 0 ? (
                      <button
                        type="button"
                        className={styles.buttonPrimary}
                        disabled={acceptRestBusy || Boolean(busyItemId) || markDoneBusy}
                        onClick={handleAcceptRest}
                      >
                        {ACTION_LABELS.acceptRest} ({pendingCount})
                      </button>
                    ) : (
                      <button
                        type="button"
                        className={styles.buttonPrimary}
                        disabled={markDoneBusy || Boolean(busyItemId) || acceptRestBusy}
                        onClick={handleMarkDone}
                      >
                        {ACTION_LABELS.markDone}
                      </button>
                    )}
                    {canUndoReviewBatch ? (
                      <button
                        type="button"
                        className={styles.buttonSecondary}
                        disabled={undoBusy || Boolean(busyItemId)}
                        onClick={handleUndoReviewBatch}
                      >
                        {ACTION_LABELS.undoReview}
                      </button>
                    ) : null}
                  </div>
                </article>
              ) : null}
            </>
          )}
        </>
      ) : (
        <section className={styles.digest} aria-label="Weekly digest">
          <div className={styles.digestHeader}>
            <div>
              <h2 className={styles.sectionTitle}>Weekly digest</h2>
              <p className={styles.digestMeta}>
                {digest.generatedAt
                  ? `Generated ${new Date(digest.generatedAt).toLocaleDateString('en-US', {
                      month: 'short',
                      day: 'numeric',
                    })}.`
                  : 'Generated from current summary and brief.'}
              </p>
            </div>
            <div className={styles.actions}>
              <button
                type="button"
                className={styles.buttonSecondary}
                onClick={() => {
                  setDigestDraft(digest.text);
                  setDigestDirty(false);
                  setCopyNote('');
                }}
                disabled={loadingDigest || !digestDraft}
              >
                Reset
              </button>
              <button
                type="button"
                className={styles.buttonPrimary}
                onClick={handleDigestCopy}
                disabled={loadingDigest || !digestDraft.trim()}
              >
                Copy digest
              </button>
            </div>
          </div>

          {digestError ? (
            <div className={styles.error} role="alert">
              {digestError}
            </div>
          ) : null}

          {loadingDigest ? <p className={styles.empty}>Loading weekly digest…</p> : null}

          {!loadingDigest && !digestError ? (
            <>
              <textarea
                aria-label="Weekly digest draft"
                className={styles.digestEditor}
                value={digestDraft}
                onChange={(event) => {
                  setDigestDraft(event.target.value);
                  setDigestDirty(true);
                  setCopyNote('');
                }}
              />

              {copyNote ? (
                <p className={styles.appliedNote} aria-live="polite">
                  {copyNote}
                </p>
              ) : null}

              <CitationsList
                citations={digest.citations}
                onOpen={handleCitationOpen}
                emptyText="No digest citations available."
              />
            </>
          ) : null}
        </section>
      )}
    </div>
  );
}

export { isResolvableItem };
