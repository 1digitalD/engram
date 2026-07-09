import { useCallback, useEffect, useMemo, useState } from 'react';
import { useOutletContext, useSearchParams } from 'react-router-dom';
import { v4API, friendlyApiError } from '../api/v4Client';
import CitationsList from '../components/CitationsList';
import { ACTION_LABELS, SURFACE_LABELS, itemTitle, sectionLabel } from './vocab';
import {
  DISMISS_REASONS,
  countPendingInReport,
  displayItemMeta,
  isResolvableItem,
} from './reviewUtils';
import { buildWeeklyDigest } from './weeklyDigest';
import styles from './ReviewSurface.module.css';

function ReviewItem({ item, suggestions, busy, onVerify, onEdit, onDismiss, onLater }) {
  const [dismissOpen, setDismissOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editValue, setEditValue] = useState(itemTitle(item));
  const meta = displayItemMeta(item, suggestions);

  if (!meta.resolvable) {
    return (
      <li className={styles.item}>
        <div className={styles.itemHeader}>
          <h3 className={styles.itemTitle}>{meta.title}</h3>
          <span className={styles.itemType}>{meta.typeLabel}</span>
        </div>
        {meta.evidence ? <p className={styles.itemEvidence}>{meta.evidence}</p> : null}
        <p className={styles.appliedNote}>Already applied — undo from Ledger in a later slice.</p>
      </li>
    );
  }

  return (
    <li className={styles.item}>
      <div className={styles.itemHeader}>
        <h3 className={styles.itemTitle}>{meta.title}</h3>
        <span className={styles.itemType}>{meta.typeLabel}</span>
      </div>
      {meta.evidence ? <p className={styles.itemEvidence}>{meta.evidence}</p> : null}

      {editOpen ? (
        <div className={styles.editForm}>
          <label htmlFor={`edit-${item.id}`}>Edit title</label>
          <input
            id={`edit-${item.id}`}
            className={styles.editInput}
            value={editValue}
            onChange={(event) => setEditValue(event.target.value)}
            disabled={busy}
          />
          <div className={styles.actions}>
            <button
              type="button"
              className={styles.buttonSecondary}
              disabled={busy}
              onClick={() => {
                setEditOpen(false);
                setEditValue(itemTitle(item));
              }}
            >
              Cancel
            </button>
            <button
              type="button"
              className={styles.buttonPrimary}
              disabled={busy || !editValue.trim()}
              onClick={() => onEdit(item.id, { title: editValue.trim() })}
            >
              Save edit
            </button>
          </div>
        </div>
      ) : dismissOpen ? (
        <div className={styles.dismissReasons}>
          <span>Dismiss reason:</span>
          <div className={styles.dismissReasonList} role="group" aria-label="Dismiss reason">
            {DISMISS_REASONS.map((reason) => (
              <button
                key={reason}
                type="button"
                className={styles.buttonSecondary}
                disabled={busy}
                onClick={() => {
                  onDismiss(item.id, reason);
                  setDismissOpen(false);
                }}
              >
                {reason}
              </button>
            ))}
            <button
              type="button"
              className={styles.buttonSecondary}
              disabled={busy}
              onClick={() => {
                onDismiss(item.id);
                setDismissOpen(false);
              }}
            >
              no reason
            </button>
          </div>
          <button
            type="button"
            className={styles.buttonSecondary}
            disabled={busy}
            onClick={() => setDismissOpen(false)}
          >
            Cancel
          </button>
        </div>
      ) : (
        <div className={styles.actions}>
          <button
            type="button"
            className={styles.buttonSecondary}
            disabled={busy}
            onClick={() => onLater(item.id)}
          >
            {ACTION_LABELS.later}
          </button>
          <button
            type="button"
            className={styles.buttonSecondary}
            disabled={busy}
            onClick={() => setDismissOpen(true)}
          >
            {ACTION_LABELS.dismiss}
          </button>
          <button
            type="button"
            className={styles.buttonSecondary}
            disabled={busy}
            onClick={() => setEditOpen(true)}
          >
            {ACTION_LABELS.edit}
          </button>
          <button
            type="button"
            className={styles.buttonPrimary}
            disabled={busy}
            onClick={() => onVerify(item.id)}
          >
            {ACTION_LABELS.verify}
          </button>
        </div>
      )}
    </li>
  );
}

