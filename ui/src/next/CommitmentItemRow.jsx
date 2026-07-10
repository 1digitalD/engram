import { Check } from 'lucide-react';
import { Link } from 'react-router-dom';

import { WorkboardItemAffordances } from './TypedAffordances';
import affordanceStyles from './TypedAffordances.module.css';
import { formatRelativeAge } from './dossierUtils';
import styles from './CommitmentItemRow.module.css';

export default function CommitmentItemRow({
  item,
  people,
  spaces,
  group = 'space',
  showNudge = false,
  states = [],
  titleHref,
  showCheckbox = false,
  showCreatedAge = false,
  expandableUpdate = false,
  onStatusChange,
  onDueChange,
  onFollowUpChange,
  onMoveSpace,
  onHandOwner,
  onLogUpdate,
  onMarkDone,
  onToggleDone,
}) {
  const isDone = item.status === 'done';
  const showFoot = states.length > 0 || item.at_risk?.reason || item.blocked_by?.length;
  const titleNode = titleHref ? (
    <Link className={styles.itemTitleLink} to={titleHref}>
      {item.title}
    </Link>
  ) : (
    item.title
  );

  return (
    <li className={styles.item}>
      <div className={styles.itemTop}>
        <div className={styles.itemTitleWrap}>
          {showCheckbox ? (
            <input
              type="checkbox"
              className={styles.doneCheckbox}
              aria-label={`Mark ${item.title} done`}
              checked={isDone}
              onChange={(event) => onToggleDone?.(item.id, event.target.checked, item.status)}
            />
          ) : null}
          <h3 className={styles.itemTitle}>{titleNode}</h3>
          {showCreatedAge && item.created_at ? (
            <span className={styles.itemAge}>{formatRelativeAge(item.created_at)}</span>
          ) : null}
        </div>
        <div className={styles.itemTopActions}>
          {item.at_risk?.flag ? <span className={styles.itemRiskFlag}>At risk</span> : null}
          {!showCheckbox ? (
            <button
              type="button"
              className={affordanceStyles.glyphButton}
              aria-label={`Mark ${item.title} done`}
              onClick={() => onMarkDone(item.id)}
            >
              <Check size={16} strokeWidth={2.25} aria-hidden="true" />
            </button>
          ) : null}
        </div>
      </div>

      <WorkboardItemAffordances
        item={item}
        people={people}
        spaces={spaces}
        group={group}
        onStatusChange={onStatusChange}
        onDueChange={onDueChange}
        onFollowUpChange={onFollowUpChange}
        onMoveSpace={onMoveSpace}
        onHandOwner={onHandOwner}
        onLogUpdate={onLogUpdate}
        showNudge={showNudge}
        expandableUpdate={expandableUpdate}
      />

      {showFoot ? (
        <div className={styles.itemFoot}>
          {states.length > 0 ? (
            <div className={styles.stateList} aria-label={`${item.title} states`}>
              {states.map((state) => (
                <span key={state} className={styles.statePill}>
                  {state}
                </span>
              ))}
            </div>
          ) : null}
          {item.at_risk?.reason ? <p className={styles.reason}>{item.at_risk.reason}</p> : null}
          {item.blocked_by?.length ? (
            <p className={styles.blockedBy}>
              Blocked by {item.blocked_by.map((blocker) => blocker.title).join(', ')}.
            </p>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}
