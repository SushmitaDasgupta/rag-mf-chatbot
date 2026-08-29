import { CHIP_LABELS, EXAMPLE_QUESTIONS } from "../types";

export function ChatInput({
  onSend,
  disabled,
  shake,
  cooldownRemaining,
}: {
  onSend: (text: string) => void;
  disabled: boolean;
  shake: boolean;
  cooldownRemaining: number;
}) {
  const locked = disabled || cooldownRemaining > 0;

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const input = form.elements.namedItem("message") as HTMLInputElement;
    const value = input.value.trim();
    if (!value) return;
    onSend(value);
    input.value = "";
  };

  return (
    <div className="shrink-0 border-t border-outline-variant bg-surface-container/90 p-4 backdrop-blur-md">
      <div className="mb-3 flex gap-2 overflow-x-auto pb-1">
        {CHIP_LABELS.map((label, i) => (
          <button
            key={label}
            type="button"
            disabled={locked}
            onClick={() => onSend(EXAMPLE_QUESTIONS[i])}
            className="chip-hover shrink-0 animate-fade-up-page rounded-full border border-outline-variant bg-surface/80 px-3 py-1.5 text-xs font-semibold text-on-surface-variant hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-50"
            style={{ animationDelay: `${(i + 1) * 50}ms` }}
          >
            {label}
          </button>
        ))}
      </div>
      <form onSubmit={handleSubmit} className={`relative ${shake ? "animate-shake" : ""}`}>
        <input
          name="message"
          type="text"
          disabled={locked}
          autoComplete="off"
          placeholder="Ask about fund facts..."
          className="w-full rounded-card border border-outline-variant bg-surface/80 py-3 pl-4 pr-32 text-base text-on-surface placeholder:text-on-surface-variant focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:cursor-not-allowed disabled:opacity-50"
        />
        <div className="absolute right-3 top-1/2 flex -translate-y-1/2 items-center gap-2">
          {cooldownRemaining > 0 ? (
            <>
              <span className="material-symbols-outlined text-base text-error">lock</span>
              <span className="text-xs font-semibold text-error">Try again in {cooldownRemaining}s</span>
            </>
          ) : (
            <button
              type="submit"
              disabled={locked}
              className="flex items-center gap-1 rounded-full bg-primary-container px-3 py-1.5 text-xs font-semibold text-on-primary-container disabled:opacity-50"
            >
              <span className="material-symbols-outlined text-[16px]">send</span>
              Send
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
