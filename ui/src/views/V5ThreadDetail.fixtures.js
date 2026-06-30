const baseEntity = {
  content: '',
  created_at: '2026-06-18T09:00:00+00:00',
  updated_at: '2026-06-27T08:47:00+00:00',
  due_at: null,
  follow_up_at: null,
  reference_url: null,
  properties: {},
  tags: [],
  ai: {},
};

const sampleEvents = [
  {
    id: 'e1',
    event_type: 'ai_updated',
    actor: 'agent:v4-extraction',
    created_at: '2026-06-27T08:47:00+00:00',
    narration: 'I created task "Ship GTM triggers" from your note.',
  },
  {
    id: 'e2',
    event_type: 'activity_update_added',
    actor: 'user',
    created_at: '2026-06-22T14:00:00+00:00',
    narration: 'Mary said she would review by end of week.',
  },
  {
    id: 'e3',
    event_type: 'created',
    actor: 'user',
    created_at: '2026-06-18T09:00:00+00:00',
    narration: 'Created this project.',
  },
];

export const threadDetailFixtures = {
  project: {
    detail: {
      entity: {
        ...baseEntity,
        id: 'project-hitl',
        type: 'project',
        title: 'HITL Pilot',
        status: 'active',
        ai: {
          entity_summary: 'Rollout to 3 design-partner teams. Blocked on Mary\'s PR #847 review (noted Jun 22). Akash shipped GTM triggers Friday — no follow-up note from you yet. At risk.',
        },
      },
      sections: [
        {
          key: 'open_tasks',
          title: 'Open Tasks',
          items: [
            {
              entity: { id: 't-review', type: 'task', title: 'Review PR #847', status: 'in_progress', properties: { priority: 'high' } },
              relationship: { relationship_type: 'parent' },
            },
            {
              entity: { id: 't-gtm', type: 'task', title: 'Reply to Akash re GTM', status: 'open' },
              relationship: { relationship_type: 'parent' },
            },
          ],
        },
        {
          key: 'people',
          title: 'People',
          items: [
            { entity: { id: 'person-mary', type: 'person', title: 'Mary', status: 'active' }, relationship: { relationship_type: 'assigned_to' } },
            { entity: { id: 'person-akash', type: 'person', title: 'Akash', status: 'active' }, relationship: { relationship_type: 'assigned_to' } },
          ],
        },
        {
          key: 'projects',
          title: 'Projects',
          items: [
            { entity: { id: 'project-engram', type: 'project', title: 'Engram itself', status: 'active' }, relationship: { relationship_type: 'related' } },
          ],
        },
      ],
      project_pulse: {
        headline: 'Focus this project on 1 stuck task and 1 overdue task.',
        summary: { open_tasks: 2, stuck_tasks: 1, overdue_tasks: 1, quiet_tasks: 0 },
        focus_items: [
          {
            kind: 'stuck',
            label: 'Blocked on review',
            entity: { id: 't-review', type: 'task', title: 'Review PR #847', status: 'blocked' },
          },
        ],
      },
      dependency_watch: {
        headline: 'Watch 1 blocked task waiting on Security approval.',
        summary: { blocked_tasks: 1, external_blockers: 1, blocking_tasks: 0 },
        focus_items: [
          {
            kind: 'external_blocker',
            label: 'Blocked by Security approval',
            entity: { id: 't-review', type: 'task', title: 'Review PR #847', status: 'blocked' },
          },
        ],
      },
    },
    events: sampleEvents,
    canonical: '# HITL Pilot\n\nRollout to 3 design-partner teams.',
  },
  person: {
    detail: {
      entity: {
        ...baseEntity,
        id: 'person-mary',
        type: 'person',
        title: 'Mary Patel',
        status: 'active',
        ai: { entity_summary: 'Final reviewer for HITL pilot. Owes PR #847 review since Jun 22.' },
      },
      sections: [
        {
          key: 'assigned_tasks',
          title: 'Assigned Tasks',
          items: [
            { entity: { id: 't-review', type: 'task', title: 'Review PR #847', status: 'blocked' }, relationship: { relationship_type: 'assigned_to' } },
          ],
        },
        {
          key: 'projects',
          title: 'Projects',
          items: [
            { entity: { id: 'project-hitl', type: 'project', title: 'HITL Pilot', status: 'active' }, relationship: { relationship_type: 'assigned_to' } },
          ],
        },
        {
          key: 'related_people',
          title: 'Related People',
          items: [
            { entity: { id: 'person-akash', type: 'person', title: 'Akash', status: 'active' }, relationship: { relationship_type: 'related' } },
          ],
        },
      ],
      pulse: {
        headline: 'Follow up on 1 stuck task and 1 overdue follow-up.',
        summary: { open_tasks: 1, stuck_tasks: 1, overdue_follow_ups: 1, quiet_tasks: 0 },
        focus_items: [
          {
            kind: 'stuck',
            label: 'Blocked on review',
            entity: { id: 't-review', type: 'task', title: 'Review PR #847', status: 'blocked' },
          },
        ],
      },
      dependency_watch: {
        headline: 'No active blockers right now.',
        summary: { blocked_tasks: 0, external_blockers: 0, blocking_tasks: 0 },
        focus_items: [],
      },
    },
    events: sampleEvents,
    canonical: '# Mary Patel\n\nFinal reviewer for HITL pilot.',
  },
  area: {
    detail: {
      entity: {
        ...baseEntity,
        id: 'area-exec',
        type: 'area',
        title: 'Execution',
        status: 'active',
      },
      sections: [
        {
          key: 'projects',
          title: 'Projects',
          items: [
            { entity: { id: 'project-hitl', type: 'project', title: 'HITL Pilot', status: 'active' }, relationship: { relationship_type: 'parent' } },
          ],
        },
        {
          key: 'people',
          title: 'People',
          items: [
            { entity: { id: 'person-mary', type: 'person', title: 'Mary', status: 'active' }, relationship: { relationship_type: 'related' } },
          ],
        },
      ],
    },
    events: sampleEvents.slice(1),
    canonical: '# Execution\n\nPortfolio area for delivery work.',
  },
  resource: {
    detail: {
      entity: {
        ...baseEntity,
        id: 'resource-prd',
        type: 'resource',
        title: 'PRD v5 draft',
        status: 'active',
        reference_url: 'https://example.com/prd',
      },
      sections: [
        {
          key: 'projects',
          title: 'Projects',
          items: [
            { entity: { id: 'project-hitl', type: 'project', title: 'HITL Pilot', status: 'active' }, relationship: { relationship_type: 'references' } },
          ],
        },
      ],
    },
    events: sampleEvents.slice(2),
    canonical: '# PRD v5 draft\n\nReference document for rollout planning.',
  },
  task: {
    detail: {
      entity: {
        ...baseEntity,
        id: 't-review',
        type: 'task',
        title: 'Review PR #847',
        status: 'blocked',
        properties: { priority: 'high' },
      },
      sections: [
        {
          key: 'project',
          title: 'Project',
          items: [
            { entity: { id: 'project-hitl', type: 'project', title: 'HITL Pilot', status: 'active' }, relationship: { relationship_type: 'parent' } },
          ],
        },
        {
          key: 'people_mentioned',
          title: 'People Mentioned',
          items: [
            { entity: { id: 'person-mary', type: 'person', title: 'Mary', status: 'active' }, relationship: { relationship_type: 'mentions' } },
          ],
        },
        {
          key: 'blocking',
          title: 'Blocked By',
          items: [
            { entity: { id: 't-security', type: 'task', title: 'Security approval', status: 'open' }, relationship: { relationship_type: 'blocks' } },
          ],
        },
      ],
      dependency_watch: {
        headline: 'Blocked by Security approval.',
        summary: { blocked_tasks: 1, external_blockers: 1, blocking_tasks: 0 },
        focus_items: [
          {
            kind: 'external_blocker',
            label: 'Blocked by Security approval',
            entity: { id: 't-review', type: 'task', title: 'Review PR #847', status: 'blocked' },
          },
        ],
      },
    },
    events: sampleEvents,
    canonical: '# Review PR #847\n\nWaiting on Mary.',
  },
  note: {
    detail: {
      entity: {
        ...baseEntity,
        id: 'note-mary',
        type: 'note',
        title: 'Mary PR review note',
        status: 'active',
        content: 'Mary said she would review PR #847 by end of week.',
      },
      sections: [
        {
          key: 'projects',
          title: 'Projects',
          items: [
            { entity: { id: 'project-hitl', type: 'project', title: 'HITL Pilot', status: 'active' }, relationship: { relationship_type: 'related' } },
          ],
        },
        {
          key: 'people_mentioned',
          title: 'People Mentioned',
          items: [
            { entity: { id: 'person-mary', type: 'person', title: 'Mary', status: 'active' }, relationship: { relationship_type: 'mentions' } },
          ],
        },
      ],
    },
    events: [
      {
        id: 'e-note',
        event_type: 'created',
        actor: 'user',
        created_at: '2026-06-22T14:00:00+00:00',
        narration: 'Captured note about Mary and PR #847.',
      },
    ],
    canonical: '# Mary PR review note\n\nMary said she would review PR #847 by end of week.',
  },
};

export function fixtureForType(type) {
  return threadDetailFixtures[type];
}
