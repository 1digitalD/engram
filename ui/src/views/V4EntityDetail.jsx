import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { v4API } from '../api/v4Client';
import styles from './V4EntityScreens.module.css';

const statusOptions = {
  note: ['active', 'processed', 'archived'],
  task: ['open', 'in_progress', 'waiting', 'blocked', 'done', 'cancelled'],
  project: ['active', 'on_hold', 'completed', 'cancelled'],
  area: ['active', 'archived'],
  person: ['active', 'archived'],
  resource: ['active', 'archived'],
};

const relationshipOptions = ['parent', 'related', 'derived_from', 'mentions', 'assigned_to', 'references', 'blocks'];

function pathForEntity(entity) {
  if (!entity) return '#';
  const base = entity.type === 'person' ? 'people' : `${entity.type}s`;
  return `/${base}/${entity.id}`;
}

export default function V4EntityDetail({ type: routeType }) {
  const { id } = useParams();
  const [detail, setDetail] = useState(null);
  const [draft, setDraft] = useState({ title: '', content: '', status: 'active' });
  const [targetEntityId, setTargetEntityId] = useState('');
  const [relationshipType, setRelationshipType] = useState('related');
  const [error, setError] = useState('');

  async function loadDetail() {
    const response = await v4API.entities.detail(id);
    setDetail(response);
    setDraft({
      title: response.entity.title || '',
      content: response.entity.content || '',
      status: response.entity.status || 'active',
    });
  }

  useEffect(() => {
    loadDetail().catch((err) => setError(err.message));
  }, [id]);

  async function handleSave(event) {
    event.preventDefault();
    setError('');
    try {
      await v4API.entities.update(id, draft);
      await loadDetail();
    } catch (err) {
      setError(err.message || 'Failed to save entity');
    }
  }

  async function handleArchive() {
    setError('');
    try {
      await v4API.entities.delete(id);
      await loadDetail();
    } catch (err) {
      setError(err.message || 'Failed to archive entity');
    }
  }

  async function handleAddRelationship(event) {
    event.preventDefault();
    if (!targetEntityId.trim()) return;
    setError('');
    try {
      await v4API.relationships.create(id, {
        target_entity_id: targetEntityId.trim(),
        relationship_type: relationshipType,
      });
      setTargetEntityId('');
      await loadDetail();
    } catch (err) {
      setError(err.message || 'Failed to add relationship');
    }
  }

  async function handleRemoveRelationship(relationshipId) {
    setError('');
    try {
      await v4API.relationships.delete(relationshipId);
      await loadDetail();
    } catch (err) {
      setError(err.message || 'Failed to remove relationship');
    }
  }

  if (!detail) {
    return (
      <main className={styles.screen}>
        <section className={styles.panel}>
          <p>{error || 'Loading entity...'}</p>
        </section>
      </main>
    );
  }

  const entity = detail.entity;
  const entityType = routeType || entity.type;

  return (
    <main className={styles.screen}>
      <section className={styles.panel}>
        <p className={styles.eyebrow}>Engram v4 {entityType}</p>
        <h1>{entity.title || 'Untitled'}</h1>
        <form onSubmit={handleSave} className={styles.form} aria-label="Edit entity">
          <input
            value={draft.title}
            onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))}
            aria-label="Title"
          />
          <textarea
            value={draft.content}
            onChange={(event) => setDraft((current) => ({ ...current, content: event.target.value }))}
            aria-label="Content"
            rows={5}
          />
          <select
            value={draft.status}
            onChange={(event) => setDraft((current) => ({ ...current, status: event.target.value }))}
            aria-label="Status"
          >
            {(statusOptions[entity.type] || ['active']).map((status) => (
              <option key={status} value={status}>{status}</option>
            ))}
          </select>
          <div className={styles.actions}>
            <button type="submit">Save</button>
            <button type="button" onClick={handleArchive}>Archive/delete</button>
          </div>
        </form>
        {error && <div className={styles.error}>{error}</div>}
      </section>

      <section className={styles.panel}>
        <h2>Add relationship</h2>
        <form onSubmit={handleAddRelationship} className={styles.inlineForm} aria-label="Add relationship">
          <input
            value={targetEntityId}
            onChange={(event) => setTargetEntityId(event.target.value)}
            placeholder="Target entity ID"
            aria-label="Target entity ID"
          />
          <select
            value={relationshipType}
            onChange={(event) => setRelationshipType(event.target.value)}
            aria-label="Relationship type"
          >
            {relationshipOptions.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
          <button type="submit">Add link</button>
        </form>
      </section>

      <section className={styles.sections}>
        {detail.sections.map((section) => (
          <article key={section.key} className={styles.panel}>
            <h2>{section.title}</h2>
            {section.items.length === 0 ? (
              <p>No linked entities.</p>
            ) : (
              <ul className={styles.cards}>
                {section.items.map((item) => (
                  <li key={item.relationship.id}>
                    <Link to={pathForEntity(item.entity)}>
                      <strong>{item.entity.title || 'Untitled'}</strong>
                      <span>{item.relationship.relationship_type}</span>
                    </Link>
                    <button type="button" onClick={() => handleRemoveRelationship(item.relationship.id)}>
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </article>
        ))}
      </section>
    </main>
  );
}
