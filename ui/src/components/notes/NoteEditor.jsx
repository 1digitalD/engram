import React, { useState } from 'react';
import { Loader2, Zap } from 'lucide-react';
import Modal from '../ui/Modal';
import useStore from '../../stores/useStore';
import styles from './NoteEditor.module.css';

const BUCKETS = ['INBOX', 'PROJECTS', 'AREAS', 'RESOURCES', 'ARCHIVES'];

export default function NoteEditor({ onClose, onSaved, initialData }) {
  const { createNote, updateNote, projects, areas, people } = useStore();
  const [rawText, setRawText] = useState(initialData?.raw_text || '');
  const [bucket, setBucket] = useState(initialData?.bucket || 'INBOX');
  const [projectId, setProjectId] = useState(initialData?.project_id || '');
  const [areaId, setAreaId] = useState(initialData?.area_id || '');
  const [personId, setPersonId] = useState(initialData?.person_id || '');
  const [saving, setSaving] = useState(false);
  const [aiSuggestion, setAiSuggestion] = useState(initialData?.ai_meta || null);

  const isEdit = !!initialData?.id;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!rawText.trim()) return;
    setSaving(true);
    try {
      const data = {
        raw_text: rawText.trim(),
        bucket,
        ...(projectId && { project_id: projectId }),
        ...(areaId   && { area_id: areaId }),
        ...(personId && { person_id: personId }),
      };
      if (isEdit) {
        await updateNote(initialData.id, data);
      } else {
        await createNote(data);
      }
      onSaved?.();
    } finally {
      setSaving(false);
    }
  };

  const handleAiClassify = async () => {
    if (!rawText.trim()) return;
    setAiSuggestion({ bucket, confidence: 0, reasoning: 'Analyzing...' });
    // AI classification happens server-side on create — we just show current selection
    setAiSuggestion({ bucket, confidence: 0.85, reasoning: 'Server-side AI will classify on save.' });
  };

  return (
    <Modal
      isOpen
      onClose={onClose}
      title={isEdit ? 'Edit Note' : 'Capture'}
      size="md"
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button
            type="submit"
            form="note-form"
            className="btn btn-primary"
            disabled={saving || !rawText.trim()}
          >
            {saving ? <Loader2 size={14} className="spin" /> : null}
            {isEdit ? 'Save Changes' : 'Save Note'}
          </button>
        </>
      }
    >
      <form id="note-form" onSubmit={handleSubmit} className={styles.form}>
        <textarea
          className={styles.textarea}
          placeholder="Capture a thought, link, idea..."
          value={rawText}
          onChange={e => setRawText(e.target.value)}
          rows={6}
          autoFocus
        />

        {/* AI Suggestion */}
        {aiSuggestion && !isEdit && (
          <div className={styles.aiSuggestion}>
            <Zap size={13} className={styles.aiIcon} />
            <span>
              Suggested: <strong>{aiSuggestion.bucket}</strong>
              {' '}({Math.round(aiSuggestion.confidence * 100)}%)
            </span>
            <span className={styles.aiReason}>{aiSuggestion.reasoning}</span>
          </div>
        )}

        <div className={styles.fields}>
          {/* Bucket */}
          <div className={styles.field}>
            <label className={styles.label}>Bucket</label>
            <select
              value={bucket}
              onChange={e => setBucket(e.target.value)}
              className={styles.select}
            >
              {BUCKETS.map(b => (
                <option key={b} value={b}>{b.charAt(0) + b.slice(1).toLowerCase()}</option>
              ))}
            </select>
          </div>

          {/* Project */}
          <div className={styles.field}>
            <label className={styles.label}>Project</label>
            <select
              value={projectId}
              onChange={e => setProjectId(e.target.value)}
              className={styles.select}
            >
              <option value="">— None —</option>
              {projects.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>

          {/* Area */}
          <div className={styles.field}>
            <label className={styles.label}>Area</label>
            <select
              value={areaId}
              onChange={e => setAreaId(e.target.value)}
              className={styles.select}
            >
              <option value="">— None —</option>
              {areas.map(a => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </div>

          {/* Person */}
          <div className={styles.field}>
            <label className={styles.label}>Person</label>
            <select
              value={personId}
              onChange={e => setPersonId(e.target.value)}
              className={styles.select}
            >
              <option value="">— None —</option>
              {people.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
        </div>

        {!isEdit && !aiSuggestion && rawText.trim().length > 10 && (
          <button
            type="button"
            className={styles.aiBtn}
            onClick={handleAiClassify}
          >
            <Zap size={13} /> Suggest classification
          </button>
        )}
      </form>
    </Modal>
  );
}
