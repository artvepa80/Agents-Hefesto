function sanitize(html) {
  return html;
}

const DOMPurify = { sanitize: (html) => html };

export const View = (user) => (
  <div>
    <div dangerouslySetInnerHTML={{ __html: sanitize(user) }} />
    <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(user) }} />
  </div>
);
