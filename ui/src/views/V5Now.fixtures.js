/**
 * Mock data matching the v5 mockup screen m-now.
 * Used until Slice 2.2 threads endpoint lands, then toggled off.
 */
export const MOCKED_NOW_DATA = {
  needs_you_now: [
    {
      id: 'task-standup',
      type: 'task',
      subject: 'Send yesterday’s standup update to the team before 10:00 AM.',
      when: 'Due in 32 min',
      why_now: 'Hard deadline this morning',
      thread: { id: 'project-launch', label: 'Product Launch', type: 'project' },
      actions: [
        { key: 'open', label: 'Open', primary: true },
        { key: 'snooze', label: 'Follow up tomorrow', title: 'Sets follow-up to 24 hours from now until a date picker ships.' },
        { key: 'done', label: 'Mark done' },
      ],
      attention_score: 94,
    },
    {
      id: 'task-pr-review',
      type: 'task',
      subject: 'Review Mary’s PR for the HITL pilot — she’s blocked on your feedback.',
      when: 'Waiting 2 days',
      why_now: 'Blocking a teammate',
      thread: { id: 'project-hitl', label: 'HITL Pilot', type: 'project' },
      actions: [
        { key: 'review', label: 'Review now', primary: true },
        { key: 'delegate', label: 'Re-assign' },
      ],
      attention_score: 88,
    },
    {
      id: 'task-contract',
      type: 'task',
      subject: 'Sign the revised vendor contract so Legal can file it today.',
      when: 'Due today',
      why_now: 'Legal deadline',
      thread: { id: 'project-vendor', label: 'Vendor Renewal', type: 'project' },
      actions: [
        { key: 'open', label: 'Open doc', primary: true },
        { key: 'remind', label: 'Remind me' },
      ],
      attention_score: 81,
    },
  ],
  waiting_on_you: [
    {
      id: 'task-akash-brief',
      type: 'task',
      subject: 'Akash is waiting on the GTM brief before he can schedule design reviews.',
      when: 'Follow-up tomorrow',
      why_now: 'Dependency for design',
      thread: { id: 'project-gtm', label: 'GTM Trigger Doc', type: 'project' },
      actions: [
        { key: 'reply', label: 'Reply to Akash', primary: true },
        { key: 'schedule', label: 'Schedule time' },
      ],
      attention_score: 62,
    },
    {
      id: 'person-henry',
      type: 'person',
      subject: 'Henry said he would share the rollout timeline by EOD yesterday.',
      when: 'Overdue by 1 day',
      why_now: 'Silent since update promised',
      thread: { id: 'person-henry', label: 'Henry', type: 'person' },
      actions: [
        { key: 'nudge', label: 'Send nudge', primary: true },
        { key: 'note', label: 'Add note' },
      ],
      attention_score: 55,
    },
  ],
  ambient: [
    {
      id: 'project-strategy',
      type: 'project',
      subject: 'Q3 strategy doc is still taking shape; no action needed this week.',
      when: 'Updated 3 days ago',
      why_now: 'Ambient context',
      thread: { id: 'project-strategy', label: 'Q3 Strategy', type: 'project' },
      actions: [
        { key: 'view', label: 'View' },
      ],
      attention_score: 18,
    },
    {
      id: 'area-health',
      type: 'area',
      subject: 'Team health metrics look stable; no open items.',
      when: 'Checked last week',
      why_now: 'Ambient context',
      thread: { id: 'area-health', label: 'Team Health', type: 'area' },
      actions: [
        { key: 'view', label: 'View' },
      ],
      attention_score: 12,
    },
  ],
};
