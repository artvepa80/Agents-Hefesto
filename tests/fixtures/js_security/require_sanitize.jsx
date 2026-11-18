const DOMPurify = require("dompurify");
const sanitizeHtml = require("sanitize-html");
const { sanitize } = require("dompurify");
const { addHook: notSanitize } = require("dompurify");
const { createDOMPurify } = require("dompurify");

const instance = createDOMPurify(window);
const clean = instance.sanitize(user);

export function View(user) {
  const step = DOMPurify.sanitize(user);
  return (
    <div>
      <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(user) }} />
      <div dangerouslySetInnerHTML={{ __html: sanitizeHtml(user) }} />
      <div dangerouslySetInnerHTML={{ __html: sanitize(user) }} />
      <div dangerouslySetInnerHTML={{ __html: notSanitize(user) }} />
      <div dangerouslySetInnerHTML={{ __html: user }} />
      <div dangerouslySetInnerHTML={{ __html: instance.sanitize(user) }} />
      <div dangerouslySetInnerHTML={{ __html: step }} />
      <div dangerouslySetInnerHTML={{ __html: clean }} />
    </div>
  );
}
