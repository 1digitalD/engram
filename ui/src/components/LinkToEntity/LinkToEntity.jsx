import React, { useState, useMemo } from 'react';
import { Link2, Loader2 } from 'lucide-react';
import { linksAPI } from '../../api/engram';
import useStore from '../../stores/useStore';
import { getEntityTitle } from '../ConnectionsPanel/ConnectionsPanel';
import styles from './LinkToEntity.module.css';

const LINK_TYPES = [
  { value: 'related', label: 'Related' },
  { value: 'references', label: 'References' },
  { value: 'blocks', label: 'Blocks' },
  { value: 'mentions', label: 'Mentions' },
  { value: 'derived_from', label: 'Derived From' },
  { value: 'assigned_to', label: 'Assigned To' },
];

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

  const handleSubmit = async () => {
    if (!pick || busy) return;
    setBusy(true);
    try {
      await linksAPI.create({ src_id: entityId, dst_id: pick, link_type: linkType });
      store.addToast({ type: 'success', message: 'Link created' });
      setPick('');
      setQuery('');
      setLinkType('related');
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
        >
          {LINK_TYPES.map(lt => (
            <option key={lt.value} value={lt.value}>{lt.label}</option>
          ))}
        </select>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={handleSubmit}
          disabled={!pick || busy}
        >
          {busy ? <Loader2 size={13} className="spin" /> : 'Link'}
        </button>
      </div>
    </div>
  );
}
