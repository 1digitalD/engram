import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import * as d3 from 'd3';
import useStore from '../stores/useStore';
import EmptyState from '../components/ui/EmptyState';
import { linksAPI } from '../api/engram';
import {
  isDailyNote,
  knowledgeLinkStrokeColor,
  KNOWLEDGE_LINK_COLORS,
  STRUCTURAL_LINK_COLOR,
  strokeWidthForKnowledgeWeight,
} from './graphUtils';
import styles from './Graph.module.css';

const TYPE_COLORS = {
  note: '#7C6AFF',
  daily: '#7C6AFF',
  resource: '#C084FC',
  project: '#4ADE80',
  area: '#60A5FA',
  person: '#FBBF24',
};

export default function Graph() {
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const navigate = useNavigate();
  const { notes, projects, areas, people, resources } = useStore();
  const [selected, setSelected] = useState(null);
  const [graphLinks, setGraphLinks] = useState([]);

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

  useEffect(() => {
    if (!svgRef.current || !containerRef.current) return;

    const hasNodes =
      notes.length > 0 ||
      projects.length > 0 ||
      areas.length > 0 ||
      people.length > 0 ||
      resources.length > 0;

    if (!hasNodes) return;

    const width = containerRef.current.clientWidth || 900;
    const height = containerRef.current.clientHeight || 600;

    const nodes = [
      ...notes.map((n) => ({
        id: `note-${n.id}`,
        type: isDailyNote(n) ? 'daily' : 'note',
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
        label: p.name,
        data: p,
      })),
      ...areas.map((a) => ({
        id: `area-${a.id}`,
        type: 'area',
        label: a.name,
        data: a,
      })),
      ...people.map((p) => ({
        id: `person-${p.id}`,
        type: 'person',
        label: p.name,
        data: p,
      })),
    ];

    const nodeIds = new Set(nodes.map((n) => n.id));

    const links = [];

    notes.forEach((n) => {
      if (n.project_id) {
        const source = `note-${n.id}`;
        const target = `project-${n.project_id}`;
        if (nodeIds.has(source) && nodeIds.has(target))
          links.push({ source, target, linkKind: 'structural' });
      }
      if (n.area_id) {
        const source = `note-${n.id}`;
        const target = `area-${n.area_id}`;
        if (nodeIds.has(source) && nodeIds.has(target))
          links.push({ source, target, linkKind: 'structural' });
      }
      if (n.person_id) {
        const source = `note-${n.id}`;
        const target = `person-${n.person_id}`;
        if (nodeIds.has(source) && nodeIds.has(target))
          links.push({ source, target, linkKind: 'structural' });
      }
    });

    resources.forEach((r) => {
      if (r.area_id) {
        const source = `resource-${r.id}`;
        const target = `area-${r.area_id}`;
        if (nodeIds.has(source) && nodeIds.has(target))
          links.push({ source, target, linkKind: 'structural' });
      }
    });

    graphLinks.forEach((l) => {
      const source = `note-${l.src_id}`;
      const target = `note-${l.dst_id}`;
      if (!nodeIds.has(source) || !nodeIds.has(target)) return;
      links.push({
        source,
        target,
        linkKind: 'knowledge',
        link_type: l.link_type,
        weight: typeof l.weight === 'number' ? l.weight : 1,
      });
    });

    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3.select(svgRef.current).attr('width', width).attr('height', height);

    const zoom = d3.zoom().scaleExtent([0.1, 4]).on('zoom', (event) => {
      g.attr('transform', event.transform);
    });
    svg.call(zoom);

    const g = svg.append('g');

    const simulation = d3
      .forceSimulation(nodes)
      .force(
        'link',
        d3.forceLink(links).id((d) => d.id).distance(90),
      )
      .force('charge', d3.forceManyBody().strength(-220))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide(22));

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
      const color = TYPE_COLORS[d.type] || '#888';
      const r = d.type === 'note' || d.type === 'daily' ? 6 : d.type === 'person' ? 8 : 10;

      if (d.type === 'resource') {
        el.append('rect')
          .attr('x', -7)
          .attr('y', -7)
          .attr('width', 14)
          .attr('height', 14)
          .attr('rx', 1)
          .attr('fill', color)
          .attr('fill-opacity', 0.45)
          .attr('stroke', color)
          .attr('stroke-width', 1.5);
      } else if (d.type === 'daily') {
        el.append('circle')
          .attr('r', r + 1)
          .attr('fill', color)
          .attr('fill-opacity', 0.12)
          .attr('stroke', color)
          .attr('stroke-width', 1);
        el.append('text')
          .attr('text-anchor', 'middle')
          .attr('dominant-baseline', 'central')
          .attr('font-size', 13)
          .attr('aria-hidden', true)
          .text(String.fromCodePoint(0x1f4c5));
      } else if (d.type === 'note') {
        el.append('circle')
          .attr('r', r)
          .attr('fill', color)
          .attr('fill-opacity', 0.5)
          .attr('stroke', color)
          .attr('stroke-width', 1.5);
      } else if (d.type === 'person') {
        el.append('polygon')
          .attr('points', '0,-8 7,4 -7,4')
          .attr('fill', color)
          .attr('fill-opacity', 0.5)
          .attr('stroke', color)
          .attr('stroke-width', 1.5);
      } else if (d.type === 'area') {
        el.append('rect')
          .attr('x', -8)
          .attr('y', -8)
          .attr('width', 16)
          .attr('height', 16)
          .attr('transform', 'rotate(45)')
          .attr('fill', color)
          .attr('fill-opacity', 0.3)
          .attr('stroke', color)
          .attr('stroke-width', 1.5)
          .attr('rx', 2);
      } else {
        el.append('rect')
          .attr('x', -10)
          .attr('y', -7)
          .attr('width', 20)
          .attr('height', 14)
          .attr('rx', 4)
          .attr('fill', color)
          .attr('fill-opacity', 0.3)
          .attr('stroke', color)
          .attr('stroke-width', 1.5);
      }
    });

    node
      .append('text')
      .text((d) => d.label)
      .attr('dy', (d) => (d.type === 'person' ? 18 : d.type === 'daily' ? 20 : 16))
      .attr('text-anchor', 'middle')
      .attr('fill', '#8888A0')
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
    });

    return () => simulation.stop();
  }, [notes, projects, areas, people, resources, graphLinks]);

  const goToNode = (d) => {
    if (!d?.data) return;
    const { type, data } = d;
    if (type === 'note' || type === 'daily') navigate(`/notes/${data.id}`);
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

  const selectedColor = selected ? TYPE_COLORS[selected.type] || '#888' : null;

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1>Graph</h1>
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

      {!hasEntities ? (
        <EmptyState
          type="graph"
          title="Nothing to graph yet"
          message="Create notes, resources, and link them to projects, areas, or people to see the connections."
        />
      ) : (
        <div ref={containerRef} className={styles.canvas}>
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
