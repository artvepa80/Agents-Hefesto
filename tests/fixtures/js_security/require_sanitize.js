const DOMPurify = require("dompurify");
const sanitizeHtml = require("sanitize-html");
const { sanitize } = require("dompurify");
const { addHook: notSanitize } = require("dompurify");

export function paint(el, user) {
  el.innerHTML = DOMPurify.sanitize(user);
  el.innerHTML = sanitizeHtml(user);
  el.innerHTML = sanitize(user);
  el.innerHTML = notSanitize(user);
  el.innerHTML = user;
}
