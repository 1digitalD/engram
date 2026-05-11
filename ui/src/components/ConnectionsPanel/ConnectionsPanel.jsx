import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, Link2, FileText, FolderOpen, Map, User, BookOpen } from 'lucide-react';
import { connectionsAPI } from '../../api/engram';
import styles from './ConnectionsPanel.module.css';

const TYPE_CONFIG = {
  note:     { label: 'Notes',     icon: FileText,  route: '/notes' },
  task:     { label: 'Tasks',     icon: FileText,  route: '/tasks' },
  project:  { label: 'Projects',  icon: FolderOpen, route: '/projects' },
  area:     { label: 'Areas',     icon: Map,       route: '/areas' },
  person:   { label: 'People',    icon: User,      route: '/people' },
  resource: { label: 'Resources', icon: BookOpen,  route: '/resources' },
};

function entityTitle(entity) {
  if (!entity) return 'Untitled';
  return entity.title || entity.name || (entity.raw_text || '').split('\n')[0].replace(/^#\s*/, '').trim() || 'Untitled';
}

function entityRoute(entity) {
  const cfg = TYPE_CONFIG[entity?.type];
  if (!cfg) return null;
  return `${cfg.route}/${entity.id}`;
}

function entityIcon(type, size = 12) {
  const cfg = TYPE_CONFIG[type];
  const Icon = cfg?.icon || FileText;
  return <Icon size={size} />;
}

export default function ConnectionsPanel({ entityId, refreshKey = 0 }) {
  const [loading, setLoading] = useState(false);
  const [groups, setGroups] = useState({});
  const [totalCount, setTotalCount] = useState(0);

  const loadConnections = useCallback(async () => {
    if (!entityId) return;
    setLoading(true);
    try {
      const res = await connectionsAPI.forEntity(entityId);
      const outgoing = res.outgoing || [];
      const incoming = res.incoming || [];

      const grouped = {};
      const seen = new Set();

      for (const link of [...outgoing, ...incoming]) {
        const entity = link.dst_entity || link.src_entity;
        if (!entity || seen.has(entity.id)) continue;
        seen.add(entity.id);

        const type = entity.type || 'note';
        if (!grouped[type]) grouped[type] = [];
        grouped[type].push({ entity, link });
      }

      setGroups(grouped);
      setTotalCount(seen.size);
    } catch {
      setGroups({});
      setTotalCount(0);
    } finally {
      setLoading(false);
    }
  }, [entityId]);

  useEffect(() => {
    loadConnections();
  }, [loadConnections, refreshKey]);

  if (loading) {
    return (
      <div className={styles.panel} data-testid="connections-panel">
        <h3 className={styles.panelTitle}>
          <Link2 size={14} /> Connections
        </h3>
        <p className={styles.muted}>
          <Loader2 size={14} className="spin" /> Loading connections…
        </p>
      </div>
    );
  }

  if (totalCount === 0) {
    return (
      <div className={styles.panel} data-testid="connections-panel">
        <h3 className={styles.panelTitle}>
          <Link2 size={14} /> Connections
        </h3>
        <p className={styles.muted}>No connections yet.</p>
      </div>
    );
  }

  const sortedTypes = Object.keys(groups).sort((a, b) => {
    const order = ['note', 'project', 'area', 'person', 'task', 'resource'];
    return order.indexOf(a) - order.indexOf(b);
  });

  return (
    <div className={styles.panel} data-testid="connections-panel">
      <h3 className={styles.panelTitle}>
        <Link2 size={14} /> Connections
        <span className={styles.count}>{totalCount}</span>
      </h3>
      {sortedTypes.map((type) => {
        const cfg = TYPE_CONFIG[type] || { label: type, icon: FileText, route: '' };
        const Icon = cfg.icon;
        return (
          <div key={type} className={styles.group} data-testid={`connections-group-${type}`}>
            <h4 className={styles.groupTitle}>
              <Icon size={12} /> {cfg.label}
            </h4>
            <ul className={styles.entityList}>
              {groups[type].map(({ entity, link }) => {
                const route = entityRoute(entity);
                return (
                  <li key={entity.id} className={styles.entityItem}>
                    {route ? (
                      <Link to={route} className={styles.entityLink} data-testid={`connection-link-${entity.id}`}>
                        {entityIcon(entity.type, 12)}
                        <span className={styles.entityName}>{entityTitle(entity)}</span>
                      </Link>
                    ) : (
                      <span className={styles.entityLink}>
                        {entityIcon(entity.type, 12)}
                        <span className={styles.entityName}>{entityTitle(entity)}</span>
                      </span>
                    )}
                    {link?.link_type && (
                      <span className={styles.linkType}>{link.link_type}</span>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
