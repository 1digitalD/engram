import { entityTitleLabel } from '../utils/entityDisplay';

const PEOPLE_SECTION_KEYS = new Set([
  'people',
  'people_mentioned',
  'related_people',
]);

const TASK_SECTION_KEYS = [
  'open_tasks',
  'assigned_tasks',
  'tasks',
  'derived_tasks',
  'blocking',
];

const THREAD_TYPES = new Set(['project', 'person']);

export function pathForEntity(entity) {
  if (!entity?.id) return '#';
  const base = entity.type === 'person' ? 'people' : `${entity.type}s`;
  return `/${base}/${entity.id}`;
}

export function sectionItems(detail, key) {
  return detail?.sections?.find((section) => section.key === key)?.items || [];
}

export function buildActivityUpdates(detail) {
  return sectionItems(detail, 'activity_updates');
}

export function activityUpdatesMeta(detail) {
  return detail?.sections?.find((section) => section.key === 'activity_updates')?.meta || null;
}

export function allSectionItems(detail) {
  return (detail?.sections || []).flatMap((section) => section.items || []);
}

export function humanizeToken(value) {
  if (!value) return '';
  return String(value).replace(/_/g, ' ');
}

export function formatTimelineDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const now = new Date();
  const sameDay = date.toDateString() === now.toDateString();
  if (sameDay) {
    return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  }
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

export function narrativeSummary(entity, canonicalText) {
  const entitySummary = entity?.ai?.entity_summary?.trim();
  if (entitySummary) return entitySummary;

  const extractionSummary = entity?.ai?.summary?.trim();
  if (extractionSummary) return extractionSummary;

  if (canonicalText) {
    const paragraph = canonicalText
      .split(/\n+/)
      .map((line) => line.trim())
      .find((line) => line && !line.startsWith('#'));
    if (paragraph) return paragraph.slice(0, 480);
  }

  if (entity?.content?.trim()) {
    return entity.content.trim().slice(0, 480);
  }

  return "I haven't summarized this yet";
}

function openTasksFromDetail(detail) {
  const items = [];
  TASK_SECTION_KEYS.forEach((key) => {
    sectionItems(detail, key).forEach((item) => {
      const status = item?.entity?.status;
      if (['open', 'in_progress', 'waiting', 'blocked'].includes(status)) {
        items.push(item);
      }
    });
  });
  return items;
}

import {
  BUMP_FOLLOW_UP_LABEL,
  FOLLOW_UP_24H_TITLE,
} from '../utils/followUpActions';

function actionButtonsForTask(item) {
  const entity = item.entity;
  return [
    { key: 'open', label: 'Open', action: 'open', href: pathForEntity(entity) },
    { key: 'done', label: '✓', action: 'done', entityId: entity.id },
    {
      key: 'remind',
      label: BUMP_FOLLOW_UP_LABEL,
      action: 'remind',
      entityId: entity.id,
      title: FOLLOW_UP_24H_TITLE,
    },
  ];
}

export function buildSignalCards(detail, entityType) {
  const cards = [];
  if (entityType === 'project' && detail?.project_pulse?.headline) {
    cards.push({
      key: 'project-pulse',
      title: 'Project pulse',
      body: detail.project_pulse.headline,
      meta: detail.project_pulse.summary,
    });
  }
  if (entityType === 'person' && detail?.pulse?.headline) {
    cards.push({
      key: 'person-pulse',
      title: '1:1 pulse',
      body: detail.pulse.headline,
      meta: detail.pulse.summary,
    });
  }
  if (detail?.dependency_watch?.headline) {
    cards.push({
      key: 'dependency-watch',
      title: 'Dependency watch',
      body: detail.dependency_watch.headline,
      meta: detail.dependency_watch.summary,
    });
  }
  return cards;
}

export function buildNextActions(detail) {
  const actions = [];
  const seen = new Set();

  const pushAction = (action) => {
    if (!action?.id || seen.has(action.id)) return;
    seen.add(action.id);
    actions.push(action);
  };

  (detail?.dependency_watch?.focus_items || []).slice(0, 2).forEach((item) => {
    pushAction({
      id: `blocker-${item.entity?.id}`,
      label: item.label || entityTitleLabel(item.entity),
      entity: item.entity,
      buttons: actionButtonsForTask(item),
    });
  });

  (detail?.project_pulse?.focus_items || detail?.pulse?.focus_items || [])
    .slice(0, 2)
    .forEach((item) => {
      pushAction({
        id: `pulse-${item.entity?.id}`,
        label: item.label ? `${entityTitleLabel(item.entity)} — ${item.label}` : entityTitleLabel(item.entity),
        entity: item.entity,
        buttons: actionButtonsForTask(item),
      });
    });

  openTasksFromDetail(detail).forEach((item) => {
    pushAction({
      id: `task-${item.entity?.id}`,
      label: entityTitleLabel(item.entity),
      entity: item.entity,
      buttons: actionButtonsForTask(item),
    });
  });

  if (actions.length === 0 && detail?.entity?.follow_up_at) {
    const threadTarget = primaryThreadTarget(detail);
    const buttons = [
      {
        key: 'remind',
        label: BUMP_FOLLOW_UP_LABEL,
        action: 'remind',
        entityId: detail.entity.id,
        title: FOLLOW_UP_24H_TITLE,
      },
    ];
    if (threadTarget && threadTarget.id !== detail.entity.id) {
      buttons.push({ key: 'open', label: 'Open thread', action: 'open', href: pathForEntity(threadTarget) });
    }
    pushAction({
      id: 'follow-up',
      label: `Follow up on ${entityTitleLabel(detail.entity)}`,
      buttons,
    });
  }

  return actions.slice(0, 3);
}

