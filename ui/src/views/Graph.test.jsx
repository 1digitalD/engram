import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Graph from './Graph';
import useStore from '../stores/useStore';
import { linksAPI } from '../api/engram';
import {
  isDailyNote,
  knowledgeLinkStrokeColor,
  strokeWidthForKnowledgeWeight,
  convexHullMonotone,
  hullPathFromXY,
  clusterAppearanceForGraphNode,
  coerceHexColor,
  GRAPH_CLUSTER_MODES,
  incomingKnowledgeBacklinkCount,
  noteActivityForHeatMap,
  heatMapNodeColors,
  heatMapRadiusScale,
  maxNoteHeatActivity,
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

  it('computes convex hull for spread points', () => {
    const square = [
      [0, 0],
      [10, 0],
      [10, 10],
      [0, 10],
      [5, 5],
    ];
    const h = convexHullMonotone(square);
    expect(h.length).toBe(4);
  });

  it('builds hull SVG path for triangle', () => {
    const d = hullPathFromXY(
      [
        [0, 0],
        [100, 0],
        [50, 80],
      ],
      20,
    );
    expect(d.startsWith('M ')).toBe(true);
    expect(d.endsWith(' Z')).toBe(true);
  });

  it('maps graph nodes to cluster keys and colors', () => {
    const projectsById = new Map([['p1', { id: 'p1', color: '#ff00aa' }]]);
    const areasById = new Map([['a1', { id: 'a1', color: '#00aaff' }]]);
    const tagsById = new Map([['t1', { id: 't1', color: '#aabb00' }]]);
    const L = {
      projectsById,
      areasById,
      tagsById,
      defaultProjectHex: '#4ADE80',
      defaultAreaHex: '#60A5FA',
    };

    const note = { type: 'note', data: { project_id: 'p1', tag_ids: ['t1'] } };
    expect(clusterAppearanceForGraphNode(note, 'project', L).key).toBe('project:p1');
    expect(clusterAppearanceForGraphNode(note, 'project', L).color).toBe('#ff00aa');

    const areaNode = { type: 'area', data: { id: 'a1', color: '#112233' } };
    expect(clusterAppearanceForGraphNode(areaNode, 'area', L).key).toBe('area:a1');
    expect(clusterAppearanceForGraphNode(areaNode, 'area', L).color).toBe('#112233');

    expect(
      clusterAppearanceForGraphNode({ type: 'note', data: { tag_ids: ['z9', 't1'] } }, 'tag', L).key,
    ).toBe('tag:t1');

    expect(coerceHexColor('oops', '#123456')).toBe('#123456');
    expect(GRAPH_CLUSTER_MODES).toContain('tag');
    expect(GRAPH_CLUSTER_MODES).toContain('none');
  });

  it('counts incoming knowledge links and heat map derivations', () => {
    const links = [
      { src_id: 'a', dst_id: 'n1', link_type: 'related' },
      { src_id: 'b', dst_id: 'n1', link_type: 'mentions' },
      { src_id: 'n1', dst_id: 'c', link_type: 'related' },
    ];
    expect(incomingKnowledgeBacklinkCount('n1', links)).toBe(2);
    expect(noteActivityForHeatMap({ id: 'n1', backlink_count: 5 }, links)).toBe(5);
    expect(noteActivityForHeatMap({ id: 'n1' }, links)).toBe(2);

    expect(maxNoteHeatActivity([{ id: 'a' }, { id: 'b', backlink_count: 3 }], links)).toBe(3);

    const low = heatMapNodeColors(0, 4, '#7C6AFF');
    const high = heatMapNodeColors(4, 4, '#7C6AFF');
    expect(low.fill).toContain('rgb');
    expect(high.fill).not.toBe(low.fill);

    expect(heatMapRadiusScale(0, 10)).toBe(1);
    expect(heatMapRadiusScale(10, 10)).toBeGreaterThan(1);
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
      tags: [],
    });
  });

  it('loads knowledge links on mount', async () => {
    vi.mocked(useStore).mockReturnValue({
      notes: [{ id: 'n1', raw_text: 'Hi', bucket: 'INBOX', project_id: null, area_id: null, person_id: null }],
      projects: [],
      areas: [],
      people: [],
      resources: [],
      tags: [],
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
      tags: [],
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
      tags: [],
    });
    renderGraph();
    expect(screen.getByText('resource')).toBeInTheDocument();
    expect(screen.getByText('Links')).toBeInTheDocument();
    expect(screen.getByText('related')).toBeInTheDocument();
  });

  it('offers Cluster by modes including None and Tag', () => {
    vi.mocked(useStore).mockReturnValue({
      notes: [{ id: 'n1', raw_text: 'Hi', bucket: 'INBOX', project_id: null, area_id: null, person_id: null }],
      projects: [],
      areas: [],
      people: [],
      resources: [],
      tags: [],
    });
    renderGraph();
    const sel = screen.getByLabelText(/cluster graph by/i);
    expect(sel).toHaveValue('none');
    fireEvent.change(sel, { target: { value: 'tag' } });
    expect(sel).toHaveValue('tag');
    fireEvent.change(sel, { target: { value: 'none' } });
    expect(sel).toHaveValue('none');
  });

  it('offers Activity heat map toggle', () => {
    vi.mocked(useStore).mockReturnValue({
      notes: [{ id: 'n1', raw_text: 'Hi', bucket: 'INBOX', project_id: null, area_id: null, person_id: null }],
      projects: [],
      areas: [],
      people: [],
      resources: [],
      tags: [],
    });
    renderGraph();
    const box = screen.getByRole('checkbox', { name: /activity heat map/i });
    expect(box).not.toBeChecked();
    fireEvent.click(box);
    expect(box).toBeChecked();
  });
});
