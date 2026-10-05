import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function EvidenceMarkdown({ children }: { children: string }) {
  return <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
    a: ({ children: label, href }) => <a href={href} target="_blank" rel="noopener noreferrer">{label}</a>,
    img: ({ alt }) => <span className="brain-callout">Figure reference{alt ? `: ${alt}` : ""}</span>
  }}>{children}</ReactMarkdown>;
}
