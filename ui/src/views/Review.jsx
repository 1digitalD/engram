import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Calendar,
  Inbox,
  CheckCircle,
  Clock,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ListTodo,
  Sparkles,
  Link2,
  Loader2,
} from 'lucide-react';
import useStore from '../stores/useStore';
import { summariesAPI, proposalsAPI } from '../api/engram';
import NoteCard from '../components/notes/NoteCard';
import styles from './Review.module.css';

const GRANULARITIES = ['DAILY', 'WEEKLY', 'MONTHLY'];
const SUMMARY_PREVIEW_CHARS = 400;

/** Local calendar YYYY-MM-DD */
function isoDateLocal(d = new Date()) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/** Monday-start week; returns [start, end) in local time */
function weeklyRange(isoDay) {
  const [yo, mo, doy] = isoDay.split('-').map(Number);
  const date = new Date(yo, mo - 1, doy, 12, 0, 0, 0);
  const day = date.getDay();
  const diffToMon = date.getDate() - day + (day === 0 ? -6 : 1);
  const monday = new Date(date.getFullYear(), date.getMonth(), diffToMon, 0, 0, 0, 0);
  const end = new Date(monday);
  end.setDate(end.getDate() + 7);
  return [monday, end];
}

function monthlyRange(isoDay) {
  const [yo, mo] = isoDay.split('-').map(Number);
  const start = new Date(yo, mo - 1, 1, 0, 0, 0, 0);
  const end = new Date(yo, mo, 1, 0, 0, 0, 0);
  return [start, end];
}

function dailyRange(isoDay) {
  const [yo, mo, doy] = isoDay.split('-').map(Number);
  const start = new Date(yo, mo - 1, doy, 0, 0, 0, 0);
  const end = new Date(yo, mo - 1, doy + 1, 0, 0, 0, 0);
  return [start, end];
}

function periodBounds(granularity, anchorIso) {
  if (granularity === 'MONTHLY') return monthlyRange(anchorIso);
  if (granularity === 'DAILY') return dailyRange(anchorIso);
  return weeklyRange(anchorIso);
}

function parseTs(s) {
  if (!s) return null;
  return new Date(s);
}

/**
 * Prefer summaries whose explicit date span overlaps [periodStart, periodEnd).
 * Fallback: generated_at falls in that window.
 */
function pickSummaryForPeriod(summaries, periodStart, periodEnd) {
  const candidates = summaries.filter((s) => {
    const from = parseTs(s.date_from);
    const to = parseTs(s.date_to);
    const gen = parseTs(s.generated_at);
    if (from && to) {
      return to >= periodStart && from < periodEnd;
    }
    if (gen) return gen >= periodStart && gen < periodEnd;
    return false;
  });
  candidates.sort((a, b) => parseTs(b.generated_at) - parseTs(a.generated_at));
  if (candidates.length) return candidates[0];
  if (summaries.length) return summaries[0];
  return null;
}

function normalizeStrList(raw) {
  if (!Array.isArray(raw)) return [];
  return raw.map((x) =>
    typeof x === 'string' ? x.trim() : String(x?.text ?? x?.item ?? '').trim()
  ).filter(Boolean);
}

function formatPeriodSubtitle(granularity, anchorIso) {
  const [start] = periodBounds(granularity, anchorIso);
  const opts = { month: 'short', day: 'numeric', year: 'numeric' };
  if (granularity === 'DAILY') {
    return start.toLocaleDateString('en-US', { weekday: 'long', ...opts });
  }
  const [periodStart, periodEnd] = periodBounds(granularity, anchorIso);
  const endLbl = new Date(periodEnd);
  endLbl.setDate(endLbl.getDate() - 1);
  if (granularity === 'MONTHLY') {
    return start.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
  }
  return `${periodStart.toLocaleDateString('en-US', opts)} — ${endLbl.toLocaleDateString(
    'en-US',
    opts
  )}`;
}

function granularityLabel(g) {
  if (g === 'DAILY') return 'Day';
  if (g === 'WEEKLY') return 'Week';
  return 'Month';
}

