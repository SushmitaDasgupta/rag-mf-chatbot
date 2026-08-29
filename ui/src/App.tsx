import { useEffect, useRef } from "react";
import { useChat } from "./hooks/useChat";
import { ChatInput } from "./components/ChatInput";
import { MessageList } from "./components/ChatMessages";
import { ComplianceBanner, Header } from "./components/Header";
import { Footer } from "./components/Footer";
import { NavSidebar } from "./components/NavSidebar";
import { ShaderBackground } from "./components/ShaderBackground";

export default function App() {
  const {
    messages,
    loading,
    canSend,
    cooldownRemaining,
    inputShake,
    sendMessage,
    newChat,
    selectSession,
    sidebarSessions,
    activeSessionId,
  } = useChat();

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = (text: string) => {
    void sendMessage(text);
  };

  return (
    <div className="relative flex min-h-screen flex-col text-on-background">
      <ShaderBackground />
      <Header />
      <NavSidebar
        sessions={sidebarSessions}
        activeId={activeSessionId}
        onNewChat={newChat}
        onSelectSession={selectSession}
      />
      <div className="flex w-full flex-grow flex-col lg:pl-[260px]">
        <div className="mx-auto mb-4 mt-24 w-full max-w-[1200px] px-6">
          <ComplianceBanner />
        </div>
        <main className="relative mx-auto flex w-full max-w-[1200px] flex-grow flex-col px-6 pb-8">
          <section className="flex h-[calc(100vh-200px)] min-h-[520px] w-full animate-fade-up-page flex-col overflow-hidden rounded-card border border-outline-variant bg-surface-container/90 backdrop-blur-md">
            <div className="flex shrink-0 items-center justify-between border-b border-outline-variant bg-surface-container/90 px-6 py-4 backdrop-blur-md">
              <div>
                <h1 className="text-xl font-semibold text-on-surface">Kotak Mutual Fund FAQ</h1>
                <p className="text-sm text-on-surface-variant">
                  Objective, source-backed answers from curated scheme pages
                </p>
              </div>
              <div className="flex items-center gap-1 rounded-full border border-outline-variant bg-surface-variant/80 px-3 py-1">
                <span className="material-symbols-outlined filled text-[16px] text-secondary">
                  verified
                </span>
                <span className="text-xs font-semibold text-on-surface-variant">
                  7 schemes supported
                </span>
              </div>
            </div>
            <MessageList
              messages={messages}
              loading={loading}
              bottomRef={bottomRef}
              onExample={handleSend}
              examplesDisabled={!canSend}
            />
            <ChatInput
              onSend={handleSend}
              disabled={!canSend}
              shake={inputShake}
              cooldownRemaining={cooldownRemaining}
            />
          </section>
        </main>
        <Footer />
      </div>
    </div>
  );
}
