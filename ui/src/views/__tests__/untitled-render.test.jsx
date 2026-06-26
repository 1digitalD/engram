import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import V4EntityList from '../V4EntityList';
import { v4API } from '../../api/v4Client';

vi.mock('../../api/v4Client', () => ({
  v4API: {
    entities: {
      list: vi.fn(),
    },
  },
}));

describe('untitled entity rendering', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it('does not render "Untitled" for null-title entities and shows a disambiguating placeholder', async () => {
    const nullTitleEntity = {
      id: 'task-null',
      type: 'task',
      title: null,
      status: 'open',
      created_at: '2026-05-20T09:00:00+00:00',
      updated_at: '2026-05-20T10:00:00+00:00',
      properties: {},
      tags: [],
    };

    v4API.entities.list.mockResolvedValue({ data: [nullTitleEntity] });

    const { container } = render(
      <MemoryRouter>
        <V4EntityList type="task" />
      </MemoryRouter>,
    );

    await screen.findByText(/\(no title\)/);

    const text = container.textContent;
    expect(text).not.toMatch(/Untitled/i);
    expect(text).toMatch(/\(no title\)/);
    expect(text).toContain('task-null');
    expect(text).toContain('[task]');
  });
});
