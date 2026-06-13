import { describe, expect, it, vi, beforeEach } from 'vitest';
import { Editor } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import { Markdown } from '@tiptap/markdown';
import { v4API } from '../api/v4Client';
import { createMentionExtension } from './mentionExtension';

vi.mock('../api/v4Client', () => ({
  v4API: { mentions: vi.fn() },
}));

function makeEditor(extra = []) {
  const element = document.createElement('div');
  document.body.appendChild(element);
  return new Editor({
    element,
    extensions: [
      StarterKit.configure({ link: { openOnClick: false, autolink: false } }),
      Markdown.configure({ html: false }),
      ...extra,
    ],
    content: '',
  });
}

describe('createMentionExtension', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches and groups entities by type via v4API.mentions', async () => {
    v4API.mentions.mockResolvedValue({
      results: {
        task: [{ id: 't1', type: 'task', title: 'Ship it', path: '/tasks/t1' }],
        person: [{ id: 'p1', type: 'person', title: 'Priya', path: '/people/p1' }],
      },
    });

    const editor = makeEditor([createMentionExtension({ name: 'entityMention', char: '[[' })]);
    const extension = editor.extensionManager.extensions.find((e) => e.name === 'entityMention');
    const items = await extension.options.suggestion.items({ query: 'pri' });

    expect(v4API.mentions).toHaveBeenCalledWith({ q: 'pri', limit: 5 });
    expect(items.task[0].title).toBe('Ship it');
    expect(items.person[0].title).toBe('Priya');
    editor.destroy();
  });

  it('inserts the picked entity as a markdown link and replaces the trigger text', () => {
    const editor = makeEditor([createMentionExtension({ name: 'entityMention', char: '[[' })]);
    editor.commands.insertContent('See [[Agent');

    const extension = editor.extensionManager.extensions.find((e) => e.name === 'entityMention');
    const docEnd = editor.state.doc.content.size - 1;
    const range = { from: docEnd - 'Agent'.length - 2, to: docEnd };
    extension.options.suggestion.command({
      editor,
      range,
      props: { id: 'proj1', type: 'project', title: 'Agent Platform', path: '/projects/proj1' },
    });

    expect(editor.getMarkdown()).toBe('See [Agent Platform](/projects/proj1) ');
    editor.destroy();
  });

  it('restricts the person-mention extension to type=person', async () => {
    v4API.mentions.mockResolvedValue({ results: {} });

    const editor = makeEditor([createMentionExtension({ name: 'personMention', char: '@', types: ['person'] })]);
    const extension = editor.extensionManager.extensions.find((e) => e.name === 'personMention');
    await extension.options.suggestion.items({ query: 'pri' });

    expect(v4API.mentions).toHaveBeenCalledWith({ q: 'pri', limit: 5, types: 'person' });
    editor.destroy();
  });
});
