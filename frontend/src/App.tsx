/**
 * Home page component.
 *
 * The root application view that composes the Sidebar, ChatWindow, and
 * AuthModal into the main two-pane layout. It manages the mobile sidebar
 * toggle state and coordinates chat lifecycle events (new chat, history
 * selection) between child components.
 *
 * State management:
 *   - ``sidebarOpen``: Controls mobile sidebar visibility. On desktop, the
 *     sidebar is always visible via CSS responsive classes.
 *   - ``chatKey``: Incremented to force React to remount the ChatWindow,
 *     which clears its internal message state when starting a new chat.
 *   - ``historyId``: When non-null, the ChatWindow enters read-only mode
 *     and loads the specified conversation from the backend.
 *   - ``refreshTrigger``: Incremented after new chats or messages to prompt
 *     the Sidebar's React Query to refetch the conversation list.
 */


import { useState, useRef } from "react";
import Sidebar from "@/components/Sidebar";
import ChatWindow from "@/components/ChatWindow";
import AuthModal from "@/components/AuthModal";
import { toast } from "react-hot-toast";
import { useAuth } from "@/context/AuthContext";
import { resetChat } from "@/lib/api";

export default function Home() {
  const touchStartX = useRef<number | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [chatKey, setChatKey] = useState(0);
  const [historyId, setHistoryId] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const { token, userId, isLoaded, login, logout } = useAuth();

  // Wait for auth state to hydrate from localStorage before rendering.
  if (!isLoaded) return null;

  // Redirect to auth modal if not logged in.
  if (!token || !userId) {
    return <AuthModal onAuthenticated={login} />;
  }

  const handleNewChat = async () => {
    try {
      await resetChat(token);
    } catch {
      // Best-effort reset UI even if the API call fails. The backend session
      // reset is a nice-to-have; the local state reset below ensures the
      // UI always responds to the user's action.
    }
    setHistoryId(null);
    setChatKey((prev) => prev + 1);
    setRefreshTrigger((prev) => prev + 1);
    toast.success("Started a new chat", { id: "Started a new chat" });
    if (sidebarOpen) setSidebarOpen(false);
  };

  const handleSelectChat = (id: string) => {
    setHistoryId(id);
    setChatKey((prev) => prev + 1);
    if (sidebarOpen) setSidebarOpen(false);
  };

  return (
    <main
      id="app-main"
      className="flex h-full w-full overflow-hidden bg-sand-50"
      data-testid="app-main"
    >
      <div
        id="sidebar-container"
        className={`fixed md:relative z-30 h-full md:w-[272px] flex-shrink-0 transition-transform duration-300 ease-in-out ${sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"} w-[272px]`}
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
          activeConversationId={historyId}
        />
      </div>

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
          historyId={historyId}
          onMessageSent={() => setRefreshTrigger((p) => p + 1)}
        />
      </div>
    </main>
  );
}
