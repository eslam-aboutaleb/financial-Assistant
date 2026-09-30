import { useRef, useState } from "react";
import { Navigate, useParams, useNavigate } from "react-router-dom";
import Sidebar from "@/components/Sidebar";
import ChatWindow from "@/components/ChatWindow";
import { toast } from "react-hot-toast";
import { useAuth } from "@/context/AuthContext";
import { resetChat } from "@/lib/api";

export default function ChatPage() {
  const touchStartX = useRef<number | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [chatKey, setChatKey] = useState(0);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const { status, logout, token } = useAuth();
  const { conversationId } = useParams<{ conversationId?: string }>();
  const navigate = useNavigate();
  const [historyLoadError, setHistoryLoadError] = useState<string | null>(null);

  if (status === "loading") {
    return (
      <div className="flex h-full w-full items-center justify-center bg-sand-50">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-insurance-info border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-insurance-ink-secondary">
            Loading OmniCare...
          </span>
        </div>
      </div>
    );
  }
  if (status !== "authenticated") return <Navigate to="/login" replace />;

  const handleNewChat = () => {
    resetChat(token).catch(() => {
      // Best-effort reset UI even if the API call fails.
    });
    setHistoryLoadError(null);
    setChatKey((prev) => prev + 1);
    setRefreshTrigger((prev) => prev + 1);
    toast.success("Started a new chat", { id: "Started a new chat" });
    if (sidebarOpen) setSidebarOpen(false);
    navigate("/chat", { replace: true });
  };

  const handleSelectChat = (id: string) => {
    setHistoryLoadError(null);
    setChatKey((prev) => prev + 1);
    if (sidebarOpen) setSidebarOpen(false);
    navigate(`/chat/${id}`);
  };

  const handleHistoryLoaded = () => {
    setHistoryLoadError(null);
  };

  const handleHistoryLoadError = (message: string) => {
    setHistoryLoadError(message);
  };

  return (
    <main
      id="app-main"
      className="flex h-full w-full overflow-hidden bg-sand-50"
      data-testid="app-main"
    >
      <div
        id="sidebar-container"
        className={`fixed md:relative z-30 h-full md:w-[272px] flex-shrink-0 transition-transform duration-300 ease-in-out ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        } w-[272px]`}
        data-testid="sidebar-container"
        onTouchStart={(e) => {
          const touch = e.touches[0];
          touchStartX.current = touch.clientX;
        }}
        onTouchEnd={(e) => {
          const touch = e.changedTouches[0];
          if (touchStartX.current && touchStartX.current - touch.clientX > 50) {
            setSidebarOpen(false);
          }
        }}
      >
        <Sidebar
          onNewChat={handleNewChat}
          onLogout={logout}
          onSelectChat={handleSelectChat}
          refreshTrigger={refreshTrigger}
          activeConversationId={conversationId}
        />
      </div>

      {historyLoadError && (
        <div className="absolute inset-0 flex items-center justify-center bg-sand-50/80 z-10">
          <div className="max-w-sm text-center p-4 bg-insurance-surface border border-insurance-border rounded-xl shadow-medium">
            <div className="text-sm font-medium text-insurance-ink mb-1">
              Failed to load conversation
            </div>
            <div className="text-xs text-insurance-ink-secondary mb-3">
              {historyLoadError}
            </div>
            <button
              onClick={() => navigate("/chat")}
              className="px-3 py-2 bg-insurance-info text-white text-xs font-medium rounded-lg hover:bg-insurance-ink-secondary transition-colors"
            >
              Start a new chat
            </button>
          </div>
        </div>
      )}
      {sidebarOpen && (
        <div
          id="sidebar-overlay"
          className="fixed inset-0 bg-warm-ink/15 backdrop-blur-sm z-10 md:hidden"
          onClick={() => setSidebarOpen(false)}
          data-testid="sidebar-overlay"
          aria-label="Close sidebar"
        />
      )}

      <div
        id="chat-container"
        className="flex-1 flex flex-col h-full relative"
        {...(sidebarOpen ? { inert: true } : {})}
        data-testid="chat-container"
      >
        <div
          id="mobile-menu-button"
          className="absolute top-0 left-0 p-4 md:hidden z-10"
          data-testid="mobile-menu-button"
        >
          <button
            id="mobile-menu-toggle"
            onClick={() => setSidebarOpen(true)}
            className="p-2 text-warm-ink bg-warm-surface border border-warm-border rounded-lg shadow-subtle hover:shadow-soft transition-subtle"
            aria-label="Open menu"
            data-testid="mobile-menu-toggle"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.8}
                d="M4 6h16M4 12h16M4 18h16"
              />
            </svg>
          </button>
        </div>
        <ChatWindow
          key={chatKey}
          onNewChat={handleNewChat}
          historyId={conversationId}
          onMessageSent={() => setRefreshTrigger((p) => p + 1)}
          onAuthError={logout}
          onHistoryLoaded={handleHistoryLoaded}
          onHistoryLoadError={handleHistoryLoadError}
        />
      </div>
    </main>
  );
}
