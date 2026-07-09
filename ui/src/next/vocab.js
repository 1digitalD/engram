/** v6 vision vocabulary — maps v4 DTO terms to UX-facing labels. */

export const ENTITY_TYPE_LABELS = {
  note: 'Stream entry',
  project: 'Space',
  area: 'Space',
  task: 'Commitment',
  person: 'Person',
  theme: 'Theme',
  resource: 'Resource',
};

export const ENTITY_TYPE_GLYPHS = {
  note: 'N',
  project: 'S',
  area: 'S',
  task: 'C',
  person: 'P',
  theme: 'T',
  resource: 'R',
};

export const SECTION_LABELS = {
  routing_summary: 'Routing summary',
  applied_annotations: 'Applied annotations',
  proposed_commitments: 'Proposed commitments',
  decisions: 'Decisions',
  questions: 'Open questions',
  leftovers: 'Leftovers',
};

export const SURFACE_LABELS = {
  today: 'Today',
  workboard: 'Workboard',
  stream: 'Stream',
  review: 'Review',
  spaces: 'Spaces',
  people: 'People',
};

export const ACTION_LABELS = {
  verify: 'Verify',
  accept: 'Verify',
  edit: 'Edit',
  dismiss: 'Dismiss',
  later: 'Later',
  acceptRest: 'Accept remainder',
};

export function entityTypeLabel(type) {
  return ENTITY_TYPE_LABELS[type] || type || 'Item';
}

export function sectionLabel(name) {
  return SECTION_LABELS[name] || name?.replace(/_/g, ' ') || 'Section';
}

export function proposalLabel(suggestion) {
  const op = suggestion?.operation_type || suggestion?.suggestion_type || '';
  if (op === 'create_decision' || suggestion?.suggestion_type === 'create_decision') {
    return 'Decision proposal';
  }
  if (
    op === 'create_entity'
    || op === 'create_new_entity'
    || suggestion?.suggestion_type === 'create_task'
  ) {
    const entityType = suggestion?.payload?.type || 'task';
    return `New ${entityTypeLabel(entityType).toLowerCase()}`;
  }
  if (op === 'link_existing') return 'Link proposal';
  if (op === 'update_entity') return 'Update proposal';
  return 'Proposal';
}

export function itemTitle(item) {
  return item?.title
    || item?.payload?.title
    || item?.payload?.statement
    || item?.question
    || item?.reason
    || 'Untitled';
}

export function itemEvidence(item) {
  return item?.payload?.evidence || item?.reason || item?.receipt?.quote || '';
}
