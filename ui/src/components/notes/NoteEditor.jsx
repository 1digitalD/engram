import React, { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Loader2, Sparkles, X, Check } from 'lucide-react';
import remarkGfm from 'remark-gfm';
import Modal from '../ui/Modal';
import useStore from '../../stores/useStore';
import styles from './NoteEditor.module.css';


export default function NoteEditor({ onClose, onSaved, initialData }) {
  const { createNote, updateNote, projects, areas, people } = useStore();
  const [rawText, setRawText] = useState(initialData?.raw_text || '');
  const [selectedProjectIds, setSelectedProjectIds] = useState(() => {
    if (!initialData) return [];
    if (Array.isArray(initialData.project_ids) && initialData.project_ids.length) return [...initialData.project_ids];
    if (initialData.project_id) return [initialData.project_id];
    return [];
  });
  const [areaId, setAreaId] = useState(initialData?.area_id || '');
  const [personId, setPersonId] = useState(initialData?.person_id || '');
  const [activeTab, setActiveTab] = useState('write');
  const [saving, setSaving] = useState(false);

  // Entity picker state per type
  const [pickers, setPickers] = useState({
    project: { query: '', open: false },
    area:    { query: '', open: false },
    person:  { query: '', open: false },
  });
  const pickerRefs = { project: useRef(null), area: useRef(null), person: useRef(null) };

  const isEdit = !!initialData?.id;

  // Build suggestions from ai_meta if present (note creation or editing)
  const aiSuggestions = initialData?._ai_meta || {};

  useEffect(() => {
    setRawText(initialData?.raw_text || '');
    setSelectedProjectIds(() => {
      if (!initialData) return [];
      if (Array.isArray(initialData.project_ids) && initialData.project_ids.length) return [...initialData.project_ids];
      if (initialData.project_id) return [initialData.project_id];
      return [];
    });
    setAreaId(initialData?.area_id || '');
    setPersonId(initialData?.person_id || '');
  }, [initialData?.id]);

  // Close pickers on outside click
  useEffect(() => {
    const handler = (e) => {
      Object.entries(pickerRefs).forEach(([type, ref]) => {
        if (ref.current && !ref.current.contains(e.target)) {
          setPickers(p => ({ ...p, [type]: { ...p[type], open: false } }));
        }
      });
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!rawText.trim()) return;
    setSaving(true);
    try {
      const data = {
        content: rawText.trim(),
        ...(selectedProjectIds.length > 0 && { project_ids: selectedProjectIds }),
        ...(areaId  && { area_id: areaId }),
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

  // ─── Entity picker helpers ────────────────────────────────

  const setPicker = (type, patch) => setPickers(p => ({ ...p, [type]: { ...p[type], ...patch } }));

  const filteredCandidates = (type, query) => {
    const q = query.trim().toLowerCase();
    if (type === 'project') {
      return projects
        .filter(p => !p.is_archived)
        .filter(p => !selectedProjectIds.includes(p.id))
        .filter(p => !q || (p.title || '').toLowerCase().includes(q))
        .slice(0, 10);
    }
    if (type === 'area') {
      return areas
        .filter(a => !a.is_archived)
        .filter(a => !q || (a.title || '').toLowerCase().includes(q))
        .slice(0, 10);
    }
    if (type === 'person') {
      return people
        .filter(p => !q || (p.title || '').toLowerCase().includes(q))
        .slice(0, 10);
    }
    return [];
  };

  const addEntity = (type, id) => {
    if (type === 'project') {
      if (selectedProjectIds.includes(id)) return;
      setSelectedProjectIds(ids => [...ids, id]);
    } else if (type === 'area') {
      setAreaId(id);
    } else if (type === 'person') {
      setPersonId(id);
    }
    setPicker(type, { query: '', open: false });
  };

  const removeEntity = (type, id) => {
    if (type === 'project') setSelectedProjectIds(ids => ids.filter(x => x !== id));
    else if (type === 'area') setAreaId('');
    else if (type === 'person') setPersonId('');
  };

  // Build entity display configs
  const selectedProjects = selectedProjectIds.map(id => projects.find(p => p.id === id)).filter(Boolean);
  const selectedArea = areas.find(a => a.id === areaId);
  const selectedPerson = people.find(p => p.id === personId);

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
            {isEdit ? 'Save Changes' : 'Save'}
          </button>
        </>
      }
    >
      <form id="note-form" onSubmit={handleSubmit} className={styles.form}>
        {/* Tabs */}
        <div className={styles.tabs} role="tablist">
          <button type="button" role="tab" aria-selected={activeTab === 'write'}
            className={`${styles.tab} ${activeTab === 'write' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('write')}>Write</button>
          <button type="button" role="tab" aria-selected={activeTab === 'preview'}
            className={`${styles.tab} ${activeTab === 'preview' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('preview')}>Preview</button>
        </div>

        {/* Write / Preview */}
        {activeTab === 'write' ? (
          <textarea
            className={styles.textarea}
            placeholder="Capture a thought, link, idea, or decision…"
            value={rawText}
            onChange={e => setRawText(e.target.value)}
            rows={7}
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

        {/* AI Suggestions Banner */}
        {!isEdit && rawText.trim().length > 10 && (aiSuggestions?.suggested_project || aiSuggestions?.suggested_area) && (
          <div className={styles.aiSuggestions}>
            <span className={styles.aiSuggestionsLabel}><Sparkles size={12} /> AI suggests:</span>
            <div className={styles.aiSuggestionsChips}>
              {aiSuggestions.suggested_project && (
                <button
                  type="button"
                  className={styles.aiSuggestChip}
                  onClick={() => {
                    const name = aiSuggestions.suggested_project.toLowerCase();
                    const exact = projects.find(p => p.title?.toLowerCase() === name);
                    const subs  = projects.filter(p => p.title?.toLowerCase().includes(name));
                    const match = exact || (subs.length === 1 ? subs[0] : null);
                    if (match) addEntity('project', match.id);
                  }}
                >
                  <span>📁 {aiSuggestions.suggested_project}</span>
                  <Check size={12} />
                </button>
              )}
              {aiSuggestions.suggested_area && (
                <button
                  type="button"
                  className={styles.aiSuggestChip}
                  onClick={() => {
                    const name = aiSuggestions.suggested_area.toLowerCase();
                    const exact = areas.find(a => a.title?.toLowerCase() === name);
                    const subs  = areas.filter(a => a.title?.toLowerCase().includes(name));
                    const match = exact || (subs.length === 1 ? subs[0] : null);
                    if (match) addEntity('area', match.id);
                  }}
                >
                  <span>🎯 {aiSuggestions.suggested_area}</span>
                  <Check size={12} />
                </button>
              )}
            </div>
          </div>
        )}

        {/* Entity Linking Section */}
        <div className={styles.entitySection}>
          {/* Projects (multi) */}
          <div className={styles.entityGroup}>
            <label className={styles.entityLabel}>Projects</label>
            <div className={styles.entityChips}>
              {selectedProjects.map(p => (
                <span key={p.id} className={styles.entityChip}>
                  <span>📁</span>
                  <span>{p.title}</span>
                  <button type="button" onClick={() => removeEntity('project', p.id)}><X size={11} /></button>
                </span>
              ))}
              <div className={styles.entityCombo} ref={pickerRefs.project}>
                <input
                  type="search"
                  autoComplete="off"
                  placeholder="Add project…"
                  className={styles.entitySearchInput}
                  value={pickers.project.query}
                  onChange={e => { setPicker('project', { query: e.target.value, open: true }); }}
                  onFocus={() => setPicker('project', { open: true })}
                  aria-expanded={pickers.project.open}
                  aria-autocomplete="list"
                />
                {pickers.project.open && (() => {
                  const candidates = filteredCandidates('project', pickers.project.query);
                  return (
                  <ul className={styles.entityDropdown} role="listbox">
                    {candidates.length === 0 && (
                      <li className={styles.entityDropdownEmpty}>No projects found</li>
                    )}
                    {candidates.map(p => (
                      <li key={p.id} role="option">
                        <button type="button" className={styles.entityDropdownItem}
                          onMouseDown={e => e.preventDefault()}
                          onClick={() => addEntity('project', p.id)}>
                          📁 {p.title}
                        </button>
                      </li>
                    ))}
                  </ul>
                  );
                })()}
              </div>
            </div>
          </div>

          {/* Area (single) */}
          <div className={styles.entityGroup}>
            <label className={styles.entityLabel}>Area</label>
            <div className={styles.entityChips}>
              {selectedArea && (
                <span className={styles.entityChip}>
                  <span>🎯</span>
                  <span>{selectedArea.title}</span>
                  <button type="button" onClick={() => removeEntity('area', areaId)}><X size={11} /></button>
                </span>
              )}
              <div className={styles.entityCombo} ref={pickerRefs.area}>
                <input
                  type="search"
                  autoComplete="off"
                  placeholder={selectedArea ? '' : 'Add area…'}
                  className={styles.entitySearchInput}
                  value={pickers.area.query}
                  onChange={e => { setPicker('area', { query: e.target.value, open: true }); }}
                  onFocus={() => setPicker('area', { open: true })}
                  aria-expanded={pickers.area.open}
                  aria-autocomplete="list"
                  disabled={!!selectedArea}
                />
                {pickers.area.open && !selectedArea && (() => {
                  const candidates = filteredCandidates('area', pickers.area.query);
                  return (
                  <ul className={styles.entityDropdown} role="listbox">
                    {candidates.length === 0 && (
                      <li className={styles.entityDropdownEmpty}>No areas found</li>
                    )}
                    {candidates.map(a => (
                      <li key={a.id} role="option">
                        <button type="button" className={styles.entityDropdownItem}
                          onMouseDown={e => e.preventDefault()}
                          onClick={() => addEntity('area', a.id)}>
                          🎯 {a.title}
                        </button>
                      </li>
                    ))}
                  </ul>
                  );
                })()}
              </div>
            </div>
          </div>

          {/* Person (single) */}
          <div className={styles.entityGroup}>
            <label className={styles.entityLabel}>Person</label>
            <div className={styles.entityChips}>
              {selectedPerson && (
                <span className={styles.entityChip}>
                  <span>👤</span>
                  <span>{selectedPerson.title}</span>
                  <button type="button" onClick={() => removeEntity('person', personId)}><X size={11} /></button>
                </span>
              )}
              <div className={styles.entityCombo} ref={pickerRefs.person}>
                <input
                  type="search"
                  autoComplete="off"
                  placeholder={selectedPerson ? '' : 'Add person…'}
                  className={styles.entitySearchInput}
                  value={pickers.person.query}
                  onChange={e => { setPicker('person', { query: e.target.value, open: true }); }}
                  onFocus={() => setPicker('person', { open: true })}
                  aria-expanded={pickers.person.open}
                  aria-autocomplete="list"
                  disabled={!!selectedPerson}
                />
                {pickers.person.open && !selectedPerson && (() => {
                  const candidates = filteredCandidates('person', pickers.person.query);
                  return (
                  <ul className={styles.entityDropdown} role="listbox">
                    {candidates.length === 0 && (
                      <li className={styles.entityDropdownEmpty}>No people found</li>
                    )}
                    {candidates.map(p => (
                      <li key={p.id} role="option">
                        <button type="button" className={styles.entityDropdownItem}
                          onMouseDown={e => e.preventDefault()}
                          onClick={() => addEntity('person', p.id)}>
                          👤 {p.title}
                        </button>
                      </li>
                    ))}
                  </ul>
                  );
                })()}
              </div>
            </div>
          </div>
        </div>
      </form>
    </Modal>
  );
}
