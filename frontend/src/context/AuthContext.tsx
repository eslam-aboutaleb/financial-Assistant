/**
 * Authentication context for the OmniCare frontend.
 *
 * Provides global access to the current user's authentication state, including
 * the JWT token, user ID, and login/logout methods. State is persisted to
 * ``localStorage`` so sessions survive page refreshes.
 *
 * Usage:
 *   Import ``useAuth`` in any client component to access the auth context:
 *     const { token, userId, login, logout } = useAuth();
 *
 * Lifecycle:
 *   - On mount, the context hydrates state from localStorage.
 *   - ``login`` stores the new token and user ID in both React state and
 *     localStorage.
 *   - ``logout`` clears both and triggers a toast notification.
 */

import { createContext, useContext, useState, ReactNode } from "react";
import { toast } from "react-hot-toast";

interface AuthContextType {
  token: string | null;
  userId: string | null;
  isLoaded: boolean;
  login: (token: string, userId: string) => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => {
    const stored = localStorage.getItem("omnicare_token");
    if (stored && stored.includes(".")) {
      return stored;
    }
    if (stored) {
      localStorage.removeItem("omnicare_token");
    }
    return null;
  });
  const [userId, setUserId] = useState<string | null>(() => {
    const stored = localStorage.getItem("omnicare_user_id");
    if (!stored) return null;
    const uuid =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (uuid.test(stored)) {
      return stored;
    }
    localStorage.removeItem("omnicare_user_id");
    return null;
  });
  const [isLoaded] = useState(true);

  const login = (newToken: string, newUserId: string) => {
    localStorage.setItem("omnicare_token", newToken);
    localStorage.setItem("omnicare_user_id", newUserId);
    setToken(newToken);
    setUserId(newUserId);
  };

  const logout = async () => {
    try {
      const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";
      await fetch(`${apiUrl}/api/v1/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } catch {
      // Best-effort logout; clear local state regardless.
    }

    localStorage.removeItem("omnicare_token");
    localStorage.removeItem("omnicare_user_id");
    setToken(null);
    setUserId(null);
    toast.success("Logged out successfully", { id: "Logged out successfully" });
  };

  return (
    <AuthContext.Provider value={{ token, userId, isLoaded, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
