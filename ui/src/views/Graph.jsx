import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import * as d3 from 'd3';
import useStore from '../stores/useStore';
import EmptyState from '../components/ui/EmptyState';
import { linksAPI } from '../api/engram';
import {
  GRAPH_ENTITY_TYPES,
  clusterAppearanceForGraphNode,
  graphNodeMatchesEnabledTypes,
  graphNodeMatchesLocationFilter,
  heatMapNodeColors,
  heatMapRadiusScale,
  hullPathFromXY,
  isDailyNote,
  isMocNote,
  knowledgeLinkStrokeColor,
  KNOWLEDGE_LINK_COLORS,
  maxNoteHeatActivity,
  neighborIdsForGraphLinks,
  noteActivityForHeatMap,
  STRUCTURAL_LINK_COLOR,
  strokeWidthForKnowledgeWeight,
} from './graphUtils';
import styles from './Graph.module.css';

const TYPE_COLORS = {
  note: 'var(--entity-note)',
  daily: 'var(--entity-note)',
  moc: 'var(--green)',
  resource: 'var(--entity-resource)',
  project: 'var(--entity-project)',
  area: 'var(--entity-area)',
  person: 'var(--entity-person)',
};

function getEntityColor(type) {
  const el = document.documentElement;
  const style = getComputedStyle(el);
  switch (type) {
    case 'note':
    case 'daily':
      return style.getPropertyValue('--entity-note').trim() || '#7C6AFF';
    case 'moc':
      return style.getPropertyValue('--green').trim() || '#22C55E';
    case 'resource':
      return style.getPropertyValue('--entity-resource').trim() || '#8B5CF6';
    case 'project':
      return style.getPropertyValue('--entity-project').trim() || '#3B82F6';
    case 'area':
      return style.getPropertyValue('--entity-area').trim() || '#F59E0B';
    case 'person':
      return style.getPropertyValue('--entity-person').trim() || '#EC4899';
    default:
      return style.getPropertyValue('--text-muted').trim() || '#ADB5BD';
  }
}

const MOC_MAP_ICON = '\u{1F5FA}'; /* world map — distinct from daily calendar */

function clusterPullForceFactory() {
  /** @type {any[]} */
  let simNodes = [];
  const strength = 0.16;

  function force(alpha) {
    const totals = new Map();
    for (const d of simNodes) {
      if (!d.clusterKey || !Number.isFinite(d.x) || !Number.isFinite(d.y)) continue;
      const cur = totals.get(d.clusterKey);
      if (!cur) totals.set(d.clusterKey, [d.x, d.y, 1]);
      else {
        cur[0] += d.x;
        cur[1] += d.y;
        cur[2] += 1;
      }
    }
    for (const [, agg] of totals) {
      if (agg[2] > 0) {
        agg[0] /= agg[2];
        agg[1] /= agg[2];
      }
    }
    for (const d of simNodes) {
      if (!d.clusterKey || !Number.isFinite(d.x)) continue;
      const cen = totals.get(d.clusterKey);
      if (!cen || cen[2] === 0) continue;
      const cx = cen[0];
      const cy = cen[1];
      d.vx = (d.vx || 0) + (cx - d.x) * strength * alpha;
      d.vy = (d.vy || 0) + (cy - d.y) * strength * alpha;
    }
  }

  force.initialize = (n) => {
    simNodes = n || [];
  };

  return force;
}

function buildForceLinks(nodeIdsSet, notes, resources, graphLinks) {
  const links = [];

  notes.forEach((n) => {
    if (n.project_id) {
      const source = `note-${n.id}`;
      const target = `project-${n.project_id}`;
      if (nodeIdsSet.has(source) && nodeIdsSet.has(target))
        links.push({ source, target, linkKind: 'structural' });
    }
    if (n.area_id) {
      const source = `note-${n.id}`;
      const target = `area-${n.area_id}`;
      if (nodeIdsSet.has(source) && nodeIdsSet.has(target))
        links.push({ source, target, linkKind: 'structural' });
    }
    if (n.person_id) {
      const source = `note-${n.id}`;
      const target = `person-${n.person_id}`;
      if (nodeIdsSet.has(source) && nodeIdsSet.has(target))
        links.push({ source, target, linkKind: 'structural' });
    }
  });

  resources.forEach((r) => {
    if (r.area_id) {
      const source = `resource-${r.id}`;
      const target = `area-${r.area_id}`;
      if (nodeIdsSet.has(source) && nodeIdsSet.has(target))
        links.push({ source, target, linkKind: 'structural' });
    }
  });

  graphLinks.forEach((l) => {
    const source = `note-${l.src_id}`;
    const target = `note-${l.dst_id}`;
    if (!nodeIdsSet.has(source) || !nodeIdsSet.has(target)) return;
    links.push({
      source,
      target,
      linkKind: 'knowledge',
      link_type: l.link_type,
      weight: typeof l.weight === 'number' ? l.weight : 1,
    });
  });

  return links;
}

