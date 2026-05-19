import React, { useMemo } from 'react';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import styles from './MarkdownContent.module.css';

marked.use({ breaks: true, gfm: true });

export default function MarkdownContent({ content, className }) {
  const html = useMemo(() => {
    if (!content) return '';
    return DOMPurify.sanitize(marked.parse(content));
  }, [content]);

  if (!html) return null;
  return (
    // eslint-disable-next-line react/no-danger
    <div
      className={`${styles.md} ${className || ''}`}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
