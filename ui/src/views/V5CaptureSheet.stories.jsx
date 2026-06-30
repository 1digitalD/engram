/**
 * Storybook stories for V5CaptureSheet.
 * States: empty, typing, streaming.
 * Attachments: none, thread, project.
 */
/* eslint-disable import/no-extraneous-dependencies */
import React, { useState } from 'react';
import V5CaptureSheet, { CAPTURE_PLACEHOLDER } from './V5CaptureSheet';

const attachmentOptions = [
  { id: '', label: 'None', type: '' },
  { id: 'thread-1', label: 'Mary · PR review', type: 'person' },
  { id: 'project-1', label: 'HITL Pilot', type: 'project' },
];

export default {
  title: 'V5/CaptureSheet',
  component: V5CaptureSheet,
  parameters: { layout: 'fullscreen' },
};

function SheetStory({ initialContent = '', initialAttachment, streamingEvents = [] }) {
  const [open, setOpen] = useState(true);
  return (
    <V5CaptureSheet
      open={open}
      onClose={() => setOpen(false)}
      defaultAttachment={initialAttachment}
      attachmentOptions={attachmentOptions}
      captureFn={async (_body, { onEvent }) => {
        for (const event of streamingEvents) {
          onEvent(event);
        }
        return {
          source_note: { id: 'note-1', title: 'Captured note' },
          applied_changes: [{ type: 'summary_updated' }],
          suggestions: [{ id: 's1' }],
          warnings: [],
        };
      }}
    />
  );
}

export const EmptyNone = {
  render: () => <SheetStory />,
};

export const TypingThread = {
  render: () => (
    <SheetStory
      initialContent="Ask Henry about rollout before Wed"
      initialAttachment={{ id: 'thread-1', type: 'person' }}
    />
  ),
};

export const StreamingProject = {
  render: () => (
    <SheetStory
      initialContent="Mary review is overdue"
      initialAttachment={{ id: 'project-1', type: 'project' }}
      streamingEvents={[
        { type: 'reading', data: { content_length: 24 } },
        { type: 'extracting', data: {} },
        { type: 'linking', data: { links_created: 1 } },
        { type: 'done', data: {} },
      ]}
    />
  ),
};

export const AttachmentNone = {
  render: () => <SheetStory initialAttachment={null} />,
};

export const AttachmentThread = {
  render: () => (
    <SheetStory initialAttachment={{ id: 'thread-1', type: 'person', label: 'Mary · PR review' }} />
  ),
};

export const AttachmentProject = {
  render: () => (
    <SheetStory initialAttachment={{ id: 'project-1', type: 'project', label: 'HITL Pilot' }} />
  ),
};

export const PlaceholderCopy = {
  render: () => (
    <p style={{ padding: 24, fontFamily: 'system-ui' }}>{CAPTURE_PLACEHOLDER}</p>
  ),
};
