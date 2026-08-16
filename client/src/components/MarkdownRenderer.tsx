import React from "react";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

// Parses inline markdown: bold, italic, inline code, links, strikethrough
function renderInlineMarkdown(text: string): React.ReactNode[] {
  const elements: React.ReactNode[] = [];
  // Tokenize inline syntax: `code`, **bold**, *italic*, [link](url), ~~strike~~
  const regex = /(`[^`]+`|\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|_[^_]+_|~~[^~]+~~|\[[^\]]+\]\([^)]+\))/g;
  
  let lastIdx = 0;
  let match: RegExpExecArray | null;
  let keyIdx = 0;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIdx) {
      elements.push(text.substring(lastIdx, match.index));
    }
    const token = match[0];
    if (token.startsWith("`") && token.endsWith("`")) {
      elements.push(
        <code
          key={`code-${keyIdx++}`}
          className="px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-pink-600 dark:text-pink-400 font-mono text-xs"
        >
          {token.slice(1, -1)}
        </code>
      );
    } else if ((token.startsWith("**") && token.endsWith("**")) || (token.startsWith("__") && token.endsWith("__"))) {
      elements.push(
        <strong key={`bold-${keyIdx++}`} className="font-bold text-slate-900 dark:text-white">
          {renderInlineMarkdown(token.slice(2, -2))}
        </strong>
      );
    } else if ((token.startsWith("*") && token.endsWith("*")) || (token.startsWith("_") && token.endsWith("_"))) {
      elements.push(
        <em key={`italic-${keyIdx++}`} className="italic text-slate-700 dark:text-slate-300">
          {renderInlineMarkdown(token.slice(1, -1))}
        </em>
      );
    } else if (token.startsWith("~~") && token.endsWith("~~")) {
      elements.push(
        <del key={`strike-${keyIdx++}`} className="line-through text-slate-400">
          {renderInlineMarkdown(token.slice(2, -2))}
        </del>
      );
    } else if (token.startsWith("[") && token.includes("](")) {
      const linkMatch = token.match(/^\[(.*?)\]\((.*?)\)$/);
      if (linkMatch) {
        elements.push(
          <a
            key={`link-${keyIdx++}`}
            href={linkMatch[2]}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 dark:text-blue-400 underline hover:text-blue-700 dark:hover:text-blue-300 transition"
          >
            {renderInlineMarkdown(linkMatch[1])}
          </a>
        );
      } else {
        elements.push(token);
      }
    } else {
      elements.push(token);
    }
    lastIdx = regex.lastIndex;
  }

  if (lastIdx < text.length) {
    elements.push(text.substring(lastIdx));
  }

  return elements.length > 0 ? elements : [text];
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, className = "" }) => {
  const lines = content.split("\n");
  const nodes: React.ReactNode[] = [];
  let i = 0;
  let keyCounter = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    // 1. Code Block: ```
    if (trimmed.startsWith("```")) {
      const language = trimmed.slice(3).trim();
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // skip closing ```
      const codeContent = codeLines.join("\n");
      nodes.push(
        <div key={`codeblock-${keyCounter++}`} className="my-4 rounded-xl overflow-hidden border border-slate-700/60 bg-slate-950 text-slate-100">
          {language && (
            <div className="px-4 py-1.5 text-[10px] uppercase font-mono tracking-wider bg-slate-900 border-b border-slate-800 text-slate-400">
              {language}
            </div>
          )}
          <pre className="p-4 overflow-x-auto text-xs font-mono leading-relaxed">
            <code>{codeContent}</code>
          </pre>
        </div>
      );
      continue;
    }

    // 2. Horizontal Rule: --- or ***
    if (/^(\*{3,}|-{3,}|_{3,})$/.test(trimmed)) {
      nodes.push(
        <hr key={`hr-${keyCounter++}`} className="my-6 border-slate-200 dark:border-slate-800" />
      );
      i++;
      continue;
    }

    // 3. Headings: # to ######
    const headingMatch = line.match(/^(#{1,6})\s+(.*)$/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      const headingText = headingMatch[2];
      const inline = renderInlineMarkdown(headingText);

      switch (level) {
        case 1:
          nodes.push(
            <h1
              key={`h1-${keyCounter++}`}
              className="text-2xl font-black text-slate-900 dark:text-white mt-6 mb-3 pb-2 border-b border-slate-200 dark:border-slate-800 tracking-tight"
            >
              {inline}
            </h1>
          );
          break;
        case 2:
          nodes.push(
            <h2
              key={`h2-${keyCounter++}`}
              className="text-lg font-bold text-slate-900 dark:text-white mt-5 mb-2.5 flex items-center gap-2"
            >
              <span className="w-1.5 h-4 rounded-full bg-blue-500 inline-block"></span>
              <span>{inline}</span>
            </h2>
          );
          break;
        case 3:
          nodes.push(
            <h3
              key={`h3-${keyCounter++}`}
              className="text-base font-bold text-slate-800 dark:text-slate-100 mt-4 mb-2"
            >
              {inline}
            </h3>
          );
          break;
        default:
          nodes.push(
            <h4
              key={`h4-${keyCounter++}`}
              className="text-sm font-semibold text-slate-800 dark:text-slate-200 mt-3 mb-1.5"
            >
              {inline}
            </h4>
          );
          break;
      }
      i++;
      continue;
    }

    // 4. Blockquotes: > ...
    if (line.startsWith(">")) {
      const quoteLines: string[] = [];
      while (i < lines.length && lines[i].startsWith(">")) {
        quoteLines.push(lines[i].replace(/^>\s?/, ""));
        i++;
      }
      const quoteText = quoteLines.join(" ");
      nodes.push(
        <blockquote
          key={`quote-${keyCounter++}`}
          className="my-3 pl-4 py-2 border-l-4 border-blue-500 bg-blue-50/50 dark:bg-blue-950/20 rounded-r-xl text-xs text-slate-700 dark:text-slate-300 italic"
        >
          {renderInlineMarkdown(quoteText)}
        </blockquote>
      );
      continue;
    }

    // 5. Tables: | Header | Header | ...
    if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("|") && lines[i].trim().endsWith("|")) {
        tableLines.push(lines[i].trim());
        i++;
      }
      if (tableLines.length >= 2) {
        const headerCols = tableLines[0]
          .slice(1, -1)
          .split("|")
          .map((c) => c.trim());
        
        // check if second line is separator (e.g. |---|---|)
        const isSeparator = /^\|?(\s*:?-+:?\s*\|)+$/.test(tableLines[1]);
        const dataRows = (isSeparator ? tableLines.slice(2) : tableLines.slice(1)).map((row) =>
          row
            .slice(1, -1)
            .split("|")
            .map((c) => c.trim())
        );

        nodes.push(
          <div key={`table-${keyCounter++}`} className="my-4 overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs">
            <table className="min-w-full text-xs text-left">
              <thead className="bg-slate-100 dark:bg-slate-800/80 text-slate-800 dark:text-slate-200 font-bold border-b border-slate-200 dark:border-slate-700">
                <tr>
                  {headerCols.map((col, idx) => (
                    <th key={`th-${idx}`} className="px-3.5 py-2.5">
                      {renderInlineMarkdown(col)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800/60 bg-white dark:bg-slate-900">
                {dataRows.map((row, rIdx) => (
                  <tr key={`tr-${rIdx}`} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition">
                    {row.map((cell, cIdx) => (
                      <td key={`td-${rIdx}-${cIdx}`} className="px-3.5 py-2 text-slate-700 dark:text-slate-300">
                        {renderInlineMarkdown(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
        continue;
      }
    }

    // 6. Lists (Ordered and Unordered, with sub-items support)
    const listMatch = line.match(/^(\s*)([-*+]|\d+\.)\s+(.*)$/);
    if (listMatch) {
      const listItems: Array<{ indent: number; ordered: boolean; text: string }> = [];
      
      while (i < lines.length) {
        const itemMatch = lines[i].match(/^(\s*)([-*+]|\d+\.)\s+(.*)$/);
        if (!itemMatch) break;
        const indent = itemMatch[1].length;
        const isOrdered = /^\d+\./.test(itemMatch[2]);
        listItems.push({ indent, ordered: isOrdered, text: itemMatch[3] });
        i++;
      }

      nodes.push(
        <ul key={`list-${keyCounter++}`} className="my-2.5 space-y-1.5 text-xs text-slate-700 dark:text-slate-300">
          {listItems.map((item, idx) => (
            <li
              key={`li-${idx}`}
              style={{ marginLeft: `${Math.min(item.indent * 10, 40)}px` }}
              className="flex items-start gap-2 leading-relaxed"
            >
              <span className="text-blue-500 dark:text-blue-400 select-none font-bold mt-0.5 text-xs">
                {item.ordered ? `${idx + 1}.` : "•"}
              </span>
              <div className="flex-1">{renderInlineMarkdown(item.text)}</div>
            </li>
          ))}
        </ul>
      );
      continue;
    }

    // 7. Empty line
    if (trimmed === "") {
      i++;
      continue;
    }

    // 8. Regular paragraph
    nodes.push(
      <p key={`p-${keyCounter++}`} className="my-2 text-xs text-slate-700 dark:text-slate-300 leading-relaxed font-normal">
        {renderInlineMarkdown(line)}
      </p>
    );
    i++;
  }

  return <div className={`markdown-body ${className}`}>{nodes}</div>;
};