export default function Graph() {
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const navigate = useNavigate();
  const pendingZoomNodeIdRef = useRef(null);
  const { notes, projects, areas, people, resources, tags } = useStore();
  const [selected, setSelected] = useState(null);
  const [graphLinks, setGraphLinks] = useState([]);
  const [clusterMode, setClusterMode] = useState('none');
  const [heatMapEnabled, setHeatMapEnabled] = useState(false);
  const [enabledTypes, setEnabledTypes] = useState(() =>
    Object.fromEntries(GRAPH_ENTITY_TYPES.map((t) => [t, true])),
  );
  const [filterProjectIds, setFilterProjectIds] = useState([]);
  const [filterAreaIds, setFilterAreaIds] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchHighlightId, setSearchHighlightId] = useState(null);
  const [searchStatus, setSearchStatus] = useState('');
  const [focusMode, setFocusMode] = useState(false);

  const lookups = useMemo(
    () => ({
      projectsById: new Map(projects.map((p) => [p.id, p])),
      areasById: new Map(areas.map((a) => [a.id, a])),
      tagsById: new Map(tags.map((t) => [t.id, t])),
      defaultProjectHex: TYPE_COLORS.project,
      defaultAreaHex: TYPE_COLORS.area,
    }),
    [projects, areas, tags],
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await linksAPI.list();
        if (!cancelled) setGraphLinks(res.data || []);
      } catch {
        if (!cancelled) setGraphLinks([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const graphPack = useMemo(() => {
    const baseNodes = [
      ...notes.map((n) => ({
        id: `note-${n.id}`,
        type: isMocNote(n) ? 'moc' : isDailyNote(n) ? 'daily' : 'note',
        label: n.raw_text?.slice(0, 40) || 'Note',
        data: n,
      })),
      ...resources.map((r) => ({
        id: `resource-${r.id}`,
        type: 'resource',
        label: r.title?.slice(0, 40) || 'Resource',
        data: r,
      })),
      ...projects.map((p) => ({
        id: `project-${p.id}`,
        type: 'project',
        label: p.title,
        data: p,
      })),
      ...areas.map((a) => ({
        id: `area-${a.id}`,
        type: 'area',
        label: a.title,
        data: a,
      })),
      ...people.map((p) => ({
        id: `person-${p.id}`,
        type: 'person',
        label: p.title,
        data: p,
      })),
    ].map((gn) => {
      const meta = clusterAppearanceForGraphNode(gn, clusterMode, lookups);
      return { ...gn, clusterKey: meta.key, clusterColor: meta.color };
    });

    let nodes = baseNodes
      .filter((n) => graphNodeMatchesEnabledTypes(n, enabledTypes))
      .filter((n) => graphNodeMatchesLocationFilter(n, filterProjectIds, filterAreaIds));

    let nodeIds = new Set(nodes.map((n) => n.id));
    let links = buildForceLinks(nodeIds, notes, resources, graphLinks);

    if (focusMode && selected?.id && nodeIds.has(selected.id)) {
      const neigh = neighborIdsForGraphLinks(selected.id, links);
      const keep = new Set([selected.id, ...neigh]);
      nodes = nodes.filter((n) => keep.has(n.id));
      nodeIds = new Set(nodes.map((n) => n.id));
      links = links.filter((l) => keep.has(l.source) && keep.has(l.target));
    }

    const clusterRows = [];
    if (clusterMode !== 'none') {
      const byKey = new Map();
      for (const n of nodes) {
        if (!n.clusterKey) continue;
        const row = byKey.get(n.clusterKey);
        if (!row) byKey.set(n.clusterKey, { key: n.clusterKey, color: n.clusterColor, members: [n] });
        else row.members.push(n);
      }
      byKey.forEach((row) => {
        if (row.members.length && row.color) clusterRows.push(row);
      });
    }

    return { nodes, links, clusterRows };
  }, [
    notes,
    projects,
    areas,
    people,
    resources,
    graphLinks,
    clusterMode,
    lookups,
    enabledTypes,
    filterProjectIds,
    filterAreaIds,
    focusMode,
    selected?.id,
  ]);

  useEffect(() => {
    if (!svgRef.current || !containerRef.current) return;

    const hasNodes =
      notes.length > 0 ||
      projects.length > 0 ||
      areas.length > 0 ||
      people.length > 0 ||
      resources.length > 0;

    if (!hasNodes) return;

    const { nodes, links, clusterRows } = graphPack;
    if (nodes.length === 0) {
      d3.select(svgRef.current).selectAll('*').remove();
      return;
    }

    const width = containerRef.current.clientWidth || 900;
    const height = containerRef.current.clientHeight || 600;

    const heatMax = heatMapEnabled ? maxNoteHeatActivity(notes, graphLinks) : 1;
    const heatAccent = TYPE_COLORS.note;

    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3.select(svgRef.current).attr('width', width).attr('height', height);

    const zoom = d3.zoom().scaleExtent([0.1, 4]).on('zoom', (event) => {
      g.attr('transform', event.transform);
    });
    svg.call(zoom);

    const g = svg.append('g');

    const hullLayer = g.append('g').attr('class', styles.hullLayer);

    const simulation = d3
      .forceSimulation(nodes)
      .force(
        'link',
        d3.forceLink(links).id((d) => d.id).distance(90),
      )
      .force('charge', d3.forceManyBody().strength(-220))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force(
        'collision',
        d3.forceCollide((d) => {
          if (heatMapEnabled && (d.type === 'note' || d.type === 'daily' || d.type === 'moc')) {
            const act = noteActivityForHeatMap(d.data, graphLinks);
            const sc = heatMapRadiusScale(act, heatMax);
            const base = d.type === 'moc' ? 20 : 14;
            return base * sc + (d.type === 'moc' ? 14 : 10);
          }
          if (d.type === 'moc') return 26;
          if (d.type === 'resource') return 14;
          if (d.type === 'person') return 14;
          if (d.type === 'area') return 16;
          return 18;
        }),
      );

    if (clusterMode !== 'none') {
      simulation.force('cluster', clusterPullForceFactory());
    }

    const hullBound = hullLayer.selectAll('path').data(clusterRows, (d) => d.key);
    hullBound.exit().remove();
    const hullSel = hullBound.enter().append('path').attr('class', styles.clusterHull).merge(hullBound);

    const link = g
      .append('g')
      .selectAll('line')
      .data(links)
      .enter()
      .append('line')
      .attr('stroke', (d) =>
        d.linkKind === 'knowledge' ? knowledgeLinkStrokeColor(d.link_type) : STRUCTURAL_LINK_COLOR,
      )
      .attr('stroke-width', (d) =>
        d.linkKind === 'knowledge' ? strokeWidthForKnowledgeWeight(d.weight) : 1,
      )
      .attr('stroke-opacity', (d) => (d.linkKind === 'knowledge' ? 0.85 : 0.45));

    const node = g
      .append('g')
      .selectAll('g')
      .data(nodes)
      .enter()
      .append('g')
      .attr('class', (d) => (searchHighlightId && d.id === searchHighlightId ? styles.nodeHighlight : null))
      .attr('cursor', 'pointer')
      .call(
        d3
          .drag()
          .on('start', (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on('drag', (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on('end', (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          }),
      )
      .on('click', (_, d) => setSelected(d));

    node.each(function (d) {
      const el = d3.select(this);
      let fill = getEntityColor(d.type);
      let stroke = fill;
      let r =
        d.type === 'moc'
          ? 11
          : d.type === 'note' || d.type === 'daily'
            ? 6
            : d.type === 'person'
              ? 8
              : 10;
      if (heatMapEnabled && (d.type === 'note' || d.type === 'daily' || d.type === 'moc')) {
        const act = noteActivityForHeatMap(d.data, graphLinks);
        const sc = heatMapRadiusScale(act, heatMax);
        r *= sc;
        const hm = heatMapNodeColors(act, heatMax, heatAccent);
        fill = hm.fill;
        stroke = hm.stroke;
      }

      const isHi = searchHighlightId && d.id === searchHighlightId;
      if (isHi) {
        el.append('circle')
          .attr('r', r + 5)
          .attr('fill', 'none')
          .attr('stroke', getEntityColor('area'))
          .attr('stroke-width', 2.5)
          .attr('stroke-opacity', 0.95);
      }

      if (d.type === 'resource') {
        el.append('rect')
          .attr('x', -7)
          .attr('y', -7)
          .attr('width', 14)
          .attr('height', 14)
          .attr('rx', 1)
          .attr('fill', fill)
          .attr('fill-opacity', 0.45)
          .attr('stroke', stroke)
          .attr('stroke-width', isHi ? 2.25 : 1.5);
      } else if (d.type === 'moc') {
        el.append('circle')
          .attr('r', r + 2)
          .attr('fill', fill)
          .attr('fill-opacity', heatMapEnabled ? 0.28 : 0.18)
          .attr('stroke', stroke)
          .attr('stroke-width', isHi ? 2.5 : 2);
        el.append('text')
          .attr('text-anchor', 'middle')
          .attr('dominant-baseline', 'central')
          .attr('font-size', 15)
          .attr('aria-hidden', true)
          .text(MOC_MAP_ICON);
      } else if (d.type === 'daily') {
        el.append('circle')
          .attr('r', r + 1)
          .attr('fill', fill)
          .attr('fill-opacity', heatMapEnabled ? 0.22 : 0.12)
          .attr('stroke', stroke)
          .attr('stroke-width', isHi ? 2 : 1);
        el.append('text')
          .attr('text-anchor', 'middle')
          .attr('dominant-baseline', 'central')
          .attr('font-size', 13)
          .attr('aria-hidden', true)
          .text(String.fromCodePoint(0x1f4c5));
      } else if (d.type === 'note') {
        el.append('circle')
          .attr('r', r)
          .attr('fill', fill)
          .attr('fill-opacity', 0.5)
          .attr('stroke', stroke)
          .attr('stroke-width', isHi ? 2.25 : 1.5);
      } else if (d.type === 'person') {
        el.append('polygon')
          .attr('points', '0,-8 7,4 -7,4')
          .attr('fill', fill)
          .attr('fill-opacity', 0.5)
          .attr('stroke', stroke)
          .attr('stroke-width', isHi ? 2.25 : 1.5);
      } else if (d.type === 'area') {
        el.append('rect')
          .attr('x', -8)
          .attr('y', -8)
          .attr('width', 16)
          .attr('height', 16)
          .attr('transform', 'rotate(45)')
          .attr('fill', fill)
          .attr('fill-opacity', 0.3)
          .attr('stroke', stroke)
          .attr('stroke-width', isHi ? 2.25 : 1.5)
          .attr('rx', 2);
      } else {
        el.append('rect')
          .attr('x', -10)
          .attr('y', -7)
          .attr('width', 20)
          .attr('height', 14)
          .attr('rx', 4)
          .attr('fill', fill)
          .attr('fill-opacity', 0.3)
          .attr('stroke', stroke)
          .attr('stroke-width', isHi ? 2.25 : 1.5);
      }
    });

    node
      .append('text')
      .text((d) => d.label)
      .attr('dy', (d) =>
        d.type === 'person' ? 18 : d.type === 'daily' || d.type === 'moc' ? 22 : 16,
      )
      .attr('text-anchor', 'middle')
      .attr('fill', getEntityColor('default'))
      .attr('font-size', 10)
      .attr('font-family', 'Inter, sans-serif')
      .each(function (d) {
        const el = d3.select(this);
        if (d.label.length > 20) el.text(d.label.slice(0, 20) + '\u2026');
      });

    simulation.on('tick', () => {
      link
        .attr('x1', (d) => d.source.x)
        .attr('y1', (d) => d.source.y)
        .attr('x2', (d) => d.target.x)
        .attr('y2', (d) => d.target.y);
      node.attr('transform', (d) => `translate(${d.x},${d.y})`);

      hullSel
        .attr('d', (d) => hullPathFromXY(d.members.map((m) => [m.x, m.y])))
        .attr('fill', (d) => d.color)
        .attr('stroke', (d) => d.color);

      const pending = pendingZoomNodeIdRef.current;
      if (pending) {
        const nd = nodes.find((n) => n.id === pending);
        if (nd && Number.isFinite(nd.x) && Number.isFinite(nd.y)) {
          const k = 2.15;
          const t = d3.zoomIdentity.translate(width / 2 - k * nd.x, height / 2 - k * nd.y).scale(k);
          try {
            zoom.transform(svg, t);
          } catch {
            /* d3-zoom uses SVG APIs that are incomplete in jsdom */
          }
          pendingZoomNodeIdRef.current = null;
        }
      }
    });

    return () => simulation.stop();
  }, [
    notes,
    projects,
    areas,
    people,
    resources,
    graphLinks,
    clusterMode,
    heatMapEnabled,
    lookups,
    graphPack,
    searchHighlightId,
  ]);

  const goToNode = (d) => {
    if (!d?.data) return;
    const { type, data } = d;
    if (type === 'note' || type === 'daily' || type === 'moc') navigate(`/notes/${data.id}`);
    else if (type === 'resource') navigate(`/resources/${data.id}`);
    else if (type === 'project') navigate(`/projects/${data.id}`);
    else if (type === 'area') navigate(`/areas/${data.id}`);
    else if (type === 'person') navigate('/people');
    setSelected(null);
  };

  const hasEntities =
    notes.length > 0 ||
    projects.length > 0 ||
    areas.length > 0 ||
    people.length > 0 ||
    resources.length > 0;

  const selectedColor = selected ? getEntityColor(selected.type) : null;

  const toggleType = (t) => {
    setEnabledTypes((prev) => {
      const next = { ...prev, [t]: !prev[t] };
      const anyOn = GRAPH_ENTITY_TYPES.some((x) => next[x]);
      if (!anyOn) return prev;
      return next;
    });
  };

  const toggleProjectFilter = (id) => {
    const k = String(id);
    setFilterProjectIds((prev) => (prev.includes(k) ? prev.filter((x) => x !== k) : [...prev, k]));
  };

  const toggleAreaFilter = (id) => {
    const k = String(id);
    setFilterAreaIds((prev) => (prev.includes(k) ? prev.filter((x) => x !== k) : [...prev, k]));
  };

  const runSearch = () => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) {
      setSearchStatus('Enter text to search.');
      return;
    }
    const pool = graphPack.nodes;
    const hit = pool.find((n) => n.label.toLowerCase().includes(q));
    if (!hit) {
      setSearchHighlightId(null);
      setSearchStatus('No visible node matches.');
      return;
    }
    setSearchHighlightId(hit.id);
    pendingZoomNodeIdRef.current = hit.id;
    setSearchStatus(`Showing: ${hit.label.slice(0, 48)}${hit.label.length > 48 ? '…' : ''}`);
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1>Graph</h1>
        <div className={styles.toolbar}>
          <div className={styles.clusterRow}>
            <label htmlFor="graph-cluster-mode" className={styles.clusterLabel}>
              Cluster by
            </label>
            <select
              id="graph-cluster-mode"
              className={styles.clusterSelect}
              aria-label="Cluster graph by"
              value={clusterMode}
              onChange={(e) => setClusterMode(e.target.value)}
            >
              <option value="none">None</option>
              <option value="project">Project</option>
              <option value="area">Area</option>
              <option value="tag">Tag</option>
            </select>
            <label className={styles.heatMapToggle}>
              <input
                id="graph-heat-map"
                type="checkbox"
                checked={heatMapEnabled}
                onChange={(e) => setHeatMapEnabled(e.target.checked)}
                aria-label="Activity heat map"
              />
              Activity heat map
            </label>
          </div>
          <div className={styles.legendWrap}>
            <div className={styles.legend}>
              {Object.entries(TYPE_COLORS).map(([type, color]) => (
                <span key={type} className={styles.legendItem}>
                  <span className={styles.legendDot} style={{ background: color }} />
                  {type}
                </span>
              ))}
            </div>
            <div className={styles.linkLegend}>
              <span className={styles.linkLegendTitle}>Links</span>
              {Object.entries(KNOWLEDGE_LINK_COLORS).map(([k, color]) => (
                <span key={k} className={styles.legendItem}>
                  <span className={styles.legendLine} style={{ background: color }} />
                  {k}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {!hasEntities ? (
        <EmptyState
          type="graph"
          title="Nothing to graph yet"
          message="Create notes, resources, and link them to projects, areas, or people to see the connections."
        />
      ) : (
        <div ref={containerRef} className={styles.canvas}>
          <aside className={styles.filterAside} aria-label="Graph filters and search">
            <p className={styles.filterAsideTitle}>Filter & search</p>

            <div>
              <p className={styles.filterSubheading}>Node types</p>
              <div className={styles.typeGrid}>
                {GRAPH_ENTITY_TYPES.map((t) => (
                  <label key={t} className={styles.typeChip}>
                    <input
                      type="checkbox"
                      checked={enabledTypes[t] !== false}
                      onChange={() => toggleType(t)}
                      aria-label={`Show ${t} nodes`}
                    />
                    {t}
                  </label>
                ))}
              </div>
            </div>

            <div>
              <p className={styles.filterSubheading}>Projects</p>
              <div className={styles.filterScroll}>
                {projects.length === 0 ? (
                  <span className={styles.searchHint}>No projects</span>
                ) : (
                  projects.map((p) => (
                    <label key={p.id} className={styles.filterOption}>
                      <input
                        type="checkbox"
                        checked={filterProjectIds.includes(String(p.id))}
                        onChange={() => toggleProjectFilter(p.id)}
                      />
                      {p.title}
                    </label>
                  ))
                )}
              </div>
              <p className={styles.searchHint}>None selected = all projects</p>
            </div>

            <div>
              <p className={styles.filterSubheading}>Areas</p>
              <div className={styles.filterScroll}>
                {areas.length === 0 ? (
                  <span className={styles.searchHint}>No areas</span>
                ) : (
                  areas.map((a) => (
                    <label key={a.id} className={styles.filterOption}>
                      <input
                        type="checkbox"
                        checked={filterAreaIds.includes(String(a.id))}
                        onChange={() => toggleAreaFilter(a.id)}
                      />
                      {a.title}
                    </label>
                  ))
                )}
              </div>
              <p className={styles.searchHint}>None selected = all areas</p>
            </div>

            <div>
              <p className={styles.filterSubheading}>Search by label</p>
              <div className={styles.searchRow}>
                <input
                  className={styles.searchInput}
                  type="search"
                  placeholder="Substring…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') runSearch();
                  }}
                  aria-label="Search graph nodes by label"
                  data-testid="graph-search-input"
                />
                <button type="button" className={styles.searchBtn} onClick={runSearch}>
                  Find
                </button>
              </div>
              {searchStatus ? <p className={styles.searchHint}>{searchStatus}</p> : null}
            </div>

            <label className={styles.focusToggle}>
              <input
                type="checkbox"
                checked={focusMode}
                onChange={(e) => setFocusMode(e.target.checked)}
                aria-label="Focus mode"
              />
              Focus mode (selection + 1-hop neighbors)
            </label>
          </aside>
          <svg ref={svgRef} className={styles.svg} />
        </div>
      )}

      {selected && (
        <div className={styles.detail}>
          <div className={styles.detailHeader}>
            <span className={styles.detailType} style={{ color: selectedColor }}>
              {selected.type}
            </span>
            <button type="button" onClick={() => setSelected(null)} className={styles.detailClose}>
              ×
            </button>
          </div>
          <p className={styles.detailLabel}>{selected.label}</p>
          {selected.data?.description && (
            <p className={styles.detailDesc}>{selected.data.description}</p>
          )}
          <button type="button" className={styles.openBtn} onClick={() => goToNode(selected)}>
            Open
          </button>
        </div>
      )}
    </div>
  );
}
