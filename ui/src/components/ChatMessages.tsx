import type { ChatMessage } from "../types";
import { EXAMPLE_QUESTIONS, SUPPORTED_SCHEMES } from "../types";

function isRefusal(type?: string): boolean {
  return (
    type === "refusal" ||
    type === "performance_refusal" ||
    type === "unsupported" ||
    type === "rate_limited"
  );
}

function AssistantBubble({ message }: { message: ChatMessage }) {
  const refusal = isRefusal(message.responseType);

  if (refusal) {
    return (
      <div className="max-w-[85%] rounded-r-xl border-l-4 border-error bg-[#451225]/90 p-4">
        <div className="flex items-start gap-2">
          <span className="material-symbols-outlined mt-0.5 text-error">info</span>
          <div>
            <p className="whitespace-pre-wrap text-base leading-relaxed text-error">
              {message.content}
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (message.isError) {
    return (
      <div className="max-w-[85%] rounded-t-bubble rounded-r-bubble rounded-bl rounded-br-sm border border-error/40 bg-surface-container-high/90 p-4">
        <p className="text-sm text-error">{message.content}</p>
      </div>
    );
  }

  return (
    <div className="max-w-[85%] rounded-t-bubble rounded-r-bubble rounded-bl rounded-br-sm border border-outline-variant bg-surface-container-high/90 p-6 shadow-sm">
      <p className="mb-4 whitespace-pre-wrap text-base leading-relaxed text-on-surface">
        {message.content}
      </p>
      {(message.citationUrl || message.lastUpdated) && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-outline-variant pt-3">
          {message.citationUrl ? (
            <a
              href={message.citationUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="citation-link flex items-center gap-1 rounded-full border border-secondary px-3 py-1 text-xs font-semibold text-secondary transition-colors hover:bg-secondary/10"
            >
              <span className="material-symbols-outlined text-[14px]">link</span>
              View scheme source
            </a>
          ) : (
            <span />
          )}
          {message.lastUpdated && (
            <span className="text-xs text-on-surface-variant">
              Last updated: {message.lastUpdated}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

export function WelcomeState({
  onExample,
  disabled,
}: {
  onExample: (q: string) => void;
  disabled: boolean;
}) {
  return (
    <div className="flex flex-col items-center py-8 text-center animate-fade-up-page">
      <span className="material-symbols-outlined mb-4 text-5xl text-primary">quiz</span>
      <h2 className="mb-2 text-xl font-semibold text-on-surface">What would you like to know?</h2>
      <p className="mb-6 max-w-md text-sm text-on-surface-variant">
        Ask about expense ratio, exit load, minimum SIP, benchmark, riskometer, or NAV for
        supported Kotak schemes.
      </p>
      <details className="mb-6 w-full max-w-lg text-left">
        <summary className="cursor-pointer text-sm font-medium text-primary">
          Supported schemes (7)
        </summary>
        <ul className="mt-2 space-y-1 text-sm text-on-surface-variant">
          {SUPPORTED_SCHEMES.map((name) => (
            <li key={name}>• {name}</li>
          ))}
        </ul>
      </details>
      <div className="flex w-full flex-wrap justify-center gap-2">
        {EXAMPLE_QUESTIONS.map((q, i) => (
          <button
            key={q}
            type="button"
            disabled={disabled}
            onClick={() => onExample(q)}
            className="chip-hover rounded-full border border-outline-variant bg-surface/80 px-3 py-1.5 text-xs font-semibold text-on-surface-variant hover:border-primary hover:text-primary disabled:opacity-50"
            style={{ animationDelay: `${(i + 1) * 50}ms` }}
          >
            {q.length > 48 ? `${q.slice(0, 45)}…` : q}
          </button>
        ))}
      </div>
    </div>
  );
}

export function TypingIndicator() {
  return (
    <div className="flex justify-start animate-fade-up-msg">
      <div className="flex items-center gap-1 rounded-t-bubble rounded-r-bubble rounded-bl rounded-br-sm border border-outline-variant bg-surface-container-high/90 px-4 py-3">
        <div className="dot-typing h-2 w-2 rounded-full bg-outline" />
        <div className="dot-typing h-2 w-2 rounded-full bg-outline" />
        <div className="dot-typing h-2 w-2 rounded-full bg-outline" />
      </div>
    </div>
  );
}

export function MessageList({
  messages,
  loading,
  bottomRef,
  onExample,
  examplesDisabled,
}: {
  messages: ChatMessage[];
  loading: boolean;
  bottomRef: React.Ref<HTMLDivElement>;
  onExample: (q: string) => void;
  examplesDisabled: boolean;
}) {
  return (
    <div className="chat-scroll flex flex-grow flex-col gap-6 overflow-y-auto p-6">
      {messages.length === 0 && !loading && (
        <WelcomeState onExample={onExample} disabled={examplesDisabled} />
      )}
      {messages.map((msg, i) => (
        <div
          key={msg.id}
          className={`flex animate-fade-up-msg ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          style={{ animationDelay: `${Math.min(i * 80, 400)}ms` }}
        >
          {msg.role === "user" ? (
            <div className="max-w-[80%] rounded-t-bubble rounded-l-bubble rounded-br rounded-bl-sm bg-primary-container p-4 text-on-primary-container">
              <p className="text-base">{msg.content}</p>
            </div>
          ) : (
            <AssistantBubble message={msg} />
          )}
        </div>
      ))}
      {loading && <TypingIndicator />}
      <div ref={bottomRef} />
    </div>
  );
}
