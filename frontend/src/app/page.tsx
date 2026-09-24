"use client";

import { useState, useEffect } from "react";
import Sidebar from "@/components/Sidebar";
import ChatWindow from "@/components/ChatWindow";
import AuthModal from "@/components/AuthModal";
import { toast } from "react-hot-toast";

export default function Home() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [chatKey, setChatKey] = useState(0);
  const [token, setToken] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    const storedToken = localStorage.getItem("omnicare_token");
    const storedUserId = localStorage.getItem("omnicare_user_id");
    if (storedToken && storedUserId) {
      setToken(storedToken);
      setUserId(storedUserId);
    }
    setIsLoaded(true);
  }, []);

  const handleAuthenticated = (newToken: string, newUserId: string) => {
    localStorage.setItem("omnicare_token", newToken);
    localStorage.setItem("omnicare_user_id", newUserId);
    setToken(newToken);
    setUserId(newUserId);
  };

  const handleLogout = () => {
    localStorage.removeItem("omnicare_token");
    localStorage.removeItem("omnicare_user_id");
    setToken(null);
    setUserId(null);
    toast.success("Logged out successfully");
  };

  const handleNewChat = async () => {
    // Reset backend conversation session so the agent starts fresh
    if (token) {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        await fetch(`${apiUrl}/api/v1/chat/reset`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
      } catch {
        // Best-effort: even if the reset call fails, we still reset the UI state
      }
    }
    setChatKey((prev) => prev + 1);
    toast.success("Started a new chat");
    if (sidebarOpen) setSidebarOpen(false);
  };

  if (!isLoaded) return null;

  if (!token || !userId) {
    return <AuthModal onAuthenticated={handleAuthenticated} />;
  }

  return (
    <main
      id="app-main"
      className="flex h-full w-full overflow-hidden"
      data-testid="app-main"
    >
      <div
        id="sidebar-container"
        className={`md:block md:w-[260px] flex-shrink-0 ${sidebarOpen ? "block" : "hidden"} absolute md:relative z-10 h-full`}
        data-testid="sidebar-container"
      >
        <Sidebar onNewChat={handleNewChat} onLogout={handleLogout} />
      </div>

      {sidebarOpen && (
        <div
          id="sidebar-overlay"
          className="fixed inset-0 bg-black bg-opacity-50 z-0 md:hidden"
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
            className="p-2 text-gray-300 hover:text-white bg-gray-900 rounded-md border border-gray-800"
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
                strokeWidth={2}
                d="M4 6h16M4 12h16M4 18h16"
              />
            </svg>
          </button>
        </div>
        <ChatWindow key={chatKey} onNewChat={handleNewChat} token={token} />
      </div>
    </main>
  );
}
