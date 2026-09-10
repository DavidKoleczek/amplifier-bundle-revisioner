import ReactMarkdown from "react-markdown";
import type { Artifact } from "../types";

/** Encode file names, never interpret an artifact path as a URL or traversal. */
export function artifactHref(path: string): string | null {
  const parts = path.split("/");
  if (parts[0] !== "data" || parts.length < 3 ||
      parts.some((part) => !part || part === "." || part === ".." || /[\\\u0000-\u001f]/.test(part))) {
    return null;
  }
  return "/" + parts.map(encodeURIComponent).join("/");
}

export function resolveLink(href: string, documentPath: string, artifacts: Artifact[]):
  { href: string; external: boolean } | null {
  if (/^(https?:|mailto:)/i.test(href) || href.startsWith("//")) {
    return { href: href.startsWith("//") ? `https:${href}` : href, external: true };
  }
  if (!href || /^[a-z][a-z\d+.-]*:/i.test(href) || href.includes("\\")) return null;
  try {
    const url = new URL(href, `https://revision.invalid/${documentPath.split("/").map(encodeURIComponent).join("/")}`);
    const path = decodeURIComponent(url.pathname.slice(1));
    const known = artifacts.find((artifact) => artifact.path === path);
    const safe = known && artifactHref(known.path);
    return safe ? { href: safe + url.search + url.hash, external: false } : null;
  } catch {
    return null;
  }
}

interface Props {
  text: string;
  documentPath: string;
  artifacts?: Artifact[];
}

export default function Markdown({ text, documentPath, artifacts = [] }: Props) {
  return (
    <div className="markdown">
      <ReactMarkdown components={{
        h1: ({ children }) => <h4>{children}</h4>,
        h2: ({ children }) => <h4>{children}</h4>,
        h3: ({ children }) => <h5>{children}</h5>,
        h4: ({ children }) => <h5>{children}</h5>,
        h5: ({ children }) => <h6>{children}</h6>,
        h6: ({ children }) => <h6>{children}</h6>,
        a: ({ href, children }) => {
          const link = resolveLink(href ?? "", documentPath, artifacts);
          return link ? (
            <a href={link.href} target="_blank" rel="noopener noreferrer"
              download={!link.external || undefined}>{children}</a>
          ) : <span>{children}</span>;
        },
        img: ({ src, alt }) => {
          const link = resolveLink(src ?? "", documentPath, artifacts);
          return (
            <span className="image-link">
              {alt ? `Image: ${alt}. ` : "Image. "}
              {link ? <a href={link.href} target="_blank" rel="noopener noreferrer"
                download={!link.external || undefined}>
                {link.external ? "Open remote image" : "Download image"}
              </a> : "Image not available in copied artifacts."}
            </span>
          );
        },
      }}>{text}</ReactMarkdown>
    </div>
  );
}