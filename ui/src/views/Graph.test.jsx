import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Graph from './Graph';
import useStore from '../stores/useStore';
import { linksAPI } from '../api/engram';
import {
  isDailyNote,
  knowledgeLinkStrokeColor,
  strokeWidthForKnowledgeWeight,
} from './graphUtils';

vi.mock('../stores/useStore');
vi.mock('../api/engram', () => ({
  linksAPI: { list: vi.fn() },
}));

function renderGraph() {
  return render(
    <MemoryRouter>
      <Graph />
    </MemoryRouter>,
  );
}

describe('graphUtils', () => {
  it('detects daily notes by INBOX bucket and heading prefix', () => {
    expect(
      isDailyNote({
        raw_text: '# Daily — 2026-05-09\n\n## Focus\n',
        bucket: 'INBOX',
      }),
    ).toBe(true);
    expect(isDailyNote({ raw_text: 'Random', bucket: 'INBOX' })).toBe(false);
    expect(
      isDailyNote({
        raw_text: '# Daily — 2026-05-09\n',
        bucket: 'ARCHIVES',
      }),
    ).toBe(false);
  });

  it('maps link types to stroke colors', () => {
    expect(knowledgeLinkStrokeColor('related')).toBe('#9333EA');
    expect(knowledgeLinkStrokeColor('child_of')).toBe('#2563EB');
    expect(knowledgeLinkStrokeColor('depends_on')).toBe('#EA580C');
    expect(knowledgeLinkStrokeColor('mentions')).toBe('#6B7280');
  });

  it('scales stroke width by knowledge link weight', () => {
    const low = strokeWidthForKnowledgeWeight(0.2);
    const high = strokeWidthForKnowledgeWeight(1.5);
    expect(high).toBeGreaterThan(low);
    expect(strokeWidthForKnowledgeWeight(NaN)).toBeGreaterThan(0);
  });
});

describe('Graph', () => {
  beforeEach(() => {
    vi.mocked(linksAPI.list).mockResolvedValue({ data: [] });
    vi.mocked(useStore).mockReturnValue({
      notes: [],
      projects: [],
      areas: [],
      people: [],
      resources: [],
    });
  });

  it('loads knowledge links on mount', async () => {
    vi.mocked(useStore).mockReturnValue({
      notes: [{ id: 'n1', raw_text: 'Hi', bucket: 'INBOX', project_id: null, area_id: null, person_id: null }],
      projects: [],
      areas: [],
      people: [],
      resources: [],
    });
    renderGraph();
    await waitFor(() => {
      expect(linksAPI.list).toHaveBeenCalled();
    });
  });

  it('shows empty state when there is no data', () => {
    renderGraph();
    expect(screen.getByText('Nothing to graph yet')).toBeInTheDocument();
  });

  it('renders graph canvas when entities exist', async () => {
    vi.mocked(useStore).mockReturnValue({
      notes: [],
      projects: [{ id: 'p1', name: 'P', description: '' }],
      areas: [],
      people: [],
      resources: [],
    });
    renderGraph();
    await waitFor(() => {
      expect(screen.queryByText('Nothing to graph yet')).not.toBeInTheDocument();
    });
    const svg = document.querySelector('svg');
    expect(svg).toBeTruthy();
  });

  it('shows node and link legends', () => {
    vi.mocked(useStore).mockReturnValue({
      notes: [{ id: 'n1', raw_text: 'Hi', bucket: 'INBOX', project_id: null, area_id: null, person_id: null }],
      projects: [],
      areas: [],
      people: [],
      resources: [],
    });
    renderGraph();
    expect(screen.getByText('resource')).toBeInTheDocument();
    expect(screen.getByText('Links')).toBeInTheDocument();
    expect(screen.getByText('related')).toBeInTheDocument();
  });
});
