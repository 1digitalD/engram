import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, Link2, FileText, FolderOpen, Map, User, Library, CheckSquare } from 'lucide-react';
import { connectionsAPI } from '../../api/engram';
import useStore from '../../stores/useStore';
import styles from './ConnectionsPanel.module.css';

const TYPE_CONFIG = {
  note:     { label: 'Notes',     icon: FileText,   route: (id) => `/notes/${id}` },
  task:     { label: 'Tasks',     icon: CheckSquare, route: (id) => `/tasks/${id}` },
  project:  { label: 'Projects',  icon: FolderOpen, route: (id) => `/projects/${id}` },
  area:     { label: 'Areas',     icon: Map,        route: (id) => `/areas/${id}` },
  person:   { label: 'People',    icon: User,       route: (id) => `/people/${id}` },
  resource: { label: 'Resources', icon: Library,    route: (id) => `/resources/${id}` },
};

const STORE_COLLECTIONS = [
  ['note', 'notes'],
  ['task', 'tasks'],
  ['project', 'projects'],
  ['area', 'areas'],
  ['person', 'people'],
  ['resource', 'resources'],
];

export function resolveEntity(id, store) {
  if (!id || !store) return null;

  for (const [type, key] of STORE_COLLECTIONS) {
    const entity = store[key]?.find((item) => item.id === id);
    if (entity) {
      return { ...entity, type };
    }
  }

  return null;
}

function normalizeEntity(entity) {
  if (!entity?.id) return null;
  return entity.type ? entity : { ...entity, type: 'note' };
}

export function getEntityTitle(entity) {
  if (!entity) return 'Untitled';
  if (entity.type === 'note') {
    return (entity.raw_text || '')
      .split('\n')[0]
      .replace(/^#\s*/, '')
      .trim() || entity.title || 'Untitled';
  }
  return entity.title || 'Untitled';
}

export function getEntityRoute(entity) {
  const cfg = TYPE_CONFIG[entity?.type];
  if (!cfg) return null;
  return cfg.route(entity.id);
}

export function EntityTypeIcon({ type, size = 12 }) {
  const cfg = TYPE_CONFIG[type];
  const Icon = cfg?.icon || FileText;
  return <Icon size={size} />;
}

export default function ConnectionsPanel({ entityId, refreshKey = 0 }) {
  const store = useStore();
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
      const collect = (link, otherId, embeddedEntity) => {
        const entity = resolveEntity(otherId, store) || normalizeEntity(embeddedEntity);
        if (!entity || seen.has(entity.id)) return;
        seen.add(entity.id);

        const type = entity.type || 'note';
        if (!grouped[type]) grouped[type] = [];
        grouped[type].push({ entity, link });
      };

      for (const link of outgoing) {
        collect(link, link.dst_id, link.dst_entity);
      }

      for (const link of incoming) {
        collect(link, link.src_id, link.src_entity);
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
                const route = getEntityRoute(entity);
                return (
                  <li key={entity.id} className={styles.entityItem}>
                    {route ? (
                      <Link to={route} className={styles.entityLink} data-testid={`connection-link-${entity.id}`}>
                        <EntityTypeIcon type={entity.type} size={12} />
                        <span className={styles.entityName}>{getEntityTitle(entity)}</span>
                      </Link>
                    ) : (
                      <span className={styles.entityLink}>
                        <EntityTypeIcon type={entity.type} size={12} />
                        <span className={styles.entityName}>{getEntityTitle(entity)}</span>
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
