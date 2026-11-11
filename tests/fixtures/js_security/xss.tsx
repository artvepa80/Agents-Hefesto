import DOMPurify from "dompurify";

const renderMarkdown = (userInput: string) => {
  return { __html: marked(userInput) as string };
};

export const Panel = (comment: string) => (
  <section>
    <div dangerouslySetInnerHTML={renderMarkdown(comment)} />
    <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(comment) }} />
    <div dangerouslySetInnerHTML={{ __html: `Hello, ${comment}` }} />
    <div dangerouslySetInnerHTML={{ __html: "<b>static</b>" }} />
    <div dangerouslySetInnerHTML={{ __html: ` <b>static</b> ` }} />
  </section>
);
