// Fixtures for core/scaffold/security/semgrep.yml (semgrep --test). Not executed.
import DOMPurify from "dompurify";

export function Bio({ html }: { html: string }) {
  // ruleid: eos-react-dangerously-set-inner-html
  const raw = <div dangerouslySetInnerHTML={{ __html: html }} />;
  // ok: eos-react-dangerously-set-inner-html
  const clean = <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(html) }} />;
  return [raw, clean];
}
