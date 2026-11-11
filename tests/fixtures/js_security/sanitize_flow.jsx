import createDOMPurify from "dompurify";
import { createDOMPurify as makePurify } from "isomorphic-dompurify";
import DOMPurify from "dompurify";

function fakeFactory(target) {
  return { sanitize: (html) => html };
}

function sanitize(html) {
  return html;
}

const instance = createDOMPurify(window);
const named = makePurify(window);
const fake = fakeFactory(window);

export function View(html) {
  const clean = DOMPurify.sanitize(html);
  const localClean = sanitize(html);
  return (
    <div>
      <div dangerouslySetInnerHTML={{ __html: instance.sanitize(html) }} />
      <div dangerouslySetInnerHTML={{ __html: named.sanitize(html) }} />
      <div dangerouslySetInnerHTML={{ __html: fake.sanitize(html) }} />
      <div dangerouslySetInnerHTML={{ __html: clean }} />
      <div dangerouslySetInnerHTML={{ __html: localClean }} />
      <div dangerouslySetInnerHTML={{ __html: html }} />
    </div>
  );
}
