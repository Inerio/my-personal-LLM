/**
 * MessageBubble — Gustave Code
 * Bulle de message avec rendu Markdown, code highlight et indicateurs d'outils.
 * Theme Clair Obscure — tons or/ambre sur fond sombre.
 */

import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

const PROFILE_LABELS = {
  fast: 'Rapide',
  llama: 'Qualité',
  mixtral: 'Expert',
};

/**
 * Certains modèles (Mixtral/Dolphin notamment) émettent des séquences
 * littérales "\n" (backslash + n, 2 caractères) au lieu de vrais retours
 * à la ligne (char 10). On les normalise avant le rendu Markdown.
 */
const normalizeNewlines = (text) => {
  if (!text) return text;
  // Remplacer les \n littéraux par de vrais retours à la ligne
  // (ne touche pas aux \\n qui sont des backslash intentionnels)
  return text.replace(/(?<!\\)\\n/g, '\n');
};

const MessageBubble = ({ message }) => {
  const isUser = message.role === 'user';
  const isError = message.isError;

  return (
    <div className={`message-enter flex ${isUser ? 'justify-end' : 'justify-start'} mb-4 px-4`}>
      <div className={`
        max-w-[80%] rounded-2xl px-4 py-3
        ${isUser
          ? 'bg-user-bubble text-text-primary rounded-br-md border border-border-color/30'
          : isError
            ? 'bg-red-950/20 border border-red-900/30 text-red-300 rounded-bl-md'
            : 'bg-assistant-bubble text-text-primary rounded-bl-md border border-border-color/20'
        }
      `}>
        {/* Indicateur d'outils utilisés */}
        {!isUser && message.tools && message.tools.length > 0 && (
          <ToolIndicators tools={message.tools} />
        )}

        {/* Bloc de réflexion (thinking) */}
        {!isUser && message.thinking && (
          <ThinkingBlock thinking={message.thinking} isStreaming={message.isStreaming} />
        )}

        {/* Contenu du message */}
        {isError ? (
          <div className="flex items-start gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-red-400 mt-0.5 shrink-0">
              <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
              <path d="M12 9v4"/><path d="M12 17h.01"/>
            </svg>
            <div className="text-sm leading-relaxed">
              <span className="font-semibold text-red-400">Erreur : </span>
              {message.content.replace(/^Erreur:\s*/i, '')}
            </div>
          </div>
        ) : isUser ? (
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="prose prose-invert prose-sm max-w-none">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code: CodeBlock,
                p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed text-sm">{children}</p>,
                ul: ({ children }) => <ul className="mb-2 ml-4 list-disc text-sm">{children}</ul>,
                ol: ({ children }) => <ol className="mb-2 ml-4 list-decimal text-sm">{children}</ol>,
                li: ({ children }) => <li className="mb-1 leading-relaxed">{children}</li>,
                h1: ({ children }) => <h1 className="text-lg font-bold mt-4 mb-2 text-accent">{children}</h1>,
                h2: ({ children }) => <h2 className="text-base font-bold mt-3 mb-2 text-accent/90">{children}</h2>,
                h3: ({ children }) => <h3 className="text-sm font-bold mt-2 mb-1 text-accent/80">{children}</h3>,
                blockquote: ({ children }) => (
                  <blockquote className="border-l-2 border-accent/40 pl-3 italic text-text-secondary my-2">
                    {children}
                  </blockquote>
                ),
                a: ({ href, children }) => (
                  <a href={href} target="_blank" rel="noopener noreferrer"
                     className="text-accent hover:text-accent-hover underline decoration-accent/30 hover:decoration-accent/60 transition-colors">
                    {children}
                  </a>
                ),
                table: ({ children }) => (
                  <div className="overflow-x-auto my-2">
                    <table className="min-w-full border border-border-color rounded">{children}</table>
                  </div>
                ),
                th: ({ children }) => (
                  <th className="px-3 py-1.5 bg-bg-tertiary border border-border-color text-left text-xs font-semibold text-accent/80">
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td className="px-3 py-1.5 border border-border-color text-xs">{children}</td>
                ),
              }}
            >
              {normalizeNewlines(message.content)}
            </ReactMarkdown>
          </div>
        )}

        {/* Curseur doré de streaming — visible dès le début, suit le texte */}
        {message.isStreaming && (
          <span className="inline-block w-2 h-4 bg-accent/80 animate-pulse ml-0.5 rounded-sm" />
        )}

        {/* Métadonnées */}
        {!isUser && message.metadata && !message.isStreaming && (
          <div className="mt-2 pt-2 border-t border-border-color/30 flex items-center gap-3 text-xs text-text-secondary/70">
            {message.metadata.profile && (
              <span className="text-accent/70">{PROFILE_LABELS[message.metadata.profile] || message.metadata.profile}</span>
            )}
            {message.metadata.thinking_time_ms && (
              <span>{(message.metadata.thinking_time_ms / 1000).toFixed(1)}s</span>
            )}
            {message.metadata.tools_used && message.metadata.tools_used.length > 0 && (
              <span>{message.metadata.tools_used.length} outil(s)</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
};


/**
 * Code block avec syntax highlighting et bouton copier.
 * Header brun chaud, style parchemin sombre.
 */
const CodeBlock = ({ node, inline, className, children, ...props }) => {
  const [copied, setCopied] = useState(false);
  const match = /language-(\w+)/.exec(className || '');
  const language = match ? match[1] : '';
  const code = String(children).replace(/\n$/, '');

  if (inline) {
    return (
      <code className="bg-bg-tertiary px-1.5 py-0.5 rounded text-accent text-xs font-mono" {...props}>
        {children}
      </code>
    );
  }

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group my-2">
      {/* Header du code block */}
      <div className="flex items-center justify-between bg-[#1a1611] rounded-t-lg px-3 py-1.5 border-b border-border-color/50">
        <span className="text-xs text-text-secondary font-mono">{language || 'code'}</span>
        <button
          onClick={handleCopy}
          className="text-xs text-text-secondary hover:text-accent transition-colors flex items-center gap-1"
        >
          {copied ? (
            <>
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="20,6 9,17 4,12"/></svg>
              Copie !
            </>
          ) : (
            <>
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
              Copier
            </>
          )}
        </button>
      </div>
      <SyntaxHighlighter
        style={vscDarkPlus}
        language={language || 'text'}
        PreTag="div"
        customStyle={{
          margin: 0,
          borderRadius: '0 0 8px 8px',
          fontSize: '0.75rem',
          background: '#12100d',
        }}
        {...props}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
};


/**
 * Code block simplifié pour le bloc de réflexion.
 */
const ThinkingCodeBlock = ({ node, inline, className, children, ...props }) => {
  const match = /language-(\w+)/.exec(className || '');
  const language = match ? match[1] : '';
  const code = String(children).replace(/\n$/, '');

  if (inline) {
    return (
      <code className="bg-black/30 px-1 py-0.5 rounded text-amber-300/80 text-[10px] font-mono" {...props}>
        {children}
      </code>
    );
  }

  return (
    <SyntaxHighlighter
      style={vscDarkPlus}
      language={language || 'text'}
      PreTag="div"
      customStyle={{
        margin: '4px 0',
        borderRadius: '6px',
        fontSize: '10px',
        padding: '8px',
        background: 'rgba(0,0,0,0.3)',
      }}
      {...props}
    >
      {code}
    </SyntaxHighlighter>
  );
};


/**
 * Bloc dépliable de réflexion (pensée interne du modèle).
 * Tons ambre/or — parfaitement dans le thème Clair Obscure.
 */
const ThinkingBlock = ({ thinking, isStreaming }) => {
  const [isOpen, setIsOpen] = useState(false);

  if (!thinking) return null;

  return (
    <div className="mb-2">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1.5 text-xs text-text-secondary/70 hover:text-accent/70 transition-colors"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg" width="10" height="10"
          viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
          className={`transition-transform duration-200 ${isOpen ? 'rotate-90' : ''}`}
        >
          <polyline points="9,18 15,12 9,6"/>
        </svg>
        <span className="flex items-center gap-1.5">
          {isStreaming && !thinking.length ? (
            <span className="animate-pulse">Réflexion en cours...</span>
          ) : (
            <>Réflexion</>
          )}
        </span>
        {isStreaming && thinking && (
          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
        )}
      </button>

      {isOpen && (
        <div className="mt-1.5 pl-3 border-l-2 border-accent/30 max-h-80 overflow-y-auto">
          <div className="prose prose-invert prose-sm max-w-none opacity-70">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code: ThinkingCodeBlock,
                p: ({ children }) => <p className="mb-1.5 last:mb-0 leading-relaxed text-xs text-text-secondary/70">{children}</p>,
                ul: ({ children }) => <ul className="mb-1.5 ml-3 list-disc text-xs text-text-secondary/70">{children}</ul>,
                ol: ({ children }) => <ol className="mb-1.5 ml-3 list-decimal text-xs text-text-secondary/70">{children}</ol>,
                li: ({ children }) => <li className="mb-0.5 leading-relaxed">{children}</li>,
                h1: ({ children }) => <h1 className="text-sm font-bold mt-2 mb-1 text-amber-300/80">{children}</h1>,
                h2: ({ children }) => <h2 className="text-xs font-bold mt-2 mb-1 text-amber-300/80">{children}</h2>,
                h3: ({ children }) => <h3 className="text-xs font-semibold mt-1 mb-0.5 text-amber-300/80">{children}</h3>,
                strong: ({ children }) => <strong className="text-amber-200/80 font-semibold">{children}</strong>,
                em: ({ children }) => <em className="text-text-secondary/60 italic">{children}</em>,
                blockquote: ({ children }) => (
                  <blockquote className="border-l-2 border-accent/20 pl-2 italic text-text-secondary/50 my-1 text-xs">
                    {children}
                  </blockquote>
                ),
                a: ({ href, children }) => (
                  <a href={href} target="_blank" rel="noopener noreferrer"
                     className="text-accent/70 hover:text-accent underline text-xs">
                    {children}
                  </a>
                ),
                table: ({ children }) => (
                  <div className="overflow-x-auto my-1">
                    <table className="min-w-full border border-border-color/30 rounded text-xs">{children}</table>
                  </div>
                ),
                th: ({ children }) => (
                  <th className="px-2 py-1 bg-black/20 border border-border-color/20 text-left text-[10px] font-semibold">
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td className="px-2 py-1 border border-border-color/20 text-[10px]">{children}</td>
                ),
              }}
            >
              {normalizeNewlines(thinking)}
            </ReactMarkdown>
            {isStreaming && (
              <span className="inline-block w-1.5 h-3 bg-accent/60 animate-pulse ml-0.5 rounded-sm" />
            )}
          </div>
        </div>
      )}
    </div>
  );
};


/**
 * Indicateurs d'outils utilisés — pastilles dorées.
 */
const ToolIndicators = ({ tools }) => {
  const toolLabels = {
    web_search_tool: 'Recherche web',
    weather_tool: 'Météo',
    wikipedia_search_tool: 'Wikipedia',
    calculator_tool: 'Calcul',
    datetime_tool: 'Date/Heure',
  };

  return (
    <div className="flex flex-wrap gap-1.5 mb-2 pb-2 border-b border-border-color/30">
      {tools.map((tool, idx) => {
        const label = toolLabels[tool.name] || tool.name;
        const isRunning = tool.status === 'running';

        return (
          <span
            key={idx}
            className={`
              inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs
              ${isRunning
                ? 'bg-accent/15 text-accent animate-pulse'
                : 'bg-bg-tertiary/50 text-text-secondary'
              }
            `}
          >
            <span>{label}</span>
            {isRunning && <span className="ml-1">...</span>}
          </span>
        );
      })}
    </div>
  );
};

export default MessageBubble;
