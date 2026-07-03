/**
 * Normalize v4 /search payloads into flat entity rows for UI lists.
 * API shape: { results: [{ entity, score, match }] }
 */
export function normalizeSearchResults(payload) {
  if (!payload) return [];

  if (Array.isArray(payload.results)) {
    return payload.results
      .map((row) => {
        const entity = row?.entity;
        if (!entity?.id) return null;
        return {
          ...entity,
          searchSnippet: row.match?.snippet || null,
          searchSource: row.match?.source || null,
        };
      })
      .filter(Boolean);
  }

  if (Array.isArray(payload.data)) {
    return payload.data;
  }

  return [];
}
