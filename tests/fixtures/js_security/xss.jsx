import DOMPurify from "dompurify";
import purify from "isomorphic-dompurify";
import sanitizeHtml from "sanitize-html";
import { sanitize as purifyHtml } from "dompurify";
import { addHook as sanitize } from "dompurify";
import * as DOMPurifyNS from "dompurify";

const DOMPurifyLocal = { sanitize: (html) => html };

function sanitizeLocal(html) {
  return html;
}

const renderComment = (input) => {
  return { __html: input };
};

const safe = (html) => ({ __html: DOMPurify.sanitize(html) });

export function View(user, ticket) {
  return (
    <div>
      <div dangerouslySetInnerHTML={{ __html: user }} />
      <div dangerouslySetInnerHTML={{ __html: ticket.message }} />
      <div dangerouslySetInnerHTML={{ __html: "<b>ok</b>" }} />
      <div dangerouslySetInnerHTML={{ __html: "<b>" + "ok" }} />
      <div dangerouslySetInnerHTML={{ __html: "<b>" + user }} />
      <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(user) }} />
      <div dangerouslySetInnerHTML={{ __html: purify.sanitize(user) }} />
      <div dangerouslySetInnerHTML={{ __html: sanitizeHtml(user) }} />
      <div dangerouslySetInnerHTML={{ __html: purifyHtml(user) }} />
      <div dangerouslySetInnerHTML={{ __html: DOMPurifyNS.sanitize(user) }} />
      <div dangerouslySetInnerHTML={{ __html: sanitize(user) }} />
      <div dangerouslySetInnerHTML={{ __html: sanitizeLocal(user) }} />
      <div dangerouslySetInnerHTML={{ __html: DOMPurifyLocal.sanitize(user) }} />
      <div dangerouslySetInnerHTML={renderComment(user)} />
      <div dangerouslySetInnerHTML={safe(user)} />
      <div dangerouslySetInnerHTML={user} />
      <a href="javascript:alert(1)">x</a>
      <a href="javascript:void(0)">x</a>
      <a href="  JAVASCRIPT:alert(1)">x</a>
      <a href="https://example.com">y</a>
      <a href={user}>z</a>
      <a href={"javascript:" + user}>n</a>
      <img src={`javascript:${user}`} />
      <img src={"https://example.com/a.png"} />
      <form action="javascript:alert(1)" />
      <form action="javascript:void(0)" />
      <form action="javascript:;" />
      <form action="https://example.com" />
      <form action={user} />
      <use xlinkHref="javascript:alert(1)" />
      <use xlinkHref={`javascript:${user}`} />
      <use xlinkHref="https://example.com/icon.svg" />
      <use xlink:href="javascript:alert(1)" />
    </div>
  );
}

const text = "dangerouslySetInnerHTML={{ __html: user }}";
// href="javascript:alert(1)"
