import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import * as d3 from 'd3';
import useStore from '../stores/useStore';
import EmptyState from '../components/ui/EmptyState';
import styles from './Graph.module.css';

const TYPE_COLORS = {
  note:    '#7C6AFF',
  project: '#4ADE80',
  area:    '#60A5FA',
  person:  '#FBBF24',
  task:    '#FF6B6B',
};

export default function Graph() {
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const navigate = useNavigate();
  const { notes, projects, areas, people, tasks } = useStore();
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (!svgRef.current || !containerRef.current) return;
    if (notes.length === 0 && projects.length === 0) return;

    const width  = containerRef.current.clientWidth  || 900;
    const height = containerRef.current.clientHeight || 600;

    // Build nodes
    const nodes = [
      ...notes.map(n => ({ id: `note-${n.id}`, type: 'note', label: n.raw_text?.slice(0, 40) || 'Note', data: n })),
      ...projects.map(p => ({ id: `project-${p.id}`, type: 'project', label: p.name, data: p })),
      ...areas.map(a => ({ id: `area-${a.id}`, type: 'area', label: a.name, data: a })),
      ...people.map(p => ({ id: `person-${p.id}`, type: 'person', label: p.name, data: p })),
    ];

    // Build links
    const links = [];
    notes.forEach(n => {
      if (n.project_id) links.push({ source: `note-${n.id}`, target: `project-${n.project_id}` });
      if (n.area_id)    links.push({ source: `note-${n.id}`, target: `area-${n.area_id}` });
      if (n.person_id)  links.push({ source: `note-${n.id}`, target: `person-${n.person_id}` });
    });

    // Clear
    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height);

    // Zoom
    const zoom = d3.zoom()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });
    svg.call(zoom);

    const g = svg.append('g');

    // Simulation
    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(d => d.id).distance(80))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide(20));

    // Links
    const link = g.append('g')
      .selectAll('line')
      .data(links)
      .enter().append('line')
      .attr('stroke', '#2A2A32')
      .attr('stroke-width', 1)
      .attr('stroke-opacity', 0.6);

    // Node groups
    const node = g.append('g')
      .selectAll('g')
      .data(nodes)
      .enter().append('g')
      .attr('cursor', 'pointer')
      .call(d3.drag()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x; d.fy = d.y;
        })
        .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null; d.fy = null;
        }))
      .on('click', (_, d) => setSelected(d));

    // Node shapes
    node.each(function(d) {
      const el = d3.select(this);
      const color = TYPE_COLORS[d.type] || '#888';
      const r = d.type === 'note' ? 6 : d.type === 'person' ? 8 : 10;

      if (d.type === 'note') {
        el.append('circle').attr('r', r).attr('fill', color).attr('fill-opacity', 0.5).attr('stroke', color).attr('stroke-width', 1.5);
      } else if (d.type === 'person') {
        el.append('polygon')
          .attr('points', '0,-8 7,4 -7,4')
          .attr('fill', color).attr('fill-opacity', 0.5).attr('stroke', color).attr('stroke-width', 1.5);
      } else if (d.type === 'area') {
        el.append('rect')
          .attr('x', -8).attr('y', -8).attr('width', 16).attr('height', 16)
          .attr('transform', 'rotate(45)')
          .attr('fill', color).attr('fill-opacity', 0.3).attr('stroke', color).attr('stroke-width', 1.5)
          .attr('rx', 2);
      } else {
        el.append('rect')
          .attr('x', -10).attr('y', -7).attr('width', 20).attr('height', 14)
          .attr('rx', 4)
          .attr('fill', color).attr('fill-opacity', 0.3).attr('stroke', color).attr('stroke-width', 1.5);
      }
    });

    // Labels
    node.append('text')
      .text(d => d.label)
      .attr('dy', d => d.type === 'person' ? 18 : 16)
      .attr('text-anchor', 'middle')
      .attr('fill', '#8888A0')
      .attr('font-size', 10)
      .attr('font-family', 'Inter, sans-serif')
      .each(function(d) {
        const el = d3.select(this);
        if (d.label.length > 20) el.text(d.label.slice(0, 20) + '…');
      });

    // Tick
    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);
      node.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    return () => simulation.stop();
  }, [notes, projects, areas, people, tasks]);

  const goToNode = (d) => {
    if (!d?.data) return;
    const { type, data } = d;
    if (type === 'note') navigate(`/notes/${data.id}`);
    else if (type === 'project') navigate(`/projects/${data.id}`);
    else if (type === 'area') navigate(`/areas/${data.id}`);
    else if (type === 'person') navigate('/people');
    setSelected(null);
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1>Graph</h1>
        <div className={styles.legend}>
          {Object.entries(TYPE_COLORS).map(([type, color]) => (
            <span key={type} className={styles.legendItem}>
              <span className={styles.legendDot} style={{ background: color }} />
              {type}
            </span>
          ))}
        </div>
      </div>

      {(notes.length === 0 && projects.length === 0) ? (
        <EmptyState
          type="graph"
          title="Nothing to graph yet"
          message="Create some notes and link them to projects, areas, or people to see the connections."
        />
      ) : (
        <div ref={containerRef} className={styles.canvas}>
          <svg ref={svgRef} className={styles.svg} />
        </div>
      )}

      {selected && (
        <div className={styles.detail}>
          <div className={styles.detailHeader}>
            <span className={styles.detailType} style={{ color: TYPE_COLORS[selected.type] }}>{selected.type}</span>
            <button type="button" onClick={() => setSelected(null)} className={styles.detailClose}>×</button>
          </div>
          <p className={styles.detailLabel}>{selected.label}</p>
          {selected.data?.description && <p className={styles.detailDesc}>{selected.data.description}</p>}
          <button type="button" className={styles.openBtn} onClick={() => goToNode(selected)}>
            Open
          </button>
        </div>
      )}
    </div>
  );
}