export default function ReviewSurface() {
  const { refreshReviewCount } = useOutletContext() || {};
  const [searchParams, setSearchParams] = useSearchParams();
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
      const payload = await v4API.reports.list({ status: 'pending' });
      const rows = payload?.data || [];
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
    loadReportDetail(activeReportId);
  }, [activeReportId, loadReportDetail]);

  useEffect(() => {
    loadDigest();
  }, [loadDigest]);

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
  const digest = useMemo(
    () => buildWeeklyDigest(summaryPayload, briefPayload),
    [summaryPayload, briefPayload],
  );

  useEffect(() => {
    if (!digestDirty) {
      setDigestDraft(digest.text);
    }
  }, [digest.text, digestDirty]);

  async function afterResolve(reportId, metricsPayload = null) {
    await refreshReviewCount?.();
    const rows = await loadReports();
    const stillPending = rows.some((row) => row.id === reportId);
    if (stillPending) {
      await loadReportDetail(reportId);
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
        // Review completion should not fail because telemetry failed.
        void err;
      }
    }

    const nextId = rows[0]?.id || null;
    setActiveReportId(nextId);
    if (nextId) {
      setSearchParams({ report: nextId });
    } else {
      setSearchParams({});
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
    setSearchParams({ report: reportId });
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

  async function handleDigestCopy() {
    if (!digestDraft.trim()) return;
    try {
      await navigator.clipboard.writeText(digestDraft);
      setCopyNote('Digest copied.');
    } catch {
      setCopyNote('Copy failed. Select the draft and copy manually.');
    }
  }

  const sourceTitle = reportDetail?.source_note?.title || 'Stream entry';

  return (
    <div className={styles.surface}>
      <header className={styles.header}>
        <h1 className={styles.title}>{SURFACE_LABELS.review}</h1>
        <p className={styles.subtitle}>
          Distillation reports — verify proposals, edit inline, or accept remainder in one batch.
        </p>
      </header>

      {error ? (
        <div className={styles.error} role="alert">
          {error}
        </div>
      ) : null}

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

            <div className={styles.digestPreview}>
              {digest.sections.map((section) => (
                <section key={section.key} className={styles.section}>
                  <h3 className={styles.digestSectionTitle}>{section.title}</h3>
                  <ul className={styles.digestList}>
                    {section.lines.map((line) => (
                      <li key={`${section.key}-${line}`} className={styles.digestListItem}>
                        {line}
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
            </div>

            <CitationsList
              citations={digest.citations}
              emptyText="No digest citations available."
            />
          </>
        ) : null}
      </section>

      {loadingList ? (
        <p className={styles.empty}>Loading reports…</p>
      ) : reports.length === 0 ? (
        <p className={styles.empty}>No pending reports.</p>
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
                <span className={styles.queueTitle}>
                  {row.id === activeReportId && reportDetail?.source_note?.title
                    ? reportDetail.source_note.title
                    : `Report ${row.id.slice(0, 8)}`}
                </span>
                <span className={styles.queueMeta}>{row.status}</span>
              </button>
            ))}
          </div>

          {loadingDetail ? <p className={styles.empty}>Loading report…</p> : null}

          {!loadingDetail && reportDetail ? (
            <article className={styles.report} aria-label="Distillation report">
              <p className={styles.subtitle}>From: {sourceTitle}</p>
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
                          busy={busyItemId === item.id || acceptRestBusy}
                          onVerify={handleVerify}
                          onEdit={handleEdit}
                          onDismiss={handleDismiss}
                          onLater={handleLater}
                        />
                      ))}
                    </ul>
                  </section>
                );
              })}

              {pendingCount > 0 ? (
                <div className={styles.batchBar}>
                  <button
                    type="button"
                    className={styles.buttonPrimary}
                    disabled={acceptRestBusy || Boolean(busyItemId)}
                    onClick={handleAcceptRest}
                  >
                    {ACTION_LABELS.acceptRest} ({pendingCount})
                  </button>
                </div>
              ) : null}
            </article>
          ) : null}
        </>
      )}
    </div>
  );
}

export { isResolvableItem };
