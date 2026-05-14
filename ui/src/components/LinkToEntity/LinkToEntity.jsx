import React, { useState, useMemo, useEffect } from 'react';
import { Link2, Loader2 } from 'lucide-react';
import { linksAPI, linkTypesAPI } from '../../api/engram';
import useStore from '../../stores/useStore';
import { getEntityTitle } from '../../utils/entity';
import styles from './LinkToEntity.module.css';

const LINK_TYPE_LABELS = {
  related: 'Related',
  parent: 'Parent',
  references: 'References',
  blocks: 'Blocks',
  mentions: 'Mentions',
  derived_from: 'Derived From',
  assigned_to: 'Assigned To',
};

const ENTITY_GROUPS = [
  { key: 'notes', label: 'Notes', type: 'note' },
  { key: 'projects', label: 'Projects', type: 'project' },
  { key: 'areas', label: 'Areas', type: 'area' },
  { key: 'people', label: 'People', type: 'person' },
  { key: 'tasks', label: 'Tasks', type: 'task' },
  { key: 'resources', label: 'Resources', type: 'resource' },
];

export default function LinkToEntity({ entityId, entityType, onLinkCreated }) {
  const store = useStore();
  const [query, setQuery] = useState('');
  const [pick, setPick] = useState('');
  const [linkType, setLinkType] = useState('related');
  const [busy, setBusy] = useState(false);
  const [allowedTypes, setAllowedTypes] = useState(null);

  const allEntities = useMemo(() => {
    const results = [];
    for (const group of ENTITY_GROUPS) {
      const items = store[group.key] || [];
      for (const item of items) {
        if (item.id === entityId) continue;
        const title = getEntityTitle({ ...item, type: group.type });
        results.push({ id: item.id, title, type: group.type, groupLabel: group.label });
      }
    }
    return results;
  }, [store, entityId]);

  const filtered = useMemo(() => {
    if (!query.trim()) return allEntities.slice(0, 80);
    const q = query.toLowerCase();
    return allEntities
      .filter(e => e.title.toLowerCase().includes(q))
      .slice(0, 80);
  }, [allEntities, query]);

  const grouped = useMemo(() => {
    const map = {};
    for (const e of filtered) {
      if (!map[e.type]) map[e.type] = [];
      map[e.type].push(e);
    }
    return map;
  }, [filtered]);

  const selectedTarget = useMemo(() => {
    return allEntities.find(e => e.id === pick) || null;
  }, [allEntities, pick]);

  useEffect(() => {
    if (!selectedTarget || !entityType) {
      setAllowedTypes(null);
      return;
    }
    let cancelled = false;
    linkTypesAPI.forPair(entityType, selectedTarget.type).then(res => {
      if (cancelled) return;
      setAllowedTypes(res.data || []);
      if (res.data?.length > 0) {
        setLinkType(res.data[0].link_type);
      }
    }).catch(() => {
      if (!cancelled) setAllowedTypes([]);
    });
    return () => { cancelled = true; };
  }, [pick, entityType, selectedTarget?.type]);

  const handleSubmit = async () => {
    if (!pick || busy) return;
    setBusy(true);
    try {
      await linksAPI.create({ src_id: entityId, dst_id: pick, link_type: linkType });
      store.addToast({ type: 'success', message: 'Link created' });
      setPick('');
      setQuery('');
      setLinkType('related');
      setAllowedTypes(null);
      onLinkCreated?.();
    } catch (e) {
      store.addToast({ type: 'error', message: e.message || 'Could not create link' });
    } finally {
      setBusy(false);
    }
  };

  const handleSearchChange = (e) => {
    setQuery(e.target.value);
    setPick('');
    setAllowedTypes(null);
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <Link2 size={14} />
        <span>Link to...</span>
      </div>
      <div className={styles.row}>
        <input
          type="search"
          className={styles.search}
          placeholder="Filter entities..."
          value={query}
          onChange={handleSearchChange}
        />
        <select
          className={styles.select}
          value={pick}
          onChange={e => setPick(e.target.value)}
        >
          <option value="">Select target...</option>
          {Object.keys(grouped).length === 0 && query.trim() && (
            <option value="" disabled>No matches</option>
          )}
          {ENTITY_GROUPS.map(group => {
            const items = grouped[group.type];
            if (!items?.length) return null;
            return (
              <optgroup key={group.type} label={group.label}>
                {items.map(item => (
                  <option key={item.id} value={item.id}>{item.title}</option>
                ))}
              </optgroup>
            );
          })}
        </select>
        <select
          className={styles.linkType}
          value={linkType}
          onChange={e => setLinkType(e.target.value)}
          disabled={!selectedTarget || allowedTypes === null}
        >
          {!selectedTarget ? (
            <option value="">Select target first</option>
          ) : allowedTypes === null ? (
            <option value="">Loading...</option>
          ) : allowedTypes.length === 0 ? (
            <option value="" disabled>No allowed link types</option>
          ) : (
            allowedTypes.map(t => (
              <option key={t.link_type} value={t.link_type}>
                {LINK_TYPE_LABELS[t.link_type] || t.link_type}
              </option>
            ))
          )}
        </select>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={handleSubmit}
          disabled={!pick || busy || !allowedTypes || allowedTypes.length === 0}
        >
          {busy ? <Loader2 size={13} className="spin" /> : 'Link'}
        </button>
      </div>
    </div>
  );
}
