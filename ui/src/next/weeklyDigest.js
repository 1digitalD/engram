function pluralize(count, singular, plural = `${singular}s`) {
  return count === 1 ? singular : plural;
}

function formatStamp(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
  }).format(date);
}

function buildMovedLines(summary) {
  const lines = [];
  if (typeof summary?.new_since_yesterday_count === 'number') {
    lines.push(`${summary.new_since_yesterday_count} new items surfaced since yesterday.`);
  }
  if (typeof summary?.today_count === 'number') {
    lines.push(`${summary.today_count} items are still asking for attention.`);
  }
  if (typeof summary?.inbox_count === 'number') {
    lines.push(`${summary.inbox_count} captures are still waiting for Review.`);
  }
  return lines;
}

function buildDecidedLines(summary, brief) {
  const lines = [];
  if (brief?.narrative) {
    lines.push(brief.narrative);
  }
  if (summary?.reviewed_today) {
    const stamp = formatStamp(summary?.last_reviewed_at);
    lines.push(stamp ? `Review sweep completed today (${stamp}).` : 'Review sweep completed today.');
  } else if (summary?.last_reviewed_at) {
    lines.push(`Last review sweep: ${formatStamp(summary.last_reviewed_at)}.`);
  }
  return lines;
}

function buildStalledLines(summary) {
  const radar = summary?.coordination_radar || {};
  const lines = [];
  if (typeof summary?.stale_projects_count === 'number') {
    lines.push(
      `${summary.stale_projects_count} ${pluralize(summary.stale_projects_count, 'space')} look stale enough to revisit.`,
    );
  }
  (radar.people || []).slice(0, 2).forEach((item) => {
    lines.push(`${item.title}: ${item.headline}`);
  });
  (radar.projects || []).slice(0, 2).forEach((item) => {
    lines.push(`${item.title}: ${item.headline}`);
  });
  return lines;
}

function buildNextLines(brief) {
  return (brief?.items || [])
    .slice(0, 4)
    .map((item) => `${item.title}: ${item.why_now}`);
}

function buildRadarCitation(item, kind) {
  if (!item?.entity_id || !item?.headline) return null;
  const counts = item.counts || {};
  const countBits = Object.entries(counts)
    .filter(([, value]) => Number(value) > 0)
    .slice(0, 2)
    .map(([key, value]) => `${value} ${key.replace(/_/g, ' ')}`);
  return {
    entity_id: item.entity_id,
    snippet: item.headline,
    meta: countBits.length > 0 ? `${kind} • ${countBits.join(' • ')}` : kind,
  };
}

function buildBriefCitation(item, generatedAt) {
  if (!item?.entity_id || !item?.why_now) return null;
  return {
    entity_id: item.entity_id,
    snippet: `${item.title}: ${item.why_now}`,
    date: generatedAt,
    meta: `Brief • urgency ${item.urgency ?? 'n/a'}`,
  };
}

export function buildWeeklyDigest(summaryPayload, briefPayload) {
  const summary = summaryPayload || {};
  const brief = briefPayload?.brief || {};

  const sections = [
    { key: 'moved', title: 'Moved', lines: buildMovedLines(summary) },
    { key: 'decided', title: 'Decided', lines: buildDecidedLines(summary, brief) },
    { key: 'stalled', title: 'Stalled', lines: buildStalledLines(summary) },
    { key: 'next', title: 'Next', lines: buildNextLines(brief) },
  ].filter((section) => section.lines.length > 0);

  const text = sections
    .map((section) => `${section.title}\n${section.lines.map((line) => `- ${line}`).join('\n')}`)
    .join('\n\n');

  const citations = [
    ...((summary?.coordination_radar?.people || [])
      .map((item) => buildRadarCitation(item, 'Person'))
      .filter(Boolean)),
    ...((summary?.coordination_radar?.projects || [])
      .map((item) => buildRadarCitation(item, 'Space'))
      .filter(Boolean)),
    ...((brief?.items || [])
      .slice(0, 4)
      .map((item) => buildBriefCitation(item, brief.generated_at))
      .filter(Boolean)),
  ];

  return {
    generatedAt: brief.generated_at || summary.last_reviewed_at || null,
    sections,
    text,
    citations,
  };
}
