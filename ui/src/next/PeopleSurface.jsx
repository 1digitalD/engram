import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { friendlyApiError, v4API } from '../api/v4Client';
import { SURFACE_LABELS } from './vocab';
import styles from './PeopleSurface.module.css';

function formatDueDate(value) {
  if (!value) return 'No due date';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'No due date';
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(date);
}

function formatLastHeard(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function taskSurfacePath(task) {
  const parentId = task?.projects?.[0]?.id || task?.areas?.[0]?.id;
  return parentId ? `/next/spaces/${parentId}` : null;
}

function sectionCommitments(prep, key) {
  return prep?.mutual_commitments?.[key] || [];
}

function quietWatchItems(detail) {
  return (detail?.pulse?.focus_items || []).filter((item) => item.kind === 'quiet');
}

function currentLoadItems(detail) {
  return (detail?.current_load || []).filter((item) => item?.task?.id);
}

function CommitmentRow({ item }) {
  const href = taskSurfacePath(item);
  const meta = [item.status || 'open', `Due ${formatDueDate(item.due_at)}`].join(' · ');
  return (
    <li className={styles.commitmentRow}>
      {href ? (
        <Link to={href} className={styles.commitmentLink}>
          {item.title}
        </Link>
      ) : (
        <span className={styles.commitmentLink}>{item.title}</span>
      )}
      <p className={styles.commitmentMeta}>{meta}</p>
    </li>
  );
}

export default function PeopleSurface() {
  const { personId } = useParams();
  const [people, setPeople] = useState([]);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadPeople = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const requests = [v4API.entities.list({ type: 'person' })];
      if (personId) {
        requests.push(v4API.entities.detail(personId));
      }
      const [peopleResponse, detailResponse] = await Promise.all(requests);
      const nextPeople = (peopleResponse?.data || [])
        .slice()
        .sort((left, right) => left.title.localeCompare(right.title));
      setPeople(nextPeople);
      setDetail(detailResponse || null);
    } catch (err) {
      setError(friendlyApiError(err, 'Could not load people.'));
      setPeople([]);
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }, [personId]);

  useEffect(() => {
    loadPeople();
  }, [loadPeople]);

  const prep = detail?.meeting_prep || null;
  const theyOwe = useMemo(() => sectionCommitments(prep, 'they_owe'), [prep]);
  const youOwe = useMemo(() => sectionCommitments(prep, 'you_owe'), [prep]);
  const quietItems = useMemo(() => quietWatchItems(detail), [detail]);
  const currentLoad = useMemo(() => currentLoadItems(detail), [detail]);
  const prepAvailable = Boolean(
    prep?.headline || (prep?.agenda_items || []).length > 0 || (prep?.recent_notes || []).length > 0,
  );

  if (!personId) {
    return (
      <section className={styles.surface} aria-label={SURFACE_LABELS.people}>
        <header className={styles.header}>
          <h1 className={styles.title}>{SURFACE_LABELS.people}</h1>
          <p className={styles.subtitle}>People in your workspace, ready for prep and follow-through.</p>
        </header>

        {error ? (
          <p className={styles.error} role="alert">
            {error}
          </p>
        ) : null}

        {loading ? <p className={styles.empty}>Loading people…</p> : null}

        {!loading && people.length === 0 ? (
          <p className={styles.empty}>No people yet. Capture notes or link commitments to people first.</p>
        ) : null}

        {!loading && people.length > 0 ? (
          <ul className={styles.peopleList}>
            {people.map((person) => (
              <li key={person.id} className={styles.personListItem}>
                <Link to={`/next/people/${person.id}`} className={styles.personLink}>
                  {person.title}
                </Link>
                <p className={styles.personMeta}>{person.status || 'active'}</p>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    );
  }

  if (loading) {
    return (
      <section className={styles.surface} aria-busy="true">
        <p className={styles.empty}>Loading person…</p>
      </section>
    );
  }

  if (error || !detail?.entity) {
    return (
      <section className={styles.surface}>
        <p className={styles.error} role="alert">
          {error || 'Person not found.'}
        </p>
        <Link to="/next/people" className={styles.backLink}>
          {SURFACE_LABELS.people}
        </Link>
      </section>
    );
  }

  return (
    <section className={styles.surface} aria-label="Person">
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>{detail.entity.title}</h1>
          <p className={styles.subtitle}>
            {detail.entity.ai?.entity_summary || 'Person rollup from current commitments and recent notes.'}
          </p>
        </div>
        <div className={styles.headerActions}>
          <Link to="/next/people" className={styles.backLink}>
            {SURFACE_LABELS.people}
          </Link>
          {prepAvailable ? (
            <a href="#person-prep" className={styles.prepShortcut}>
              Jump to prep
            </a>
          ) : null}
        </div>
      </header>

      {detail.pulse?.headline ? <p className={styles.pulseHeadline}>{detail.pulse.headline}</p> : null}

      <div className={styles.columns}>
        <section className={styles.card} aria-label="They owe you">
          <h2 className={styles.cardTitle}>They owe you</h2>
          {theyOwe.length > 0 ? (
            <ul className={styles.commitmentList}>
              {theyOwe.map((item) => (
                <CommitmentRow key={item.id} item={item} />
              ))}
            </ul>
          ) : (
            <p className={styles.emptyHint}>No open commitments on their side.</p>
          )}
        </section>

        <section className={styles.card} aria-label="You owe them">
          <h2 className={styles.cardTitle}>You owe them</h2>
          {youOwe.length > 0 ? (
            <ul className={styles.commitmentList}>
              {youOwe.map((item) => (
                <CommitmentRow key={item.id} item={item} />
              ))}
            </ul>
          ) : (
            <p className={styles.emptyHint}>Nothing queued on your side.</p>
          )}
        </section>
      </div>

      <section className={styles.cardWide} aria-label="Quiet watch">
        <h2 className={styles.cardTitle}>Quiet watch</h2>
        {quietItems.length > 0 ? (
          <ul className={styles.watchList}>
            {quietItems.map((item) => {
              const href = taskSurfacePath(item.entity);
              return (
                <li key={item.entity?.id || item.label} className={styles.watchRow}>
                  <div>
                    {href ? (
                      <Link to={href} className={styles.commitmentLink}>
                        {item.entity?.title || item.label}
                      </Link>
                    ) : (
                      <span className={styles.commitmentLink}>{item.entity?.title || item.label}</span>
                    )}
                    <p className={styles.commitmentMeta}>{item.label}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className={styles.emptyHint}>No quiet work to chase right now.</p>
        )}
      </section>

      {currentLoad.length > 0 ? (
        <section className={styles.cardWide} aria-label="Current load">
          <h2 className={styles.cardTitle}>Current load</h2>
          <ul className={styles.watchList}>
            {currentLoad.map((item) => {
              const href = taskSurfacePath(item.task);
              return (
                <li key={item.task.id} className={styles.watchRow}>
                  <div>
                    {href ? (
                      <Link to={href} className={styles.commitmentLink}>
                        {item.task.title}
                      </Link>
                    ) : (
                      <span className={styles.commitmentLink}>{item.task.title}</span>
                    )}
                    <p className={styles.commitmentMeta}>
                      {item.lastHeardPreview}
                      {item.last_heard_at ? ` · Last heard ${formatLastHeard(item.last_heard_at)}` : ''}
                    </p>
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      {prepAvailable ? (
        <section className={styles.cardWide} aria-label="Meeting prep" id="person-prep">
          <h2 className={styles.cardTitle}>Meeting prep</h2>
          {prep.headline ? <p className={styles.prepHeadline}>{prep.headline}</p> : null}

          {(prep.agenda_items || []).length > 0 ? (
            <ul className={styles.agendaList}>
              {prep.agenda_items.map((item) => (
                <li key={item.entity?.id || item.title} className={styles.agendaRow}>
                  <span className={styles.agendaTitle}>{item.title}</span>
                  {item.reason ? <p className={styles.commitmentMeta}>{item.reason}</p> : null}
                </li>
              ))}
            </ul>
          ) : null}

          {(prep.recent_notes || []).length > 0 ? (
            <div className={styles.notesBlock}>
              {(prep.recent_notes || []).map((note) => (
                <article key={note.id} className={styles.noteCard}>
                  <h3 className={styles.noteTitle}>{note.title}</h3>
                  {note.preview ? <p className={styles.notePreview}>{note.preview}</p> : null}
                </article>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}
    </section>
  );
}
