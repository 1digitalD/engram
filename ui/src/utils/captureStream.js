const API_PREFIX = '/api/v4';

function parseSseBlock(block) {
  let eventType = null;
  let data = null;
  for (const line of block.split('\n')) {
    if (line.startsWith('event: ')) {
      eventType = line.slice('event: '.length);
    } else if (line.startsWith('data: ')) {
      try {
        data = JSON.parse(line.slice('data: '.length));
      } catch {
        data = line.slice('data: '.length);
      }
    }
  }
  if (eventType == null) return null;
  return { type: eventType, data };
}

export function formatCaptureStreamLabel(event) {
  if (!event?.type) return '';
  const { type, data } = event;
  switch (type) {
    case 'reading':
      return 'Reading your note…';
    case 'extracting':
      return 'extracting…';
    case 'candidates':
      return data?.count
        ? `Found ${data.count} candidate${data.count === 1 ? '' : 's'}…`
        : 'Reviewing candidates…';
    case 'reconciling':
      return 'Reconciling suggestions…';
    case 'applying':
      return 'Applying safe changes…';
    case 'linking':
      if (data?.links_created > 0) {
        return `linking (${data.links_created} link${data.links_created === 1 ? '' : 's'})…`;
      }
      return 'linking…';
    case 'summarizing':
      return 'Summarizing…';
    case 'done':
      return 'done';
    case 'error':
      return data?.message || 'Capture failed';
    default:
      return type;
  }
}

/**
 * POST /api/v4/capture?stream=true and invoke onEvent for each SSE event.
 * Resolves with the final done payload or rejects on HTTP/network errors.
 */
export async function captureStream(body, { onEvent } = {}) {
  const url = new URL(`${API_PREFIX}/capture`, window.location.origin);
  url.searchParams.set('stream', 'true');

  const response = await fetch(url.toString(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  const contentType = (response.headers.get('content-type') || '').toLowerCase();
  if (!response.ok) {
    const isJson = contentType.includes('application/json');
    const errorBody = isJson
      ? await response.json().catch(() => ({ error: response.statusText }))
      : { error: `${response.status} ${response.statusText}` };
    const error = new Error(errorBody.error || errorBody.message || `HTTP ${response.status}`);
    error.status = response.status;
    error.body = errorBody;
    throw error;
  }

  if (!response.body) {
    throw new Error('Streaming not supported');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let donePayload = null;
  let streamError = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const blocks = buffer.split('\n\n');
    buffer = blocks.pop() || '';

    for (const block of blocks) {
      const event = parseSseBlock(block.trim());
      if (!event) continue;
      onEvent?.(event);
      if (event.type === 'done') {
        donePayload = event.data;
      } else if (event.type === 'error') {
        streamError = new Error(event.data?.message || 'Capture failed');
      }
    }
  }

  if (buffer.trim()) {
    const event = parseSseBlock(buffer.trim());
    if (event) {
      onEvent?.(event);
      if (event.type === 'done') donePayload = event.data;
      else if (event.type === 'error') {
        streamError = new Error(event.data?.message || 'Capture failed');
      }
    }
  }

  if (streamError) throw streamError;
  if (donePayload) return donePayload;
  throw new Error('Capture stream ended without a done event');
}
