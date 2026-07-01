import CitationsList from './CitationsList';

const meta = {
  title: 'V5/CitationsList',
  component: CitationsList,
  parameters: {
    layout: 'padded',
  },
};

export default meta;

const baseCitation = {
  entity_id: 'note-mary',
  snippet: 'Mary said she would review PR #847 by end of week.',
  created_at: '2026-06-22T14:00:00+00:00',
};

export const SingleCitation = {
  args: {
    citations: [baseCitation],
    onOpen: () => {},
  },
};

export const MultipleCitations = {
  args: {
    citations: [
      baseCitation,
      {
        entity_id: 'note-akash',
        snippet: 'Akash shipped the GTM triggers on Friday and is waiting for feedback on the draft campaign before we can schedule the launch review.',
        created_at: '2026-06-25T09:30:00+00:00',
        meta: 'parent project',
      },
      {
        entity_id: 'task-review',
        snippet: 'Review PR #847',
        created_at: '2026-06-20T10:00:00+00:00',
        meta: 'assigned to Mary',
      },
    ],
    onOpen: () => {},
  },
};

export const NoCitations = {
  args: {
    citations: [],
    emptyText: 'No citations available.',
    onOpen: () => {},
  },
};
