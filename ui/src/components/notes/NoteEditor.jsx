import React, { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Loader2, Sparkles, X } from 'lucide-react';
import remarkGfm from 'remark-gfm';
import Modal from '../ui/Modal';
import useStore from '../../stores/useStore';
import styles from './NoteEditor.module.css';

const BUCKETS = ['INBOX', 'PROJECTS', 'AREAS', 'RESOURCES', 'ARCHIVES'];
const BUCKET_LABELS = {
  INBOX:     'Inbox',
  PROJECTS:  'Projects',
  AREAS:     'Areas',
  RESOURCES: 'Resources',
  ARCHIVES:  'Archives',
};

function initialProjectIds(data) {
  if (!data) return [];
  if (Array.isArray(data.project_ids) && data.project_ids.length) {
    return [...data.project_ids];
  }
  if (data.project_id) return [data.project_id];
  return [];
}

export default function NoteEditor({ onClose, onSaved, initialData }) {
  const { createNote, updateNote, projects, areas, people } = useStore();
  const [rawText, setRawText] = useState(initialData?.raw_text || '');
  const [bucket, setBucket] = useState(initialData?.bucket || 'INBOX');
  const [selectedProjectIds, setSelectedProjectIds] = useState(() => initialProjectIds(initialData));
  const [projectQuery, setProjectQuery] = useState('');
  const [projectPickerOpen, setProjectPickerOpen] = useState(false);
  const projectComboRef = useRef(null);
  const [areaId, setAreaId] = useState(initialData?.area_id || '');
  const [personId, setPersonId] = useState(initialData?.person_id || '');
  const [activeTab, setActiveTab] = useState('write');
  const [saving, setSaving] = useState(false);

  const isEdit = !!initialData?.id;

  useEffect(() => {
    setRawText(initialData?.raw_text || '');
    setBucket(initialData?.bucket || 'INBOX');
    setSelectedProjectIds(initialProjectIds(initialData));
    setAreaId(initialData?.area_id || '');
    setPersonId(initialData?.person_id || '');
    setProjectQuery('');
    setProjectPickerOpen(false);
  }, [initialData?.id]);

  useEffect(() => {
    const onDocClick = (e) => {
      if (!projectComboRef.current) return;
      if (!projectComboRef.current.contains(e.target)) setProjectPickerOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!rawText.trim()) return;
    setSaving(true);
    try {
      const data = {
        raw_text: rawText.trim(),
        bucket,
        ...(isEdit && { project_ids: selectedProjectIds }),
        ...(!isEdit && selectedProjectIds.length > 0 && { project_ids: selectedProjectIds }),
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

  const addProject = (pid) => {
    if (!pid || selectedProjectIds.includes(pid)) return;
    setSelectedProjectIds((ids) => [...ids, pid]);
    setProjectQuery('');
    setProjectPickerOpen(false);
  };

  const removeProjectChip = (pid) => {
    setSelectedProjectIds((ids) => ids.filter((x) => x !== pid));
  };

  const q = projectQuery.trim().toLowerCase();
  const projectCandidates = projects
    .filter((p) => !p.is_archived)
    .filter((p) => !selectedProjectIds.includes(p.id))
    .filter((p) => !q || (p.name || '').toLowerCase().includes(q))
    .slice(0, 12);

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
            {isEdit ? 'Save Changes' : 'Save & Classify'}
          </button>
        </>
      }
    >
      <form id="note-form" onSubmit={handleSubmit} className={styles.form}>
        <div className={styles.tabs} role="tablist" aria-label="Editor mode">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'write'}
            className={`${styles.tab} ${activeTab === 'write' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('write')}
          >
            Write
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'preview'}
            className={`${styles.tab} ${activeTab === 'preview' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('preview')}
          >
            Preview
          </button>
        </div>

        {activeTab === 'write' ? (
          <textarea
            className={styles.textarea}
            placeholder="Capture a thought, link, idea, or decision..."
            value={rawText}
            onChange={e => setRawText(e.target.value)}
            rows={6}
            autoFocus
          />
        ) : (
          <div className={styles.preview}>
            {rawText.trim() ? (
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{rawText}</ReactMarkdown>
            ) : (
              <p className={styles.previewEmpty}>Nothing to preview yet.</p>
            )}
          </div>
        )}

        {!isEdit && rawText.trim().length > 10 && (
          <p className={styles.aiHint}>
            <Sparkles size={12} />
            AI will classify this note, extract tasks, and link it to entities on save.
          </p>
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
                <option key={b} value={b}>{BUCKET_LABELS[b]}</option>
              ))}
            </select>
          </div>

          {/* Projects (multi chip + search) */}
          <div className={`${styles.field} ${styles.fieldWide}`}>
            <label className={styles.label} htmlFor="note-editor-project-search">Projects</label>
            <div className={styles.projectChipStack}>
              {selectedProjectIds.length > 0 && (
                <div className={styles.projectChips} aria-label="Selected projects">
                  {selectedProjectIds.map((pid) => {
                    const p = projects.find((x) => x.id === pid);
                    const label = p?.name || pid.slice(0, 8);
                    return (
                      <span key={pid} className={styles.editorProjectChip}>
                        <span className={styles.editorProjectChipLabel}>{label}</span>
                        <button
                          type="button"
                          className={styles.editorProjectChipRemove}
                          aria-label={`Remove ${label}`}
                          onClick={() => removeProjectChip(pid)}
                        >
                          <X size={12} strokeWidth={2.5} />
                        </button>
                      </span>
                    );
                  })}
                </div>
              )}
              <div className={styles.projectCombo} ref={projectComboRef}>
                <input
                  id="note-editor-project-search"
                  type="search"
                  autoComplete="off"
                  className={styles.projectSearchInput}
                  placeholder="Type to search projects…"
                  value={projectQuery}
                  onChange={(e) => {
                    setProjectQuery(e.target.value);
                    setProjectPickerOpen(true);
                  }}
                  onFocus={() => setProjectPickerOpen(true)}
                  aria-expanded={projectPickerOpen}
                  aria-controls="note-editor-project-suggestions"
                  aria-autocomplete="list"
                />
                {projectPickerOpen && projectCandidates.length > 0 && (
                  <ul
                    id="note-editor-project-suggestions"
                    className={styles.projectSuggestions}
                    role="listbox"
                  >
                    {projectCandidates.map((p) => (
                      <li key={p.id} role="option">
                        <button
                          type="button"
                          className={styles.projectSuggestionBtn}
                          onMouseDown={(e) => e.preventDefault()}
                          onClick={() => addProject(p.id)}
                        >
                          {p.name}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
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
      </form>
    </Modal>
  );
}
