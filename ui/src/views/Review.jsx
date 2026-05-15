import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
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
  FolderKanban,
  LayoutGrid,
  FileWarning,
  RotateCcw,
  Archive,
  ExternalLink,
  HeartPulse,
} from 'lucide-react';
import useStore from '../stores/useStore';
import { summariesAPI, proposalsAPI, reviewAPI, metricsAPI, suggestionsAPI, changeBatchesAPI } from '../api/engram';
import NoteCard from '../components/notes/NoteCard';
import styles from './Review.module.css';
import {
  REVIEW_WORKFLOW_STEPS,
  usePersistedReviewWorkflow,
} from './reviewWorkflowState';

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

/** Twelve-week trends from metrics snapshots (SVG). Each series uses its own vertical scale. */
function HealthTrendChart({ series }) {
  const w = 380;
  const h = 168;
  const pad = { l: 40, r: 44, t: 18, b: 34 };
  const iw = w - pad.l - pad.r;
  const ih = h - pad.t - pad.b;
  const n = Math.max(1, series?.length || 0);

  const orphanVals = (series || []).map((s) =>
    typeof s.orphan_rate === 'number' ? s.orphan_rate : null
  );
  const capVals = (series || []).map((s) =>
    typeof s.capture_rate === 'number' ? s.capture_rate : null
  );

  const maxO = Math.max(0.05, ...orphanVals.filter((v) => v != null), 0);
  const maxC = Math.max(1, ...capVals.filter((v) => v != null), 0);

  const xAt = (i) => pad.l + (n <= 1 ? iw / 2 : (i / (n - 1)) * iw);

  const ptsOrphan = orphanVals
    .map((v, i) => (v == null ? null : `${xAt(i)},${pad.t + ih - (v / maxO) * ih}`))
    .filter(Boolean)
    .join(' ');
  const ptsCap = capVals
    .map((v, i) => (v == null ? null : `${xAt(i)},${pad.t + ih - (v / maxC) * ih}`))
    .filter(Boolean)
    .join(' ');

  const formatWeek = (iso) => {
    if (!iso) return '';
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const rows = series || [];

  return (
    <div className={styles.healthTrendWrap} data-testid="review-health-trend-chart">
      <svg
        width={w}
        height={h}
        className={styles.healthTrendSvg}
        role="img"
        aria-label="Orphan rate and weekly capture count over the last twelve weeks"
      >
        <text x={pad.l} y={14} className={styles.healthTrendCaption}>
          Orphan rate and captures per rolling week (each series scaled to its own max)
        </text>
        <line x1={pad.l} y1={pad.t + ih} x2={pad.l + iw} y2={pad.t + ih} stroke="var(--border)" strokeWidth={1} />
        <line x1={pad.l} y1={pad.t} x2={pad.l} y2={pad.t + ih} stroke="var(--border)" strokeWidth={1} />
        <line x1={pad.l + iw} y1={pad.t} x2={pad.l + iw} y2={pad.t + ih} stroke="var(--border)" strokeWidth={1} />
        {ptsOrphan ? (
          <polyline fill="none" stroke="var(--red)" strokeWidth={2} points={ptsOrphan} />
        ) : null}
        {ptsCap ? (
          <polyline fill="none" stroke="var(--accent)" strokeWidth={2} points={ptsCap} />
        ) : null}
        {rows.map((s, i) => (
          <text key={s.week_start || `w-${i}`} x={xAt(i)} y={h - 8} textAnchor="middle" className={styles.healthTrendTick}>
            {formatWeek(s.week_start)}
          </text>
        ))}
      </svg>
      <div className={styles.healthTrendLegend}>
        <span className={styles.healthTrendLegendOrphan}>
          ● Orphan rate (0–{(maxO * 100).toFixed(0)}% scale)
        </span>
        <span className={styles.healthTrendLegendCap}>● Weekly captures / 7d (0–{maxC} scale)</span>
      </div>
    </div>
  );
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

const STEP_ICON = {
  inbox: Inbox,
  projects: FolderKanban,
  areas: LayoutGrid,
  orphans: FileWarning,
  proposals: Link2,
  insights: Sparkles,
  plan: Calendar,
};

function WorkflowStepPanel({ stepIndex, step, flow, patchFlow, eyebrow, badge, children }) {
  const id = step.id;
  const Icon = STEP_ICON[id] || ListTodo;
  const expanded = !!flow.expanded[id];
  const completed = !!flow.completed[id];
  const panelId = `review-panel-${id}`;
  const headId = `review-head-${id}`;

  return (
    <section
      className={styles.workflowStep}
      aria-labelledby={headId}
      data-testid={`review-step-${id}`}
      id={`review-step-${id}`}
    >
      <div className={styles.workflowStepHead}>
        <button
          type="button"
          className={styles.workflowStepToggle}
          id={headId}
          aria-expanded={expanded}
          aria-controls={panelId}
          onClick={() =>
            patchFlow((w) => ({
              ...w,
              expanded: { ...w.expanded, [id]: !expanded },
              lastActiveStepId: id,
            }))
          }
        >
          <span className={styles.workflowStepCaret} aria-hidden>
            {expanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
          </span>
          <span className={styles.workflowStepNum}>{stepIndex + 1}</span>
          <Icon size={16} className={styles.workflowStepTitleIcon} aria-hidden />
          <span className={styles.workflowStepTitle}>{step.title}</span>
          {typeof badge === 'number' ? <span className={styles.workflowStepBadge}>{badge}</span> : null}
          {eyebrow ? <span className={styles.workflowStepEyebrow}>{eyebrow}</span> : null}
        </button>
        <label className={styles.workflowDoneLabel}>
          <input
            type="checkbox"
            checked={completed}
            onChange={() =>
              patchFlow((w) => ({
                ...w,
                completed: { ...w.completed, [id]: !completed },
                lastActiveStepId: id,
              }))
            }
            aria-label={`Mark step complete: ${step.title}`}
          />
          <span className={styles.workflowDoneText}>Reviewed</span>
        </label>
      </div>
      {expanded ? (
        <div className={styles.workflowStepBody} id={panelId} role="region" aria-labelledby={headId}>
          {children}
        </div>
      ) : null}
    </section>
  );
}
export default function Review() {
  const navigate = useNavigate();
  const { notes, tasks, projects, areas, addToast, updateNote } = useStore();
  const {
    state: reviewFlow,
    setState: setReviewFlow,
    hydrated,
    hadPersistedDraft,
    resetWorkflow,
  } = usePersistedReviewWorkflow();

  const activeProjects = useMemo(
    () => (projects || []).filter((p) => !p.is_archived),
    [projects]
  );
  const activeAreas = useMemo(
    () => (areas || []).filter((a) => !a.is_archived),
    [areas]
  );

  const orphanNotes = useMemo(
    () =>
      notes.filter((n) => {
        if (n.is_archived) return false;
        if (n.bucket === 'INBOX') return false;
        const linkTotal = Number(n.link_count) || 0;
        if (linkTotal !== 0) return false;
        const hasProject = !!(n.project_id || (n.project_ids?.length ?? 0) > 0);
        if (hasProject) return false;
        if (n.area_id) return false;
        return true;
      }),
    [notes]
  );
  const [orphanRowBusyId, setOrphanRowBusyId] = useState(null);
  const [orphanBulkBusy, setOrphanBulkBusy] = useState(false);

  const [granularity, setGranularity] = useState('WEEKLY');
  const [anchorDate, setAnchorDate] = useState(() => isoDateLocal());

  const [digestLoading, setDigestLoading] = useState(true);
  const [digestError, setDigestError] = useState(null);
  const [weeklyDigest, setWeeklyDigest] = useState(null);

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

  const [aiSuggestions, setAiSuggestions] = useState([]);
  const [aiSuggestionsLoading, setAiSuggestionsLoading] = useState(false);
  const [aiSuggestionsError, setAiSuggestionsError] = useState(null);
  const [aiSuggestionBusyId, setAiSuggestionBusyId] = useState(null);
  const [editingSuggestionId, setEditingSuggestionId] = useState(null);
  const [editingOperationType, setEditingOperationType] = useState('');
  const [editingReason, setEditingReason] = useState('');
  const [changeBatches, setChangeBatches] = useState([]);
  const [changeBatchesLoading, setChangeBatchesLoading] = useState(false);

  const [insightsTab, setInsightsTab] = useState('summary');
  const [healthHistory, setHealthHistory] = useState([]);
  const [healthHistoryLoading, setHealthHistoryLoading] = useState(false);
  const [healthHistoryError, setHealthHistoryError] = useState(null);

  const loadHealthHistory = useCallback(async () => {
    setHealthHistoryLoading(true);
    setHealthHistoryError(null);
    try {
      const res = await metricsAPI.healthHistory({ weeks: 12 });
      setHealthHistory(res.data || []);
    } catch (e) {
      setHealthHistoryError(e.message || 'Failed to load health history');
      setHealthHistory([]);
    } finally {
      setHealthHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    if (insightsTab === 'health') loadHealthHistory();
  }, [insightsTab, loadHealthHistory]);

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

  const loadAiSuggestions = useCallback(async () => {
    setAiSuggestionsLoading(true);
    setAiSuggestionsError(null);
    try {
      const res = await suggestionsAPI.list({ status: 'pending', limit: 500 });
      setAiSuggestions(res.data || []);
    } catch (e) {
      setAiSuggestionsError(e.message || 'Failed to load AI suggestions');
      setAiSuggestions([]);
    } finally {
      setAiSuggestionsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAiSuggestions();
  }, [loadAiSuggestions]);

  const loadChangeBatches = useCallback(async () => {
    setChangeBatchesLoading(true);
    try {
      const res = await changeBatchesAPI.list({ limit: 10 });
      setChangeBatches(res.data || []);
    } catch {
      setChangeBatches([]);
    } finally {
      setChangeBatchesLoading(false);
    }
  }, []);

  useEffect(() => {
    loadChangeBatches();
  }, [loadChangeBatches]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setDigestLoading(true);
      setDigestError(null);
      try {
        const data = await reviewAPI.weeklyDigest({ days: 7 });
        if (!cancelled) setWeeklyDigest(data);
      } catch (e) {
        if (!cancelled) {
          setDigestError(e.message || 'Could not load weekly digest');
          setWeeklyDigest(null);
        }
      } finally {
        if (!cancelled) setDigestLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

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

  const handleOrphanProjectChange = async (noteId, projectId) => {
    if (orphanBulkBusy || orphanRowBusyId) return;
    setOrphanRowBusyId(noteId);
    try {
      await updateNote(noteId, { project_id: projectId || null });
    } finally {
      setOrphanRowBusyId(null);
    }
  };

  const handleOrphanAreaChange = async (noteId, areaId) => {
    if (orphanBulkBusy || orphanRowBusyId) return;
    setOrphanRowBusyId(noteId);
    try {
      await updateNote(noteId, { area_id: areaId || null });
    } finally {
      setOrphanRowBusyId(null);
    }
  };

  const handleOrphanArchiveOne = async (noteId) => {
    if (orphanBulkBusy || orphanRowBusyId) return;
    setOrphanRowBusyId(noteId);
    try {
      await updateNote(noteId, { is_archived: true });
    } finally {
      setOrphanRowBusyId(null);
    }
  };

  const handleBulkArchiveOrphans = async () => {
    if (orphanNotes.length === 0 || orphanBulkBusy) return;
    const msg = `Archive all ${orphanNotes.length} orphan note${orphanNotes.length === 1 ? '' : 's'}? They will leave active lists.`;
    if (!window.confirm(msg)) return;
    setOrphanBulkBusy(true);
    const ids = orphanNotes.map((n) => n.id);
    let ok = 0;
    let firstErr = null;
    for (const id of ids) {
      try {
        await updateNote(id, { is_archived: true }, { silent: true });
        ok += 1;
      } catch (e) {
        firstErr = e;
        break;
      }
    }
    setOrphanBulkBusy(false);
    if (firstErr) {
      addToast({
        type: 'error',
        message: firstErr.message || `Archived ${ok} notes, then an error occurred`,
      });
    } else {
      addToast({
        type: 'success',
        message:
          ok === 1 ? 'Archived 1 orphan note' : `Archived ${ok} orphan notes`,
      });
    }
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

  const doneStepCount = useMemo(
    () => REVIEW_WORKFLOW_STEPS.filter((s) => reviewFlow.completed[s.id]).length,
    [reviewFlow.completed]
  );
  const workflowProgressPct = Math.round((doneStepCount / REVIEW_WORKFLOW_STEPS.length) * 100);

  const focusStepRelative = useCallback(
    (delta) => {
      const curIdx = REVIEW_WORKFLOW_STEPS.findIndex((s) => s.id === reviewFlow.lastActiveStepId);
      const idx = curIdx >= 0 ? curIdx : 0;
      const nextIdx = Math.max(0, Math.min(REVIEW_WORKFLOW_STEPS.length - 1, idx + delta));
      const next = REVIEW_WORKFLOW_STEPS[nextIdx];
      setReviewFlow((w) => ({
        ...w,
        lastActiveStepId: next.id,
        expanded: { ...w.expanded, [next.id]: true },
      }));
      queueMicrotask(() => {
        document.getElementById(`review-step-${next.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      });
    },
    [reviewFlow.lastActiveStepId, setReviewFlow]
  );

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1>Review</h1>
        <p className={styles.subtitle}>
          Guided weekly rhythm — housekeeping, surfaced insights, and light planning. Expand each step below; your checklist
          and open sections persist in localStorage so pausing mid-review is safe.
        </p>
      </div>

      <section
        className={styles.digestCard}
        aria-labelledby="weekly-digest-heading"
        data-testid="review-weekly-digest"
      >
        <p id="weekly-digest-heading" className={styles.digestEyebrow}>
          Past 7 days
        </p>
        {digestLoading ? (
          <p className={styles.digestBodyMuted}>
            <Loader2 size={16} className="spin" aria-hidden /> Loading your weekly snapshot…
          </p>
        ) : digestError ? (
          <p className={styles.digestError} role="alert">
            {digestError}
          </p>
        ) : weeklyDigest ? (
          <p className={styles.digestBody}>
            You captured{' '}
            <strong data-testid="digest-notes">{weeklyDigest.notes_captured}</strong> notes, created{' '}
            <strong data-testid="digest-tasks">{weeklyDigest.tasks_created}</strong> tasks, completed{' '}
            <strong data-testid="digest-projects">{weeklyDigest.projects_completed}</strong> projects, made{' '}
            <strong data-testid="digest-links">{weeklyDigest.connections_made}</strong> connections.
          </p>
        ) : (
          <p className={styles.digestBodyMuted}>No digest data.</p>
        )}
      </section>

      <div className={styles.workflowRail} data-testid="review-workflow-progress">
        <div className={styles.workflowRailTop}>
          <p className={styles.workflowRailTitle}>Weekly checklist</p>
          <span className={styles.workflowRailCount}>
            {doneStepCount} / {REVIEW_WORKFLOW_STEPS.length} reviewed
          </span>
        </div>
        <div
          className={styles.workflowProgressTrack}
          role="progressbar"
          aria-valuenow={doneStepCount}
          aria-valuemin={0}
          aria-valuemax={REVIEW_WORKFLOW_STEPS.length}
          aria-valuetext={`${doneStepCount} of ${REVIEW_WORKFLOW_STEPS.length} sections marked reviewed`}
          aria-label="Weekly review checklist progress"
        >
          <div className={styles.workflowProgressFill} style={{ width: `${workflowProgressPct}%` }} />
        </div>
        <div className={styles.workflowRailNav}>
          <button type="button" className={styles.workflowNavBtn} onClick={() => focusStepRelative(-1)}>
            <ChevronLeft size={16} aria-hidden />
            Previous
          </button>
          <button type="button" className={styles.workflowNavBtn} onClick={() => focusStepRelative(1)}>
            Next
            <ChevronRight size={16} aria-hidden />
          </button>
          <button type="button" className={styles.workflowResetBtn} onClick={resetWorkflow}>
            <RotateCcw size={14} aria-hidden /> Reset progress
          </button>
        </div>
        {hydrated && hadPersistedDraft ? (
          <p className={styles.resumeBand} role="status">
            Continuing a saved review — reopen this page anytime to pick up where you left off.
          </p>
        ) : null}
      </div>

      <div className={styles.workflowStack}>
        <WorkflowStepPanel
          stepIndex={0}
          step={REVIEW_WORKFLOW_STEPS[0]}
          flow={reviewFlow}
          patchFlow={setReviewFlow}
          badge={inbox.length}
          eyebrow="Route captures out of inbox"
        >
          <p className={styles.workflowLead}>Triage notes still sitting in the inbox.</p>
          {inbox.length === 0 ? (
            <p className={styles.empty}>Inbox is clear.</p>
          ) : (
            <div className={styles.noteList}>
              {inbox.slice(0, 8).map((n) => (
                <NoteCard key={n.id} note={n} />
              ))}
              {inbox.length > 8 ? (
                <Link to="/inbox" className={styles.moreLink}>
                  Open full inbox (+{inbox.length - 8} more)
                </Link>
              ) : (
                <Link to="/inbox" className={styles.moreLink}>
                  Open inbox →
                </Link>
              )}
            </div>
          )}
        </WorkflowStepPanel>

        <WorkflowStepPanel
          stepIndex={1}
          step={REVIEW_WORKFLOW_STEPS[1]}
          flow={reviewFlow}
          patchFlow={setReviewFlow}
          badge={aiSuggestions.length}
          eyebrow="Accept, edit, or dismiss"
        >
          <div className={styles.workflowEmbed}>
            <section className={styles.proposalsSection} aria-label="AI Suggestions">
              <div className={styles.proposalsHead}>
                <div className={styles.proposalsTitleRow}>
                  <Sparkles size={18} className={styles.proposalsIcon} aria-hidden />
                  <h2>AI Suggestions</h2>
                  <span className={styles.badge}>{aiSuggestions.length}</span>
                  <button
                    type="button"
                    className={styles.retryBtn}
                    disabled={aiSuggestionsLoading}
                    onClick={() => loadAiSuggestions()}
                  >
                    Refresh
                  </button>
                </div>
                <p className={styles.proposalsLead}>
                  Tasks, projects, and links extracted from your captures. Accept to create, dismiss to ignore.
                </p>
              </div>

              {aiSuggestionsError && (
                <p className={styles.summaryError} role="alert">
                  Could not load suggestions: {aiSuggestionsError}
                </p>
              )}

              {aiSuggestionsLoading && !aiSuggestionsError && (
                <p className={styles.summaryMuted}>
                  <Loader2 size={14} className="spin" aria-hidden /> Loading suggestions…
                </p>
              )}

              {!aiSuggestionsLoading && !aiSuggestionsError && aiSuggestions.length === 0 && (
                <p className={styles.summaryMuted}>No pending suggestions. Captured items will appear here.</p>
              )}

              {!aiSuggestionsLoading && aiSuggestions.length > 0 && (
                <ul className={styles.proposalList}>
                  {aiSuggestions.map((s) => {
                    const busy = aiSuggestionBusyId === s.id;
                    return (
                      <li key={s.id} className={styles.proposalRow}>
                        <div className={styles.proposalMain}>
                          <span style={{ fontWeight: 600, color: 'var(--text)' }}>
                            {s.suggestion_type}
                          </span>
                          <span style={{ color: 'var(--text-muted)', fontSize: '11px', marginLeft: '6px' }}>
                            {s.operation_type}
                          </span>
                          <span style={{
                            fontSize: '10px',
                            fontFamily: 'var(--font-mono, monospace)',
                            color: s.confidence >= 0.92 ? 'var(--green)' : s.confidence >= 0.7 ? 'var(--yellow)' : 'var(--text-muted)',
                          }}>
                            {s.confidence != null ? Math.round(s.confidence * 100) + '%' : ''}
                          </span>
                          {s.reason && <p className={styles.proposalReason}>{s.reason}</p>}
                        </div>
                        <div className={styles.proposalActions}>
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            onClick={async () => {
                              if (busy) return;
                              setAiSuggestionBusyId(s.id);
                              try {
                                await suggestionsAPI.accept(s.id);
                                await loadAiSuggestions();
                                addToast({ type: 'success', message: 'Suggestion accepted' });
                              } catch (e) {
                                addToast({ type: 'error', message: e.message || 'Failed to accept suggestion' });
                              } finally {
                                setAiSuggestionBusyId(null);
                              }
                            }}
                            disabled={busy}
                            title="Accept suggestion"
                          >
                            {busy ? <Loader2 size={13} className="spin" /> : <CheckCircle size={13} />}
                            Accept
                          </button>
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            onClick={() => {
                              if (busy) return;
                              setEditingSuggestionId(s.id);
                              setEditingOperationType(s.operation_type || '');
                              setEditingReason(s.reason || '');
                            }}
                            disabled={busy}
                            title="Edit suggestion"
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            onClick={async () => {
                              if (busy) return;
                              setAiSuggestionBusyId(s.id);
                              try {
                                await suggestionsAPI.dismiss(s.id);
                                await loadAiSuggestions();
                                addToast({ type: 'success', message: 'Suggestion dismissed' });
                              } catch (e) {
                                addToast({ type: 'error', message: e.message || 'Failed to dismiss suggestion' });
                              } finally {
                                setAiSuggestionBusyId(null);
                              }
                            }}
                            disabled={busy}
                            title="Dismiss suggestion"
                          >
                            Dismiss
                          </button>
                        </div>
                        {editingSuggestionId === s.id && (
                          <div style={{ width: '100%', display: 'grid', gap: '6px', marginTop: '8px' }}>
                            <input
                              value={editingOperationType}
                              onChange={(e) => setEditingOperationType(e.target.value)}
                              placeholder="operation_type"
                              style={{ padding: '6px 8px', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--surface)' }}
                            />
                            <textarea
                              value={editingReason}
                              onChange={(e) => setEditingReason(e.target.value)}
                              placeholder="reason"
                              rows={2}
                              style={{ padding: '6px 8px', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--surface)' }}
                            />
                            <div style={{ display: 'flex', gap: '6px' }}>
                              <button
                                type="button"
                                className="btn btn-primary btn-sm"
                                onClick={async () => {
                                  setAiSuggestionBusyId(s.id);
                                  try {
                                    await suggestionsAPI.edit(s.id, {
                                      operation_type: editingOperationType.trim() || s.operation_type,
                                      reason: editingReason.trim(),
                                    });
                                    await loadAiSuggestions();
                                    addToast({ type: 'success', message: 'Suggestion updated' });
                                    setEditingSuggestionId(null);
                                  } catch (e) {
                                    addToast({ type: 'error', message: e.message || 'Failed to edit suggestion' });
                                  } finally {
                                    setAiSuggestionBusyId(null);
                                  }
                                }}
                                disabled={busy}
                              >
                                Save
                              </button>
                              <button
                                type="button"
                                className="btn btn-ghost btn-sm"
                                onClick={() => setEditingSuggestionId(null)}
                                disabled={busy}
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}

              <div style={{ marginTop: '12px' }}>
                <div className={styles.proposalsLead} style={{ marginBottom: '8px' }}>
                  Recent AI change batches
                </div>
                {changeBatchesLoading ? (
                  <p className={styles.summaryMuted}>Loading batches…</p>
                ) : changeBatches.length === 0 ? (
                  <p className={styles.summaryMuted}>No recent batches.</p>
                ) : (
                  <ul className={styles.proposalList}>
                    {changeBatches.map((b) => (
                      <li key={b.id} className={styles.proposalRow}>
                        <div className={styles.proposalMain}>
                          <span style={{ fontWeight: 600, color: 'var(--text)' }}>{b.summary || 'AI changes'}</span>
                          <p className={styles.proposalReason}>{b.applied_at}</p>
                        </div>
                        <div className={styles.proposalActions}>
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            disabled={!!b.undone_at}
                            onClick={async () => {
                              try {
                                await changeBatchesAPI.undo(b.id);
                                addToast({ type: 'success', message: 'Batch undone' });
                                await loadChangeBatches();
                                await loadAiSuggestions();
                              } catch (e) {
                                addToast({ type: 'error', message: e.message || 'Failed to undo batch' });
                              }
                            }}
                          >
                            Undo
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </section>
          </div>
        </WorkflowStepPanel>

        <WorkflowStepPanel
          stepIndex={2}
          step={REVIEW_WORKFLOW_STEPS[2]}
          flow={reviewFlow}
          patchFlow={setReviewFlow}
          badge={activeProjects.length}
        >
          <p className={styles.workflowLead}>Spend a pass on active projects.</p>
          {activeProjects.length === 0 ? (
            <p className={styles.empty}>No active projects.</p>
          ) : (
            <ul className={styles.workflowBulletList}>
              {activeProjects.map((proj) => (
                <li key={proj.id}>
                  <Link to={`/projects/${proj.id}`} className={styles.workflowDashLink}>
                    {proj.title || 'Untitled project'}
                  </Link>
                </li>
              ))}
              <li>
                <Link to="/projects" className={styles.workflowDashLinkMuted}>
                  All projects →
                </Link>
              </li>
            </ul>
          )}
        </WorkflowStepPanel>

        <WorkflowStepPanel
          stepIndex={3}
          step={REVIEW_WORKFLOW_STEPS[3]}
          flow={reviewFlow}
          patchFlow={setReviewFlow}
          badge={activeAreas.length}
        >
          <p className={styles.workflowLead}>Check each area still reflects how you actually work.</p>
          {activeAreas.length === 0 ? (
            <p className={styles.empty}>No areas.</p>
          ) : (
            <ul className={styles.workflowBulletList}>
              {activeAreas.map((a) => (
                <li key={a.id}>
                  <Link to={`/areas/${a.id}`} className={styles.workflowDashLink}>
                    {a.title || 'Untitled area'}
                  </Link>
                </li>
              ))}
              <li>
                <Link to="/areas" className={styles.workflowDashLinkMuted}>
                  All areas →
                </Link>
              </li>
            </ul>
          )}
        </WorkflowStepPanel>

        <WorkflowStepPanel
          stepIndex={4}
          step={REVIEW_WORKFLOW_STEPS[4]}
          flow={reviewFlow}
          patchFlow={setReviewFlow}
          badge={orphanNotes.length}
          eyebrow="0 links · no project · no area · not inbox"
        >
          <p className={styles.workflowLead}>
            Notes with no graph links and no project or area — assign context, open links on the note,
            or archive if obsolete.
          </p>
          {orphanNotes.length === 0 ? (
            <p className={styles.empty}>No orphan notes right now.</p>
          ) : (
            <>
              <div className={styles.orphanToolbar}>
                <button
                  type="button"
                  className={styles.proposalsToolbarBtnMuted}
                  disabled={orphanBulkBusy || !!orphanRowBusyId}
                  onClick={handleBulkArchiveOrphans}
                >
                  {orphanBulkBusy ? (
                    <Loader2 size={14} className="spin" aria-hidden />
                  ) : (
                    <Archive size={14} aria-hidden />
                  )}
                  Archive all orphans
                </button>
              </div>
              <ul className={styles.orphanList} aria-label="Orphan notes">
                {orphanNotes.map((n) => {
                  const rowBusy = orphanRowBusyId === n.id;
                  const disabled = orphanBulkBusy || (!!orphanRowBusyId && !rowBusy);
                  const projVal =
                    (Array.isArray(n.project_ids) && n.project_ids[0]) || n.project_id || '';
                  return (
                    <li key={n.id} className={styles.orphanRow}>
                      <Link to={`/notes/${n.id}`} className={styles.orphanTitle}>
                        {notePreviewLine(n)}
                      </Link>
                      <div className={styles.orphanControls}>
                        <label className={styles.orphanField}>
                          <span className={styles.orphanFieldLabel}>Project</span>
                          <select
                            className={styles.orphanSelect}
                            value={projVal}
                            disabled={disabled}
                            aria-label={`Assign project for note ${notePreviewLine(n)}`}
                            onChange={(e) =>
                              handleOrphanProjectChange(n.id, e.target.value || null)
                            }
                          >
                            <option value="">—</option>
                            {activeProjects.map((p) => (
                              <option key={p.id} value={p.id}>
                                {p.title || 'Untitled'}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className={styles.orphanField}>
                          <span className={styles.orphanFieldLabel}>Area</span>
                          <select
                            className={styles.orphanSelect}
                            value={n.area_id || ''}
                            disabled={disabled}
                            aria-label={`Assign area for note ${notePreviewLine(n)}`}
                            onChange={(e) =>
                              handleOrphanAreaChange(n.id, e.target.value || null)
                            }
                          >
                            <option value="">—</option>
                            {activeAreas.map((a) => (
                              <option key={a.id} value={a.id}>
                                {a.title || 'Untitled'}
                              </option>
                            ))}
                          </select>
                        </label>
                        <div className={styles.orphanRowActions}>
                          <button
                            type="button"
                            className={styles.proposalsToolbarBtn}
                            disabled={disabled}
                            onClick={() => navigate(`/notes/${n.id}`)}
                          >
                            <ExternalLink size={14} aria-hidden />
                            Quick link
                          </button>
                          <button
                            type="button"
                            className={styles.proposalsToolbarBtnMuted}
                            disabled={disabled}
                            onClick={() => handleOrphanArchiveOne(n.id)}
                          >
                            {rowBusy ? (
                              <Loader2 size={14} className="spin" aria-hidden />
                            ) : (
                              <Archive size={14} aria-hidden />
                            )}
                            Archive
                          </button>
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </>
          )}
        </WorkflowStepPanel>

        <WorkflowStepPanel
          stepIndex={5}
          step={REVIEW_WORKFLOW_STEPS[5]}
          flow={reviewFlow}
          patchFlow={setReviewFlow}
          badge={linkProposals.length}
        >
          <div className={styles.workflowEmbed}>
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
          </div>
        </WorkflowStepPanel>

<WorkflowStepPanel
          stepIndex={6}
          step={REVIEW_WORKFLOW_STEPS[6]}
          flow={reviewFlow}
          patchFlow={setReviewFlow}
          badge={summaries.length}
          eyebrow="Health and insights"
        >
          {insightsTab === 'summary' ? (
            <p className={styles.workflowMeta}>
              {granularityLabel(granularity)} · {formatPeriodSubtitle(granularity, anchorDate)}
            </p>
          ) : (
            <p className={styles.workflowMeta}>Stored weekly snapshots · trailing twelve UTC weeks</p>
          )}
          <div className={styles.workflowEmbed}>
            <div className={styles.insightsTabs} role="tablist" aria-label="Insights panels">
              <button
                type="button"
                role="tab"
                aria-selected={insightsTab === 'summary'}
                className={
                  insightsTab === 'summary' ? `${styles.insightsTab} ${styles.insightsTabActive}` : styles.insightsTab
                }
                onClick={() => setInsightsTab('summary')}
              >
                Summary rollup
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={insightsTab === 'health'}
                className={
                  insightsTab === 'health' ? `${styles.insightsTab} ${styles.insightsTabActive}` : styles.insightsTab
                }
                onClick={() => setInsightsTab('health')}
              >
                System Health
              </button>
            </div>
            {insightsTab === 'summary' ? (
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
            ) : (
              <section className={styles.summaryHero} aria-label="System health history">
                <div className={styles.summaryHeroTop}>
                  <div className={styles.summaryHeroTitle}>
                    <HeartPulse size={18} className={styles.summaryIcon} aria-hidden />
                    <h2>System Health</h2>
                  </div>
                  <button
                    type="button"
                    className={styles.retryBtn}
                    disabled={healthHistoryLoading}
                    onClick={() => loadHealthHistory()}
                  >
                    Refresh
                  </button>
                </div>
                <p className={styles.summaryMuted}>
                  Weekly orphan rate and capture activity from persisted snapshots (updated when health metrics are computed).
                </p>
                {healthHistoryError && (
                  <p className={styles.summaryError} role="alert">
                    {healthHistoryError}
                  </p>
                )}
                {healthHistoryLoading && !healthHistoryError && (
                  <p className={styles.summaryMuted}>
                    <Loader2 size={14} className="spin" aria-hidden /> Loading history…
                  </p>
                )}
                {!healthHistoryLoading && !healthHistoryError ? (
                  <HealthTrendChart series={healthHistory} />
                ) : null}
              </section>
            )}
          </div>
        </WorkflowStepPanel>

        <WorkflowStepPanel stepIndex={7} step={REVIEW_WORKFLOW_STEPS[7]} flow={reviewFlow} patchFlow={setReviewFlow}>
          <p className={styles.workflowLead}>
            Lightweight forward look: dues, backlog, and trailing capture pulse for the coming week.
          </p>
          <div className={styles.workflowEmbed}>
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
        </WorkflowStepPanel>

      </div>

    </div>
  );
}
