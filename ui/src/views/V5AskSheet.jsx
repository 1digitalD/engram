import {
  useCallback, useEffect, useRef, useState,
} from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, ArrowRight, Plus } from 'lucide-react';
import Sheet from '../components/Sheet';
import CitationsList from '../components/CitationsList';
import CitationEntitySheet from '../components/CitationEntitySheet';
import { v4API, friendlyApiError } from '../api/v4Client';
import { useCapture } from '../context/CaptureContext';
import { legacyPath } from '../legacy/legacyPaths';
import styles from './V5AskSheet.module.css';

function entityPath(entityId, type) {
  if (type === 'person') return legacyPath(`/people/${entityId}`);
  if (type) return legacyPath(`/${type}s/${entityId}`);
  return legacyPath(`/entities/${entityId}`);
}

function ActionList({ actions, onOpen, onCapture }) {
  if (!actions?.length) return null;
  return (
    <div className={styles.actions} role="list" aria-label="Suggested actions">
      {actions.map((action, index) => {
        if (action.type === 'capture') {
          return (
            <button
              key={`capture-${index}`}
              type="button"
              className={styles.actionButtonPrimary}
              onClick={onCapture}
            >
              <Plus size={14} strokeWidth={2.2} aria-hidden="true" />
              {action.label}
            </button>
          );
        }
        if (action.type === 'open') {
          return (
            <button
              key={`open-${index}`}
              type="button"
              className={styles.actionButton}
              onClick={() => onOpen(action.payload)}
            >
              {action.label}
            </button>
          );
        }
        return null;
      })}
    </div>
  );
}

export default function V5AskSheet({ open, onClose }) {
  const navigate = useNavigate();
  const { openCapture } = useCapture();
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [citationEntityId, setCitationEntityId] = useState(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (open) {
      setQuestion('');
      setResult(null);
      setError('');
      setLoading(false);
      window.setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  const runAsk = useCallback(async () => {
    const trimmed = question.trim();
    if (!trimmed || loading) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const data = await v4API.ask({ question: trimmed, top_k: 5 });
      setResult(data);
    } catch (err) {
      setError(friendlyApiError(err));
    } finally {
      setLoading(false);
    }
  }, [question, loading]);

  const handleKeyDown = useCallback((event) => {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      runAsk();
    }
  }, [runAsk]);

  const handleOpen = useCallback((payload) => {
    onClose?.();
    const entityId = payload?.entity_id;
    if (entityId) {
      navigate(entityPath(entityId, payload?.type));
    }
  }, [navigate, onClose]);

  const handleCapture = useCallback(() => {
    onClose?.();
    openCapture(question.trim());
  }, [onClose, openCapture, question]);

  const isIdk = result?.confidence === 'low' && result?.citations?.length === 0;

  return (
    <Sheet open={open} onClose={onClose} ariaLabel="Ask Engram" mobileBottomSheet>
      <div className={styles.askSheet}>
        <header className={styles.header}>
          <div className={styles.inputWrap}>
            <Sparkles size={16} strokeWidth={2.2} aria-hidden="true" />
            <input
              ref={inputRef}
              type="text"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything about your workspace…"
              aria-label="Question"
              className={styles.input}
              disabled={loading}
              autoComplete="off"
              autoCorrect="off"
              autoCapitalize="off"
              spellCheck="false"
            />
          </div>
          <button
            type="button"
            className={styles.askButton}
            onClick={runAsk}
            disabled={!question.trim() || loading}
            aria-label="Ask"
          >
            <ArrowRight size={16} strokeWidth={2.2} aria-hidden="true" />
          </button>
        </header>

        <div className={styles.body}>
          {loading && (
            <div className={styles.thinking} aria-live="polite">
              <span className={styles.thinkingSpinner} aria-hidden="true" />
              <span>Searching workspace and grounding an answer…</span>
            </div>
          )}

          {error && (
            <p className={styles.message} role="alert">{error}</p>
          )}

          {!loading && !error && result && (
            <div className={styles.answerWrap}>
              {result.question && (
                <p className={styles.questionLine}>{result.question}</p>
              )}

              {isIdk ? (
                <div className={styles.idkState}>
                  <p className={styles.idkAnswer}>{result.answer}</p>
                  {result.caveats?.length > 0 && (
                    <ul className={styles.caveats}>
                      {result.caveats.map((caveat, index) => (
                        <li key={index}>{caveat}</li>
                      ))}
                    </ul>
                  )}
                </div>
              ) : (
                <>
                  <div
                    className={styles.answer}
                    style={{ whiteSpace: 'pre-wrap' }}
                  >
                    {result.answer}
                  </div>
                  <CitationsList
                    citations={result.citations}
                    onOpen={(citation) => setCitationEntityId(citation.entity_id)}
                  />
                </>
              )}

              <ActionList
                actions={result.suggested_actions}
                onOpen={handleOpen}
                onCapture={handleCapture}
              />
            </div>
          )}

          {!loading && !error && !result && (
            <p className={styles.hint}>
              Ask a question like “What did Mary say about the PR review?”
            </p>
          )}
        </div>

        <footer className={styles.footer}>
          <span className={styles.footerHint}>
            <kbd>↵</kbd>
            {' '}
            or
            {' '}
            <kbd>⌘</kbd>
            +
            <kbd>↵</kbd>
            {' '}
            to ask ·
            {' '}
            <kbd>esc</kbd>
            {' '}
            to close
          </span>
        </footer>
      </div>
      <CitationEntitySheet
        entityId={citationEntityId}
        open={!!citationEntityId}
        onClose={() => setCitationEntityId(null)}
      />
    </Sheet>
  );
}
