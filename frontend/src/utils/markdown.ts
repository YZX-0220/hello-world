import { marked } from 'marked';
import DOMPurify from 'dompurify';

export function renderMd(text: string): string {
  const html = marked.parse(text || '', { gfm: true, breaks: true, async: false });
  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true },
    FORBID_TAGS: ['img', 'form', 'input', 'button', 'style'],
    FORBID_ATTR: ['style'],
  });
}
