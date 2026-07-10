import { useEffect, useRef, useState } from 'react';

import { v4API, friendlyApiError } from '../api/v4Client';

const DEBOUNCE_MS = 180;

export default function useRecallSearch(query) {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const timerRef = useRef(null);
  const requestIdRef = useRef(0);

  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setResults([]);
      setLoading(false);
      setError('');
      return undefined;
    }

    setLoading(true);
    setError('');
    setResults([]);

    if (timerRef.current) {
      window.clearTimeout(timerRef.current);
    }

    const requestId = ++requestIdRef.current;
    timerRef.current = window.setTimeout(() => {
      v4API.search({ q: trimmed, limit: 12 })
        .then((response) => {
          if (requestId !== requestIdRef.current) return;
          setResults(response?.data || []);
        })
        .catch((err) => {
          if (requestId !== requestIdRef.current) return;
          setError(friendlyApiError(err, 'Search failed.'));
          setResults([]);
        })
        .finally(() => {
          if (requestId !== requestIdRef.current) return;
          setLoading(false);
        });
    }, DEBOUNCE_MS);

    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
  }, [query]);

  return { results, loading, error };
}
