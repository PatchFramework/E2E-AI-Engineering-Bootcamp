import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import { Copy, Check, Code as CodeIcon } from 'lucide-react';
import { MermaidRenderer } from './MermaidRenderer';
import { ChartWidgetRenderer } from './ChartWidgetRenderer';
import { CopilotWidget } from '../../../models/copilot';

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

interface CodeBlockProps {
  language: string;
  value: string;
}

const CodeBlock: React.FC<CodeBlockProps> = ({ language, value }) => {
  const [copied, setCopied] = useState(false);

  // Check if this is a Mermaid diagram
  if (language === 'mermaid') {
    return <MermaidRenderer chart={value} />;
  }

  // Check if this is an embedded Chart/Visual Widget definition
  if (language === 'chart' || language === 'widget' || language === 'json:widget' || language === 'json') {
    try {
      const parsed = JSON.parse(value.trim());
      if (parsed && typeof parsed === 'object' && ('widgetType' in parsed || 'chartType' in parsed || 'wordCloudData' in parsed)) {
        const widget: CopilotWidget = {
          widgetType: parsed.widgetType || 'chart',
          chartType: parsed.chartType,
          title: parsed.title || 'Visualization',
          description: parsed.description,
          unit: parsed.unit,
          series: parsed.series,
          data: parsed.data,
          columns: parsed.columns,
          rows: parsed.rows,
          wordCloudData: parsed.wordCloudData,
        };
        return <ChartWidgetRenderer widget={widget} />;
      }
    } catch {
      // Fall through to regular code block
    }
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore
    }
  };

  return (
    <div className="my-2.5 rounded-xl border border-slate-800 bg-slate-950 overflow-hidden group">
      <div className="flex items-center justify-between px-3 py-1.5 bg-slate-900/90 border-b border-slate-800/80 text-[10px] text-slate-400">
        <div className="flex items-center gap-1.5 font-mono">
          <CodeIcon className="w-3 h-3 text-brand-400" />
          <span>{language || 'code'}</span>
        </div>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1 px-1.5 py-0.5 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
          title="Copy Code"
        >
          {copied ? (
            <>
              <Check className="w-3 h-3 text-emerald-400" />
              <span className="text-[9px] text-emerald-400">Copied</span>
            </>
          ) : (
            <>
              <Copy className="w-3 h-3" />
              <span className="text-[9px]">Copy</span>
            </>
          )}
        </button>
      </div>
      <div className="p-3 overflow-x-auto font-mono text-[11px] leading-relaxed text-slate-300">
        <pre className="m-0">{value}</pre>
      </div>
    </div>
  );
};

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, className = '' }) => {
  return (
    <div className={`prose-markdown ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={{
          // Headings
          h1: ({ children, ...props }) => (
            <h1 className="text-sm font-bold text-slate-100 mt-3 mb-1.5 pb-1 border-b border-slate-800 first:mt-0" {...props}>
              {children}
            </h1>
          ),
          h2: ({ children, ...props }) => (
            <h2 className="text-xs font-bold text-slate-100 mt-2.5 mb-1 pb-0.5 border-b border-slate-800/60 first:mt-0" {...props}>
              {children}
            </h2>
          ),
          h3: ({ children, ...props }) => (
            <h3 className="text-[11px] font-bold text-slate-200 mt-2 mb-1 first:mt-0" {...props}>
              {children}
            </h3>
          ),
          h4: ({ children, ...props }) => (
            <h4 className="text-[11px] font-semibold text-slate-300 mt-1.5 mb-0.5 first:mt-0" {...props}>
              {children}
            </h4>
          ),

          // Paragraphs & Text
          p: ({ children, ...props }) => (
            <p className="my-1.5 leading-relaxed text-slate-200 text-xs first:mt-0 last:mb-0" {...props}>
              {children}
            </p>
          ),
          strong: ({ children, ...props }) => (
            <strong className="font-semibold text-white" {...props}>
              {children}
            </strong>
          ),
          b: ({ children, ...props }) => (
            <b className="font-semibold text-white" {...props}>
              {children}
            </b>
          ),
          em: ({ children, ...props }) => (
            <em className="italic text-slate-300" {...props}>
              {children}
            </em>
          ),
          i: ({ children, ...props }) => (
            <i className="italic text-slate-300" {...props}>
              {children}
            </i>
          ),
          del: ({ children, ...props }) => (
            <del className="line-through text-slate-400" {...props}>
              {children}
            </del>
          ),

          // Lists
          ul: ({ children, ...props }) => (
            <ul className="list-disc list-outside ml-4 my-1.5 space-y-1 text-slate-200 text-xs" {...props}>
              {children}
            </ul>
          ),
          ol: ({ children, ...props }) => (
            <ol className="list-decimal list-outside ml-4 my-1.5 space-y-1 text-slate-200 text-xs" {...props}>
              {children}
            </ol>
          ),
          li: ({ children, ...props }) => (
            <li className="leading-relaxed pl-0.5" {...props}>
              {children}
            </li>
          ),

          // Blockquotes
          blockquote: ({ children, ...props }) => (
            <blockquote
              className="border-l-2 border-brand-500 bg-slate-900/50 pl-3 py-1.5 my-2 text-slate-300 italic rounded-r-lg text-xs"
              {...props}
            >
              {children}
            </blockquote>
          ),

          // Code blocks & Inline code
          code: ({ node, className: codeClassName, children, ...props }) => {
            const match = /language-(\w+)/.exec(codeClassName || '');
            const isInline = !match && !codeClassName && typeof children === 'string' && !children.includes('\n');

            if (isInline) {
              return (
                <code
                  className="bg-slate-900 text-brand-300 px-1.5 py-0.5 rounded font-mono text-[11px] border border-slate-800 font-normal"
                  {...props}
                >
                  {children}
                </code>
              );
            }

            const language = match ? match[1] : (codeClassName || '').replace(/^language-/, '');
            const value = String(children).replace(/\n$/, '');

            return <CodeBlock language={language} value={value} />;
          },

          // Tables
          table: ({ children, ...props }) => (
            <div className="my-2.5 overflow-x-auto rounded-lg border border-slate-800 bg-slate-950/90 shadow-sm">
              <table className="w-full text-left text-[11px] text-slate-300 border-collapse" {...props}>
                {children}
              </table>
            </div>
          ),
          thead: ({ children, ...props }) => (
            <thead className="bg-slate-900/90 text-slate-300 font-semibold border-b border-slate-800 uppercase text-[10px]" {...props}>
              {children}
            </thead>
          ),
          tbody: ({ children, ...props }) => (
            <tbody className="divide-y divide-slate-850" {...props}>
              {children}
            </tbody>
          ),
          tr: ({ children, ...props }) => (
            <tr className="hover:bg-slate-900/40 transition-colors" {...props}>
              {children}
            </tr>
          ),
          th: ({ children, ...props }) => (
            <th className="px-3 py-1.5 font-semibold text-slate-200" {...props}>
              {children}
            </th>
          ),
          td: ({ children, ...props }) => (
            <td className="px-3 py-1.5 text-slate-300 font-mono" {...props}>
              {children}
            </td>
          ),

          // Links
          a: ({ href, children, ...props }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-brand-400 hover:text-brand-300 underline underline-offset-2 transition"
              {...props}
            >
              {children}
            </a>
          ),

          // Horizontal rule
          hr: ({ ...props }) => <hr className="border-slate-800 my-2.5" {...props} />,

          // Input (task lists)
          input: ({ type, checked, ...props }) => {
            if (type === 'checkbox') {
              return (
                <input
                  type="checkbox"
                  checked={checked}
                  readOnly
                  className="mr-1.5 rounded border-slate-700 bg-slate-900 text-brand-500 focus:ring-0 focus:ring-offset-0 cursor-default"
                  {...props}
                />
              );
            }
            return <input type={type} {...props} />;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};
