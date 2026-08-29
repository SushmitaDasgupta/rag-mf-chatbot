export interface SidebarSession {
  id: string;
  title: string;
}

export function NavSidebar({
  sessions,
  activeId,
  onNewChat,
  onSelectSession,
}: {
  sessions: SidebarSession[];
  activeId: string | null;
  onNewChat: () => void;
  onSelectSession: (id: string) => void;
}) {
  const today = sessions.slice(0, 4);
  const older = sessions.slice(4);

  return (
    <aside className="fixed left-0 top-16 z-40 hidden h-[calc(100vh-64px)] w-[260px] shrink-0 animate-fade-up-page flex-col gap-4 overflow-y-auto border-r border-outline-variant bg-surface/90 py-4 backdrop-blur-md lg:flex">
      <div className="mb-1 px-4">
        <button
          type="button"
          onClick={onNewChat}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary-container py-2 text-sm font-medium text-on-primary-container transition-opacity hover:opacity-90"
        >
          <span className="material-symbols-outlined text-[20px]">add</span>
          New Chat
        </button>
      </div>
      <div className="flex flex-col gap-1 px-4">
        {today.length > 0 && (
          <>
            <div className="mb-1 mt-1 px-2 py-1 text-xs font-semibold text-on-surface-variant">
              Today
            </div>
            {today.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => onSelectSession(s.id)}
                className={`flex items-center gap-2 rounded-lg px-2 py-2 text-left transition-colors ${
                  activeId === s.id
                    ? "bg-surface-variant/80 text-on-surface"
                    : "text-on-surface-variant hover:bg-surface-variant/50"
                }`}
              >
                <span className="material-symbols-outlined text-[18px]">chat_bubble</span>
                <span className="truncate text-sm font-medium">{s.title}</span>
              </button>
            ))}
          </>
        )}
        {older.length > 0 && (
          <>
            <div className="mb-1 mt-3 px-2 py-1 text-xs font-semibold text-on-surface-variant">
              Previous 7 Days
            </div>
            {older.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => onSelectSession(s.id)}
                className={`flex items-center gap-2 rounded-lg px-2 py-2 text-left transition-colors ${
                  activeId === s.id
                    ? "bg-surface-variant/80 text-on-surface"
                    : "text-on-surface-variant hover:bg-surface-variant/50"
                }`}
              >
                <span className="material-symbols-outlined text-[18px]">chat_bubble</span>
                <span className="truncate text-sm font-medium">{s.title}</span>
              </button>
            ))}
          </>
        )}
        {sessions.length === 0 && (
          <p className="px-2 py-4 text-xs text-on-surface-variant">
            Start a new chat to ask factual scheme questions.
          </p>
        )}
      </div>
    </aside>
  );
}
