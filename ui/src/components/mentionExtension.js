import { Extension } from '@tiptap/core';
import { PluginKey } from '@tiptap/pm/state';
import Suggestion from '@tiptap/suggestion';
import { ReactRenderer } from '@tiptap/react';
import { v4API } from '../api/v4Client';
import MentionList from './MentionList';

function positionPopup(popup, clientRect) {
  let rect;
  try {
    rect = clientRect?.();
  } catch {
    return;
  }
  if (!rect) return;
  popup.style.position = 'fixed';
  popup.style.left = `${Math.round(rect.left)}px`;
  popup.style.top = `${Math.round(rect.bottom + 4)}px`;
  popup.style.zIndex = '1000';
}

/**
 * Builds a Tiptap extension that opens an inline picker when `char` is typed,
 * letting the user pick an existing entity (grouped by type) to link to.
 * The picked entity is inserted as a markdown link `[Title](/type/id)`,
 * which the capture/activity-update endpoints resolve into a `mentions`
 * relationship without any LLM involvement.
 */
export function createMentionExtension({ name, char, types }) {
  return Extension.create({
    name,

    addOptions() {
      return {
        suggestion: {
          char,
          allowSpaces: true,
          startOfLine: false,
          items: async ({ query }) => {
            try {
              const params = { q: query, limit: 5 };
              if (types) params.types = types.join(',');
              const data = await v4API.mentions(params);
              return data.results || {};
            } catch {
              return {};
            }
          },
          command: ({ editor, range, props }) => {
            editor
              .chain()
              .focus()
              .deleteRange(range)
              .insertContent([
                { type: 'text', marks: [{ type: 'link', attrs: { href: props.path } }], text: props.title },
                { type: 'text', text: ' ' },
              ])
              .run();
          },
          render: () => {
            let component;
            let popup;

            return {
              onStart: (props) => {
                component = new ReactRenderer(MentionList, { props, editor: props.editor });
                popup = document.createElement('div');
                popup.style.position = 'fixed';
                document.body.appendChild(popup);
                popup.appendChild(component.element);
                positionPopup(popup, props.clientRect);
              },
              onUpdate: (props) => {
                component.updateProps(props);
                positionPopup(popup, props.clientRect);
              },
              onKeyDown: (props) => {
                if (props.event.key === 'Escape') {
                  popup?.remove();
                  return true;
                }
                return component.ref?.onKeyDown(props) ?? false;
              },
              onExit: () => {
                popup?.remove();
                component?.destroy();
              },
            };
          },
        },
      };
    },

    addProseMirrorPlugins() {
      return [
        Suggestion({
          editor: this.editor,
          pluginKey: new PluginKey(`suggestion-${this.name}`),
          ...this.options.suggestion,
        }),
      ];
    },
  });
}