function notePreviewLine(n) {
  if (!n) return '';
  const line = (n.raw_text || '').split('\n')[0].replace(/^#\s*/, '').trim();
  return (line || 'Untitled').slice(0, 72);
}

/** Move anchor date by one period in local calendar (week = 7 days, month = 1 month). */
function shiftAnchorIso(isoDay, granularity, delta) {
  const [yo, mo, doy] = isoDay.split('-').map(Number);
  const d = new Date(yo, mo - 1, doy, 12, 0, 0, 0);
  if (granularity === 'DAILY') d.setDate(d.getDate() + delta);
  else if (granularity === 'WEEKLY') d.setDate(d.getDate() + 7 * delta);
  else d.setMonth(d.getMonth() + delta);
  return isoDateLocal(d);
}

export default function Review() {
  const { notes, tasks, addToast } = useStore();
  const [granularity, setGranularity] = useState('WEEKLY');
  const [anchorDate, setAnchorDate] = useState(() => isoDateLocal());

  const [summariesLoading, setSummariesLoading] = useState(false);
  const [summariesError, setSummariesError] = useState(null);
  const [summaries, setSummaries] = useState([]);

  const [themesOpen, setThemesOpen] = useState(true);
  const [narrativeOpen, setNarrativeOpen] = useState(true);
  const [summaryExpanded, setSummaryExpanded] = useState(false);

  const [linkProposals, setLinkProposals] = useState([]);
  const [linkProposalsLoading, setLinkProposalsLoading] = useState(false);
  const [linkProposalsError, setLinkProposalsError] = useState(null);
  const [selectedProposalIds, setSelectedProposalIds] = useState(() => new Set());
  const [proposalBulkBusy, setProposalBulkBusy] = useState(false);
  const [proposalRowBusyId, setProposalRowBusyId] = useState(null);

  const loadLinkProposals = useCallback(async () => {
    setLinkProposalsLoading(true);
    setLinkProposalsError(null);
    try {
      const res = await proposalsAPI.list({ status: 'pending', limit: 500 });
      setLinkProposals(res.data || []);
    } catch (e) {
      const msg = e.message || 'Failed to load link proposals';
      setLinkProposalsError(msg);
      setLinkProposals([]);
    } finally {
      setLinkProposalsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadLinkProposals();
  }, [loadLinkProposals]);

  const resolveNote = useCallback((nid) => notes.find((n) => n.id === nid), [notes]);

  const toggleProposalSelected = useCallback((id) => {
    setSelectedProposalIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAllProposals = useCallback(() => {
    setSelectedProposalIds(new Set(linkProposals.map((p) => p.id)));
  }, [linkProposals]);

  const clearProposalSelection = useCallback(() => {
    setSelectedProposalIds(new Set());
  }, []);

  const runProposalActions = useCallback(
    async (ids, action) => {
      const list = [...ids];
      let ok = 0;
      let firstErr = null;
      for (const id of list) {
        try {
          if (action === 'accept') await proposalsAPI.accept(id);
          else await proposalsAPI.dismiss(id);
          ok += 1;
        } catch (e) {
          firstErr = e;
          break;
        }
      }
      await loadLinkProposals();
      setSelectedProposalIds((prev) => {
        const next = new Set(prev);
        list.slice(0, ok).forEach((id) => next.delete(id));
        return next;
      });
      if (firstErr) {
        addToast({
          type: 'error',
          message: firstErr.message || `${action} failed after ${ok} succeeded`,
        });
      } else if (ok > 0) {
        addToast({
          type: 'success',
          message:
            ok === 1
              ? `Proposal ${action === 'accept' ? 'accepted' : 'dismissed'}`
              : `${ok} proposals ${action === 'accept' ? 'accepted' : 'dismissed'}`,
        });
      }
      return { ok, err: firstErr };
    },
    [loadLinkProposals, addToast]
  );

  const handleAcceptRow = async (id) => {
    if (proposalBulkBusy || proposalRowBusyId) return;
    setProposalRowBusyId(id);
    await runProposalActions([id], 'accept');
    setProposalRowBusyId(null);
  };

  const handleDismissRow = async (id) => {
    if (proposalBulkBusy || proposalRowBusyId) return;
    setProposalRowBusyId(id);
    await runProposalActions([id], 'dismiss');
    setProposalRowBusyId(null);
  };

  const handleBulkAccept = async () => {
    const ids = [...selectedProposalIds];
    if (!ids.length || proposalBulkBusy || proposalRowBusyId) return;
    setProposalBulkBusy(true);
    await runProposalActions(ids, 'accept');
    setProposalBulkBusy(false);
  };

  const handleBulkDismiss = async () => {
    const ids = [...selectedProposalIds];
    if (!ids.length || proposalBulkBusy || proposalRowBusyId) return;
    setProposalBulkBusy(true);
    await runProposalActions(ids, 'dismiss');
    setProposalBulkBusy(false);
  };

  const handleAcceptAll = async () => {
    const ids = linkProposals.map((p) => p.id);
    if (!ids.length || proposalBulkBusy || proposalRowBusyId) return;
    setProposalBulkBusy(true);
    await runProposalActions(ids, 'accept');
    clearProposalSelection();
    setProposalBulkBusy(false);
  };

  const loadSummaries = useCallback(async () => {
    setSummariesLoading(true);
    setSummariesError(null);
    try {
      const res = await summariesAPI.list({ granularity });
      setSummaries(res.data || []);
    } catch (e) {
      setSummariesError(e.message);
      setSummaries([]);
    } finally {
      setSummariesLoading(false);
    }
  }, [granularity]);

  useEffect(() => {
    loadSummaries();
  }, [loadSummaries]);

  const [periodStart, periodEnd] = useMemo(
    () => periodBounds(granularity, anchorDate),
    [granularity, anchorDate]
  );

  const selectedSummary = useMemo(
    () => pickSummaryForPeriod(summaries, periodStart, periodEnd),
    [summaries, periodStart, periodEnd]
  );

  const keyThemes = useMemo(
    () => normalizeStrList(selectedSummary?.key_themes),
    [selectedSummary]
  );
  const actionItems = useMemo(
    () => normalizeStrList(selectedSummary?.action_items),
    [selectedSummary]
  );
  const summaryText = selectedSummary?.summary_text?.trim() || '';

  const summaryPreview =
    summaryText.length <= SUMMARY_PREVIEW_CHARS
      ? summaryText
      : `${summaryText.slice(0, SUMMARY_PREVIEW_CHARS).trim()}…`;

  useEffect(() => {
    setSummaryExpanded(false);
    setThemesOpen(true);
    const themes = normalizeStrList(selectedSummary?.key_themes);
    setNarrativeOpen(themes.length === 0);
  }, [granularity, anchorDate, selectedSummary?.id, keyThemes.length]);

  const now = new Date();
  const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  const weekAhead = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);

  const inbox = notes.filter((n) => n.bucket === 'INBOX');
  const recent = notes.filter(
    (n) => new Date(n.created_at) >= weekAgo && n.bucket !== 'INBOX'
  );
  const upcomingTasks = tasks.filter((t) => {
    if (!t.due_date) return false;
    const d = new Date(t.due_date);
    return d >= now && d <= weekAhead;
  });

  const pendingTasks = tasks.filter(
    (t) => !t.due_date && t.status !== 'DONE' && t.status !== 'CANCELLED'
  );

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1>Review</h1>
        <p className={styles.subtitle}>
          Saved rollups and workspace pulse · {granularityLabel(granularity)} ·{' '}
          {formatPeriodSubtitle(granularity, anchorDate)}
        </p>
      </div>

      <section className={styles.summaryHero} aria-label="Saved summary rollup">
        <div className={styles.summaryHeroTop}>
          <div className={styles.summaryHeroTitle}>
            <Sparkles size={18} className={styles.summaryIcon} aria-hidden />
            <h2>Progressive summary</h2>
          </div>
          <button
            type="button"
            className={styles.retryBtn}
            disabled={summariesLoading}
            onClick={() => loadSummaries()}
          >
            Refresh
          </button>
        </div>

        <div className={styles.summaryControls}>
          <div className={styles.periodPicker}>
            <label className={styles.controlLabel}>
              Period
              <div className={styles.dateRow}>
                <button
                  type="button"
                  className={styles.periodStepBtn}
                  aria-label={`Previous ${granularityLabel(granularity).toLowerCase()}`}
                  onClick={() => setAnchorDate((d) => shiftAnchorIso(d, granularity, -1))}
                >
                  <ChevronLeft size={18} aria-hidden />
                </button>
                <input
                  type="date"
                  className={styles.dateInput}
                  value={anchorDate}
                  onChange={(e) => setAnchorDate(e.target.value)}
                />
                <button
                  type="button"
                  className={styles.periodStepBtn}
                  aria-label={`Next ${granularityLabel(granularity).toLowerCase()}`}
                  onClick={() => setAnchorDate((d) => shiftAnchorIso(d, granularity, 1))}
                >
                  <ChevronRight size={18} aria-hidden />
                </button>
              </div>
            </label>
          </div>
          <fieldset className={styles.granFieldset}>
            <legend className={styles.visuallyHidden}>Granularity</legend>
            <div className={styles.segmented} role="group" aria-label="Summary granularity">
              {GRANULARITIES.map((g) => (
                <button
                  key={g}
                  type="button"
                  className={g === granularity ? styles.segmentActive : styles.segment}
                  onClick={() => setGranularity(g)}
                >
                  {g === 'DAILY' ? 'Day' : g === 'WEEKLY' ? 'Week' : 'Month'}
                </button>
              ))}
            </div>
          </fieldset>
        </div>

        <p className={styles.periodLine}>{formatPeriodSubtitle(granularity, anchorDate)}</p>

        {summariesError && (
          <p className={styles.summaryError} role="alert">
            Could not load summaries: {summariesError}
          </p>
        )}

        {!summariesError && summariesLoading && (
          <p className={styles.summaryMuted}>Loading summaries…</p>
        )}

        {!summariesLoading && !selectedSummary && !summariesError && (
          <p className={styles.summaryEmpty}>
            No saved summary matches this granularity and date window. Trigger one from the backend
            (e.g.{' '}
            <code className={styles.inlineCode}>POST /api/v1/summarize</code>
            ), then refresh here.
          </p>
        )}

        {selectedSummary && !summariesLoading && (
          <>
            <div className={styles.summaryMeta}>
              <span>Type: {selectedSummary.summary_type || '—'}</span>
              <span>
                Updated{' '}
                {parseTs(selectedSummary.generated_at)?.toLocaleString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                }) || '—'}
              </span>
            </div>

            {keyThemes.length > 0 && (
              <div className={styles.progressLayer}>
                <button
                  type="button"
                  className={styles.progressToggle}
                  onClick={() => setThemesOpen(!themesOpen)}
                  aria-expanded={themesOpen}
                >
                  {themesOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                  Key themes
                  <span className={styles.layerBadge}>{keyThemes.length}</span>
                </button>
                {themesOpen && (
                  <ul className={styles.themeChips} aria-label="Key themes">
                    {keyThemes.map((t, i) => (
                      <li key={i} className={styles.themeChip}>
                        {t}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {summaryText && (
              <div className={styles.progressLayer}>
                <button
                  type="button"
                  className={styles.progressToggle}
                  onClick={() => setNarrativeOpen(!narrativeOpen)}
                  aria-expanded={narrativeOpen}
                >
                  {narrativeOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                  Narrative
                </button>
                {narrativeOpen && (
                  <>
                    <div className={styles.summaryBody}>
                      {(summaryExpanded ? summaryText : summaryPreview).split('\n\n').map((para, idx) =>
                        para ? (
                          <p
                            key={`para-${selectedSummary?.id}-${idx}-${para.slice(0, 12)}`}
                            className={styles.summaryPara}
                          >
                            {para}
                          </p>
                        ) : null
                      )}
                    </div>
                    {summaryText.length > SUMMARY_PREVIEW_CHARS && (
                      <button
                        type="button"
                        className={styles.expandBtn}
                        onClick={() => setSummaryExpanded(!summaryExpanded)}
                      >
                        {summaryExpanded ? 'Show less' : 'Show full summary'}
                      </button>
                    )}
                  </>
                )}
              </div>
            )}

            <div className={styles.progressLayer}>
              <div className={styles.progressStaticHead}>
                <ListTodo size={14} aria-hidden /> Action items
                {actionItems.length > 0 && (
                  <span className={styles.layerBadge}>{actionItems.length}</span>
                )}
              </div>
              {actionItems.length === 0 ? (
                <p className={styles.summaryMuted}>No action items captured for this summary.</p>
              ) : (
                <ul className={styles.actionList} aria-label="Action items">
                  {actionItems.map((item, i) => (
                    <li key={i} className={styles.actionItem}>
                      <span className={styles.actionBullet} aria-hidden />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {!keyThemes.length && !summaryText && !actionItems.length && (
              <p className={styles.summaryMuted}>
                Summary record exists but narrative and themes are empty.
              </p>
            )}
          </>
        )}
      </section>

      <section className={styles.proposalsSection} aria-label="Pending link proposals">
        <div className={styles.proposalsHead}>
          <div className={styles.proposalsTitleRow}>
            <Link2 size={18} className={styles.proposalsIcon} aria-hidden />
            <h2>Pending link proposals</h2>
            <span className={styles.badge}>{linkProposals.length}</span>
            <button
              type="button"
              className={styles.retryBtn}
              disabled={linkProposalsLoading || proposalBulkBusy}
              onClick={() => loadLinkProposals()}
            >
              Refresh
            </button>
          </div>
          <p className={styles.proposalsLead}>
            AI-suggested relationships between notes. Accept to create a link, or dismiss to clear.
          </p>
        </div>

        {linkProposalsError && (
          <p className={styles.summaryError} role="alert">
            Could not load proposals: {linkProposalsError}
          </p>
        )}

        {linkProposalsLoading && !linkProposalsError && (
          <p className={styles.summaryMuted}>
            <Loader2 size={14} className="spin" aria-hidden /> Loading proposals…
          </p>
        )}

        {!linkProposalsLoading && !linkProposalsError && linkProposals.length === 0 && (
          <p className={styles.summaryMuted}>No pending proposals. Generate some from the API or note detail.</p>
        )}

        {!linkProposalsLoading && linkProposals.length > 0 && (
          <>
            <div className={styles.proposalsToolbar}>
              <div className={styles.proposalsToolbarLeft}>
                <button
                  type="button"
                  className={styles.proposalsToolbarBtn}
                  onClick={selectAllProposals}
                  disabled={proposalBulkBusy || !!proposalRowBusyId}
                >
                  Select all
                </button>
                <button
                  type="button"
                  className={styles.proposalsToolbarBtn}
                  onClick={clearProposalSelection}
                  disabled={proposalBulkBusy || !!proposalRowBusyId || selectedProposalIds.size === 0}
                >
                  Clear selection
                </button>
                <span className={styles.proposalsSelectionHint}>
                  {selectedProposalIds.size} selected
                </span>
              </div>
              <div className={styles.proposalsToolbarRight}>
                <button
                  type="button"
                  className={styles.proposalsToolbarBtn}
                  onClick={handleBulkAccept}
                  disabled={
                    proposalBulkBusy ||
                    !!proposalRowBusyId ||
                    selectedProposalIds.size === 0
                  }
                >
                  {proposalBulkBusy ? (
                    <Loader2 size={14} className="spin" aria-hidden />
                  ) : (
                    <CheckCircle size={14} aria-hidden />
                  )}
                  Accept selected
                </button>
                <button
                  type="button"
                  className={styles.proposalsToolbarBtnMuted}
                  onClick={handleBulkDismiss}
                  disabled={
                    proposalBulkBusy ||
                    !!proposalRowBusyId ||
                    selectedProposalIds.size === 0
                  }
                >
                  Dismiss selected
                </button>
                <button
                  type="button"
                  className={styles.proposalsAcceptAll}
                  onClick={handleAcceptAll}
                  disabled={proposalBulkBusy || !!proposalRowBusyId}
                  title="Accept every pending proposal in this list"
                >
                  {proposalBulkBusy ? (
                    <Loader2 size={14} className="spin" aria-hidden />
                  ) : (
                    <Sparkles size={14} aria-hidden />
                  )}
                  Accept all
                </button>
              </div>
            </div>

            <ul className={styles.proposalsList}>
              {linkProposals.map((p) => {
                const src = resolveNote(p.src_id);
                const dst = resolveNote(p.dst_id);
                const rowBusy = proposalRowBusyId === p.id;
                const disabledRow = proposalBulkBusy || proposalRowBusyId !== null;
                const checked = selectedProposalIds.has(p.id);
                return (
                  <li key={p.id} className={styles.proposalCard}>
                    <label className={styles.proposalCheck}>
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={proposalBulkBusy || !!proposalRowBusyId}
                        onChange={() => toggleProposalSelected(p.id)}
                      />
                    </label>
                    <div className={styles.proposalContext}>
                      <div className={styles.proposalPair}>
                        <Link to={`/notes/${p.src_id}`} className={styles.proposalNoteLink}>
                          {notePreviewLine(src) || `Note ${String(p.src_id).slice(0, 8)}…`}
                        </Link>
                        <span className={styles.proposalArrow} aria-hidden>
                          ↔
                        </span>
                        <Link to={`/notes/${p.dst_id}`} className={styles.proposalNoteLink}>
                          {notePreviewLine(dst) || `Note ${String(p.dst_id).slice(0, 8)}…`}
                        </Link>
                      </div>
                      {!src && (
                        <p className={styles.proposalMissing}>Source note not in workspace cache.</p>
                      )}
                      {!dst && (
                        <p className={styles.proposalMissing}>Target note not in workspace cache.</p>
                      )}
                      <span className={styles.proposalConf}>
                        {Math.round((p.confidence ?? 0) * 100)}% confidence
                        {p.created_at && (
                          <>
                            {' · '}
                            <span className={styles.proposalWhen}>
                              {parseTs(p.created_at)?.toLocaleDateString('en-US', {
                                month: 'short',
                                day: 'numeric',
                              }) || ''}
                            </span>
                          </>
                        )}
                      </span>
                      {p.reason ? <p className={styles.proposalReason}>{p.reason}</p> : null}
                    </div>
                    <div className={styles.proposalRowActions}>
                      <button
                        type="button"
                        className={styles.proposalAcceptBtn}
                        onClick={() => handleAcceptRow(p.id)}
                        disabled={disabledRow}
                      >
                        {rowBusy ? (
                          <Loader2 size={13} className="spin" aria-hidden />
                        ) : (
                          <CheckCircle size={13} aria-hidden />
                        )}
                        Accept
                      </button>
                      <button
                        type="button"
                        className={styles.proposalDismissBtn}
                        onClick={() => handleDismissRow(p.id)}
                        disabled={disabledRow}
                      >
                        Dismiss
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </section>

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
              {inbox.slice(0, 5).map((n) => (
                <NoteCard key={n.id} note={n} />
              ))}
              {inbox.length > 5 && (
                <Link to="/inbox" className={styles.moreLink}>
                  +{inbox.length - 5} more in inbox →
                </Link>
              )}
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
              {recent.slice(0, 5).map((n) => (
                <NoteCard key={n.id} note={n} />
              ))}
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
              {upcomingTasks.map((t) => (
                <div key={t.id} className={styles.taskItem}>
                  <span>{t.title}</span>
                  <span className={styles.dueDate}>
                    {new Date(t.due_date).toLocaleDateString('en-US', {
                      month: 'short',
                      day: 'numeric',
                    })}
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
              {pendingTasks.slice(0, 8).map((t) => (
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
