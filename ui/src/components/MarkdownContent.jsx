import { useMemo } from 'react';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import styles from './MarkdownContent.module.css';

marked.use({ breaks: true, gfm: true });

function markdownToPlainText(md) {
  if (!md) return '';
  let text = md;
  // Strip fenced code blocks first (keep inner text).
  text = text.replace(/```[\w-]*\n([\s\S]*?)```/g, '$1');
  // Inline code.
  text = text.replace(/`([^`]+)`/g, '$1');
  // Images: keep alt text.
  text = text.replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1');
  // Links: keep label.
  text = text.replace(/\[([^\]]+)\]\([^)]*\)/g, '$1');
  // Headings markers.
  text = text.replace(/^\s{0,3}#{1,6}\s+/gm, '');
  // Blockquotes.
  text = text.replace(/^\s{0,3}>\s?/gm, '');
  // Bullet / ordered list markers → " · " separator (drop leading separator below).
  text = text.replace(/^\s*[-*+]\s+/gm, ' · ');
  text = text.replace(/^\s*\d+\.\s+/gm, ' · ');
  // Bold / italic / strikethrough markers.
  text = text.replace(/(\*\*|__)(.*?)\1/g, '$2');
  text = text.replace(/(\*|_)(.*?)\1/g, '$2');
  text = text.replace(/~~(.*?)~~/g, '$1');
  // Collapse whitespace and trim a leading separator.
  text = text.replace(/\s+/g, ' ').trim();
  text = text.replace(/^·\s*/, '');
  return text;
}

export default function MarkdownContent({ content, className, compact = false }) {
  const html = useMemo(() => {
    if (!content || compact) return '';
    return DOMPurify.sanitize(marked.parse(content));
  }, [content, compact]);

  if (compact) {
    const text = markdownToPlainText(content);
    if (!text) return null;
    return <div className={`${styles.md} ${styles.mdCompact} ${className || ''}`}>{text}</div>;
  }

  if (!html) return null;
  return <div className={`${styles.md} ${className || ''}`} dangerouslySetInnerHTML={{ __html: html }} />;
}
