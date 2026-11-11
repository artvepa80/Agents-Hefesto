import DOMPurify from "dompurify";
import sanitizeHtml from "sanitize-html";

function sanitize(html) {
  return html;
}

export function renderHTML(elementId, content, name) {
  const el = document.getElementById(elementId);
  if (el) {
    el.innerHTML = content;
    el.innerHTML = "<b>ok</b>";
    el.innerHTML = DOMPurify.sanitize(content);
    el.innerHTML = sanitizeHtml(content);
    el.innerHTML = sanitize(content);
    el.outerHTML = content;
    el.innerHTML += content;
    el.insertAdjacentHTML("beforeend", content);
    el.insertAdjacentHTML("beforeend", "<b>ok</b>");
  }
  document.write(`<h1>Welcome, ${name}</h1>`);
  document.write("<b>ok</b>");
  document.writeln(content);
}

const sample = "el.innerHTML = content";
// document.write(`<h1>${name}</h1>`)