export function buildPeople(detail) {
  const people = [];
  const seen = new Set();

  (detail?.sections || []).forEach((section) => {
    if (!PEOPLE_SECTION_KEYS.has(section.key)) return;
    (section.items || []).forEach((item) => {
      const entity = item?.entity;
      if (!entity || entity.type !== 'person' || seen.has(entity.id)) return;
      seen.add(entity.id);
      people.push({
        id: entity.id,
        entity,
        relationship: humanizeToken(item.relationship?.relationship_type || section.title),
        subtitle: item.label || section.title,
      });
    });
  });

  return people;
}

export function buildRelatedThreads(detail, entity) {
  const linked = allSectionItems(detail)
    .map((item) => item?.entity)
    .filter((item) => item && THREAD_TYPES.has(item.type) && item.id !== entity?.id);

  const personCount = buildPeople(detail).length;

  const unique = new Map();
  linked.forEach((thread) => {
    if (unique.has(thread.id)) return;
    unique.set(thread.id, {
      id: thread.id,
      entity: thread,
      subtitle: thread.type === 'person'
        ? 'related person'
        : (personCount
          ? `shares ${personCount} linked ${personCount === 1 ? 'member' : 'members'}`
          : 'linked thread'),
      score: (thread.status === 'active' ? 2 : 0) + (thread.type === 'project' ? 1 : 0),
    });
  });

  return [...unique.values()]
    .sort((a, b) => b.score - a.score)
    .slice(0, 6);
}

function primaryThreadTarget(detail) {
  const entity = detail?.entity;
  if (!entity) return null;
  if (THREAD_TYPES.has(entity.type)) return entity;
  return buildRelatedThreads(detail, entity)[0]?.entity || entity;
}

export function statusLabel(status) {
  return humanizeToken(status || 'active');
}

function referenceSnippet(entity) {
  const summary = entity?.ai?.entity_summary?.trim() || entity?.ai?.summary?.trim();
  if (summary) return summary;

  const title = entity?.title?.trim();
  if (title) return title;

  const content = entity?.content?.trim();
  if (content) return content.slice(0, 140);

  return '(no summary)';
}

export function buildMeetingPrep(detail) {
  if (detail?.entity?.type !== 'person') return null;
  const prep = detail?.meeting_prep;
  if (!prep) return null;

  const agendaItems = (prep.agenda_items || []).map((item) => ({
    id: item.entity?.id || item.title,
    kind: item.kind,
    title: item.title,
    reason: item.reason,
    entity: item.entity,
  }));

  const recentNotes = (prep.recent_notes || []).map((note) => ({
    id: note.id,
    title: note.title,
    preview: note.preview,
    updatedAt: note.updated_at,
  }));

  if (!prep.headline && agendaItems.length === 0 && recentNotes.length === 0) {
    return null;
  }

  return {
    headline: prep.headline,
    counts: prep.counts,
    agendaItems,
    recentNotes,
  };
}

export function buildCurrentLoad(detail) {
  if (detail?.entity?.type !== 'person') return [];
  const load = detail?.current_load;
  if (!Array.isArray(load) || load.length === 0) return [];

  return load.map((item) => ({
    id: item.task?.id,
    task: item.task,
    lastHeardAt: item.last_heard_at,
    lastHeardPreview: item.last_heard_preview,
  })).filter((item) => item.id);
}

export function buildReferences(detail, entity) {
  const references = [];
  const seen = new Set();

  (detail?.sections || []).forEach((section) => {
    (section.items || []).forEach((item) => {
      const related = item?.entity;
      if (!related || related.id === entity?.id || seen.has(related.id)) return;
      seen.add(related.id);
      const relationshipType = item.relationship?.relationship_type;
      references.push({
        entity_id: related.id,
        snippet: referenceSnippet(related),
        created_at: related.created_at,
        updated_at: related.updated_at,
        entity: related,
        meta: humanizeToken(relationshipType || section.title),
      });
    });
  });

  return references;
}
